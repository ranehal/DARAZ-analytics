"""Flask Backend API for Daraz Price Tracker & Comparison Dashboard."""
import csv, io
from flask import Flask, jsonify, request, render_template, Response
import db, scraper, config

app = Flask(__name__, static_folder="static", template_folder="templates")


def _enrich_units(products):
    for p in products:
        p["unit_price"] = None
        p["unit_str"] = None
        if p.get("price") and p.get("unit_qty") and p.get("unit"):
            u_price = p["price"] / p["unit_qty"]
            p["unit_price"] = round(u_price, 2)
            p["unit_str"] = f"{config.CURRENCY}{round(u_price, 2)} / {p['unit']}"
    return products


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    return jsonify(db.get_dashboard_stats())


@app.route("/api/categories")
def api_categories():
    all_cats = db.get_all_categories()
    cat_map = {c["id"]: {**c, "children": []} for c in all_cats}
    tree = []
    for c in all_cats:
        if c["parent_id"] and c["parent_id"] in cat_map:
            cat_map[c["parent_id"]]["children"].append(cat_map[c["id"]])
        elif not c["parent_id"]:
            tree.append(cat_map[c["id"]])
    return jsonify(tree)


@app.route("/api/products")
def api_products():
    cat_id = request.args.get("category_id", type=int)
    search = request.args.get("search", type=str)
    limit = request.args.get("limit", default=0, type=int)
    offset = request.args.get("offset", default=0, type=int)
    alltime_low = request.args.get("alltime_low", default="false").lower() == "true"

    products = db.get_products(category_id=cat_id, search=search, limit=limit,
                               offset=offset, alltime_low=alltime_low)
    return jsonify(_enrich_units(products))


@app.route("/api/product/<item_id>")
def api_product_detail(item_id):
    with db.get_conn() as conn:
        p_row = conn.execute("""
            SELECT p.*, c.name AS category_name, c.slug AS category_slug
            FROM products p LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.item_id=?
        """, (item_id,)).fetchone()
        if not p_row:
            return jsonify({"error": "Product not found"}), 404

        product = dict(p_row)
        history = db.get_price_history(item_id, days=180)
        stats = db.get_price_stats(item_id)

        unit_history = []
        if product["unit_qty"] and product["unit_qty"] > 0:
            for h in history:
                unit_history.append({
                    "scraped_at": h["scraped_at"],
                    "unit_price": round(h["price"] / product["unit_qty"], 2),
                    "unit": product["unit"]
                })

        return jsonify({
            "product": product,
            "history": history,
            "unit_history": unit_history,
            "stats": stats
        })


# ── Campaigns & Flash Sales ──────────────────────────────────────────────────

@app.route("/api/campaigns")
def api_campaigns():
    section = request.args.get("section", type=str)
    return jsonify(db.get_campaigns(section=section))


@app.route("/api/flash-sales")
def api_flash_sales():
    limit = request.args.get("limit", default=100, type=int)
    return jsonify(db.get_flash_sales(limit=limit))


# ── Analytics ────────────────────────────────────────────────────────────────

@app.route("/api/price-drops")
def api_price_drops():
    limit = request.args.get("limit", default=50, type=int)
    min_pct = request.args.get("min_pct", default=1.0, type=float)
    return jsonify(db.get_price_drops(limit=limit, min_pct=min_pct))


@app.route("/api/top-discounts")
def api_top_discounts():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify(db.get_top_discounts(limit=limit))


@app.route("/api/top-sellers")
def api_top_sellers():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify(db.get_top_sellers(limit=limit))


@app.route("/api/price-movers")
def api_price_movers():
    days = request.args.get("days", default=7, type=int)
    limit = request.args.get("limit", default=50, type=int)
    return jsonify(db.get_price_change_leaders(days=days, limit=limit))


@app.route("/api/analytics")
def api_analytics():
    return jsonify({
        "category_distribution": db.get_category_distribution(),
        "discount_distribution": db.get_discount_distribution(),
    })


# ── Export ───────────────────────────────────────────────────────────────────

@app.route("/api/export.csv")
def api_export_csv():
    products = db.get_products(limit=0)
    products = _enrich_units(products)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["item_id", "name", "brand", "category", "price", "original",
                     "discount", "unit", "unit_qty", "unit_price", "url", "image",
                     "rating", "review_cnt", "sold_cnt", "last_scraped"])
    for p in products:
        writer.writerow([
            p.get("item_id"), p.get("name"), p.get("brand"), p.get("category_name"),
            p.get("price"), p.get("original"), p.get("discount"),
            p.get("unit"), p.get("unit_qty"), p.get("unit_price"),
            p.get("url"), p.get("image"), p.get("rating"),
            p.get("review_cnt"), p.get("sold_cnt"), p.get("scraped_at"),
        ])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=daraz_products.csv"})


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    try:
        pages = request.json.get("pages", 10) if request.is_json else 10
        scraper.run(max_pages=pages)
        return jsonify({"status": "success", "message": "Live API scrape completed!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    db.init_db()
    print("Dashboard server starting on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)

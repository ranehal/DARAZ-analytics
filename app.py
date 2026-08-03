"""Flask Backend API for Daraz Price Tracker & Comparison Dashboard."""
from flask import Flask, jsonify, request, render_template
import db, scraper

app = Flask(__name__, static_folder="static", template_folder="templates")

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
    
    products = db.get_products(category_id=cat_id, search=search, limit=limit, offset=offset, alltime_low=alltime_low)
    
    for p in products:
        p["unit_price"] = None
        p["unit_str"] = None
        if p["price"] and p["unit_qty"] and p["unit"]:
            u_price = p["price"] / p["unit_qty"]
            p["unit_price"] = round(u_price, 2)
            p["unit_str"] = f"৳{round(u_price, 2)} / {p['unit']}"
            
    return jsonify(products)

@app.route("/api/product/<item_id>")
def api_product_detail(item_id):
    with db.get_conn() as conn:
        p_row = conn.execute("SELECT * FROM products WHERE item_id=?", (item_id,)).fetchone()
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

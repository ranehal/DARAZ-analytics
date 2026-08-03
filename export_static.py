"""Export SQLite database to static JSON files for GitHub Pages hosting."""
import os, json
import db

def export():
    db.init_db()
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/products", exist_ok=True)

    # 1. Stats
    stats = db.get_dashboard_stats()
    with open("data/stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    # 2. Categories
    all_cats = db.get_all_categories()
    cat_map = {c["id"]: {**c, "children": []} for c in all_cats}
    tree = []
    for c in all_cats:
        if c["parent_id"] and c["parent_id"] in cat_map:
            cat_map[c["parent_id"]]["children"].append(cat_map[c["id"]])
        elif not c["parent_id"]:
            tree.append(cat_map[c["id"]])
    with open("data/categories.json", "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2)

    # 3. Products
    products = db.get_products()
    for p in products:
        p["unit_price"] = None
        p["unit_str"] = None
        if p["price"] and p["unit_qty"] and p["unit"]:
            u_price = p["price"] / p["unit_qty"]
            p["unit_price"] = round(u_price, 2)
            p["unit_str"] = f"৳{round(u_price, 2)} / {p['unit']}"

    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2)

    # 4. Product Details
    with db.get_conn() as conn:
        all_p = conn.execute("SELECT * FROM products").fetchall()
        for p_row in all_p:
            product = dict(p_row)
            item_id = product["item_id"]
            history = db.get_price_history(item_id, days=180)
            p_stats = db.get_price_stats(item_id)
            unit_history = []
            if product["unit_qty"] and product["unit_qty"] > 0:
                for h in history:
                    unit_history.append({
                        "scraped_at": h["scraped_at"],
                        "unit_price": round(h["price"] / product["unit_qty"], 2),
                        "unit": product["unit"]
                    })
            detail = {
                "product": product,
                "history": history,
                "unit_history": unit_history,
                "stats": p_stats
            }
            with open(f"data/products/{item_id}.json", "w", encoding="utf-8") as f:
                json.dump(detail, f, indent=2)

    print("Static export completed successfully!")

if __name__ == "__main__":
    export()

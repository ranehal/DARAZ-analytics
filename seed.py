"""Seed database with realistic initial product & price history data."""
import random
from datetime import datetime, timedelta
from db import init_db, upsert_category, upsert_product, insert_price, get_conn

SAMPLE_CATEGORIES = [
    {"slug": "groceries", "name": "Groceries & Staples", "icon": "🛒", "subs": [
        {"slug": "rice-grain", "name": "Rice & Grains"},
        {"slug": "edible-oil", "name": "Edible Oils"},
        {"slug": "beverages", "name": "Beverages & Tea"},
    ]},
    {"slug": "electronics", "name": "Electronics & Gadgets", "icon": "⚡", "subs": [
        {"slug": "smartphones", "name": "Smartphones"},
        {"slug": "laptops", "name": "Laptops & Computers"},
        {"slug": "audio", "name": "Headphones & Audio"},
    ]},
    {"slug": "health-beauty", "name": "Health & Beauty", "icon": "✨", "subs": [
        {"slug": "skincare", "name": "Skincare & Lotions"},
        {"slug": "haircare", "name": "Shampoo & Hair Care"},
    ]},
    {"slug": "home-appliances", "name": "Home & Kitchen", "icon": "🏠", "subs": [
        {"slug": "kitchen-appliances", "name": "Blenders & Cookers"},
        {"slug": "air-cooling", "name": "Fans & Air Coolers"},
    ]}
]

SAMPLE_PRODUCTS = [
    # Groceries
    {"item_id": "DRZ-RICE-5KG", "name": "Nazirshail Premium Rice 5 kg Pack", "brand": "Miniket", "cat": "rice-grain", "price": 460, "unit": "kg", "qty": 5, "img": "https://img.drz.lazcdn.com/static/bd/p/afe115bd8af39bc97c8e0244a0f6efae.png_460x460q80.jpg_.webp"},
    {"item_id": "DRZ-OIL-5L", "name": "Rupchanda Fortified Soyabean Oil 5 Litre", "brand": "Rupchanda", "cat": "edible-oil", "price": 810, "unit": "L", "qty": 5, "img": "https://img.drz.lazcdn.com/g/kf/S7464e1d485194dd79a71fd23c3ab889d1.jpg_460x460q80.jpg_.webp"},
    {"item_id": "DRZ-TEA-400G", "name": "Ispahani Mirzapore Black Tea 400g", "brand": "Ispahani", "cat": "beverages", "price": 220, "unit": "g", "qty": 400, "img": "https://img.drz.lazcdn.com/static/bd/p/2bb209284605e25ac1eb73de065a47d1.jpg_460x460q80.jpg_.webp"},
    {"item_id": "DRZ-MILK-1L", "name": "Aarong Dairy Full Cream Milk 1 L", "brand": "Aarong", "cat": "beverages", "price": 95, "unit": "L", "qty": 1, "img": "https://img.drz.lazcdn.com/g/tps/imgextra/i1/O1CN01Wvq2tm1jBdHn2dY1K_!!6000000004510-2-tps-432-54.png_460x460q80.jpg_.webp"},
    
    # Electronics
    {"item_id": "DRZ-REDMI-NOTE13", "name": "Xiaomi Redmi Note 13 (8GB RAM / 256GB ROM)", "brand": "Xiaomi", "cat": "smartphones", "price": 22999, "unit": "pcs", "qty": 1, "img": "https://img.drz.lazcdn.com/g/kf/S16bac2c7adc34a17a8b76787ca88b3b16.jpg_460x460q80.jpg_.webp"},
    {"item_id": "DRZ-REALME-BUDS", "name": "Realme Buds T100 True Wireless Earbuds", "brand": "Realme", "cat": "audio", "price": 1850, "unit": "pcs", "qty": 1, "img": "https://img.drz.lazcdn.com/static/bd/p/d62b5622903e1c3bdba9c0cb99f33796.jpg_960x960q75.jpg_.webp"},
    {"item_id": "DRZ-ANKER-POWER", "name": "Anker 20000mAh Power Bank 22.5W Fast Charge", "brand": "Anker", "cat": "audio", "price": 3200, "unit": "pcs", "qty": 1, "img": "https://img.drz.lazcdn.com/static/bd/p/d90c672925c95250c057e38f669f13e9.jpg_460x460q80.jpg_.webp"},
    
    # Health & Beauty
    {"item_id": "DRZ-DOVE-SHAMPOO", "name": "Dove Intense Repair Shampoo 650 ml", "brand": "Dove", "cat": "haircare", "price": 680, "unit": "ml", "qty": 650, "img": "https://img.drz.lazcdn.com/static/bd/p/f842decdbcd5daff96850e09ef92a4db.jpg_460x460q80.jpg_.webp"},
    {"item_id": "DRZ-NEVEA-CREAM", "name": "Nivea Soft Moisturizer Cream 300 ml", "brand": "Nivea", "cat": "skincare", "price": 520, "unit": "ml", "qty": 300, "img": "https://img.drz.lazcdn.com/static/bd/p/2f50c7e6a037a57db8ffeca2d76ad8b6.jpg_460x460q80.jpg_.webp"},

    # Home Appliances
    {"item_id": "DRZ-WALTON-BLENDER", "name": "Walton 3 in 1 Heavy Duty Blender 750W", "brand": "Walton", "cat": "kitchen-appliances", "price": 3450, "unit": "pcs", "qty": 1, "img": "https://img.drz.lazcdn.com/static/bd/p/af903e39a8eaad7d52bc8f7c22af138c.jpg_460x460q80.jpg_.webp"},
    {"item_id": "DRZ-VISION-COOKER", "name": "Vision Automatic Rice Cooker 2.8 Litre", "brand": "Vision", "cat": "kitchen-appliances", "price": 2890, "unit": "L", "qty": 2.8, "img": "https://img.drz.lazcdn.com/static/bd/p/4a266ab4cebcb7166c91bbadd5928ef5.jpg_460x460q80.jpg_.webp"}
]

def seed_database():
    init_db()
    cat_map = {}
    
    # Insert categories
    for cat in SAMPLE_CATEGORIES:
        parent_id = upsert_category(cat["slug"], cat["name"], level=0)
        cat_map[cat["slug"]] = parent_id
        for sub in cat["subs"]:
            sub_id = upsert_category(sub["slug"], sub["name"], parent_id=parent_id, level=1)
            cat_map[sub["slug"]] = sub_id

    # Insert products and 60 days of price history
    now = datetime.now()
    for p in SAMPLE_PRODUCTS:
        cat_id = cat_map.get(p["cat"])
        prod_id = upsert_product(
            item_id=p["item_id"],
            name=p["name"],
            brand=p["brand"],
            category_id=cat_id,
            url=f"https://www.daraz.com.bd/products/{p['item_id'].lower()}.html",
            image=p["img"],
            unit=p["unit"],
            unit_qty=p["qty"]
        )

        base_price = p["price"]
        # Generate 60 daily history points with realistic price fluctuations & discounts
        with get_conn() as conn:
            for day_offset in range(60, -1, -1):
                timestamp = (now - timedelta(days=day_offset)).strftime("%Y-%m-%d %H:%M:%S")
                # price fluctuates +- 12%
                noise = random.choice([0, 0, 0, -0.05, 0.03, -0.10, 0.05, -0.15])
                curr_price = round(base_price * (1 + noise), 2)
                orig_price = round(base_price * 1.15, 2)
                discount = round((orig_price - curr_price) / orig_price * 100, 1)
                rating = round(random.uniform(4.2, 4.9), 1)
                reviews = random.randint(45, 1200)
                sold = random.randint(100, 5000)

                conn.execute("""
                    INSERT INTO price_history(product_id, price, original, discount, rating, review_cnt, sold_cnt, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (prod_id, curr_price, orig_price, discount, rating, reviews, sold, timestamp))

    print(f"Successfully seeded database with {len(SAMPLE_PRODUCTS)} products and 60-day price history!")

if __name__ == "__main__":
    seed_database()

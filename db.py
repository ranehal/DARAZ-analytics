"""Database layer — SQLite price history store (CamelCamelCamel style)."""
import sqlite3, contextlib, os

DB_PATH = os.path.join(os.path.dirname(__file__), "daraz_prices.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS categories (
    id        INTEGER PRIMARY KEY,
    slug      TEXT UNIQUE NOT NULL,
    name      TEXT NOT NULL,
    parent_id INTEGER REFERENCES categories(id),
    url       TEXT,
    level     INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS products (
    id           INTEGER PRIMARY KEY,
    item_id      TEXT UNIQUE NOT NULL,
    name         TEXT NOT NULL,
    brand        TEXT,
    category_id  INTEGER REFERENCES categories(id),
    url          TEXT,
    image        TEXT,
    unit         TEXT,        -- kg / L / pcs / g / ml etc.
    unit_qty     REAL,        -- numeric quantity for unit price calc
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS price_history (
    id          INTEGER PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    price       REAL NOT NULL,
    original    REAL,
    discount    REAL,
    rating      REAL,
    review_cnt  INTEGER,
    sold_cnt    INTEGER,
    in_stock    INTEGER DEFAULT 1,
    scraped_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ph_product  ON price_history(product_id);
CREATE INDEX IF NOT EXISTS idx_ph_scraped  ON price_history(scraped_at);
CREATE INDEX IF NOT EXISTS idx_prod_cat    ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_cat_parent  ON categories(parent_id);
"""

@contextlib.contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)

# ── Categories ────────────────────────────────────────────────────────────────

def upsert_category(slug, name, parent_id=None, url=None, level=0):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO categories(slug,name,parent_id,url,level)
            VALUES(?,?,?,?,?)
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name, parent_id=excluded.parent_id,
                url=excluded.url,  level=excluded.level
        """, (slug, name, parent_id, url, level))
        return conn.execute("SELECT id FROM categories WHERE slug=?", (slug,)).fetchone()[0]

def get_all_categories():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT c.*, COUNT(p.id) as item_count
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.id
            GROUP BY c.id
            ORDER BY c.level, c.name
        """).fetchall()
        return [dict(r) for r in rows]

# ── Products ─────────────────────────────────────────────────────────────────

def upsert_product(item_id, name, brand=None, category_id=None, url=None, image=None, unit=None, unit_qty=None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO products(item_id,name,brand,category_id,url,image,unit,unit_qty)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(item_id) DO UPDATE SET
                name=excluded.name, brand=excluded.brand,
                category_id=excluded.category_id, url=excluded.url,
                image=excluded.image, unit=excluded.unit,
                unit_qty=excluded.unit_qty, updated_at=CURRENT_TIMESTAMP
        """, (item_id, name, brand, category_id, url, image, unit, unit_qty))
        return conn.execute("SELECT id FROM products WHERE item_id=?", (item_id,)).fetchone()[0]

def get_products(category_id=None, limit=0, offset=0, search=None, alltime_low=False):
    with get_conn() as conn:
        wheres, params = [], []
        if category_id:
            wheres.append("p.category_id=?"); params.append(category_id)
        if search:
            wheres.append("p.name LIKE ?"); params.append(f"%{search}%")
            
        where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        
        sql = f"""
            SELECT p.*,
                   ph.price, ph.original, ph.discount, ph.rating, ph.review_cnt, ph.sold_cnt,
                   ph.in_stock, ph.scraped_at,
                   c.name AS category_name, c.slug AS category_slug,
                   stats.min_price, stats.max_price, stats.avg_price
            FROM products p
            LEFT JOIN (
                SELECT product_id, price, original, discount, rating, review_cnt,
                       sold_cnt, in_stock, scraped_at
                FROM price_history
                WHERE id IN (SELECT MAX(id) FROM price_history GROUP BY product_id)
            ) ph ON ph.product_id = p.id
            LEFT JOIN (
                SELECT product_id, MIN(price) as min_price, MAX(price) as max_price, AVG(price) as avg_price
                FROM price_history
                GROUP BY product_id
            ) stats ON stats.product_id = p.id
            LEFT JOIN categories c ON c.id = p.category_id
            {where_sql}
        """
        
        if alltime_low:
            sql += " AND ph.price <= (stats.min_price * 1.02) " if where_sql else " WHERE ph.price <= (stats.min_price * 1.02) "

        sql += " ORDER BY ph.scraped_at DESC "
        if limit and limit > 0:
            sql += " LIMIT ? OFFSET ? "
            params.extend([limit, offset])

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

# ── Price History ─────────────────────────────────────────────────────────────

def insert_price(product_id, price, original=None, discount=None, rating=None,
                 review_cnt=None, sold_cnt=None, in_stock=1):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO price_history(product_id,price,original,discount,rating,review_cnt,sold_cnt,in_stock)
            VALUES(?,?,?,?,?,?,?,?)
        """, (product_id, price, original, discount, rating, review_cnt, sold_cnt, in_stock))

def get_price_history(item_id, days=180):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM products WHERE item_id=?", (item_id,)).fetchone()
        if not row: return []
        rows = conn.execute("""
            SELECT price, original, discount, rating, review_cnt, sold_cnt, in_stock, scraped_at
            FROM price_history
            WHERE id IN (
                SELECT MAX(id) FROM price_history
                WHERE product_id=? AND scraped_at >= datetime('now', ?)
                GROUP BY date(scraped_at)
            )
            ORDER BY scraped_at ASC
        """, (row[0], f"-{days} days")).fetchall()
        return [dict(r) for r in rows]

def get_price_stats(item_id):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM products WHERE item_id=?", (item_id,)).fetchone()
        if not row: return {}
        stats = conn.execute("""
            SELECT MIN(price) min_price, MAX(price) max_price, AVG(price) avg_price,
                   COUNT(*) data_points,
                   MIN(scraped_at) first_seen, MAX(scraped_at) last_seen
            FROM price_history WHERE product_id=?
        """, (row[0],)).fetchone()
        return dict(stats) if stats else {}

# ── Dashboard Stats ───────────────────────────────────────────────────────────

def get_dashboard_stats():
    with get_conn() as conn:
        alltime_low_cnt = conn.execute("""
            SELECT COUNT(DISTINCT p.id)
            FROM products p
            JOIN (
                SELECT product_id, price FROM price_history
                WHERE id IN (SELECT MAX(id) FROM price_history GROUP BY product_id)
            ) ph ON ph.product_id = p.id
            JOIN (
                SELECT product_id, MIN(price) as min_price FROM price_history GROUP BY product_id
            ) stats ON stats.product_id = p.id
            WHERE ph.price <= (stats.min_price * 1.02)
        """).fetchone()[0]

        return {
            "total_products":   conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "total_categories": conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
            "total_records":    conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0],
            "alltime_low_cnt":  alltime_low_cnt,
            "last_scrape":      conn.execute("SELECT MAX(scraped_at) FROM price_history").fetchone()[0],
        }

if __name__ == "__main__":
    init_db()
    print("Database initialised:", DB_PATH)

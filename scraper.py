"""
Daraz Bangladesh Deep Scraper — Live API Scraper (Uncapped Category Scraping)
Hits Daraz live public endpoints directly across all subcategories & pages.
Run:  python scraper.py [--pages N] [--categories-only]
"""
import re, json, time, random, hashlib, argparse, logging
from datetime import date
from urllib.parse import urlencode, urljoin, urlparse, parse_qs
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from db import init_db, upsert_category, upsert_product, insert_price, get_all_categories

# ── Config ───────────────────────────────────────────────────────────────────
BASE       = "https://www.daraz.com.bd"
CAT_API    = BASE + "/catalog/"
HEADERS    = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         BASE + "/",
    "X-Requested-With": "XMLHttpRequest",
}
SESSION  = requests.Session()
SESSION.headers.update(HEADERS)
DELAY    = (0.5, 1.2)
MAX_RETRIES = 3

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("scraper.log", encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger(__name__)

# ── Unit-price parser ────────────────────────────────────────────────────────
UNIT_RE = re.compile(
    r'(\d+\.?\d*)\s*'
    r'(kg|g|lb|oz|L|ml|litre|liter|pcs|pc|piece|pieces|pack|set|pair|pairs|m|cm|mm|roll|sheet|tablet|tab|capsule|cap|sachet|bottle|box|bag|tin|jar)\b',
    re.IGNORECASE
)
UNIT_CANON = {
    "litre":"L","liter":"L","pieces":"pcs","piece":"pcs","pc":"pcs",
    "pairs":"pair","capsule":"cap","tablet":"tab",
}

def parse_unit(name: str):
    m = UNIT_RE.search(name)
    if not m: return None, None
    qty  = float(m.group(1))
    unit = UNIT_CANON.get(m.group(2).lower(), m.group(2).lower())
    return unit, qty

def safe_get(url, params=None, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=20)
            r.raise_for_status()
            return r
        except requests.RequestException as exc:
            log.warning("Attempt %d failed for %s: %s", attempt+1, url, exc)
            time.sleep(2 ** attempt + random.uniform(0, 1))
    return None

def jitter(): time.sleep(random.uniform(*DELAY))

# ── Category discovery ────────────────────────────────────────────────────────

def fetch_category_tree():
    log.info("Fetching homepage category tree directly from Live API...")
    r = safe_get(BASE + "/")
    if not r: return []

    m = re.search(r'window\.__data__\s*=\s*(\{.+?\});\s*</script>', r.text, re.DOTALL)
    cats = []
    if m:
        try:
            data = json.loads(m.group(1))
            tree = (data.get("categoryTree") or
                    data.get("data", {}).get("categoryTree") or
                    data.get("pageData", {}).get("categoryTree") or [])
            if isinstance(tree, list): cats = tree
            log.info("Found %d top-level categories from Live API", len(cats))
        except Exception as exc:
            log.warning("JSON parse of __data__ failed: %s", exc)

    if not cats:
        cats = _scrape_nav_links(r.text)

    return cats

def _scrape_nav_links(html: str):
    cats = []
    seen = set()
    for m in re.finditer(r'href="(/[a-z0-9\-]+/)"[^>]*>([^<]+)<', html):
        path, name = m.group(1), m.group(2).strip()
        slug = path.strip("/")
        if slug and slug not in seen and len(slug) > 2:
            seen.add(slug)
            cats.append({"name": name, "url": BASE + path, "slug": slug})
    return cats

def _flatten_category_tree(tree, parent_id=None, level=0):
    result = []
    for node in tree:
        name = node.get("name") or node.get("title") or ""
        url  = node.get("url") or node.get("mUrl") or node.get("pUrl") or ""
        slug = node.get("slug") or node.get("categorySlug") or ""

        if not slug:
            slug = urlparse(url).path.strip("/").split("/")[-1] or hashlib.md5(name.encode()).hexdigest()[:8]

        if not url.startswith("http"):
            url = urljoin(BASE, url)

        cat_id = upsert_category(slug, name, parent_id=parent_id, url=url, level=level)
        result.append((cat_id, slug, url))

        children = node.get("children") or node.get("subCategories") or node.get("sub") or []
        result.extend(_flatten_category_tree(children, parent_id=cat_id, level=level+1))

    return result

# ── Product listing scraper (Uncapped) ───────────────────────────────────────

def scrape_category_products(cat_id: int, slug: str, url: str, max_pages: int = 100):
    """
    Scrape products in a category dynamically up to max_pages.
    Daraz returns 40 items per page. (100 pages = 4,000 items per category/subcategory!)
    """
    log.info("Scraping Category: %s (cat_id=%d, max_pages=%d)", slug, cat_id, max_pages)

    page = 1
    total_scraped = 0

    while page <= max_pages:
        params = {
            "ajax": "true",
            "page": page,
            "q": slug.replace("-", " ")
        }

        jitter()
        r = safe_get(CAT_API, params=params)
        if not r: break

        try:
            data = r.json()
        except Exception:
            items = _parse_product_html(r.text, cat_id)
            if not items: break
            _save_products(items, cat_id)
            total_scraped += len(items)
            page += 1
            continue

        items = _extract_items_from_api(data)
        if not items:
            log.info("  Page %d — Daraz returned 0 items. Reached end of category (%d items total).", page, total_scraped)
            break

        _save_products(items, cat_id)
        total_scraped += len(items)
        log.info("  Page %d — saved %d items (Category cumulative total: %d)", page, len(items), total_scraped)

        # Daraz sends 40 items per page; if less than 40 return, it's the last page
        if len(items) < 40:
            log.info("  Page %d — final page batch received (%d items). Category complete.", page, len(items))
            break

        page += 1

def _extract_items_from_api(data: dict):
    if not isinstance(data, dict): return []
    
    mods = data.get("mods") or data.get("mainInfo", {}).get("mods") or {}
    items = mods.get("listItems") or []
    if items: return items
    
    items = data.get("listItems") or data.get("items") or []
    if items: return items

    nested = data.get("data") or {}
    items  = nested.get("items") or nested.get("products") or []
    if items: return items

    return []

def _parse_product_html(html: str, cat_id: int):
    items = []
    m = re.search(r'__Q_INITIAL_STATE__\s*=\s*(\{.+?\});\s*</script>', html, re.DOTALL)
    if not m:
        m = re.search(r'window\.pageData\s*=\s*(\{.+?\});\s*</script>', html, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            items = _extract_items_from_api(d)
        except Exception: pass
    return items

def _extract_price(item):
    price_raw = (item.get("price") or item.get("rrp_price") or
                 item.get("sale_price") or item.get("salePrice") or "0")
    orig_raw  = (item.get("original_price") or item.get("originalPrice") or item.get("originalPriceShow"))
    try: price = float(re.sub(r"[^\d.]", "", str(price_raw)))
    except: price = 0.0
    try: orig  = float(re.sub(r"[^\d.]", "", str(orig_raw)))
    except: orig = None
    discount = item.get("discount") or item.get("priceDiscount")
    try: discount = float(re.sub(r"[^\d.]", "", str(discount))) if discount else None
    except: discount = None
    return price, orig, discount

def _save_products(items, cat_id: int):
    for item in items:
        try:
            item_id = str(item.get("itemId") or item.get("id") or item.get("skuId") or "")
            name    = (item.get("name") or item.get("title") or "").strip()
            if not item_id or not name: continue

            brand   = item.get("brandName") or item.get("brand") or item.get("sellerName")
            url     = item.get("itemUrl") or item.get("url") or ""
            if url and not url.startswith("http"): url = urljoin("https:", url) if url.startswith("//") else urljoin(BASE, url)
            image   = (item.get("image") or item.get("mainImage") or item.get("thumbnailUrl") or "")

            unit, unit_qty = parse_unit(name)

            rating     = item.get("ratingScore") or item.get("averageRating")
            review_cnt = item.get("review") or item.get("reviewCount")
            sold_cnt   = item.get("sold") or item.get("soldCount")

            try: rating     = float(rating) if rating else None
            except: rating = None
            try: review_cnt = int(review_cnt) if review_cnt else None
            except: review_cnt = None
            try: sold_cnt   = int(str(sold_cnt).replace("+","").replace(",","")) if sold_cnt else None
            except: sold_cnt = None

            price, orig, discount = _extract_price(item)
            if price <= 0: continue

            prod_id = upsert_product(item_id, name, brand=brand, category_id=cat_id,
                                     url=url, image=image, unit=unit, unit_qty=unit_qty)
            insert_price(prod_id, price, original=orig, discount=discount,
                         rating=rating, review_cnt=review_cnt, sold_cnt=sold_cnt)
        except Exception as exc:
            log.warning("Failed saving item %s: %s", item.get("itemId","?"), exc)

# ── Main ──────────────────────────────────────────────────────────────────────

def run(max_pages: int = 100, categories_only: bool = False):
    init_db()
    log.info("=== Daraz Live API Deep Scraper starting (Uncapped) — %s ===", date.today())

    tree = fetch_category_tree()
    if tree:
        cat_list = _flatten_category_tree(tree)
        log.info("Loaded %d categories dynamically from Live API", len(cat_list))
    else:
        log.info("Loading existing categories from database...")
        cat_list = [(c["id"], c["slug"], c["url"]) for c in get_all_categories()]

    if categories_only:
        log.info("Categories updated, exiting.")
        return

    MAX_WORKERS = 5
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(scrape_category_products, cat_id, slug, url, max_pages): (cat_id, slug)
            for cat_id, slug, url in cat_list
        }
        for future in as_completed(futures):
            cat_id, slug = futures[future]
            try:
                future.result()
            except Exception as exc:
                log.warning("Category %s live fetch error: %s", slug, exc)

    log.info("=== Live API Scrape complete ===")

    # Auto-export static JSON for GitHub Pages hosting
    try:
        from export_static import export as export_static_json
        log.info("Exporting static data for GitHub Pages...")
        export_static_json()
    except Exception as exc:
        log.warning("Failed to auto-export static data: %s", exc)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Daraz Live API Price Scraper")
    ap.add_argument("--pages",           type=int, default=100, help="Max pages per category (default: 100 = 4,000 items/cat)")
    ap.add_argument("--categories-only", action="store_true", help="Only refresh category tree")
    args = ap.parse_args()
    run(max_pages=args.pages, categories_only=args.categories_only)

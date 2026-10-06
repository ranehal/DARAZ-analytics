"""
Discovery module — uses Scrapling to efficiently surface every Daraz section:
categories, flash sales, fests/campaigns, and voucher hubs.

Scrapling gives us stealthy TLS impersonation + adaptive parsing so the
homepage SSR payload (which now embeds flash-sale & campaign data inline)
can be harvested without a headless browser.
"""
import re, json, logging
from urllib.parse import urljoin, urlparse, parse_qs, unquote, unquote_plus

import config

log = logging.getLogger(__name__)

# Scrapling is the preferred (stealthy, TLS-impersonated) fetcher. If it is not
# available (e.g. a restricted Kaggle runtime), fall back to plain requests so
# discovery never hard-fails.
try:
    from scrapling.fetchers import Fetcher
    HAS_SCRAPLING = True
except Exception:
    HAS_SCRAPLING = False
    import requests

# ── Fetching ─────────────────────────────────────────────────────────────────

def fetch_homepage():
    """Fetch the Daraz homepage — via Scrapling when available, else requests."""
    url = config.BASE_URL + "/"
    if HAS_SCRAPLING:
        page = Fetcher.get(
            url,
            timeout=config.REQUEST_TIMEOUT,
            stealthy_headers=True,
            impersonate=config.IMPERSONATE,
        )
        return str(page.html_content)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = requests.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.text


def _decode(s):
    """Best-effort decode of URL-encoded or HTML-escaped strings."""
    if s is None:
        return ""
    s = s.strip()
    try:
        s = unquote(s)
    except Exception:
        pass
    try:
        s = unquote_plus(s)
    except Exception:
        pass
    return s


# ── Flash Sales ──────────────────────────────────────────────────────────────

FLASH_CARD_RE = re.compile(
    r'<a[^>]+card-fs-content-body-unit[^>]*'
    r'href="(?P<url>[^"]+)"[^>]*'
    r'data-spm-protocol="i"[^>]*'
    r'id="(?P<item_id>\d+)"[^>]*'
    r'name="(?P<name>[^"]+)"'
    r'(?P<inner>.*?)</a>',
    re.DOTALL,
)

IMG_RE = re.compile(r'<img[^>]+src="(?P<src>[^"]+)"')
FS_PRICE_RE = re.compile(r'fs-card-price.*?<span class="price">(?P<p>[0-9.,]+)</span>', re.DOTALL)
FS_ORIG_RE  = re.compile(r'fs-card-origin-price.*?<span class="price">(?P<p>[0-9.,]+)</span>', re.DOTALL)
FS_DISC_RE  = re.compile(r'itemDiscount">-(?P<d>[0-9.]+)%?<')
FS_SOLD_RE  = re.compile(r'fs-card-sold[^>]*>\s*(?P<s>[0-9.,+kKmM]+)?\s*<', re.DOTALL)


def _clean_product_url(url):
    """Strip Daraz tracking params, keeping a clean canonical product URL."""
    if not url:
        return ""
    url = url.replace("&amp;", "&")
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    path = parsed.path
    # Normalise the -i{itemId}-s{sku}.html slug to a clean product path
    if "/products/" in path:
        path = re.sub(r"-s\d+\.html$", ".html", path)
        path = path.replace(" ", "")
    return f"{config.BASE_URL}{path}"


def discover_flash_sales(html):
    """Extract flash-sale items embedded in the homepage SSR markup."""
    items = []
    for m in FLASH_CARD_RE.finditer(html):
        try:
            item_id = m.group("item_id")
            inner = m.group("inner")
            name = _decode(m.group("name"))
            url = _clean_product_url(m.group("url"))

            img = ""
            im = IMG_RE.search(inner)
            if im:
                img = im.group("src")

            price = original = discount = sold = None
            pm = FS_PRICE_RE.search(inner)
            if pm:
                price = float(pm.group("p").replace(",", ""))
            om = FS_ORIG_RE.search(inner)
            if om:
                original = float(om.group("p").replace(",", ""))
            dm = FS_DISC_RE.search(inner)
            if dm:
                discount = float(dm.group("d"))
            sm = FS_SOLD_RE.search(inner)
            if sm and sm.group("s"):
                sold = _parse_sold(sm.group("s").replace(",", "").lower())
            if sold is None:
                # fallback: sold count is embedded in the clickTrackInfo URL param
                sold = _sold_from_clicktrack(m.group("url"))

            if item_id and name:
                items.append({
                    "item_id": item_id,
                    "name": name,
                    "image": img,
                    "url": url,
                    "price": price,
                    "original": original,
                    "discount": discount,
                    "sold": sold,
                })
        except Exception as exc:
            log.debug("Flash card parse error: %s", exc)
    log.info("Discovered %d flash-sale items from homepage", len(items))
    return items


def _parse_sold(raw):
    raw = raw.strip()
    if not raw:
        return None
    try:
        if raw.endswith("k") or raw.endswith("K"):
            return int(float(raw[:-1]) * 1000)
        if raw.endswith("m") or raw.endswith("M"):
            return int(float(raw[:-1]) * 1000000)
        if raw.endswith("+"):
            return int(raw[:-1])
        return int(raw)
    except Exception:
        return None


def _sold_from_clicktrack(url):
    """Parse fs_item_sold_cnt out of the URL's clickTrackInfo param."""
    if not url:
        return None
    m = re.search(r"fs_item_sold_cnt%3A(\d+)", url)
    if m:
        return int(m.group(1))
    return None


# ── Campaigns / Fests ────────────────────────────────────────────────────────

CAMPAIGN_LINK_RE = re.compile(
    r'href="(?P<url>https?://(?:www\.)?daraz\.com\.bd/(?P<slug>[a-z0-9\-]+)/?(?:\?[^"]*)?)"',
    re.IGNORECASE,
)
MEGASCENARIO_RE = re.compile(r'wh_pid=/lazada/(megascenario|channel)/bd/(?P<path>[^&"\']+)')


def discover_campaigns(html):
    """Extract campaign/fest/voucher section links, classified by slug."""
    found = {}
    # Direct known slugs
    for slug, (label, section) in config.KNOWN_CAMPAIGNS.items():
        pat = re.compile(
            rf'href="[^"]*/{re.escape(slug)}/?(?:\?[^"]*)?"',
            re.IGNORECASE,
        )
        if pat.search(html):
            found[slug] = {
                "slug": slug,
                "name": label,
                "section": section,
                "badge": config.SECTION_BADGE.get(section, "📣"),
                "url": f"{config.BASE_URL}/{slug}/",
            }

    # Generic *-sale / *-fest slugs not in the known map
    for m in CAMPAIGN_LINK_RE.finditer(html):
        slug = m.group("slug")
        if slug in found or not slug:
            continue
        if re.search(r"(sale|fest|deal|campaign|offer|voucher|mall)", slug):
            section = "voucher" if "voucher" in slug else ("fest" if "fest" in slug else "campaign")
            found[slug] = {
                "slug": slug,
                "name": _slug_to_title(slug),
                "section": section,
                "badge": config.SECTION_BADGE.get(section, "📣"),
                "url": f"{config.BASE_URL}/{slug}/",
            }

    # Megascenario / channel deep links (flashsale channel, megadeals, etc.)
    for m in MEGASCENARIO_RE.finditer(html):
        path = m.group("path")
        slug = "wow-" + re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")[:48]
        if slug not in found:
            section = "flash_sale" if "flashsale" in path else "campaign"
            found[slug] = {
                "slug": slug,
                "name": _slug_to_title(path.split("/")[-1]),
                "section": section,
                "badge": config.SECTION_BADGE.get(section, "📣"),
                "url": urljoin(config.BASE_URL, "/"),  # deep links kept generic
            }

    campaigns = sorted(found.values(), key=lambda c: c["name"])
    log.info("Discovered %d campaign/fest sections", len(campaigns))
    return campaigns


def _slug_to_title(slug):
    return " ".join(w.capitalize() for w in slug.replace("-", " ").split())


# ── Categories ───────────────────────────────────────────────────────────────

CAT_CARD_RE = re.compile(
    r'<a[^>]+data-spm-protocol="i"[^>]*venture="BD"[^>]*'
    r'id="(?P<id>\d+)"[^>]*'
    r'name="(?P<name>[^"]+)"'
    r'(?P<inner>.*?)</a>',
    re.DOTALL,
)
CAT_HREF_RE = re.compile(r'href="(?P<url>[^"]+)"[^>]*>', re.IGNORECASE)
CAT_IMAGE_MARK = "card-categories-image"
FLASH_MARK = "card-fs-content-body-unit"


def discover_category_cards(html):
    """
    Extract category chips embedded in homepage markup. Only real category
    cards are kept (they carry a `card-categories-image` inner block);
    flash-sale / product cards are explicitly excluded.
    Returns unique (id, name, url) tuples.
    """
    cats = []
    seen = set()
    for m in CAT_CARD_RE.finditer(html):
        cid = m.group("id")
        name = _decode(m.group("name"))
        inner = m.group("inner")
        if not cid or not name or cid in seen:
            continue
        if FLASH_MARK in inner or CAT_IMAGE_MARK not in inner:
            continue
        start = m.start()
        prefix = html[max(0, start - 600):start]
        hrefs = CAT_HREF_RE.findall(prefix)
        url = urljoin(config.BASE_URL, hrefs[-1].replace("&amp;", "&")) if hrefs else ""
        if not url:
            url = f"{config.BASE_URL}/?categoryId={cid}"
        seen.add(cid)
        cats.append({"id": int(cid), "name": name, "url": url, "slug": f"c{cid}"})
    log.info("Discovered %d category cards from homepage", len(cats))
    return cats


# ── Unified discovery ────────────────────────────────────────────────────────

def discover():
    """Run full discovery and return a structured payload."""
    html = fetch_homepage()
    return {
        "flash_sales": discover_flash_sales(html),
        "campaigns": discover_campaigns(html),
        "categories": discover_category_cards(html),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    result = discover()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

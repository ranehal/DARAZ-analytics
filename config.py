"""Central configuration for the Daraz Analytics stack."""
import os

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
BASE_URL   = "https://www.daraz.com.bd"
DB_PATH    = os.path.join(BASE_DIR, "daraz_prices.db")
DATA_DIR   = os.path.join(BASE_DIR, "data")
PRODUCTS_DIR = os.path.join(DATA_DIR, "products")

CURRENCY   = "৳"

# Scrapling fetcher defaults (stealthy, chrome TLS impersonation)
IMPERSONATE = "chrome"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

# Known campaign / fest / flash-sale sections to surface on the dashboard.
# Slug -> (human label, section type)
KNOWN_CAMPAIGNS = {
    "flash-sale":         ("Flash Sale",        "flash_sale"),
    "collectible-vouchers": ("Voucher Center",  "voucher"),
    "eid-big-sale":       ("Eid Big Sale",      "fest"),
    "grand-eid-fest":     ("Grand Eid Fest",    "fest"),
    "bn-grand-eid-fest":  ("Eid Fest (BN)",     "fest"),
    "daraz-mall-fest":    ("Daraz Mall Fest",   "fest"),
    "10-10-mega-sale":    ("10.10 Mega Sale",   "fest"),
    "11-11-sale-gcp":     ("11.11 Sale",        "fest"),
    "11-11-sale":         ("11.11 Sale",        "fest"),
    "12-12-sale":         ("12.12 Sale",        "fest"),
    "valentines-day-sale":("Valentine's Day",   "fest"),
    "anniversary-sale":   ("Anniversary Sale",  "fest"),
    "bn-11-11-sale":      ("11.11 (BN)",        "fest"),
    "bn-valentines-day-sale": ("Valentine's (BN)", "fest"),
}

# Section emoji / badges used for UI polish
SECTION_BADGE = {
    "flash_sale": "⚡",
    "voucher":    "🎟️",
    "fest":       "🎉",
    "campaign":   "📣",
}

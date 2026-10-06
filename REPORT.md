# Daraz Analytics — Upgrade & QA Report

**Date:** 2026-10-07 · **Repo:** `ranehal/DARAZ-analytics` · **Branch:** `main`

---

## 1. Scope

This upgrade turns the Daraz price-tracker into a full **market-intelligence
dashboard** — adding Scrapling-powered section discovery (flash sales, fests,
campaigns, vouchers, categories), new analytics endpoints, and a polished
multi-view frontend — while guaranteeing the **Kaggle orchestrator pipeline
(`kaggle gitGOD.ipynb` → `run_scheduled_repo` → `scraper.py`) is never broken.**

---

## 2. New capabilities

### 2.1 Scrapling discovery (`discovery.py`)
Harvests the Daraz homepage SSR payload (which now embeds flash-sale & campaign
data inline, replacing the old `window.__data__` categoryTree):

- **Flash sales** — price, original, discount %, sold count (parsed from
  `clickTrackInfo`), and a **clean canonical product URL** (tracking params stripped).
- **Campaigns / fests / vouchers** — 35 sections discovered & classified
  (`flash_sale` / `fest` / `voucher` / `campaign`) from a slug registry +
  megascenario deep-links.
- **Category chips** — real Daraz category IDs & names, with explicit exclusion
  of flash-sale/product cards (bug fixed — see §5.2).

### 2.2 Database layer (`db.py`)
New tables `campaigns` and `flash_sales`, plus analytics query helpers:
`get_price_drops`, `get_top_discounts`, `get_top_sellers`,
`get_price_change_leaders`, `get_category_distribution`,
`get_discount_distribution`.

### 2.3 API (`app.py`)
New endpoints: `/api/campaigns`, `/api/flash-sales`, `/api/price-drops`,
`/api/top-discounts`, `/api/top-sellers`, `/api/price-movers`, `/api/analytics`,
and `/api/export.csv`. Product detail now joins `category_name`.

### 2.4 Frontend (`templates/index.html` + static `index.html`)
Six views — Overview, Flash Sales, Fests & Campaigns, Deals & Drops, Analytics,
All Products — with search, sort, all-time-low filter, category sidebar, Chart.js
doughnut/bar charts, and a price-history modal. Dark glassmorphism theme,
responsive layout, static-`data/*.json` fallback for GitHub Pages.

### 2.5 Static export (`export_static.py`)
Now emits `campaigns.json`, `flash_sales.json`, and `analytics.json` for the
static (GitHub Pages) dashboard.

---

## 3. Kaggle-pipeline safety (critical)

The Kaggle notebook clones this repo and runs `scraper.py` directly. Guardrails:

1. **`scraper.py` imports `discovery` lazily** inside a `try/except`. If Scrapling
   is absent, `HAS_DISCOVERY = False` and the core scraper continues unchanged.
2. **`discovery.py` falls back to plain `requests`** when Scrapling import fails,
   so discovery itself never hard-fails.
3. **`requirements.txt` uses `scrapling[fetchers]`** (the light fetcher extra, not
   `[all]`), and the orchestrator already installs `requirements.txt` with
   `check=False`, so install failures don't abort the run.
4. **Schema is additive** — `products` + `price_history` are untouched, so the
   orchestrator's `_extract_repo_price_stats` (which reads those tables) keeps
   working.

Verified by simulating a missing-Scrapling environment:

```
scraper import OK without scrapling; HAS_DISCOVERY = False
discovery import OK without scrapling; HAS_SCRAPLING = False
discovery (requests fallback) → flash 6, campaigns 35, categories 23
```

---

## 4. Quality assurance

- **Syntax:** `ast.parse` passes for all 7 Python modules.
- **Frontend JS:** extracted inline `<script>` and `node --check` → clean.
- **Flask smoke test:** all 13 routes return `200` (`/`, `/api/stats`,
  `/api/campaigns`, `/api/flash-sales`, `/api/price-drops`, `/api/top-discounts`,
  `/api/top-sellers`, `/api/price-movers`, `/api/analytics`, `/api/products`,
  `/api/categories`, `/api/product/<id>`, `/api/export.csv`).
- **Static contracts:** `analytics.json` / `flash_sales.json` / `campaigns.json`
  shapes match the frontend's fallback parsing.
- **Live scraper run:** `python scraper.py --categories-only` succeeds end-to-end
  (discovery → category tree → export).

---

## 5. Bugs found & fixed

1. **Category-tree pollution** — the category-card regex also matched flash-sale
   product anchors, leaking product names (e.g. "BLOOM TURMERIC POWDER") into the
   category tree. Fixed with `card-categories-image` marker + `card-fs-*` exclusion;
   23 polluted rows purged from the DB.
2. **Missing sold counts** on flash-sale cards — added `fs_item_sold_cnt` parsing
   from the URL's `clickTrackInfo` as a fallback.
3. **Ugly flash-sale URLs** — added `_clean_product_url` to strip tracking params
   and normalize `-s{sku}.html` slugs.
4. **Overview static fallback crash** — `loadOverview` now guards against
   `analytics.json` returning an object instead of an array.
5. **Inconsistent flash-sale count** — `get_dashboard_stats` now uses
   `COUNT(DISTINCT item_id)` to match `get_flash_sales` deduplication.
6. **Unicode re-encoding noise** — reverted `ensure_ascii=False` on existing
   exports (products/categories/detail), keeping the diff clean.

---

## 6. Files changed

| File | Change |
|------|--------|
| `discovery.py` | **new** — Scrapling discovery (flash sales, campaigns, categories) |
| `config.py` | **new** — central constants + known-campaign registry |
| `scraper.py` | discovery integration, lazy Scrapling import, `_auto_export` helper |
| `db.py` | `campaigns` + `flash_sales` tables, analytics queries |
| `app.py` | new REST endpoints + CSV export + category_name join |
| `export_static.py` | campaigns / flash_sales / analytics exports |
| `templates/index.html`, `index.html` | full dashboard rewrite (6 views) |
| `requirements.txt` | `scrapling[fetchers]>=0.4.15` |
| `README.md` | architecture & usage docs |

---

## 7. Installed / used SOTA tooling

- **Scrapling** (skill `scrapling-official`) — stealthy TLS-impersonated fetching
  and adaptive parsing for section discovery.
- **Chart.js** — analytics visualization.
- Existing stack retained: Flask, requests, SQLite.

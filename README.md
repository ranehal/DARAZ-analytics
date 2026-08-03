# Daraz Analytics & Price Tracker 🛍️📊

A real-time price scraper, analytics, and historical price tracking dashboard for Daraz Bangladesh (CamelCamelCamel style).

## Features
- **Real-Time & Uncapped Scraper**: Scrapes public Daraz catalog APIs dynamically across all categories & subcategories.
- **Price History & Analytics**: Tracks price fluctuations, all-time lows, original vs discounted prices, seller ratings, and unit price calculations (e.g., ৳/kg, ৳/L, ৳/pc).
- **Interactive Dashboard**: Modern web interface built with Flask and Vanilla CSS/JS featuring category trees, full-text product search, price history modals, stats, and real-time live scrape triggers.

## Project Structure
```
DARAZ-analytics/
├── app.py              # Flask API server & web app routes
├── db.py               # SQLite database access layer & schema
├── scraper.py          # Daraz public API scraper module
├── seed.py             # Database seeder with sample history
├── runall.bat          # Windows launcher script
├── daraz_prices.db     # SQLite price database
├── requirements.txt    # Python dependencies
└── templates/
    └── index.html      # Interactive analytics dashboard UI
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Seed Database (Optional)
If starting fresh or resetting data:
```bash
python seed.py
```

### 3. Run Scraper
```bash
python scraper.py --pages 10
```

### 4. Start Dashboard Server
```bash
python app.py
```
Open `http://localhost:5000` in your browser.

#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          JINXMP3 SHOPIFY STORE AGENT  v2.0                                 ║
║          Full Shopify Admin API integration + storefront HTML generator    ║
╚══════════════════════════════════════════════════════════════════════════════╝

This agent:
  1. Connects to your Shopify store via Admin API
  2. Reads catalog.json and creates/updates Shopify products
  3. Generates an upgraded storefront HTML (index.html) with embedded buy buttons
  4. Manages collections, metafields, and inventory
  5. Provides a report of store health

Usage:
  python shopify_store_agent.py --sync          # sync catalog → Shopify products
  python shopify_store_agent.py --report        # print store summary
  python shopify_store_agent.py --build-front   # regenerate upgraded index.html
  python shopify_store_agent.py --all           # run all tasks
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SITE_DIR = (SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR)
SITE_DIR = Path(os.getenv("JINX_SITE_DIR") or str(DEFAULT_SITE_DIR)).resolve()
SHOPIFY_STORE  = os.getenv("SHOPIFY_STORE_DOMAIN", "")   # e.g. jinxmp3.myshopify.com
SHOPIFY_TOKEN  = os.getenv("SHOPIFY_ADMIN_TOKEN",  "")
SHOPIFY_KEY    = os.getenv("SHOPIFY_API_KEY",      "")    # for Storefront API (buy buttons)
CATALOG_JSON   = SITE_DIR / "public" / "catalog.json"
OUTPUT_HTML    = SITE_DIR / "public" / "index.html"
API_VERSION    = "2024-01"
BASE_URL       = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}"

# ── HTTP Helper ───────────────────────────────────────────────────────────────
def shopify_request(method: str, path: str, body: dict = None) -> tuple[int, dict]:
    url  = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    hdrs = {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
    except Exception as ex:
        return 0, {"error": str(ex)}


# ── Product Sync ──────────────────────────────────────────────────────────────
def get_all_shopify_products() -> dict:
    """Return {sku: product_id} map for all existing products."""
    status, data = shopify_request("GET", f"/products.json?limit=250&fields=id,variants")
    if status != 200:
        print(f"[ERROR] Could not fetch products: {data}")
        return {}
    sku_map = {}
    for p in data.get("products", []):
        for v in p.get("variants", []):
            if v.get("sku"):
                sku_map[v["sku"]] = str(p["id"])
    return sku_map


def create_shopify_product(entry: dict, tunnel_host: str = "www.jinxmp3.com") -> str | None:
    """Create a Shopify product for a catalog entry. Returns product ID string."""
    cover_url = f"https://{tunnel_host}{entry.get('coverUrl', '')}" if entry.get("coverUrl") else None
    payload = {
        "product": {
            "title": entry.get("title", "Untitled Release"),
            "body_html": (
                f"<p><strong>{entry.get('title', '')}</strong> — digital release by "
                f"<em>{entry.get('artist', 'jinx3')}</em>.<br>"
                f"Produced by {entry.get('producer', 'Guice Atkinson')}.</p>"
                f"<p>🎵 <a href='{entry.get('hyperfollowUrl', '')}'>Stream on all platforms</a></p>"
            ),
            "vendor": entry.get("artist", "jinx3"),
            "product_type": "Digital Music",
            "tags": "music, digital, wav, beat, jinx3, download",
            "status": "active",
            "variants": [
                {
                    "title": "WAV Download",
                    "price": "4.99",
                    "sku": entry.get("slug", ""),
                    "inventory_management": None,
                    "fulfillment_service": "manual",
                    "requires_shipping": False,
                    "taxable": True,
                    "inventory_policy": "continue",
                }
            ],
            "images": [{"src": cover_url}] if cover_url else [],
        }
    }
    status, data = shopify_request("POST", "/products.json", payload)
    if status in (200, 201):
        pid = str(data["product"]["id"])
        print(f"  [+] Created: '{entry['title']}' → Shopify ID {pid}")
        return pid
    print(f"  [!] Failed to create '{entry.get('title')}': HTTP {status} — {data}")
    return None


def sync_catalog_to_shopify():
    """Main sync: catalog.json → Shopify products."""
    if not SHOPIFY_STORE or not SHOPIFY_TOKEN:
        print("[WARN] SHOPIFY_STORE_DOMAIN or SHOPIFY_ADMIN_TOKEN not set. Set them in your .env file.")
        return

    print(f"\n{'='*60}")
    print("  SHOPIFY CATALOG SYNC")
    print(f"{'='*60}")

    catalog = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    existing = get_all_shopify_products()
    print(f"  Catalog entries : {len(catalog)}")
    print(f"  Existing Shopify: {len(existing)} products")

    created = 0
    skipped = 0
    errors  = 0

    for i, entry in enumerate(catalog):
        slug = entry.get("slug", "")
        # Already synced?
        if entry.get("shopifyProductId") or slug in existing:
            if slug in existing and not entry.get("shopifyProductId"):
                catalog[i]["shopifyProductId"] = existing[slug]
            skipped += 1
            continue

        pid = create_shopify_product(entry)
        if pid:
            catalog[i]["shopifyProductId"] = pid
            created += 1
        else:
            errors += 1
        time.sleep(0.6)  # Shopify rate limit: ~2 req/s

    # Write updated catalog
    CATALOG_JSON.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"\n  ✅ Sync complete: {created} created, {skipped} skipped, {errors} errors")


# ── Store Report ──────────────────────────────────────────────────────────────
def print_store_report():
    if not SHOPIFY_STORE or not SHOPIFY_TOKEN:
        print("[WARN] Shopify credentials not configured.")
        return
    status, data = shopify_request("GET", "/products/count.json")
    count = data.get("count", "?") if status == 200 else "?"
    status2, orders = shopify_request("GET", "/orders/count.json?status=any")
    order_count = orders.get("count", "?") if status2 == 200 else "?"
    print(f"""
{'='*60}
  SHOPIFY STORE REPORT  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}
{'='*60}
  Store          : {SHOPIFY_STORE}
  Total products : {count}
  Total orders   : {order_count}
{'='*60}""")


# ── Upgraded Storefront HTML Generator ───────────────────────────────────────
STOREFRONT_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>jinx3 — Music & Beats</title>
  <meta name="description" content="Official site of jinx3 / Guice Atkinson. Stream, download, and buy beats." />
  <link rel="stylesheet" href="styles.css" />
  <style>
    /* ── UPGRADED STOREFRONT STYLES ── */
    :root {
      --bg: #0a0a0f;
      --surface: #13131a;
      --card: #1a1a24;
      --accent: #7c3aed;
      --accent2: #a855f7;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --border: #2d2d3d;
      --green: #22c55e;
      --radius: 12px;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; min-height: 100vh; }

    /* NAV */
    nav { display: flex; align-items: center; justify-content: space-between; padding: 1rem 2rem;
          background: rgba(10,10,15,0.95); backdrop-filter: blur(12px);
          border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 100; }
    .nav-logo { font-size: 1.5rem; font-weight: 800; background: linear-gradient(135deg, var(--accent), var(--accent2));
                -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .nav-links { display: flex; gap: 1.5rem; }
    .nav-links a { color: var(--muted); text-decoration: none; font-size: 0.9rem; transition: color .2s; }
    .nav-links a:hover { color: var(--text); }

    /* HERO */
    .hero { text-align: center; padding: 5rem 2rem 3rem;
            background: radial-gradient(ellipse at 50% 0%, rgba(124,58,237,0.15) 0%, transparent 70%); }
    .hero h1 { font-size: clamp(2.5rem, 6vw, 4.5rem); font-weight: 900; line-height: 1.1;
               background: linear-gradient(135deg, #fff 30%, var(--accent2));
               -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .hero p { color: var(--muted); font-size: 1.1rem; margin-top: 1rem; max-width: 500px; margin-inline: auto; }
    .hero-cta { display: inline-flex; gap: 1rem; margin-top: 2rem; flex-wrap: wrap; justify-content: center; }
    .btn { padding: .7rem 1.6rem; border-radius: 8px; font-weight: 600; font-size: .9rem;
           cursor: pointer; border: none; transition: all .2s; text-decoration: none; display: inline-block; }
    .btn-primary { background: var(--accent); color: #fff; }
    .btn-primary:hover { background: var(--accent2); transform: translateY(-1px); }
    .btn-ghost { background: transparent; color: var(--text); border: 1px solid var(--border); }
    .btn-ghost:hover { border-color: var(--accent); color: var(--accent2); }
    .btn-buy { background: linear-gradient(135deg, var(--accent), var(--accent2));
               color: #fff; font-size: .8rem; padding: .5rem 1rem; }
    .btn-buy:hover { opacity: .9; transform: translateY(-1px); }

    /* STATS BAR */
    .stats-bar { display: flex; justify-content: center; gap: 3rem; padding: 1.5rem 2rem;
                 background: var(--surface); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); flex-wrap: wrap; }
    .stat { text-align: center; }
    .stat-num { font-size: 1.8rem; font-weight: 800; color: var(--accent2); }
    .stat-label { font-size: .75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }

    /* CATALOG */
    .section { padding: 3rem 2rem; max-width: 1400px; margin-inline: auto; }
    .section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 1rem; }
    .section-title { font-size: 1.4rem; font-weight: 700; }
    .search-bar { background: var(--card); border: 1px solid var(--border); border-radius: 8px;
                  color: var(--text); padding: .6rem 1rem; font-size: .9rem; width: 260px; outline: none; }
    .search-bar:focus { border-color: var(--accent); }
    .catalog-count { color: var(--muted); font-size: .85rem; }

    .catalog-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1.25rem; }
    .release-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
                    overflow: hidden; transition: transform .2s, border-color .2s; }
    .release-card:hover { transform: translateY(-4px); border-color: var(--accent); }
    .card-cover-wrapper { position: relative; aspect-ratio: 1; overflow: hidden; background: #111; }
    .card-cover { width: 100%; height: 100%; object-fit: cover; display: block; }
    .play-btn { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
                background: rgba(0,0,0,.5); color: #fff; font-size: 1.5rem; cursor: pointer;
                border: none; opacity: 0; transition: opacity .2s; }
    .card-cover-wrapper:hover .play-btn { opacity: 1; }
    .play-btn.playing { opacity: 1; background: rgba(124,58,237,.6); }
    .card-body { padding: .85rem; }
    .card-title { font-size: .9rem; font-weight: 700; margin-bottom: .2rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .card-artist { font-size: .75rem; color: var(--muted); margin-bottom: .75rem; }
    .card-actions { display: flex; gap: .5rem; flex-wrap: wrap; }

    /* SERVICES */
    .services-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.25rem; }
    .service-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.5rem; }
    .service-card h3 { font-size: 1.1rem; margin-bottom: .5rem; }
    .service-card p { color: var(--muted); font-size: .9rem; margin-bottom: 1rem; }
    .price { font-size: 1.3rem; font-weight: 800; color: var(--accent2); margin-bottom: .75rem; }
    .service-card ul { list-style: none; }
    .service-card li::before { content: "✓ "; color: var(--green); }
    .service-card li { font-size: .85rem; color: var(--muted); margin-bottom: .3rem; }

    /* FOOTER */
    footer { text-align: center; padding: 2rem; color: var(--muted); font-size: .85rem;
             border-top: 1px solid var(--border); margin-top: 4rem; }
    footer a { color: var(--accent2); text-decoration: none; }
  </style>
</head>
<body>

<nav>
  <span class="nav-logo">jinx3</span>
  <div class="nav-links">
    <a href="#catalog">Catalog</a>
    <a href="music.html">Music</a>
    <a href="#services">Services</a>
    <a href="studio.html">Studio</a>
    <a href="admin.html">Admin</a>
  </div>
</nav>

<section class="hero">
  <h1>Guice Atkinson<br>/ jinx3</h1>
  <p>Independent artist · producer · sovereign digital distribution</p>
  <div class="hero-cta">
    <a href="#catalog" class="btn btn-primary">Browse Catalog</a>
    <a href="music.html" class="btn btn-ghost">Stream Music</a>
  </div>
</section>

<div class="stats-bar">
  <div class="stat">
    <div class="stat-num" id="catalog-count">—</div>
    <div class="stat-label">Releases</div>
  </div>
  <div class="stat">
    <div class="stat-num" id="shopify-count">—</div>
    <div class="stat-label">Products</div>
  </div>
  <div class="stat">
    <div class="stat-num">∞</div>
    <div class="stat-label">Platforms</div>
  </div>
</div>

<main>
  <!-- CATALOG -->
  <section class="section" id="catalog">
    <div class="section-header">
      <h2 class="section-title">Music Catalog</h2>
      <div style="display:flex;gap:.75rem;align-items:center;flex-wrap:wrap;">
        <span class="catalog-count" id="catalog-label"></span>
        <input class="search-bar" id="catalog-search" type="search" placeholder="Search releases…" />
      </div>
    </div>
    <div class="catalog-grid" id="catalog-grid">
      <p style="color:var(--muted)">Loading catalog…</p>
    </div>
  </section>

  <!-- SERVICES -->
  <section class="section" id="services">
    <div class="section-header">
      <h2 class="section-title">Services</h2>
    </div>
    <div class="services-grid" id="service-cards">
      <p style="color:var(--muted)">Loading services…</p>
    </div>
  </section>
</main>

<footer>
  <p>© 2026 Guice Atkinson / jinx3 — All rights reserved.</p>
  <p style="margin-top:.5rem"><a href="https://distrokid.com/hyperfollow/jinx310" target="_blank">DistroKid</a> · <a href="admin.html">Admin</a></p>
</footer>

<script src="app.js"></script>
</body>
</html>
'''


def build_upgraded_storefront():
    """Write the upgraded index.html to the public folder."""
    OUTPUT_HTML.write_text(STOREFRONT_TEMPLATE, encoding="utf-8")
    print(f"[+] Upgraded storefront written to {OUTPUT_HTML}")


# ── Entry Point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="JINXMP3 Shopify Store Agent")
    parser.add_argument("--sync",        action="store_true", help="Sync catalog → Shopify products")
    parser.add_argument("--report",      action="store_true", help="Print store report")
    parser.add_argument("--build-front", action="store_true", help="Regenerate upgraded index.html")
    parser.add_argument("--all",         action="store_true", help="Run all tasks")
    args = parser.parse_args()

    if args.all or args.build_front:
        build_upgraded_storefront()
    if args.all or args.sync:
        sync_catalog_to_shopify()
    if args.all or args.report:
        print_store_report()

    if not any([args.sync, args.report, args.build_front, args.all]):
        parser.print_help()


if __name__ == "__main__":
    main()

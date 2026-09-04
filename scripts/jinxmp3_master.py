#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          JINXMP3 MASTER AUTOMATION ENGINE  v3.0                            ║
║          Guice Atkinson / jinx3 — Sovereign Local System Controller        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Single-program controller that unifies:
  1. Cloudflare Tunnel management (create / start / stop / status)
  2. Origin server management (Node.js server.js @ 127.0.0.1:8080)
  3. Catalog pipeline (generate-catalog.js → catalog.json)
  4. Shopify product sync (map catalog entries → Shopify products via Admin API)
  5. GitHub auto-commit & push
  6. System health monitor with NLP problem router
  7. Interactive CLI menu + headless mode (cron-friendly)

Usage:
  python jinxmp3_master.py                  # interactive menu
  python jinxmp3_master.py --task health    # headless health check
  python jinxmp3_master.py --task tunnel    # start tunnel
  python jinxmp3_master.py --task catalog   # regenerate catalog
  python jinxmp3_master.py --task shopify   # sync Shopify products
  python jinxmp3_master.py --task git       # commit & push
  python jinxmp3_master.py --task agent     # run AI store agent loop
  python jinxmp3_master.py --fix "problem"  # NLP auto-fix
"""

import os
import sys
import json
import time
import re
import subprocess
import threading
import argparse
import signal
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# ─────────────────────────────────────────────
# CONFIGURATION  (edit or set via .env)
# ─────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SITE_DIR = (SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR)
SITE_DIR = Path(os.getenv("JINX_SITE_DIR") or str(DEFAULT_SITE_DIR)).resolve()

DEFAULT_MUSIC_VAULTS = [
    os.getenv("JINX_MUSIC_DIR"),
    str(SITE_DIR / "public" / "releases"),
    str(Path.home() / "Music" / "Suno_DistroKid_Releases"),
    r"C:\Users\Jinx\Music\Suno_DistroKid_Releases",
    r"C:/Users/Jinx/Music/Suno_DistroKid_Releases",
]

MUSIC_VAULT = next(
    (Path(p) for p in DEFAULT_MUSIC_VAULTS if p and Path(p).exists()),
    Path(DEFAULT_MUSIC_VAULTS[1])
)
ORIGIN_URL      = os.getenv("JINX_ORIGIN_URL",      "http://127.0.0.1:8080")
TUNNEL_NAME     = os.getenv("JINX_TUNNEL_NAME",     "jinxmp3")
TUNNEL_HOSTNAME = os.getenv("JINX_TUNNEL_HOSTNAME", "www.jinxmp3.com")
CF_API_TOKEN    = os.getenv("CLOUDFLARE_API_TOKEN",  "")
CF_ZONE_ID      = os.getenv("CLOUDFLARE_ZONE_ID",    "")
SHOPIFY_STORE   = os.getenv("SHOPIFY_STORE_DOMAIN",  "")   # e.g. jinxmp3.myshopify.com
SHOPIFY_TOKEN   = os.getenv("SHOPIFY_ADMIN_TOKEN",   "")   # Admin API access token
OPENROUTER_KEY  = os.getenv("OPENROUTER_API_KEY",    "")
GIT_REMOTE      = os.getenv("JINX_GIT_REMOTE",       "origin")
GIT_BRANCH      = os.getenv("JINX_GIT_BRANCH",       "master")
LOG_FILE        = SITE_DIR / "logs" / "master.jsonl"

# ANSI colours
C = {
    "reset": "\033[0m",  "bold": "\033[1m",
    "green": "\033[92m", "yellow": "\033[93m",
    "red":   "\033[91m", "cyan":  "\033[96m",
    "blue":  "\033[94m", "magenta": "\033[95m",
}

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
def log(category: str, level: str, message: str, meta: dict = None):
    """Append a structured JSON line to master.jsonl and print to console."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "level": level,
        "message": message,
        **(meta or {}),
    }
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    colour = {"INFO": C["green"], "WARN": C["yellow"], "ERROR": C["red"]}.get(level, C["cyan"])
    ts = entry["timestamp"][11:19]
    print(f"{C['bold']}[{ts}]{C['reset']} {colour}[{category}/{level}]{C['reset']} {message}")


# ─────────────────────────────────────────────
# SHELL HELPER
# ─────────────────────────────────────────────
def run(cmd: str, cwd: Path = None, timeout: int = 60) -> tuple[bool, str]:
    """Run a shell command, return (success, output)."""
    try:
        res = subprocess.run(
            cmd, cwd=str(cwd or SITE_DIR),
            capture_output=True, text=True,
            shell=True, timeout=timeout
        )
        out = (res.stdout + res.stderr).strip()
        return res.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────
# 1. ORIGIN SERVER
# ─────────────────────────────────────────────
class OriginServer:
    """Manages the local Node.js origin server at 127.0.0.1:8080."""

    @staticmethod
    def is_alive() -> bool:
        try:
            req = urllib.request.urlopen(f"{ORIGIN_URL}/api/status", timeout=3)
            return req.status == 200
        except Exception:
            return False

    @staticmethod
    def start():
        log("ORIGIN", "INFO", "Starting Node.js origin server…")
        if OriginServer.is_alive():
            log("ORIGIN", "INFO", "Origin already running.")
            return True

        node_server = SITE_DIR / "server.js"
        try:
            if os.name == "nt":
                subprocess.Popen(
                    ["node", str(node_server)],
                    cwd=str(SITE_DIR),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                )
            else:
                subprocess.Popen(
                    ["node", str(node_server)],
                    cwd=str(SITE_DIR),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
        except Exception as exc:
            log("ORIGIN", "ERROR", f"Failed to launch origin server: {exc}")
            return False

        time.sleep(3)
        if OriginServer.is_alive():
            log("ORIGIN", "INFO", "Origin server started successfully.")
            return True
        log("ORIGIN", "ERROR", "Failed to start origin server.")
        return False

    @staticmethod
    def stop():
        log("ORIGIN", "INFO", "Stopping Node.js origin server…")
        if os.name == "nt":
            ok, out = run("taskkill /F /IM node.exe /T")
        else:
            ok, out = run("pkill -f 'node .*server.js' || true")
        log("ORIGIN", "INFO" if ok else "WARN", f"Stop result: {out}")
        return ok

    @staticmethod
    def status() -> dict:
        alive = OriginServer.is_alive()
        return {"alive": alive, "url": ORIGIN_URL}


# ─────────────────────────────────────────────
# 2. CLOUDFLARE TUNNEL
# ─────────────────────────────────────────────
class CloudflareTunnel:
    """Manages cloudflared tunnel lifecycle."""

    CONFIG_PATH = Path(os.path.expanduser("~")) / ".cloudflared" / "config.yml"

    @staticmethod
    def create_tunnel():
        """Create a new named tunnel via cloudflared CLI."""
        log("CONDUIT", "INFO", f"Creating Cloudflare tunnel '{TUNNEL_NAME}'…")
        ok, out = run(f"cloudflared tunnel create {TUNNEL_NAME}")
        if ok:
            log("CONDUIT", "INFO", f"Tunnel created: {out}")
        else:
            log("CONDUIT", "WARN", f"Tunnel create output: {out}")
        return ok, out

    @staticmethod
    def write_config(local_url: str = ORIGIN_URL):
        """Write ~/.cloudflared/config.yml for the tunnel."""
        # Get tunnel ID
        ok, out = run(f"cloudflared tunnel info {TUNNEL_NAME} --output json")
        tunnel_id = ""
        if ok:
            try:
                data = json.loads(out)
                tunnel_id = data.get("id", "")
            except Exception:
                pass

        cfg = f"""tunnel: {tunnel_id or TUNNEL_NAME}
credentials-file: {Path.home() / '.cloudflared' / (tunnel_id + '.json') if tunnel_id else '~/.cloudflared/credentials.json'}

ingress:
  - hostname: {TUNNEL_HOSTNAME}
    service: {local_url}
  - service: http_status:404
"""
        CloudflareTunnel.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CloudflareTunnel.CONFIG_PATH.write_text(cfg, encoding="utf-8")
        log("CONDUIT", "INFO", f"Config written to {CloudflareTunnel.CONFIG_PATH}")

    @staticmethod
    def add_dns_route():
        """Add CNAME DNS route for the tunnel hostname."""
        log("CONDUIT", "INFO", f"Adding DNS route {TUNNEL_HOSTNAME}…")
        ok, out = run(f"cloudflared tunnel route dns {TUNNEL_NAME} {TUNNEL_HOSTNAME}")
        log("CONDUIT", "INFO" if ok else "WARN", f"DNS route: {out}")
        return ok

    @staticmethod
    def start():
        """Start the tunnel (non-blocking background process)."""
        log("CONDUIT", "INFO", "Starting Cloudflare tunnel…")
        if not CloudflareTunnel.CONFIG_PATH.exists():
            log("CONDUIT", "WARN", "No config.yml found — writing default config.")
            CloudflareTunnel.write_config()
        cmd = [
            "cloudflared", "tunnel", "--config", str(CloudflareTunnel.CONFIG_PATH), "run", TUNNEL_NAME
        ]
        subprocess.Popen(cmd, cwd=str(SITE_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=(os.name != "nt"))
        time.sleep(2)
        log("CONDUIT", "INFO", "Tunnel process launched in background.")

    @staticmethod
    def stop():
        if os.name == "nt":
            ok, out = run("taskkill /F /IM cloudflared.exe /T")
        else:
            ok, out = run("pkill -f 'cloudflared.*tunnel' || true")
        log("CONDUIT", "INFO" if ok else "WARN", f"Tunnel stop: {out}")

    @staticmethod
    def status() -> dict:
        ok, out = run("cloudflared tunnel info " + TUNNEL_NAME)
        return {"running": ok, "info": out[:300] if out else ""}

    @staticmethod
    def full_setup():
        """One-shot: create tunnel + write config + add DNS + start."""
        log("CONDUIT", "INFO", "=== FULL TUNNEL SETUP SEQUENCE ===")
        CloudflareTunnel.create_tunnel()
        CloudflareTunnel.write_config()
        CloudflareTunnel.add_dns_route()
        OriginServer.start()
        CloudflareTunnel.start()
        log("CONDUIT", "INFO", "Full tunnel setup complete. www.jinxmp3.com should be live shortly.")


# ─────────────────────────────────────────────
# 3. CATALOG PIPELINE
# ─────────────────────────────────────────────
class CatalogPipeline:
    """Runs generate-catalog.js and validates catalog.json."""

    CATALOG_SCRIPT = SITE_DIR / "scripts" / "generate-catalog.js"
    CATALOG_JSON   = SITE_DIR / "public" / "catalog.json"

    @staticmethod
    def generate():
        log("CATALOG", "INFO", "Running catalog generation pipeline…")
        ok, out = run(f'node "{CatalogPipeline.CATALOG_SCRIPT}"', cwd=SITE_DIR)
        if ok:
            count = CatalogPipeline.count()
            log("CATALOG", "INFO", f"Catalog generated. {count} releases catalogued.", {"count": count})
        else:
            log("CATALOG", "ERROR", f"Catalog generation failed: {out}")
        return ok

    @staticmethod
    def count() -> int:
        try:
            data = json.loads(CatalogPipeline.CATALOG_JSON.read_text(encoding="utf-8"))
            return len(data)
        except Exception:
            return 0

    @staticmethod
    def load() -> list:
        try:
            return json.loads(CatalogPipeline.CATALOG_JSON.read_text(encoding="utf-8"))
        except Exception:
            return []

    @staticmethod
    def save(data: list):
        CatalogPipeline.CATALOG_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────
# 4. SHOPIFY INTEGRATION
# ─────────────────────────────────────────────
class ShopifyAgent:
    """
    Syncs catalog entries with Shopify products via the Admin REST API.
    Creates products for releases that have no shopifyProductId,
    and updates catalog.json with the returned product IDs.
    """

    BASE_URL = f"https://{SHOPIFY_STORE}/admin/api/2024-01"

    @staticmethod
    def _headers() -> dict:
        return {
            "X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _request(method: str, path: str, body: dict = None) -> tuple[int, dict]:
        url = f"{ShopifyAgent.BASE_URL}{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=ShopifyAgent._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
        except Exception as ex:
            return 0, {"error": str(ex)}

    @staticmethod
    def list_products(limit: int = 250) -> list:
        status, data = ShopifyAgent._request("GET", f"/products.json?limit={limit}")
        if status == 200:
            return data.get("products", [])
        log("SHOPIFY", "ERROR", f"Failed to list products: {data}")
        return []

    @staticmethod
    def create_product(release: dict) -> Optional[str]:
        """Create a Shopify product for a catalog release. Returns product ID."""
        product = {
            "product": {
                "title": release.get("title", "Untitled"),
                "body_html": f"<p>Digital release by <strong>{release.get('artist', 'jinx3')}</strong>. "
                             f"Produced by {release.get('producer', 'Guice Atkinson')}.</p>"
                             f"<p><a href='{release.get('hyperfollowUrl', '')}'>Stream on all platforms</a></p>",
                "vendor": release.get("artist", "jinx3"),
                "product_type": "Digital Music",
                "tags": "music, digital, wav, beat, jinx3",
                "variants": [
                    {
                        "title": "WAV Download",
                        "price": "4.99",
                        "sku": release.get("slug", ""),
                        "inventory_management": None,
                        "fulfillment_service": "manual",
                        "requires_shipping": False,
                        "taxable": True,
                    }
                ],
                "images": [{"src": f"https://{TUNNEL_HOSTNAME}{release.get('coverUrl', '')}"}]
                if release.get("coverUrl") else [],
            }
        }
        status, data = ShopifyAgent._request("POST", "/products.json", product)
        if status in (200, 201):
            pid = str(data["product"]["id"])
            log("SHOPIFY", "INFO", f"Created product '{release['title']}' → ID {pid}")
            return pid
        log("SHOPIFY", "ERROR", f"Failed to create '{release.get('title')}': {data}")
        return None

    @staticmethod
    def sync_catalog():
        """
        Main sync loop:
        1. Load catalog.json
        2. For every entry missing a shopifyProductId, create a Shopify product
        3. Write updated IDs back to catalog.json
        """
        if not SHOPIFY_STORE or not SHOPIFY_TOKEN:
            log("SHOPIFY", "WARN", "SHOPIFY_STORE_DOMAIN or SHOPIFY_ADMIN_TOKEN not set. Skipping sync.")
            return

        log("SHOPIFY", "INFO", "Starting Shopify catalog sync…")
        catalog = CatalogPipeline.load()
        updated = 0
        errors  = 0

        for i, entry in enumerate(catalog):
            if entry.get("shopifyProductId"):
                continue  # already synced
            pid = ShopifyAgent.create_product(entry)
            if pid:
                catalog[i]["shopifyProductId"] = pid
                updated += 1
            else:
                errors += 1
            time.sleep(0.5)  # respect Shopify rate limit (2 req/s)

        CatalogPipeline.save(catalog)
        log("SHOPIFY", "INFO", f"Sync complete. {updated} created, {errors} errors.", {"updated": updated, "errors": errors})

    @staticmethod
    def get_store_summary() -> dict:
        products = ShopifyAgent.list_products()
        return {
            "total_products": len(products),
            "titles": [p["title"] for p in products[:10]],
        }


# ─────────────────────────────────────────────
# 5. GITHUB AUTO-COMMIT
# ─────────────────────────────────────────────
class GitManager:
    """Auto-commit and push changes to GitHub."""

    @staticmethod
    def status() -> str:
        ok, out = run("git status --short", cwd=SITE_DIR)
        return out

    @staticmethod
    def commit_and_push(message: str = None):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        msg = message or f"chore: automated sync [{ts}]"
        log("GIT", "INFO", f"Committing with message: {msg}")
        run("git add -A", cwd=SITE_DIR)
        ok, out = run(f'git commit -m "{msg}"', cwd=SITE_DIR)
        if not ok and "nothing to commit" in out:
            log("GIT", "INFO", "Nothing to commit.")
            return True
        push_ok, push_out = run(f"git push {GIT_REMOTE} {GIT_BRANCH}", cwd=SITE_DIR)
        if push_ok:
            log("GIT", "INFO", "Pushed to GitHub successfully.")
        else:
            log("GIT", "ERROR", f"Push failed: {push_out}")
        return push_ok


# ─────────────────────────────────────────────
# 6. AI STORE AGENT
# ─────────────────────────────────────────────
class StoreAgent:
    """
    AI agent loop that manages the store:
    - Monitors health every 5 minutes
    - Auto-fixes issues via NLP routing
    - Syncs Shopify products when catalog changes
    - Commits changes to GitHub
    - Generates a daily store report
    """

    POLL_INTERVAL = int(os.getenv("AGENT_POLL_SECONDS", "300"))  # 5 min default
    _running = False

    @staticmethod
    def nlp_classify(problem: str) -> str:
        desc = problem.lower()
        matrix = {
            "CONDUIT":   [r"tunnel", r"cloudflare", r"dns", r"routing", r"502", r"504", r"530"],
            "CATALOG":   [r"catalog", r"release", r"distrokid", r"song", r"card", r"cover"],
            "ORIGIN":    [r"server", r"port 8080", r"localhost", r"127\.0\.0\.1", r"node", r"down"],
            "SHOPIFY":   [r"shopify", r"product", r"buy", r"checkout", r"store", r"payment"],
            "GIT":       [r"git", r"commit", r"push", r"github", r"sync"],
            "TELEMETRY": [r"log", r"audit", r"state", r"telemetry", r"checkpoint"],
        }
        scores = {cat: sum(len(re.findall(kw, desc)) for kw in kws) for cat, kws in matrix.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "GENERAL"

    @staticmethod
    def auto_fix(problem: str) -> bool:
        category = StoreAgent.nlp_classify(problem)
        log("AGENT", "INFO", f"NLP classified '{problem[:60]}' → {category}")
        if category == "CONDUIT":
            return CloudflareTunnel.full_setup() or True
        elif category == "CATALOG":
            return CatalogPipeline.generate()
        elif category == "ORIGIN":
            return OriginServer.start()
        elif category == "SHOPIFY":
            ShopifyAgent.sync_catalog()
            return True
        elif category == "GIT":
            return GitManager.commit_and_push()
        else:
            # Full stack check
            OriginServer.start()
            CatalogPipeline.generate()
            ShopifyAgent.sync_catalog()
            GitManager.commit_and_push()
            return True

    @staticmethod
    def health_check() -> dict:
        origin = OriginServer.status()
        catalog_count = CatalogPipeline.count()
        tunnel = CloudflareTunnel.status()
        git_status = GitManager.status()
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "origin": origin,
            "catalog_releases": catalog_count,
            "tunnel": tunnel,
            "git_dirty": bool(git_status.strip()),
        }
        log("AGENT", "INFO", "Health check complete.", report)
        return report

    @staticmethod
    def generate_report() -> str:
        hc = StoreAgent.health_check()
        shopify = ShopifyAgent.get_store_summary() if SHOPIFY_STORE and SHOPIFY_TOKEN else {"total_products": "N/A"}
        lines = [
            "=" * 60,
            f"  JINXMP3 DAILY STORE REPORT  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "=" * 60,
            f"  Origin server : {'✅ ONLINE' if hc['origin']['alive'] else '❌ OFFLINE'}",
            f"  Tunnel        : {'✅ RUNNING' if hc['tunnel']['running'] else '❌ DOWN'}",
            f"  Catalog       : {hc['catalog_releases']} releases",
            f"  Shopify prods : {shopify['total_products']}",
            f"  Git dirty     : {'YES — uncommitted changes' if hc['git_dirty'] else 'Clean'}",
            "=" * 60,
        ]
        report = "\n".join(lines)
        print(report)
        return report

    @classmethod
    def run_loop(cls):
        """Background agent loop — monitors and auto-fixes every POLL_INTERVAL seconds."""
        cls._running = True
        log("AGENT", "INFO", f"Store agent loop started. Poll interval: {cls.POLL_INTERVAL}s")
        while cls._running:
            try:
                hc = StoreAgent.health_check()
                if not hc["origin"]["alive"]:
                    StoreAgent.auto_fix("origin server down")
                if not hc["tunnel"]["running"]:
                    StoreAgent.auto_fix("tunnel down")
                if hc["git_dirty"]:
                    GitManager.commit_and_push()
            except Exception as e:
                log("AGENT", "ERROR", f"Agent loop error: {e}")
            time.sleep(cls.POLL_INTERVAL)

    @classmethod
    def stop(cls):
        cls._running = False
        log("AGENT", "INFO", "Store agent loop stopped.")


# ─────────────────────────────────────────────
# 7. INTERACTIVE CLI MENU
# ─────────────────────────────────────────────
MENU = """
╔══════════════════════════════════════════════════════╗
║         JINXMP3 MASTER CONTROL  v3.0                ║
╠══════════════════════════════════════════════════════╣
║  1  Health check & report                           ║
║  2  Start origin server (Node.js :8080)             ║
║  3  Stop origin server                              ║
║  4  Full Cloudflare tunnel setup (NEW tunnel)       ║
║  5  Start existing tunnel                           ║
║  6  Stop tunnel                                     ║
║  7  Regenerate music catalog                        ║
║  8  Sync Shopify products                           ║
║  9  Git commit & push                               ║
║  10 Start AI store agent loop (background)          ║
║  11 Stop AI store agent loop                        ║
║  12 NLP auto-fix (describe problem)                 ║
║  0  Exit                                            ║
╚══════════════════════════════════════════════════════╝
"""

def interactive_menu():
    agent_thread: Optional[threading.Thread] = None

    def handle_exit(sig, frame):
        StoreAgent.stop()
        print(f"\n{C['yellow']}Goodbye.{C['reset']}")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)

    while True:
        print(MENU)
        choice = input(f"{C['cyan']}Enter choice: {C['reset']}").strip()

        if choice == "1":
            StoreAgent.generate_report()

        elif choice == "2":
            OriginServer.start()

        elif choice == "3":
            OriginServer.stop()

        elif choice == "4":
            CloudflareTunnel.full_setup()

        elif choice == "5":
            OriginServer.start()
            CloudflareTunnel.start()

        elif choice == "6":
            CloudflareTunnel.stop()

        elif choice == "7":
            CatalogPipeline.generate()

        elif choice == "8":
            ShopifyAgent.sync_catalog()

        elif choice == "9":
            msg = input("Commit message (blank = auto): ").strip() or None
            GitManager.commit_and_push(msg)

        elif choice == "10":
            if agent_thread and agent_thread.is_alive():
                print(f"{C['yellow']}Agent already running.{C['reset']}")
            else:
                agent_thread = threading.Thread(target=StoreAgent.run_loop, daemon=True)
                agent_thread.start()
                print(f"{C['green']}Agent loop started in background.{C['reset']}")

        elif choice == "11":
            StoreAgent.stop()

        elif choice == "12":
            problem = input("Describe the problem: ").strip()
            StoreAgent.auto_fix(problem)

        elif choice == "0":
            handle_exit(None, None)

        else:
            print(f"{C['red']}Invalid choice.{C['reset']}")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="JINXMP3 Master Automation Engine")
    parser.add_argument("--task", choices=["health", "tunnel", "catalog", "shopify", "git", "agent", "report"],
                        help="Run a specific task headlessly")
    parser.add_argument("--fix", metavar="PROBLEM", help="NLP auto-fix for a described problem")
    args = parser.parse_args()

    if args.fix:
        StoreAgent.auto_fix(args.fix)
    elif args.task == "health":
        StoreAgent.generate_report()
    elif args.task == "tunnel":
        CloudflareTunnel.full_setup()
    elif args.task == "catalog":
        CatalogPipeline.generate()
    elif args.task == "shopify":
        ShopifyAgent.sync_catalog()
    elif args.task == "git":
        GitManager.commit_and_push()
    elif args.task == "agent":
        StoreAgent.run_loop()
    elif args.task == "report":
        StoreAgent.generate_report()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()

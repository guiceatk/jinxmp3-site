# JINXMP3 Master Automation Suite

**Guice Atkinson / jinx3 — Complete Local System Automation**

This suite unifies every moving part of the jinxmp3.com sovereign stack into two Python programs and one configuration file.

---

## Files

| File | Purpose |
|---|---|
| `jinxmp3_master.py` | **Master controller** — interactive menu + headless CLI for all subsystems |
| `shopify_store_agent.py` | **Shopify agent** — product sync, store report, upgraded storefront HTML |
| `build_music_product.py` | Validates audio, renders a 45-second preview, and creates a licensed ZIP bundle |
| `.env.example` | Environment variable template — copy to `.env` and fill in secrets |

---

## Quick Start

### 1. Install Python dependencies

```bash
pip install requests python-dotenv
```

### 2. Configure environment

```bash
copy .env.example .env
# Edit .env with your real Cloudflare, Shopify, and path values
```

### 3. Run the master controller

```bash
python jinxmp3_master.py
```

This opens the interactive menu:

```
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
```

---

## Headless / Cron Usage

Run specific tasks without the interactive menu:

```bash
# Full health check and report
python jinxmp3_master.py --task health

# Create new Cloudflare tunnel + DNS + start
python jinxmp3_master.py --task tunnel

# Regenerate catalog.json from music vault
python jinxmp3_master.py --task catalog

# Sync catalog → Shopify products
python jinxmp3_master.py --task shopify

# Git commit & push
python jinxmp3_master.py --task git

# Run the AI store agent loop (blocks — use in background)
python jinxmp3_master.py --task agent

# NLP auto-fix
python jinxmp3_master.py --fix "tunnel is down and site shows 530"
```

---

## Cloudflare Tunnel Setup (Step-by-Step)

This is the **complete sequence** to bring `www.jinxmp3.com` back online after deleting the old tunnel.

### Prerequisites

- `cloudflared` installed on your Windows machine
- `CLOUDFLARE_API_TOKEN` set in `.env` (Cloudflare Dashboard → My Profile → API Tokens → Create Token → Edit zone DNS)
- `CLOUDFLARE_ZONE_ID` set in `.env` (Cloudflare Dashboard → jinxmp3.com → Overview → Zone ID)

### Option A — Automated (recommended)

```bash
python jinxmp3_master.py --task tunnel
```

This runs the full sequence automatically:
1. `cloudflared tunnel create jinxmp3`
2. Writes `~/.cloudflared/config.yml`
3. `cloudflared tunnel route dns jinxmp3 www.jinxmp3.com`
4. Starts the Node.js origin server
5. Starts the cloudflared tunnel process

### Option B — Manual (if cloudflared is not on PATH)

```powershell
# Step 1: Create the tunnel
cloudflared tunnel create jinxmp3

# Step 2: Note the tunnel ID printed above, then write config.yml
# File: C:\Users\Jinx\.cloudflared\config.yml
# Content:
#   tunnel: <TUNNEL_ID>
#   credentials-file: C:\Users\Jinx\.cloudflared\<TUNNEL_ID>.json
#   ingress:
#     - hostname: www.jinxmp3.com
#       service: http://127.0.0.1:8080
#     - service: http_status:404

# Step 3: Add DNS route (auto-creates CNAME in Cloudflare)
cloudflared tunnel route dns jinxmp3 www.jinxmp3.com

# Step 4: Start origin server
cd C:\Users\Jinx\projects\jinxmp3-site
node server.js

# Step 5: Start tunnel (in a new terminal)
cloudflared tunnel run jinxmp3
```

### Verification

After completing setup, verify:
- `curl https://www.jinxmp3.com/api/status` should return `{"status":"online"}`
- Cloudflare Dashboard → jinxmp3.com → DNS should show a CNAME for `www` pointing to `<tunnel-id>.cfargotunnel.com`

---

## Shopify Integration

### Setup

1. Go to **Shopify Admin → Settings → Apps and sales channels → Develop apps**
2. Create an app named `jinxmp3-automation`
3. Under **Admin API access scopes**, enable:
   - `read_products`, `write_products`
   - `read_orders`
   - `read_inventory`, `write_inventory`
4. Install the app and copy the **Admin API access token** → paste into `.env` as `SHOPIFY_ADMIN_TOKEN`
5. Set `SHOPIFY_STORE_DOMAIN=jinxmp3.myshopify.com` in `.env`

### Sync catalog to Shopify

```bash
python shopify_store_agent.py --sync
```

This reads `catalog.json`, creates a Shopify product for every entry that does not yet have a `shopifyProductId`, and writes the IDs back to `catalog.json`. The buy buttons in `app.js` will automatically activate once the IDs are populated.

### Build upgraded storefront

```bash
python shopify_store_agent.py --build-front
```

Writes a fully upgraded `public/index.html` with:
- Dark gradient hero section
- Stats bar (release count, product count)
- Responsive catalog grid with play buttons
- Shopify buy button integration
- Services section
- Sticky navigation

### Run all Shopify tasks

```bash
python shopify_store_agent.py --all
```

## One-click product ingestion

Package a release without modifying the source vault:

```bash
python scripts/build_music_product.py <track-id>
python scripts/shopify_store_agent.py --sync
```

The package is written to `staging/products/<track-id>/`. Shopify sync only
creates drafts for verified bundles containing a companion cover and a master
audio file larger than 1 MB; publishing remains a manual approval step.

---

## GitHub Connector — Capabilities

The GitHub connector (already enabled in your Manus session) provides:

| Capability | What it does |
|---|---|
| **Repo listing** | `gh repo list` — lists all your repos with metadata |
| **Commit history** | `gh api repos/{owner}/{repo}/commits` — full commit log |
| **Branch management** | Create, list, delete branches |
| **Issue tracking** | Create, list, close issues and pull requests |
| **File operations** | Read/write files directly via the GitHub API |
| **Releases** | Create tagged releases with assets |
| **Webhooks** | Register webhooks for CI/CD triggers |
| **Actions** | Trigger and monitor GitHub Actions workflows |
| **Code search** | Search across your codebase |

**Your repos fetched live:**

| Repo | Visibility | Last Updated |
|---|---|---|
| `guiceatk/jinxmp3-site` | Public | 2026-08-07 |
| `guiceatk/ai-automation-workspace` | Private | 2026-08-07 |
| `guiceatk/media-automation-empire` | Public | 2026-06-11 |
| `guiceatk/chat` | Private | 2026-06-11 |

**Recent commits on `jinxmp3-site`:**

| SHA | Message | Date |
|---|---|---|
| `adf9b1e` | feat: integrate safe SymPy symbolic optimization | 2026-08-07 |
| `59877f4` | feat: implement complete Offline Recursive Engine | 2026-08-07 |
| `d6f03ee` | feat: add single-program NLP Orchestrator | 2026-08-07 |
| `857e6fd` | docs: Dual Parallel Processing & Hermeneutic Synthesis Model | 2026-08-07 |
| `2bc4ca1` | security: ensure .env files excluded from git | 2026-08-07 |

---

## AI Store Agent Loop

The agent loop (`--task agent` or menu option 10) runs every 5 minutes and:

1. Checks if the origin server is alive — restarts it if not
2. Checks if the Cloudflare tunnel is running — restarts it if not
3. Detects uncommitted git changes — auto-commits and pushes
4. Can be extended to: sync new catalog entries to Shopify, send alerts, generate daily reports

To run it as a Windows scheduled task:

```powershell
# Create a scheduled task that runs the agent every 5 minutes
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\Users\Jinx\projects\jinxmp3-site\jinxmp3_master.py --task agent"
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 5) -Once -At (Get-Date)
Register-ScheduledTask -TaskName "JINXMP3_Agent" -Action $action -Trigger $trigger -RunLevel Highest
```

---

## Architecture Overview

```
www.jinxmp3.com (Cloudflare DNS)
        │
        ▼
Cloudflare Tunnel (cloudflared)
        │
        ▼
127.0.0.1:8080 (Node.js server.js)
        │
        ├── /public/index.html    ← Upgraded storefront (shopify_store_agent.py)
        ├── /public/catalog.json  ← 447 releases (generate-catalog.js)
        ├── /api/status           ← Health endpoint
        ├── /api/microtask        ← AI micro-task scaffold
        └── /api/save-services    ← Services config endpoint
                │
                ▼
        Shopify Admin API
        (products, orders, inventory)
                │
                ▼
        GitHub (auto-commit via jinxmp3_master.py)
```

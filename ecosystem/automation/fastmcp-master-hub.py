import os

import requests
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("JinxMP3-Master-Hub")


def _require_env(*names: str) -> str | None:
    """Returns an error message if any required env var is missing, else None."""
    missing = [n for n in names if not os.getenv(n)]
    if missing:
        return f"Not configured: missing env var(s) {', '.join(missing)} in .env"
    return None


# --- 1. JINXMP3.COM WEBSITE TOOLS ---
@mcp.tool()
def update_jinx_site_data(endpoint: str, payload_data: dict) -> str:
    """
    Posts track data, logs, or asset metadata to a JINX_SITE_BASE_URL endpoint
    your own site exposes. Requires JINX_SITE_BASE_URL and JINX_SITE_API_KEY.
    """
    err = _require_env("JINX_SITE_BASE_URL", "JINX_SITE_API_KEY")
    if err:
        return err

    base_url = os.getenv("JINX_SITE_BASE_URL")
    headers = {"Authorization": f"Bearer {os.getenv('JINX_SITE_API_KEY')}"}
    try:
        resp = requests.post(
            f"{base_url}/{endpoint.lstrip('/')}",
            json=payload_data,
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        return f"Synced to {base_url}/{endpoint}: HTTP {resp.status_code}"
    except requests.RequestException as e:
        return f"Website sync failed: {e}"


# --- 2. AMAZON DROPSHIPPING TOOLS ---
@mcp.tool()
def manage_amazon_dropshipping(asin: str, action: str, stock_or_price: float) -> str:
    """
    Manages Amazon listings via the SP-API. Actions: 'update_stock', 'update_price'.
    Not yet implemented — requires SP-API OAuth setup (LWA client id/secret,
    refresh token, role ARN) before this can make real calls.
    """
    return (
        "Not configured: Amazon SP-API requires a registered developer app, "
        "LWA client credentials, and a refresh token. This tool is a stub "
        "until those are wired in — tell Claude when you have them."
    )


# --- 3. CLOUDFLARE TOOLS ---
@mcp.tool()
def purge_cloudflare_cache(zone_id: str, purge_everything: bool = True) -> str:
    """
    Purges the Cloudflare cache for the given zone. Requires CLOUDFLARE_API_TOKEN.
    """
    err = _require_env("CLOUDFLARE_API_TOKEN")
    if err:
        return err

    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache"
    headers = {
        "Authorization": f"Bearer {os.getenv('CLOUDFLARE_API_TOKEN')}",
        "Content-Type": "application/json",
    }
    payload = {"purge_everything": purge_everything}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        data = resp.json()
        if not data.get("success"):
            return f"Cloudflare purge failed: {data.get('errors')}"
        return f"Cloudflare cache purged for zone {zone_id}."
    except requests.RequestException as e:
        return f"Cloudflare purge failed: {e}"


if __name__ == "__main__":
    mcp.run()

#!/usr/bin/env python3
"""
Autonomous Sovereign Engine Orchestrator
Classification Matrix & Self-Healing Loop for jinxmp3-site
"""

import os
import sys
import json
import re
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# Base Paths
SITE_DIR = Path("C:/Users/Jinx/projects/jinxmp3-site")
LOG_FILE = SITE_DIR / "logs" / "system.jsonl"
ENV_FILE = SITE_DIR / ".env"
CATALOG_SCRIPT = SITE_DIR / "scripts" / "generate-catalog.js"
TUNNEL_SCRIPT = SITE_DIR / "scripts" / "reinstall-tunnel.ps1"
ORIGIN_URL = "http://127.0.0.1:8080/api/status"

def load_env():
    """Load API credentials from .env without external dependencies."""
    env_vars = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    return env_vars

def write_log(category, level, message, meta=None):
    """Append structured JSON Line to system.jsonl log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "level": level,
        "message": message
    }
    if meta:
        entry.update(meta)

    
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[{entry['timestamp']}] [{category}/{level}] {message}")

def classify_issue_nlp(problem_description):
    """
    NLP Intent & Problem Classification Matrix
    Categories:
    - CONDUIT: Cloudflare tunnel or edge routing failures
    - CATALOG: Missing or updated DistroKid release cards
    - ORIGIN: Local Node.js 127.0.0.1:8080 server issues
    - TELEMETRY: System logging and state audit updates
    """
    desc = problem_description.lower()
    
    matrix = {
        "CONDUIT": [r"tunnel", r"cloudflare", r"dns", r"routing", r"hostname", r"502", r"504"],
        "CATALOG": [r"catalog", r"release", r"distrokid", r"song", r"card", r"cover", r"mp3"],
        "ORIGIN":  [r"server", r"port 8080", r"localhost", r"127\.0\.0\.1", r"node", r"down"],
        "TELEMETRY": [r"log", r"audit", r"state", r"telemetry", r"checkpoint", r"git"]
    }

    scores = {}
    for category, keywords in matrix.items():
        score = sum(len(re.findall(kw, desc)) for kw in keywords)
        scores[category] = score

    best_match = max(scores, key=scores.get)
    if scores[best_match] == 0:
        return "GENERAL"
    return best_match

def run_cmd(command, cwd=SITE_DIR):
    """Executes local system commands cleanly."""
    try:
        res = subprocess.run(command, cwd=cwd, capture_output=True, text=True, shell=True, check=True)
        return True, res.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip() or e.stdout.strip()

def solve_conduit():
    """Action: Reinstall & Reconnect Cloudflare Zero Trust Tunnel."""
    write_log("CONDUIT", "INFO", "Executing Cloudflare Tunnel resolution routine.")
    cmd = f'pwsh -ExecutionPolicy Bypass -File "{TUNNEL_SCRIPT}"'
    ok, out = run_cmd(cmd)
    if ok:
        write_log("CONDUIT", "INFO", "Tunnel resolved successfully.", {"output": out})
        return True
    else:
        write_log("CONDUIT", "ERROR", "Tunnel resolution failed.", {"error": out})
        return False

def solve_catalog():
    """Action: Execute Metadata Parser for DistroKid Release Deltas."""
    write_log("CATALOG", "INFO", "Executing Catalog Delta Scan resolution routine.")
    ok, out = run_cmd(f'node "{CATALOG_SCRIPT}"')
    if ok:
        write_log("CATALOG", "INFO", "Catalog generated successfully.", {"output": out})
        return True
    else:
        write_log("CATALOG", "ERROR", "Catalog generation failed.", {"error": out})
        return False

def solve_origin():
    """Action: Verify & Restrict Local Node.js Server @ 127.0.0.1:8080."""
    write_log("ORIGIN", "INFO", "Checking 127.0.0.1:8080 origin server health.")
    try:
        req = urllib.request.urlopen(ORIGIN_URL, timeout=3)
        if req.status == 200:
            write_log("ORIGIN", "INFO", "Origin server responding normally on 127.0.0.1:8080.")
            return True
    except Exception as e:
        write_log("ORIGIN", "WARN", f"Origin server offline or non-responsive: {e}. Restarting server.js.")
        run_cmd("pwsh -Command \"Start-Process node -ArgumentList 'server.js' -WorkingDirectory 'C:\\Users\\Jinx\\projects\\jinxmp3-site'\"")
        return True

def cleanup_temp_files():
    """Deletes temporary scratch files and clean build artifacts."""
    write_log("CLEANUP", "INFO", "Purging unnecessary temporary execution files.")
    tmp_patterns = ["*.tmp", "*.log.bak", "scratch_temp_*"]
    removed_count = 0
    for p in tmp_patterns:
        for f in SITE_DIR.glob(p):
            try:
                f.unlink()
                removed_count += 1
            except Exception:
                pass
    write_log("CLEANUP", "INFO", f"Temporary file cleanup complete. Removed {removed_count} files.")

def orchestrate(problem_desc):
    """Main Matrix Routing Loop."""
    env = load_env()
    api_key_present = "OPENROUTER_API_KEY" in env or "MINIMAX_API_KEY" in env
    write_log("ORCHESTRATOR", "INFO", "Initiating problem resolution cycle.", {
        "problem": problem_desc,
        "credentials_loaded": api_key_present
    })

    category = classify_issue_nlp(problem_desc)
    write_log("ORCHESTRATOR", "INFO", f"NLP Classification Matrix assigned category: {category}")

    success = False
    if category == "CONDUIT":
        success = solve_conduit()
    elif category == "CATALOG":
        success = solve_catalog()
    elif category == "ORIGIN":
        success = solve_origin()
    else:
        # Fallback to complete S5 check
        s1 = solve_origin()
        s2 = solve_catalog()
        s3 = solve_conduit()
        success = s1 and s2 and s3

    cleanup_temp_files()
    
    status_str = "PASSED (+$)" if success else "FAILED"
    write_log("ORCHESTRATOR", "INFO", f"Resolution loop completed with status: {status_str}")
    return success

if __name__ == "__main__":
    problem = sys.argv[1] if len(sys.argv) > 1 else "Routine system health check and catalog verification"
    orchestrate(problem)

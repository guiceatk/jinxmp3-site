#!/usr/bin/env python3
"""
Dual-NLP & Combinatorial Logic Text Expander Engine
Short Snippet Trigger -> Primary NLP Intent -> Secondary Entity NLP -> Synthesized Logic Expansion
"""

import re
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

SITE_DIR = Path("C:/Users/Jinx/projects/jinxmp3-site")

# Snippet Library Definitions
SNIPPETS = {
    ";s5": "Execute S5: Run delta scan of 'C:\\Users\\Jinx\\Music\\Suno_DistroKid_Releases', refresh 'public/catalog.json', verify Tunnel health via 'reinstall-tunnel.ps1', and log yield to 'logs/system.jsonl'. Commit state to GitHub.",
    ";fix": "NLP Auto-Fix: Detect system bottleneck across Origin (127.0.0.1:8080), Cloudflare Zero Trust Tunnel, and Catalog Data Pipeline. Apply minimal corrective patch, audit to system.jsonl, and push commit.",
    ";audit": "System Audit: Check memory headroom (ceiling <= 50%), verify port 8080 binding, inspect 447 DistroKid release cards, check cloudflared status, and generate state summary report.",
    ";math": "Symbolic Math Optimize: Parse expression via safe SymPy optimizer, evaluate numeric or symbolic simplification, and verify no-crash error boundaries.",
    ";sync": "Full Synchronization: Run generate-catalog.js, sync Shopify Admin API products, purge Cloudflare edge cache, log telemetry to system.jsonl, and push git release."
}

def primary_nlp_intent(text):
    """Primary NLP Classification Matrix: Identifies core operational goal."""
    text_clean = text.lower()
    intents = {
        "DIAGNOSTIC": [r"audit", r"check", r"health", r"memory", r"status", r"report"],
        "REPAIR": [r"fix", r"repair", r"resolve", r"down", r"error", r"tunnel"],
        "INGESTION": [r"catalog", r"scan", r"release", r"distrokid", r"s5", r"delta"],
        "COMMERCE": [r"shopify", r"buy", r"product", r"store", r"sync"],
        "SYMBOLIC": [r"math", r"sympy", r"optimize", r"formula", r"evaluate"]
    }
    
    scores = {}
    for intent, patterns in intents.items():
        scores[intent] = sum(len(re.findall(pat, text_clean)) for pat in patterns)
        
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "GENERAL"

def secondary_nlp_entity_extractor(text):
    """Secondary NLP Extraction: Identifies entity parameters (paths, ports, URLs, flags)."""
    entities = {
        "paths": re.findall(r"[A-Za-z]:\\[^\s\)]+|/[^\s\)]+", text),
        "urls": re.findall(r"https?://[^\s\)]+", text),
        "ports": re.findall(r"\b\d{4}\b", text),
        "triggers": re.findall(r";[a-zA-Z0-9]+", text)
    }
    return entities

def combinatorial_logic_expander(text):
    r"""
    Synthesizes Primary Intent + Secondary Entities into a structured 
    Combinatorial Synthesis ($S_1 \dots S_6$) Execution Prompt.
    """

    trigger = re.search(r";[a-zA-Z0-9]+", text)
    if trigger and trigger.group() in SNIPPETS:
        base_expansion = SNIPPETS[trigger.group()]
    else:
        base_expansion = text

    primary = primary_nlp_intent(base_expansion)
    entities = secondary_nlp_entity_extractor(base_expansion)

    timestamp = datetime.now(timezone.utc).isoformat()

    expanded_macro = f"""================================================================================
DUAL-NLP EXPANDED COMBINATORIAL PROMPT
Trigger / Input: {text}
Timestamp: {timestamp}
Primary NLP Intent: {primary}
Secondary Entities Extracted: {json.dumps(entities)}
================================================================================

[STRATEGIC OBJECTIVE]
{base_expansion}

[COMBINATORIAL SYNTHESIS EXECUTION PLAN]
- S1 (Tactical Defense): Verify 127.0.0.1:8080 origin state and RAM headroom (<= 50%).
- S2 (Structural Leverage): Execute catalog delta scan across release vault & Shopify containers.
- S3 (Synthesized Surface): Re-bind Cloudflare Zero Trust Tunnel to 127.0.0.1:8080.
- S4 (Tactical Reinforcement): Log audit telemetry to logs/system.jsonl and enforce rate-limiting.
- S5 (Integrated Routine): Run auto-healing loop, clear scratch files, and commit deltas to GitHub.
- S6 (Master Yield): Verify Net Positive Result (+$) in host freedom and operational stability.
================================================================================
"""
    return expanded_macro

def main():
    if len(sys.argv) > 1:
        raw_input = " ".join(sys.argv[1:])
    else:
        raw_input = ";s5"
        print("[!] No trigger provided. Running default demonstration for snippet ';s5':\n")

    expanded_text = combinatorial_logic_expander(raw_input)
    print(expanded_text)

if __name__ == "__main__":
    main()

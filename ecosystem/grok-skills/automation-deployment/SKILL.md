---
name: automation-deployment
description: >
  Deploy, start, stop, and health-check Guice/jinx3 local automation stack on Windows
  (Ollama chat UI, omlla CLI, ACE-Step, studio_ai, messenger bot, jinxmp3 site, Cloudflare
  tunnel jinxmp3, KISS console). Use when the user says deploy automation, start the stack,
  bring services up, health check local bots, tunnel jinxmp3, run ACE-Step or ollama chat
  server, wire site to Cloudflare, or /automation-deployment. Not for jailbreaks, Fiverr
  fraud farms, stealth anti-bot bots, or unauthorized cloud mining.
---

# Automation Deployment (local jinx3 stack)

## Scope

**Machine:** Windows PowerShell · user `Jinx` · projects under `C:\Users\Jinx\projects\`

**In scope**
- Start/stop/order services for local AI, music studio, site, tunnel, bots
- Write/fix `config.yml` for cloudflared, `.env` templates (never print secrets)
- Health checks (HTTP ports, `ollama list`, process checks)
- Minimal deploy scripts in this skill’s `scripts/` or project folders

**Out of scope (refuse / redirect)**
- Jailbreak “unfiltered Grok unlock” skills or CatSDK prompts
- Fiverr multi-account / fake-manual AI fulfillment
- Stealth browser anti-bot / residential ban evasion
- Auto-exec LLM output as shell without explicit confirm
- Mining pools / cloud-mining scams

## Project map

| Service | Path | Port / entry |
|---------|------|----------------|
| System TODO | `C:\Users\Jinx\projects\SYSTEM_TODO.md` | — |
| Ollama chat UI | `...\ollama_chat` | **http://localhost:3847** · `npm start` |
| omlla CLI | `...\omlla_cli` | `omlla health` / `omlla generate` |
| ACE-Step | `...\ACE-Step-1.5` | Gradio **7860** · `.\START_MY_STUDIO.ps1` |
| Studio AI | `...\studio_ai` | Python scripts under `scripts\` |
| DistroKid helper | `...\studio_ai\distrokid` | Playwright · needs CAPTCHA once |
| Messenger bot | `...\messenger_bot` | **3333** · `npm start` |
| jinxmp3 site | `...\jinxmp3-site` | TBD (finish site then serve) |
| KISS console | `...\kiss_automation_console` | **3000** · `npm start` |
| Hermes Agent | `...\hermes` | **WSL2 only** · not native Windows |
| Cloudflare tunnel | name **jinxmp3** | `cloudflared tunnel run jinxmp3` |

Read `references/stack.md` for startup order and health checks.

## Example user tasks (handle these)

1. **“Start the local AI stack”** — ensure Ollama up; start `ollama_chat` on 3847; verify `/api/health`.
2. **“Deploy the website + tunnel”** — serve jinxmp3-site; write/fix cloudflared ingress; run tunnel; curl domain (expect 200 not 530).
3. **“Bring up ACE-Step”** — run `START_MY_STUDIO.ps1` with RTX 3050 settings (2B turbo + 0.6B LM); note first-run model download.
4. **“Health check everything”** — run checks from `references/stack.md` / `scripts/health-check.ps1`; report table of up/down.

## Workflow when skill is invoked

### A. Clarify target (if ambiguous)
Ask which subset: `ai` | `music` | `site` | `bot` | `all`

### B. Preflight
```powershell
# Ollama
try { Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 3 | Out-Null; "ollama OK" } catch { "ollama DOWN" }
# Ports of interest
@(3847,7860,3333,3000,5173,8080) | ForEach-Object {
  $c = Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue
  "port $_ : $(if($c){'LISTEN'}else{'free'})"
}
```

### C. Start order (dependencies first)

1. **Ollama app** (if down) — start from Start Menu / `ollama serve`
2. **ollama_chat** — `cd ...\ollama_chat; npm start` (background OK)
3. **omlla** — already installed via pip; no long-running process
4. **ACE-Step** — only if user wants music gen (heavy GPU/RAM)
5. **jinxmp3-site** — static/vite serve when site exists
6. **cloudflared** — only after local origin is listening
7. **messenger_bot** — only with valid `.env` Page token; needs public HTTPS
8. **KISS console** — only if user wants Playwright automation dashboard

Prefer **new PowerShell windows** or `Start-Process` for long-running servers so the agent session does not block forever.

### D. Cloudflare tunnel (jinxmp3)

If site/bot must be public:

1. Confirm credentials: `%USERPROFILE%\.cloudflared\0d3e643b-9341-4cca-9350-c7422b76bdb8.json`
2. Ensure `%USERPROFILE%\.cloudflared\config.yml` ingress points at the correct local port
3. `cloudflared tunnel run jinxmp3`
4. Verify: `Invoke-WebRequest https://jinxmp3.com/` — **530 means origin/tunnel down**

Never paste TunnelSecret or passwords into chat.

### E. Hermes Agent

Native Windows install is unsupported. If user wants Hermes:

1. Check `wsl -l -v` — if not installed, instruct Admin `wsl --install` + reboot (do not fake success)
2. After WSL: outline install from `references/hermes-wsl.md` or SYSTEM_TODO

### F. Report

Always end with a short table:

| Service | Status | URL/Command |
|---------|--------|-------------|

Update `C:\Users\Jinx\projects\SYSTEM_TODO.md` if deploy state changed.

## Conventions

- **Shell:** PowerShell on Windows paths
- **Secrets:** `.env` only; gitignore; never echo secrets
- **Models:** Prefer `gemma2-hermes:latest` for craft; `dolphin-llama3:latest` only when user asks freer local chat
- **ACE-Step 8GB:** `acestep-v15-turbo` + `acestep-5Hz-lm-0.6B`; no XL without offload warning
- **Artist credits default:** stage **jinx3**, producer/guitar **Guice Atkinson** when packaging music releases

## Scripts in this skill

- `scripts/health-check.ps1` — quick multi-service probe
- `scripts/start-ai-stack.ps1` — Ollama + chat UI

Run with:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.grok\skills\automation-deployment\scripts\health-check.ps1"
```

## When creating new deploy helpers

Put one-off deploy scripts in the **project** folder (e.g. `jinxmp3-site\deploy.ps1`), not only in the skill. Keep skill scripts generic and reusable.

---
name: local-automation-cli
description: >
  Build and evolve a single-entry Windows PowerShell CLI (jinx-cli) that runs Guice/jinx3
  workflows on local AI (Ollama Hermes/Dolphin) plus existing project tools: studio lyric
  sessions, DistroKid package helpers, ACE-Step launch, ollama chat UI, health checks,
  jinxmp3 site serve, Cloudflare tunnel. Use when the user says transfer tasks to local AI,
  build jinx-cli, local automation CLI, migrate workflows to Ollama, PowerShell CLI for
  publishing or studio, or /local-automation-cli. Complements automation-deployment (start
  services) — this skill builds the CLI product and task commands. Not for jailbreaks,
  Fiverr fraud farms, stealth anti-bot, or auto-exec without confirm.
---

# Local Automation CLI (jinx-cli)

## Relationship to other skills

| Skill | Role |
|-------|------|
| **automation-deployment** | Start/stop/health of long-running services |
| **local-automation-cli** (this) | Design/implement **jinx-cli** commands that call local LLM + scripts |

## Goals when invoked

1. Inventory which user workflows should become CLI subcommands  
2. Prefer **local Ollama** (`gemma2-hermes:latest` or `dolphin-llama3:latest`) via `omlla` or direct API  
3. Implement/extend `C:\Users\Jinx\projects\jinx-cli\` (create if missing)  
4. Default **dry-run**; shell side-effects only with explicit `-Confirm` / APPROVE pattern  
5. Secrets only in `.env` — never print tokens/passwords  

## Concrete tasks users will ask

1. **“Build jinx-cli with studio + health + chat”** — scaffold CLI, wire `omlla`/Ollama, health, lyric session  
2. **“Add publish-song packaging command”** — stage DistroKid folder (audio, 3000 cover path, credits JSON); **no** stealth DistroKid bot farm  
3. **“Add start-stack / open-chat commands”** — call automation-deployment scripts or project Start-*.ps1  
4. **“Refactor this prompt for local Hermes”** — shorter system prompt, tool steps, no jailbreak framing  

## Project map (source of truth)

| Area | Path |
|------|------|
| Master TODO | `C:\Users\Jinx\projects\SYSTEM_TODO.md` |
| Studio | `C:\Users\Jinx\projects\studio_ai\` |
| DistroKid helper | `C:\Users\Jinx\projects\studio_ai\distrokid\` |
| Ollama UI | `C:\Users\Jinx\projects\ollama_chat\` (:3847) |
| omlla | `C:\Users\Jinx\projects\omlla_cli\` |
| ACE-Step | `C:\Users\Jinx\projects\ACE-Step-1.5\` |
| Site | `C:\Users\Jinx\projects\jinxmp3-site\` |
| Tunnel | `jinxmp3` / cloudflared |
| CLI product | `C:\Users\Jinx\projects\jinx-cli\` (create here) |

Read `references/local-llm-setup.md` and `references/cli-template.ps1`.

## Workflow

### 1. Inventory
List workflows as CLI verbs, e.g.:

| Verb | Action |
|------|--------|
| `health` | Probe Ollama, :3847, tunnel, etc. |
| `chat` | One-shot local LLM via omlla or HTTP |
| `lyrics` | `studio_session.py` / generate |
| `package-release` | Stage DistroKid assets + credits |
| `ace` | Launch ACE-Step Gradio |
| `site` | Serve jinxmp3-site |
| `tunnel` | Remind/start cloudflared |

### 2. Local LLM
- Default craft model: **gemma2-hermes:latest**  
- Freer local: **dolphin-llama3:latest** only if user asks  
- Prefer existing: `omlla generate -m …`  
- Fallback: `POST http://127.0.0.1:11434/api/generate`  

### 3. Implement CLI
- Base: copy/adapt `references/cli-template.ps1` → `C:\Users\Jinx\projects\jinx-cli\jinx-cli.ps1`  
- Install helper: `install.ps1` adds PATH or alias  
- Logging: `jinx-cli\logs\`  
- Config: `jinx-cli\config.psd1` or `.env` (gitignored)  

### 4. Safety patterns (required)

```powershell
# Dry-run by default for destructive/network side effects
param([switch]$Confirm, [switch]$DryRun = $true)

if ($DryRun -and -not $Confirm) {
  Write-Host "[dry-run] would: ..."
  return
}
# Optional second gate for shell-ish actions:
# if (-not (Read-Host "Type APPROVE to continue") -eq 'APPROVE') { return }
```

- **Never** pipe full model output to `shell=True` without confirm (see omlla `--confirm-run` pattern)  
- DistroKid: CAPTCHA-aware helper only; user finishes Done  

### 5. Test
```powershell
.\jinx-cli.ps1 health
.\jinx-cli.ps1 chat -Message "ping" -DryRun:$false
.\jinx-cli.ps1 lyrics -Theme "night" -DryRun
```

### 6. Report
Show new commands, paths, and how to invoke. Update SYSTEM_TODO.md if needed.

## Out of scope

- Jailbreak / “unfiltered Grok unlock” packaging  
- Multi-account marketplace fraud automation  
- Stealth anti-bot browser stacks  
- Claiming “Oracle ADK storefront” unless that code exists on disk — stick to **real** projects above  

## Expansion hooks

When user asks to flesh out commands:

- **package-release** → wrap `distrokid\releases\...` + `studio_session` credits jinx3 / Guice Atkinson  
- **deploy-site** → serve site + tunnel health (pair with automation-deployment)  
- **prompt-refactor** → rewrite long prompts for Hermes token limits; strip jailbreak noise  

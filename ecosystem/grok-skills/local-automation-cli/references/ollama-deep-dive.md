# Ollama deep dive — jinx3 Windows stack (~15 GB RAM, RTX 3050 8 GB)

## Install (you already have Ollama)

```powershell
ollama --version
ollama list
# winget install Ollama.Ollama   # only if reinstalling
```

Prefer the **app running in background** over Docker on 15 GB RAM.

## Models that fit this machine

| Priority | Model | Use |
|----------|--------|-----|
| Primary craft | `gemma2-hermes:latest` | General + freer tone |
| Orchestration | `qwen2.5:7b` | Planning / structured steps |
| Custom | `jinx-local` | Modelfile over Hermes (see jinx-cli) |
| Freer chat | `dolphin-llama3:latest` | When user asks |
| Tiny | `llama3.2:1b` / `qwen2.5:0.5b` | Health / smoke only |

**Avoid on 15 GB:** 70B, XL music models + huge LLM at once.

```powershell
ollama pull qwen2.5:7b
ollama pull gemma2-hermes
```

## Custom agent model

```powershell
cd C:\Users\Jinx\projects\jinx-cli
ollama create jinx-local -f Modelfile.jinx
ollama run jinx-local "Plan a DistroKid package for one song in 4 steps"
```

## API modes jinx-cli supports

| Mode | Endpoint | When |
|------|----------|------|
| generate | `/api/generate` | Simple completion |
| chat | `/api/chat` | System + user (default) |
| openai | `/v1/chat/completions` | OpenAI-compatible clients |

Always `stream: false` in orchestration loops for reliability.

## Hybrid “escalate to Grok”

There is no automatic Grok 4.6 API from this skill. Pattern:

1. Local `plan` / `chat` first  
2. If user is unsatisfied → they paste into this Grok Build chat  
3. Never auto-upload secrets to cloud  

## GPU

RTX 3050 8 GB: Ollama will offload what fits. Don’t run ACE-Step Gradio + 14B chat simultaneously if VRAM errors appear.

## Windows service (optional later)

Only after daily use is stable:

- Task Scheduler: “At log on” → start Ollama  
- Or NSSM for `ollama serve`  

Not required for jinx-cli.

## Pair with automation-deployment

- **local-automation-cli** = jinx-cli commands + LLM  
- **automation-deployment** = start :3847, tunnel, health-check.ps1  

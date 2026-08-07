# Local LLM setup (Windows, ~15–16 GB RAM)

## Recommended stack (already on this machine)

| Tool | Role | Notes |
|------|------|--------|
| **Ollama** | Runtime | `http://127.0.0.1:11434` |
| **gemma2-hermes:latest** | Default craft model | Good default for CLI |
| **dolphin-llama3:latest** | Freer local chat | Heavier (~4.7 GB) |
| **llama3.2** | Fallback smaller | Fast |
| **omlla** | CLI to Ollama | `omlla generate/chat/health` |
| **ollama_chat** | Browser UI | http://localhost:3847 |

## Commands

```powershell
ollama list
omlla health
omlla generate -m gemma2-hermes:latest "Summarize in 3 bullets: ..."

cd C:\Users\Jinx\projects\ollama_chat
$env:OLLAMA_MODEL = "gemma2-hermes:latest"
npm start
```

## Other options (not required)

| Tool | When |
|------|------|
| LM Studio | GUI model browser; expose local OpenAI-compatible port |
| llama.cpp | Max control / custom GGUF |

## RAM tips (gaming PC)

- Prefer one heavy model loaded at a time  
- Close ACE-Step Gradio when only chatting  
- 8B-class models OK; 70B not realistic on 16 GB  

## jinx-cli integration

```powershell
cd C:\Users\Jinx\projects\jinx-cli
.\jinx-cli.ps1 health
.\jinx-cli.ps1 models
.\jinx-cli.ps1 chat -Message "ping"
.\jinx-cli.ps1 plan -Message "package one song for DistroKid"

# Optional custom model
ollama create jinx-local -f Modelfile.jinx
$env:LOCAL_LLM_MODEL = "jinx-local:latest"
```

See also: `references/ollama-deep-dive.md` and `C:\Users\Jinx\projects\jinx-cli\Invoke-LocalLlm.ps1`.

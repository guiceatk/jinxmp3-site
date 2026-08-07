# Local stack — startup order & health

## Startup order

```text
1. Ollama (11434)
2. ollama_chat (3847)     optional AI UI
3. jinxmp3-site (serve)   when site ready
4. cloudflared jinxmp3    after origin up
5. messenger_bot (3333)   needs token + public URL
6. ACE-Step (7860)        heavy; on demand
7. kiss console (3000)    on demand
```

## Health checks

| Check | Command / URL |
|-------|----------------|
| Ollama | `http://127.0.0.1:11434/api/tags` |
| Chat UI | `http://localhost:3847/api/health` |
| omlla | `omlla health` |
| ACE-Step | `http://127.0.0.1:7860` (after Gradio up) |
| Messenger | `http://localhost:3333/health` |
| KISS | `http://localhost:3000/` |
| Site tunnel | `https://jinxmp3.com/` (200 = good; 530 = origin/tunnel down) |

## RTX 3050 notes

- ACE-Step: 8GB VRAM → turbo 2B + LM 0.6B, CPU offload on
- Avoid XL 4B models without heavy offload

## WSL / Hermes

- Official Hermes Agent: install **inside WSL2** only
- Clone path on Windows: `C:\Users\Jinx\projects\hermes` → in WSL `/mnt/c/Users/Jinx/projects/hermes`
- Prefer re-clone under `~/hermes` in WSL for performance

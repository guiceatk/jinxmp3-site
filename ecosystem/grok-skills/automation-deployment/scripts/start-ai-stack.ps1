# Start Ollama (if needed) + ollama_chat UI on :3847
$ErrorActionPreference = "Continue"
$chat = "C:\Users\Jinx\projects\ollama_chat"

try {
  Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null
  Write-Host "Ollama: already up"
} catch {
  Write-Host "Starting Ollama..."
  $ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
  if (Test-Path $ollama) { Start-Process $ollama } else { Write-Host "Install Ollama from https://ollama.com" }
  Start-Sleep -Seconds 5
}

$listening = Get-NetTCPConnection -LocalPort 3847 -State Listen -ErrorAction SilentlyContinue
if ($listening) {
  Write-Host "Chat UI already on :3847"
} else {
  if (-not (Test-Path $chat)) { throw "Missing $chat" }
  Write-Host "Starting ollama_chat..."
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-ExecutionPolicy", "Bypass", "-Command",
    "cd '$chat'; if (-not (Test-Path node_modules)) { npm install }; `$env:OLLAMA_MODEL='gemma2-hermes:latest'; npm start"
  )
  Start-Sleep -Seconds 4
}

try {
  $h = Invoke-RestMethod "http://localhost:3847/api/health" -TimeoutSec 5
  Write-Host "Chat UI health: ok=$($h.ok) models=$($h.models.Count)"
  Write-Host "Open http://localhost:3847"
} catch {
  Write-Host "Chat UI not healthy yet: $_"
}

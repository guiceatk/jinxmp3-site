$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "public")
Write-Host "jinxmp3 site -> http://localhost:8080" -ForegroundColor Cyan
Write-Host "Then run Start-Tunnel.ps1 (APPROVE) to expose jinxmp3.com"
python -m http.server 8080

# Start site origin + Cloudflare tunnel (jinxmp3)
# Site must listen on 8080 (npm start in this folder).

$ErrorActionPreference = "Stop"
$SiteRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$config = Join-Path $env:USERPROFILE ".cloudflared\config.yml"

Write-Host "1) Ensure site is running: http://127.0.0.1:8080" -ForegroundColor Cyan
try {
  $null = Invoke-WebRequest "http://127.0.0.1:8080/" -UseBasicParsing -TimeoutSec 3
  Write-Host "   Origin OK" -ForegroundColor Green
} catch {
  Write-Host "   Origin DOWN — starting site in new window..." -ForegroundColor Yellow
  Start-Process powershell -ArgumentList "-NoExit -ExecutionPolicy Bypass -File `"$SiteRoot\Start-Site.ps1`""
  Start-Sleep -Seconds 5
}

Write-Host "2) Starting cloudflared tunnel jinxmp3..." -ForegroundColor Cyan
if (-not (Test-Path $config)) { throw "Missing $config" }

$ans = Read-Host "Type APPROVE to run production tunnel (fixes 530 when DNS is correct)"
if ($ans -ne "APPROVE") {
  Write-Host "Canceled."
  exit 0
}

cloudflared tunnel --config $config run jinxmp3

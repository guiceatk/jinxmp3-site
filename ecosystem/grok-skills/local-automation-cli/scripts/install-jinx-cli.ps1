# Install jinx-cli from skill template into projects\jinx-cli
$ErrorActionPreference = "Stop"
$skillRef = Join-Path $PSScriptRoot "..\references\cli-template.ps1"
$destDir = "C:\Users\Jinx\projects\jinx-cli"
$dest = Join-Path $destDir "jinx-cli.ps1"

New-Item -ItemType Directory -Force -Path $destDir, (Join-Path $destDir "logs") | Out-Null
Copy-Item $skillRef $dest -Force

$launcher = Join-Path $destDir "jinx.cmd"
@"
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0jinx-cli.ps1" %*
"@ | Set-Content $launcher -Encoding ASCII

Write-Host "Installed:"
Write-Host "  $dest"
Write-Host "  $launcher"
Write-Host ""
Write-Host "Try:"
Write-Host "  cd $destDir"
Write-Host "  .\jinx-cli.ps1 health"
Write-Host "  .\jinx-cli.ps1 chat -Message `"hello`""

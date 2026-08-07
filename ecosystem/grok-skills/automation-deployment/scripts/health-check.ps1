# Multi-service health probe for jinx3 local stack
$ErrorActionPreference = "Continue"

function Test-Http($name, $url) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 4
    [PSCustomObject]@{ Service = $name; Status = "UP"; Detail = "HTTP $($r.StatusCode)" }
  } catch {
    [PSCustomObject]@{ Service = $name; Status = "DOWN"; Detail = $_.Exception.Message.Split("`n")[0] }
  }
}

$rows = @()
$rows += Test-Http "Ollama" "http://127.0.0.1:11434/api/tags"
$rows += Test-Http "Ollama Chat UI" "http://localhost:3847/api/health"
$rows += Test-Http "Messenger bot" "http://localhost:3333/health"
$rows += Test-Http "KISS console" "http://localhost:3000/"
$rows += Test-Http "ACE-Step Gradio" "http://127.0.0.1:7860/"

try {
  $null = Get-Command omlla -ErrorAction Stop
  $h = omlla health 2>&1 | Out-String
  if ($h -match '"ok"\s*:\s*true') {
    $rows += [PSCustomObject]@{ Service = "omlla CLI"; Status = "UP"; Detail = "omlla health ok" }
  } else {
    $rows += [PSCustomObject]@{ Service = "omlla CLI"; Status = "DOWN"; Detail = $h.Trim().Substring(0, [Math]::Min(80, $h.Length)) }
  }
} catch {
  $rows += [PSCustomObject]@{ Service = "omlla CLI"; Status = "DOWN"; Detail = "not on PATH" }
}

$cf = Get-Process cloudflared -ErrorAction SilentlyContinue
$rows += [PSCustomObject]@{
  Service = "cloudflared"
  Status  = if ($cf) { "UP" } else { "DOWN" }
  Detail  = if ($cf) { "PID $($cf.Id -join ',')" } else { "not running" }
}

$rows | Format-Table -AutoSize
$rows | ConvertTo-Json | Set-Content -Path (Join-Path $PSScriptRoot "..\last-health.json") -Encoding utf8
Write-Host "Wrote last-health.json"

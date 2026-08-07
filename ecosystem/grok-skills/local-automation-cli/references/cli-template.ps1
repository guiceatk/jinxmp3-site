# jinx-cli — local automation (Ollama Hermes/Dolphin/Qwen)
[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [ValidateSet("help", "health", "models", "chat", "plan", "lyrics", "package-release", "ace", "site")]
  [string]$Command = "help",

  [Parameter(Position = 1)]
  [string]$ReleaseName = "",

  [string]$Message = "",
  [string]$Theme = "",
  [string]$TrackPath = "",
  [string]$Title = "",
  [string]$CoverPath = "",
  [string]$Model = "",
  [ValidateSet("generate", "chat", "openai")]
  [string]$LlmMode = "chat",
  [switch]$Confirm,
  [switch]$DryRun,
  [switch]$SkipLlm,
  [switch]$Approve
)

# -Approve is alias energy for -Confirm
if ($Approve) { $Confirm = $true }

$ErrorActionPreference = "Stop"
$Root = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
. (Join-Path $Root "Invoke-LocalLlm.ps1")
. (Join-Path $Root "commands\Package-Release.ps1")

if (-not $Model) { $Model = Get-DefaultModel }

$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("jinx-cli_{0:yyyyMMdd}.log" -f (Get-Date))

function Write-Log([string]$Text) {
  Add-Content -Path $LogFile -Value ("{0:o} {1}" -f (Get-Date), $Text)
  Write-Host $Text
}

function Test-DryRun { return ($DryRun -and -not $Confirm) }

function Cmd-Help {
  @"
jinx-cli — local automation (Hermes / Dolphin / Qwen via Ollama)

  health
  models
  chat -Message "..."
  plan -Message "..."
  lyrics -Theme "..." [-DryRun]
  package-release [ReleaseName] -TrackPath path -Title name [-CoverPath path] [-DryRun] [-Confirm|-Approve] [-SkipLlm]
  ace [-DryRun]
  site

Examples:
  .\jinx-cli.ps1 health
  .\jinx-cli.ps1 package-release "EmpireOfMud-Vol3" -DryRun
  .\jinx-cli.ps1 package-release "EmpireOfMud-Vol3" -TrackPath "...\track.mp3" -Confirm
  .\jinx-cli.ps1 chat -Message "ping" -Model gemma2-hermes:latest

env: LOCAL_LLM_MODEL, OLLAMA_HOST
"@ | Write-Host
}

function Cmd-Health {
  Write-Log "default model=$Model"
  foreach ($c in @(
      @{ n = "Ollama"; u = "$(Get-OllamaBase)/api/tags" },
      @{ n = "ChatUI"; u = "http://localhost:3847/api/health" },
      @{ n = "KISS"; u = "http://localhost:3000/" }
    )) {
    try {
      $null = Invoke-WebRequest -Uri $c.u -UseBasicParsing -TimeoutSec 3
      Write-Log "[UP]   $($c.n)"
    } catch { Write-Log "[DOWN] $($c.n)" }
  }
}

function Cmd-Models {
  (Invoke-RestMethod "$(Get-OllamaBase)/api/tags").models | ForEach-Object { $_.name }
}

function Cmd-Chat {
  if (-not $Message) { throw "need -Message" }
  Write-Log "chat model=$Model"
  (Invoke-LocalLlm -Prompt $Message -Model $Model -Mode $LlmMode).Text
}

function Cmd-Plan {
  if (-not $Message) { throw "need -Message" }
  (Invoke-LocalLlmPlan -Task $Message -Model $Model).Text
}

function Cmd-Lyrics {
  if (-not $Theme) { $Theme = "untitled" }
  $py = "C:\Users\Jinx\projects\studio_ai\scripts\studio_session.py"
  if (Test-DryRun) { Write-Log "[dry-run] python $py --theme $Theme"; return }
  python $py --theme $Theme --lines 12
}

function Cmd-Ace {
  $ps1 = "C:\Users\Jinx\projects\ACE-Step-1.5\START_MY_STUDIO.ps1"
  if (Test-DryRun) { Write-Log "[dry-run] $ps1"; return }
  if ((Read-Host "Type APPROVE to launch ACE-Step") -ne "APPROVE") { return }
  Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$ps1`""
}

function Cmd-Site {
  Write-Log "Site: C:\Users\Jinx\projects\jinxmp3-site"
  Write-Log "Tunnel: cloudflared tunnel run jinxmp3"
}

# package-release: positional ReleaseName can be title
if ($Command -eq "package-release") {
  if ($ReleaseName -and -not $Title) { $Title = $ReleaseName }
  Invoke-PackageRelease -Title $Title -TrackPath $TrackPath -CoverPath $CoverPath `
    -Model $Model -Confirm:$Confirm -DryRun:$DryRun -SkipLlm:$SkipLlm
  return
}

switch ($Command) {
  "help" { Cmd-Help }
  "health" { Cmd-Health }
  "models" { Cmd-Models }
  "chat" { Cmd-Chat }
  "plan" { Cmd-Plan }
  "lyrics" { Cmd-Lyrics }
  "ace" { Cmd-Ace }
  "site" { Cmd-Site }
  default { Cmd-Help }
}

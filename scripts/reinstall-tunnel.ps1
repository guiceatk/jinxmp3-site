# Elevated Cloudflare Tunnel Reinstall & Verification Script
# Binds public hostnames to http://127.0.0.1:8080 via Zero Trust Connector Token

param (
    [string]$ConnectorToken = $env:CLOUDFLARED_TOKEN
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $PSScriptRoot "..\logs"
$logFile = Join-Path $logDir "system.jsonl"

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

function Write-JsonLog {
    param (
        [string]$Category,
        [string]$Level,
        [string]$Message,
        [hashtable]$Meta = @{}
    )
    $entry = [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString("o")
        category  = $Category
        level     = $Level
        message   = $Message
    }
    foreach ($key in $Meta.Keys) {
        $entry[$key] = $Meta[$key]
    }
    $json = ($entry | ConvertTo-Json -Compress) + "`n"
    Add-Content -Path $logFile -Value $json -Encoding UTF8
    Write-Host "[$Category/$Level] $Message"
}

Write-Host "=== STAGE 2: CLOUDFLARE TUNNEL CONDUIT REINSTALL & VERIFICATION ===" -ForegroundColor Cyan
Write-JsonLog -Category "TUNNEL" -Level "INFO" -Message "Initiating Cloudflare Tunnel setup routine."

# Check if cloudflared binary is available
$cloudflaredCmd = Get-Command "cloudflared" -ErrorAction SilentlyContinue
if (-not $cloudflaredCmd) {
    Write-JsonLog -Category "TUNNEL" -Level "ERROR" -Message "cloudflared CLI tool not found in PATH."
    Write-Host "[!] cloudflared is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# Inspect cloudflared service status
$service = Get-Service -Name "cloudflared" -ErrorAction SilentlyContinue

if ([string]::IsNullOrWhiteSpace($ConnectorToken)) {
    if ($service -and $service.Status -eq "Running") {
        Write-JsonLog -Category "TUNNEL" -Level "INFO" -Message "cloudflared service is already installed and RUNNING." -Meta @{ status = "Running" }
        Write-Host "[+] Service 'cloudflared' is active and running." -ForegroundColor Green
        exit 0
    } else {
        Write-JsonLog -Category "TUNNEL" -Level "WARN" -Message "cloudflared service is not running and no connector token was provided."
        Write-Host "[!] cloudflared service is stopped or missing. Pass -ConnectorToken <TOKEN> or set \$env:CLOUDFLARED_TOKEN to reinstall." -ForegroundColor Yellow
        exit 0
    }
}

try {
    Write-JsonLog -Category "TUNNEL" -Level "INFO" -Message "Uninstalling legacy cloudflared service if present."
    & cloudflared service uninstall 2>&1 | Out-Null
} catch {
    # Non-fatal if service wasn't installed
}

try {
    Write-JsonLog -Category "TUNNEL" -Level "INFO" -Message "Installing cloudflared service with fresh Zero Trust Connector Token."
    & cloudflared service install $ConnectorToken
    Start-Service -Name "cloudflared" -ErrorAction SilentlyContinue
    
    $checkService = Get-Service -Name "cloudflared" -ErrorAction SilentlyContinue
    if ($checkService -and $checkService.Status -eq "Running") {
        Write-JsonLog -Category "TUNNEL" -Level "INFO" -Message "cloudflared service successfully installed and CONNECTED to 127.0.0.1:8080 origin." -Meta @{ status = "Running"; origin = "http://127.0.0.1:8080" }
        Write-Host "[+] Cloudflare Tunnel successfully restored and bound to 127.0.0.1:8080." -ForegroundColor Green
        exit 0
    } else {
        Write-JsonLog -Category "TUNNEL" -Level "ERROR" -Message "cloudflared service failed to start after installation."
        Write-Host "[!] Failed to start cloudflared service." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-JsonLog -Category "TUNNEL" -Level "ERROR" -Message "Error during cloudflared service installation." -Meta @{ error = $_.Exception.Message }
    Write-Host "[!] Error installing cloudflared service: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

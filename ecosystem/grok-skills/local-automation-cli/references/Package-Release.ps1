# Package-Release — stage DistroKid-ready folders for jinx3
# Dot-sourced by jinx-cli.ps1

function Get-DefaultModel {
  if ($env:LOCAL_LLM_MODEL) { return $env:LOCAL_LLM_MODEL }
  try {
    $tags = Invoke-RestMethod "$(Get-OllamaBase)/api/tags" -TimeoutSec 3
    $names = @($tags.models | ForEach-Object { $_.name })
    if ($names -contains "jinx-local:latest") { return "jinx-local:latest" }
    if ($names -contains "gemma2-hermes:latest") { return "gemma2-hermes:latest" }
    if ($names -match "dolphin-llama3") { return "dolphin-llama3:latest" }
    if ($names -match "qwen2.5:7b") { return ($names | Where-Object { $_ -match "qwen2.5:7b" } | Select-Object -First 1) }
  } catch { }
  return "gemma2-hermes:latest"
}

function New-ReleaseSlug([string]$Title) {
  $s = $Title.Trim() -replace '[^\w\s\-]', '' -replace '\s+', '_'
  if (-not $s) { $s = "release_{0:yyyyMMdd_HHmmss}" -f (Get-Date) }
  return $s
}

function Get-ReleasePlan {
  param(
    [string]$Title,
    [string]$TrackPath,
    [string]$CoverPath,
    [string]$OutDir,
    [string]$Model
  )
  $prompt = @"
Plan a DistroKid-style single release package. Output plain numbered steps only (max 10). No markdown fences.

Release title: $Title
Audio source: $TrackPath
Cover source: $(if($CoverPath){$CoverPath}else{'(none — flag as missing)'})
Output folder: $OutDir
Artist stage name: jinx3
Guitar credit: Guice Atkinson
Producer credit: Guice Atkinson

Include: metadata JSON fields, file naming, artwork 3000x3000 check, verification steps, DistroKid form notes.
"@
  try {
    $r = Invoke-LocalLlm -Prompt $prompt -Model $Model -Mode chat -Temperature 0.25 -System "You are jinx-local release planner. Concise numbered plans only. No shell commands that delete data."
    return $r.Text
  } catch {
    return @"
1. Create folder $OutDir
2. Copy audio to track.*
3. Copy/validate cover_3000.jpg if provided
4. Write release_info.json with jinx3 / Guice Atkinson credits
5. Write UPLOAD_NOTES.txt for DistroKid form
6. Verify files exist and sizes > 0
7. User runs DistroKid helper or uploads manually
"@
  }
}

function Invoke-PackageRelease {
  param(
    [string]$Title,
    [string]$TrackPath,
    [string]$CoverPath = "",
    [string]$Model = "",
    [switch]$Confirm,
    [switch]$DryRun,
    [switch]$SkipLlm
  )

  if (-not $Model) { $Model = Get-DefaultModel }
  if (-not $Title) { throw "package-release requires -Title (or release name)" }
  if (-not $TrackPath) {
    # default to existing empire pack track if present
    $fallback = "C:\Users\Jinx\projects\studio_ai\distrokid\releases\empire_of_mud_jinx3\track.mp3"
    if (Test-Path $fallback) {
      $TrackPath = $fallback
      Write-Host "Using default track: $TrackPath"
    } else {
      throw "package-release requires -TrackPath"
    }
  }
  if (-not (Test-Path -LiteralPath $TrackPath)) { throw "Track not found: $TrackPath" }

  $slug = New-ReleaseSlug $Title
  $releasesRoot = "C:\Users\Jinx\projects\studio_ai\distrokid\releases"
  $out = Join-Path $releasesRoot $slug
  $ext = [IO.Path]::GetExtension($TrackPath)
  if (-not $ext) { $ext = ".mp3" }

  if (-not $CoverPath) {
    $guess = Join-Path (Split-Path $TrackPath -Parent) "cover_3000.jpg"
    if (Test-Path $guess) { $CoverPath = $guess }
    $empireCover = "C:\Users\Jinx\projects\studio_ai\distrokid\releases\empire_of_mud_jinx3\cover_3000.jpg"
    if (-not $CoverPath -and (Test-Path $empireCover) -and $Title -match 'mud|empire') {
      $CoverPath = $empireCover
    }
  }

  Write-Host "=== package-release ===" -ForegroundColor Cyan
  Write-Host "Title : $Title"
  Write-Host "Track : $TrackPath"
  Write-Host "Cover : $(if($CoverPath){$CoverPath}else{'(missing)'})"
  Write-Host "Out   : $out"
  Write-Host "Model : $Model"
  Write-Host ""

  if (-not $SkipLlm) {
    Write-Host "--- LLM plan ($Model) ---" -ForegroundColor Yellow
    $plan = Get-ReleasePlan -Title $Title -TrackPath $TrackPath -CoverPath $CoverPath -OutDir $out -Model $Model
    Write-Host $plan
    Write-Host "-------------------------`n"
  }

  $actions = @(
    "Create $out",
    "Copy audio -> track$ext",
    $(if ($CoverPath) { "Copy cover -> cover_3000.jpg" } else { "WARN: no cover; user must add cover_3000.jpg" }),
    "Write release_info.json",
    "Write UPLOAD_NOTES.txt",
    "Write checklist.md"
  )
  Write-Host "File actions:" -ForegroundColor Cyan
  $i = 1
  foreach ($a in $actions) { Write-Host ("  {0}. {1}" -f $i, $a); $i++ }

  if ($DryRun -and -not $Confirm) {
    Write-Host "`n[dry-run] No files written. Re-run with -Confirm to execute." -ForegroundColor Green
    return [pscustomobject]@{ DryRun = $true; OutDir = $out; Title = $Title }
  }

  if (-not $Confirm) {
    $ans = Read-Host "Type APPROVE to write release files (anything else cancels)"
    if ($ans -ne "APPROVE") {
      Write-Host "Canceled."
      return $null
    }
  }

  New-Item -ItemType Directory -Force -Path $out | Out-Null
  $trackDest = Join-Path $out "track$ext"
  Copy-Item -LiteralPath $TrackPath -Destination $trackDest -Force

  $coverDest = $null
  $coverOk = $false
  if ($CoverPath -and (Test-Path -LiteralPath $CoverPath)) {
    $coverDest = Join-Path $out "cover_3000.jpg"
    Copy-Item -LiteralPath $CoverPath -Destination $coverDest -Force
    $coverOk = $true
    # optional dimension note via .NET if available
    try {
      Add-Type -AssemblyName System.Drawing -ErrorAction SilentlyContinue
      $img = [System.Drawing.Image]::FromFile($coverDest)
      $w = $img.Width; $h = $img.Height
      $img.Dispose()
      if ($w -ne 3000 -or $h -ne 3000) {
        Write-Host "WARN: cover is ${w}x${h} (DistroKid prefers 3000x3000)" -ForegroundColor Yellow
      }
    } catch { }
  }

  $meta = [ordered]@{
    title            = $Title
    artist           = "jinx3"
    guitar           = "Guice Atkinson"
    producer         = "Guice Atkinson"
    primary_genre    = ""
    language         = "English"
    explicit         = $false
    source_track     = $TrackPath
    staged_track     = $trackDest
    cover            = $coverDest
    cover_ok         = $coverOk
    staged_at        = (Get-Date).ToString("o")
    distrokid_notes  = "Set artist to jinx3; add Guice Atkinson as guitar + producer on Apple/iTunes credits if available."
  }
  $meta | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $out "release_info.json") -Encoding utf8

  $notes = @"
DistroKid upload notes — $Title
================================
Artist / stage name : jinx3
Track title         : $Title
Guitar              : Guice Atkinson
Producer            : Guice Atkinson

Files in this folder:
- track$ext
$(if($coverOk){"- cover_3000.jpg"}else{"- (ADD cover_3000.jpg - square 3000x3000 JPG)"})
- release_info.json
- checklist.md

Steps:
1. Log into DistroKid (CAPTCHA may be required)
2. New release → 1 song
3. Upload track + artwork
4. Enter credits above
5. Review stores + AI disclosure honestly if required
6. Submit only when you approve

Helper (optional):
  cd C:\Users\Jinx\projects\studio_ai\distrokid
  python upload_one_song.py --audio "$trackDest" --title "$Title" --artist "jinx3" --cover "$(if($coverDest){$coverDest}else{'PATH_TO_COVER'})" --producer "Guice Atkinson" --guitar "Guice Atkinson" --fresh-login
"@
  Set-Content (Join-Path $out "UPLOAD_NOTES.txt") -Value $notes -Encoding utf8

  $check = @"
# Checklist — $Title

- [ ] Audio sounds correct (play track$ext)
- [ ] Cover is square JPG ~3000x3000
- [ ] release_info.json credits correct
- [ ] DistroKid form matches jinx3 + Guice Atkinson
- [ ] Delivered / submitted
"@
  Set-Content (Join-Path $out "checklist.md") -Value $check -Encoding utf8

  Write-Host "`nStaged release:" -ForegroundColor Green
  Get-ChildItem $out | Format-Table Name, Length -AutoSize
  Write-Host "Folder: $out"
  return [pscustomobject]@{ DryRun = $false; OutDir = $out; Title = $Title; Track = $trackDest; Cover = $coverDest }
}

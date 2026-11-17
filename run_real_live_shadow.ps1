<#
.SYNOPSIS
  Live SHADOW run in a container with NO network, OUTSIDE Claude Code. MODE=SHADOW: everything is scored and recorded, nothing is shown to operators.
  Mounts the site folder (config\ read-only, data\, models\, reports\, incoming\ read-only) and prints ONLY file paths, never data values.
.PARAMETER SiteDir  Site folder with config\site.yaml, config\tag_map.yaml, incoming\*.csv (historian exports). data\, models\, reports\ are created.
.PARAMETER Image    Image built earlier (docker build -t heater-c-advisory:0.9 .) and loaded on this computer.
.PARAMETER CycleSeconds  Seconds between cycles (default 3600).
.PARAMETER Name     Container name.
DRAFT, REQUIRES SITE/OEM/EHS/MOC APPROVAL. Advisory only; the container has no network and no write path to any plant system.
#>
param(
  [Parameter(Mandatory = $true)][string]$SiteDir,
  [string]$Image = "heater-c-advisory:0.9",
  [int]$CycleSeconds = 3600,
  [string]$Name = "heater-c-shadow"
)
$ErrorActionPreference = "Stop"
$SiteDir = (Resolve-Path $SiteDir).Path
foreach ($d in "config", "data", "models", "reports", "incoming") { New-Item -ItemType Directory -Force -Path (Join-Path $SiteDir $d) | Out-Null }
if (-not (Test-Path (Join-Path $SiteDir "config\site.yaml"))) { Write-Output "REFUSED: missing $(Join-Path $SiteDir 'config\site.yaml')"; exit 2 }

docker rm -f $Name 2>$null | Out-Null
$id = docker run -d --name $Name --network none --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true --user 10001:10001 `
  -e MODE=SHADOW -e HEATER_SITE=/app/config/site.yaml -e CYCLE_SECONDS=$CycleSeconds `
  -v "$(Join-Path $SiteDir 'config'):/app/config:ro" -v "$(Join-Path $SiteDir 'data'):/app/data" -v "$(Join-Path $SiteDir 'models'):/app/models" `
  -v "$(Join-Path $SiteDir 'reports'):/app/reports" -v "$(Join-Path $SiteDir 'incoming'):/incoming:ro" `
  $Image sh /app/ops/shadow_loop.sh
if ($LASTEXITCODE -ne 0) { Write-Output "STEP FAILED: docker run (is the image '$Image' loaded?)"; exit $LASTEXITCODE }
Write-Output "started container: $Name (no network, MODE=SHADOW)"
Write-Output "outputs (files only): $(Join-Path $SiteDir 'reports\shadow_replay.csv')"
Write-Output "                      $(Join-Path $SiteDir 'reports\monitoring')"
Write-Output "stop with: docker rm -f $Name"

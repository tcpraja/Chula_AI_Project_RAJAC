<#
.SYNOPSIS
  Retrospective run on a historian CSV export, OUTSIDE Claude Code, on a site computer. Read-only.
  check_mapping -> ingest -> clean -> train -> shadow -> monitor -> M&V retrospective, all inside a working copy under OutDir.
  Prints ONLY file paths (never data values). All program output goes to log files in OutDir\logs.
.PARAMETER Site    Filled site config yaml (see config\site_template.yaml).
.PARAMETER Path    Historian CSV export.
.PARAMETER OutDir  Site output folder (created). Working copy: OutDir\workspace; logs: OutDir\logs.
.PARAMETER Python  Python 3.11 executable (default: .venv of this repository, else python).
DRAFT, REQUIRES SITE/OEM/EHS/MOC APPROVAL. Advisory only; no write path to any plant system.
#>
param(
  [Parameter(Mandatory = $true)][string]$Site,
  [Parameter(Mandatory = $true)][string]$Path,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [string]$Python = ""
)
$ErrorActionPreference = "Stop"
$Repo = $PSScriptRoot
if (-not $Python) {
  $venv = Join-Path $Repo ".venv\Scripts\python.exe"
  $Python = if (Test-Path $venv) { $venv } else { "python" }
}
$Site = (Resolve-Path $Site).Path
$Path = (Resolve-Path $Path).Path
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$Work = Join-Path $OutDir "workspace"
$Logs = Join-Path $OutDir "logs"
New-Item -ItemType Directory -Force -Path $Work, $Logs | Out-Null

# working copy of the code and config: the tool writes data\, models\, reports\ next to src\, so outputs land in the site folder
foreach ($d in "src", "config") {
  Copy-Item -Recurse -Force (Join-Path $Repo $d) $Work
}
Get-ChildItem -Recurse -Directory -Filter "__pycache__" $Work | Remove-Item -Recurse -Force
# reference files the tool reads (frozen model design, data dictionary, AI-energy table); generated outputs are written next to them
New-Item -ItemType Directory -Force -Path (Join-Path $Work "reports") | Out-Null
foreach ($f in "model_card.md", "03_data_dictionary.csv", "economics_summary.csv") {
  $src = Join-Path $Repo ("reports\" + $f)
  if (Test-Path $src) { Copy-Item -Force $src (Join-Path $Work "reports") }
}
$SiteDir = Split-Path $Site -Parent
$SiteCopy = Join-Path $Work "config\site.yaml"
Copy-Item -Force $Site $SiteCopy
foreach ($f in (Get-ChildItem $SiteDir -File -Filter "*.yaml")) { Copy-Item -Force $f.FullName (Join-Path $Work "config") }
foreach ($f in (Get-ChildItem $SiteDir -File -Filter "*.csv")) { if ($f.FullName -ne $Path) { Copy-Item -Force $f.FullName (Join-Path $Work "config") } }
Copy-Item -Force $Site $SiteCopy
$env:HEATER_SITE = $SiteCopy
$env:PYTHONPATH = $Work

$n = 0
function Invoke-Step([string]$Name, [string[]]$PyArgs) {
  $script:n++
  $log = Join-Path $Logs ("{0:D2}_{1}.log" -f $script:n, $Name)
  $p = Start-Process -FilePath $Python -ArgumentList ((@("-m") + $PyArgs) | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -WorkingDirectory $Work -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $log -RedirectStandardError ($log + ".err")
  if ($p.ExitCode -ne 0) {
    Write-Output "STEP FAILED: $Name (exit $($p.ExitCode)). See: $log and $log.err"
    exit $p.ExitCode
  }
  Write-Output "ok  $Name  -> $log"
}

Invoke-Step "check_mapping" @("src.adapters.check_mapping", "--site", $SiteCopy, "--path", $Path)
Invoke-Step "ingest" @("src.adapters.ingest", "--site", $SiteCopy, "--path", $Path, "--out", (Join-Path $Work "data\raw_site\raw.csv"))
Invoke-Step "clean" @("src.pipeline", "--stage", "clean", "--source", "csv", "--path", (Join-Path $Work "data\raw_site\raw.csv"), "--site", $SiteCopy)
Invoke-Step "train" @("src.pipeline", "--stage", "train")
Invoke-Step "shadow" @("src.pipeline", "--stage", "shadow")
Invoke-Step "monitor" @("src.monitor", "--quiet", "--out", (Join-Path $Work "reports\monitoring"))
Invoke-Step "mv_retrospective" @("src.mv_report", "--mode", "retrospective", "--path", (Join-Path $Work "data\clean\clean_heater_c.csv"), "--site", $SiteCopy,
                                 "--out", (Join-Path $Work "reports\mv"), "--quiet")

Write-Output "DONE. Outputs (files only):"
Write-Output "  $(Join-Path $Work 'reports\monitoring')"
Write-Output "  $(Join-Path $Work 'reports\mv\mv_retrospective.md')"
Write-Output "  $(Join-Path $Work 'reports\shadow_replay.csv')"
Write-Output "  $Logs"

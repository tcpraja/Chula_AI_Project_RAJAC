<#
.SYNOPSIS
  Measurement and verification, TRIAL mode, OUTSIDE Claude Code. Baseline vs trial windows, SFC normalised for load and moisture,
  comparable-load matching, 90 % bootstrap CI, fan penalty, AI kWh. A saving is reported only if the CI excludes 0.
  Optionally ingests and cleans a newer export first. Prints ONLY file paths, never data values.
.PARAMETER Site          Filled site config yaml; its mv: section may hold the four window dates.
.PARAMETER Workspace     Workspace created by run_real_retrospective.ps1 (OutDir\workspace).
.PARAMETER Path          Optional newer historian CSV export to ingest and clean into the workspace first.
.PARAMETER BaselineStart,BaselineEnd,TrialStart,TrialEnd   YYYY-MM-DD windows (override the site config).
.PARAMETER Python        Python 3.11 executable (default: .venv of this repository, else python).
Trial mode REFUSES to guess windows. DRAFT, REQUIRES SITE/OEM/EHS/MOC APPROVAL.
#>
param(
  [Parameter(Mandatory = $true)][string]$Site,
  [Parameter(Mandatory = $true)][string]$Workspace,
  [string]$Path = "",
  [string]$BaselineStart = "", [string]$BaselineEnd = "", [string]$TrialStart = "", [string]$TrialEnd = "",
  [string]$Python = ""
)
$ErrorActionPreference = "Stop"
$Repo = $PSScriptRoot
if (-not $Python) {
  $venv = Join-Path $Repo ".venv\Scripts\python.exe"
  $Python = if (Test-Path $venv) { $venv } else { "python" }
}
$Workspace = (Resolve-Path $Workspace).Path
$Site = (Resolve-Path $Site).Path
$Logs = Join-Path (Split-Path $Workspace -Parent) "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$SiteCopy = Join-Path $Workspace "config\site.yaml"
Copy-Item -Force $Site $SiteCopy
$env:HEATER_SITE = $SiteCopy
$env:PYTHONPATH = $Workspace

$n = 0
function Invoke-Step([string]$Name, [string[]]$PyArgs) {
  $script:n++
  $log = Join-Path $Logs ("mv{0:D2}_{1}.log" -f $script:n, $Name)
  $p = Start-Process -FilePath $Python -ArgumentList ((@("-m") + $PyArgs) | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -WorkingDirectory $Workspace -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $log -RedirectStandardError ($log + ".err")
  if ($p.ExitCode -ne 0) {
    Write-Output "STEP FAILED: $Name (exit $($p.ExitCode)). See: $log and $log.err"
    exit $p.ExitCode
  }
  Write-Output "ok  $Name  -> $log"
}

if ($Path) {
  $Path = (Resolve-Path $Path).Path
  Invoke-Step "check_mapping" @("src.adapters.check_mapping", "--site", $SiteCopy, "--path", $Path)
  Invoke-Step "ingest" @("src.adapters.ingest", "--site", $SiteCopy, "--path", $Path, "--out", (Join-Path $Workspace "data\raw_site\raw.csv"))
  Invoke-Step "clean" @("src.pipeline", "--stage", "clean", "--source", "csv", "--path", (Join-Path $Workspace "data\raw_site\raw.csv"), "--site", $SiteCopy)
}
$mvArgs = @("src.mv_report", "--mode", "trial", "--path", (Join-Path $Workspace "data\clean\clean_heater_c.csv"), "--site", $SiteCopy,
            "--out", (Join-Path $Workspace "reports\mv"), "--quiet")
if ($BaselineStart) { $mvArgs += @("--baseline-start", $BaselineStart) }
if ($BaselineEnd) { $mvArgs += @("--baseline-end", $BaselineEnd) }
if ($TrialStart) { $mvArgs += @("--trial-start", $TrialStart) }
if ($TrialEnd) { $mvArgs += @("--trial-end", $TrialEnd) }
Invoke-Step "mv_trial" $mvArgs
Write-Output "DONE. Report (file only): $(Join-Path $Workspace 'reports\mv\mv_trial.md')"

$Profiles = if ($env:R_FIGURE_PROFILES) { $env:R_FIGURE_PROFILES } else { "core,publication" }

$ErrorActionPreference = "Stop"

$InstallerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReportPath = Join-Path $InstallerDir "environment-windows.json"
$HelperPath = Join-Path $InstallerDir "check_r_environment.py"
if (-not (Test-Path $HelperPath)) {
    $SkillRoot = Split-Path -Parent (Split-Path -Parent $InstallerDir)
    $HelperPath = Join-Path $SkillRoot "scripts\check_r_environment.py"
}

$Python = Get-Command py -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $Python) {
    throw "Python 3 is required to run the environment checker. Install Python, then rerun this script."
}

if ($Python.Name -eq "py.exe" -or $Python.Name -eq "py") {
    & $Python.Source -3 $HelperPath `
        --profiles $Profiles `
        --install-r --install-missing --report $ReportPath
} else {
    & $Python.Source $HelperPath `
        --profiles $Profiles `
        --install-r --install-missing --report $ReportPath
}

Write-Host "R environment check complete: $ReportPath"

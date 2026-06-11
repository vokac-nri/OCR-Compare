# Tiny shim compiled into OCR-Compare.exe by tools\build_launcher.ps1.
# All launcher logic lives in bootstrap.ps1 next to the exe at the repo root,
# so logic changes never require recompiling. Keep this file dumb.
#
# The param block mirrors bootstrap.ps1: ps2exe only binds declared
# parameters (a bare @args stays empty inside a compiled exe).
param(
    [switch]$Recheck,
    [switch]$Reinstall,
    [ValidateSet('auto','gpu','cpu')][string]$Variant = 'auto',
    [switch]$NoLaunch,
    [switch]$NoPause
)

# Inside a ps2exe-compiled exe $PSScriptRoot is empty; the process's main
# module is the exe itself. When run as a plain script (testing), the main
# module is powershell/pwsh and $PSScriptRoot works - but we're in tools\, so
# the repo root is one level up.
$self = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
if ([System.IO.Path]::GetFileNameWithoutExtension($self) -match '^(powershell|pwsh)$') {
    $root = Split-Path -Parent $PSScriptRoot
} else {
    $root = Split-Path -Parent $self
}

$bootstrap = Join-Path $root "bootstrap.ps1"
if (-not (Test-Path $bootstrap)) {
    Write-Host "bootstrap.ps1 not found next to the launcher ($root)." -ForegroundColor Red
    Write-Host "OCR-Compare.exe must stay in the OCR-Compare repo folder." -ForegroundColor Red
    Read-Host "Press Enter to close" | Out-Null
    exit 1
}

# ps2exe rewrites PSModulePath for its embedded host; a child powershell.exe
# inherits that and loses cmdlet autoloading (Get-FileHash etc.). Drop the
# variable so the child rebuilds the default path.
Remove-Item Env:PSModulePath -ErrorAction SilentlyContinue

$forward = @()
if ($Recheck)            { $forward += "-Recheck" }
if ($Reinstall)          { $forward += "-Reinstall" }
if ($Variant -ne "auto") { $forward += @("-Variant", $Variant) }
if ($NoLaunch)           { $forward += "-NoLaunch" }
if ($NoPause)            { $forward += "-NoPause" }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bootstrap @forward
exit $LASTEXITCODE

# Compile tools\launcher_stub.ps1 into OCR-Compare.exe at the repo root.
# Re-run only when the stub changes - bootstrap.ps1 (where all the logic
# lives) is read at launch time, not baked into the exe.
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Get-Module -ListAvailable -Name ps2exe)) {
    Write-Host "Installing ps2exe module (CurrentUser scope, from PSGallery)..." -ForegroundColor Cyan
    # Bootstrap the NuGet provider explicitly: Install-Module otherwise prompts
    # for it and hangs in non-interactive Windows PowerShell.
    if (-not (Get-PackageProvider -Name NuGet -ListAvailable -ErrorAction SilentlyContinue)) {
        Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force -Scope CurrentUser | Out-Null
    }
    Install-Module ps2exe -Scope CurrentUser -Force -AllowClobber
}

$out = Join-Path $repoRoot "OCR-Compare.exe"
# Console app on purpose (no -noConsole): double-clicking opens a console so
# first-run install progress is visible and pause-on-failure keeps it open.
Invoke-ps2exe -inputFile (Join-Path $PSScriptRoot "launcher_stub.ps1") -outputFile $out `
    -title "OCR Compare" -description "One-click launcher for OCR Compare" `
    -company "CoreBTS" -version "1.0.0.0"

Write-Host "`nBuilt $out" -ForegroundColor Green
Write-Host "Note: the exe is unsigned - SmartScreen/AV may warn on first run." -ForegroundColor Yellow
Write-Host "Machines that block it can use Start-OCR-Compare.cmd instead." -ForegroundColor Yellow

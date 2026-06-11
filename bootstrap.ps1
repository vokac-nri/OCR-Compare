# One-click launcher for OCR Compare. Double-click OCR-Compare.exe or
# Start-OCR-Compare.cmd (both thin wrappers around this script), or run it
# directly.
#
# Every launch verifies the install and fixes only what is missing or at the
# wrong version, then starts the GUI:
#   - no conda anywhere      -> downloads Miniforge and installs it silently
#   - envs missing           -> full setup_env.ps1 (first run: 30-60 min, GBs)
#   - packages missing/wrong -> setup_env.ps1 -Repair (minutes)
#   - everything healthy     -> stamp fast path, app starts in ~2 s
#
# The fast path spawns no conda/pip/python at all: a stamp file records the
# SHA256 of the pinned manifests (requirements\ + environment.yml) from the
# last verified launch, and while it matches and the env interpreters still
# exist, checking is skipped entirely. Edit any manifest (or pass -Recheck)
# and the next launch re-verifies.
#
#   -Recheck        ignore the stamp; run the dependency checker now
#   -Reinstall      force a full setup_env.ps1 pass
#   -Variant        gpu|cpu wheel choice; auto (default) = NVIDIA detection,
#                   remembered in the stamp so it never flip-flops
#   -NoLaunch       verify/repair only, don't start the GUI
#   -NoPause        don't wait for Enter on failure (for scripted use)
#
# State + logs: %LOCALAPPDATA%\OCR-Compare\ (NOT the repo - the repo is
# OneDrive-synced and install state is machine-local). Delete
# launcher_state.json there to force a full re-check.
param(
    [switch]$Recheck,
    [switch]$Reinstall,
    [ValidateSet('auto','gpu','cpu')][string]$Variant = 'auto',
    [switch]$NoLaunch,
    [switch]$NoPause
)
$ErrorActionPreference = "Stop"
# Bump to invalidate every machine's stamp after launcher-logic changes.
$BootstrapVersion = 1

$root = $PSScriptRoot
$stateDir = Join-Path $env:LOCALAPPDATA "OCR-Compare"
$logDir = Join-Path $stateDir "logs"
$stampPath = Join-Path $stateDir "launcher_state.json"
New-Item -ItemType Directory -Force $logDir | Out-Null
try { $Host.UI.RawUI.WindowTitle = "OCR Compare - launcher" } catch {}

Start-Transcript -Path (Join-Path $logDir ("bootstrap-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date))) | Out-Null
Get-ChildItem $logDir -Filter "bootstrap-*.log" | Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 10 | Remove-Item -ErrorAction SilentlyContinue

function Get-ManifestHash {
    # Hash of every pin source + the launcher version: any edit invalidates
    # the stamp and the next launch re-verifies.
    $files = @(Get-ChildItem (Join-Path $root "requirements") -Recurse -File | Sort-Object FullName)
    $files += Get-Item (Join-Path $root "environment.yml")
    $concat = (($files | ForEach-Object { (Get-FileHash $_.FullName -Algorithm SHA256).Hash }) -join "|") + "|v$BootstrapVersion"
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return [System.BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($concat))).Replace("-", "") }
    finally { $sha.Dispose() }
}

function Get-DetectedVariant {
    try { & nvidia-smi -L *> $null; if ($LASTEXITCODE -eq 0) { return "gpu" } } catch {}
    try {
        if (Get-CimInstance Win32_VideoController -ErrorAction Stop | Where-Object { $_.Name -match "NVIDIA" }) { return "gpu" }
    } catch {}
    return "cpu"
}

function Invoke-CheckDeps([string]$envPython, [string]$envName, [string]$v, [string]$paddleV, [string[]]$extra) {
    # Write-Host keeps the checker's stdout out of the function's return value
    # (a bare native call would make the function return output + exit code).
    & $envPython (Join-Path $root "tools\check_deps.py") `
        --manifest-dir (Join-Path $root "requirements\$envName") `
        --variant $v --paddle-variant $paddleV @extra | ForEach-Object { Write-Host "  $_" }
    return $LASTEXITCODE
}

$exitCode = 0
try {
    $stamp = $null
    if (Test-Path $stampPath) {
        try { $stamp = Get-Content $stampPath -Raw | ConvertFrom-Json } catch { $stamp = $null }
    }
    $manifestHash = Get-ManifestHash

    # ---- fast path: stamp says this exact pin set was verified on this machine
    $fast = $false
    if ($stamp -and -not $Recheck -and -not $Reinstall -and
        $stamp.schema -eq 1 -and $stamp.manifest_hash -eq $manifestHash -and
        $stamp.envs.main -and (Test-Path $stamp.envs.main) -and
        $stamp.envs.paddle -and (Test-Path $stamp.envs.paddle)) {
        $mainPy = $stamp.envs.main
        $fast = $true
        Write-Host "Dependencies verified (cached) - starting OCR Compare..." -ForegroundColor Green
    }

    if (-not $fast) {
        # ---- conda
        . (Join-Path $root "tools\conda_locate.ps1")
        $conda = Find-CondaExe
        if (-not $conda) {
            Write-Host "No conda installation found - installing Miniforge (one-time)." -ForegroundColor Yellow
            $conda = Install-Miniforge
        }
        $condaRoot = Get-CondaRoot $conda
        $mainPy = Join-Path $condaRoot "envs\ocr-compare\python.exe"
        $paddlePy = Join-Path $condaRoot "envs\ocr-compare-paddle\python.exe"

        # ---- variant: explicit > stamped > detected
        if ($Variant -ne "auto") { $v = $Variant }
        elseif ($stamp -and $stamp.variant) { $v = $stamp.variant }
        else {
            $v = Get-DetectedVariant
            Write-Host "Hardware detection: $(if ($v -eq 'gpu') { 'NVIDIA GPU found - using CUDA wheels' } else { 'no NVIDIA GPU - using CPU wheels (PaddleOCR-VL will be impractically slow)' })" -ForegroundColor Cyan
        }
        $paddleV = $v
        if ($stamp -and $stamp.paddle_effective -and $Variant -eq "auto") { $paddleV = $stamp.paddle_effective }

        $setupRan = $false
        if ($Reinstall -or -not (Test-Path $mainPy)) {
            Write-Host "Environments missing or -Reinstall set: full setup (first run takes 30-60 min)..." -ForegroundColor Yellow
            & (Join-Path $root "setup_env.ps1") -Variant $v
            $setupRan = $true
        } else {
            Write-Host "Checking dependencies against pinned manifests..." -ForegroundColor Cyan
            $problems = Invoke-CheckDeps $mainPy "ocr-compare" $v $paddleV @("--require-sitecustomize", "--require-cli", "tesseract", "pdftotext")
            if ($problems -eq 0) {
                if (Test-Path $paddlePy) {
                    $problems = Invoke-CheckDeps $paddlePy "ocr-compare-paddle" $v $paddleV @("--require-sitecustomize")
                } else {
                    Write-Host "paddle env missing" -ForegroundColor Yellow
                    $problems = 1
                }
            }
            if ($problems -ne 0) {
                Write-Host "Found $problems problem(s) - repairing (only missing/outdated pieces are installed)..." -ForegroundColor Yellow
                & (Join-Path $root "setup_env.ps1") -Variant $v -Repair -PaddleVariant $paddleV
                $setupRan = $true
            }
        }

        if ($setupRan) {
            $result = Get-Content (Join-Path $stateDir "setup_result.json") -Raw | ConvertFrom-Json
            $paddleV = $result.paddle_effective
            # post-setup verification: both envs must now satisfy the manifests
            if ((Invoke-CheckDeps $mainPy "ocr-compare" $v $paddleV @("--require-sitecustomize", "--require-cli", "tesseract", "pdftotext")) -ne 0) {
                throw "ocr-compare env still fails the dependency check after setup - see output above"
            }
            if ((Invoke-CheckDeps $paddlePy "ocr-compare-paddle" $v $paddleV @("--require-sitecustomize")) -ne 0) {
                throw "ocr-compare-paddle env still fails the dependency check after setup - see output above"
            }
        }

        # ---- stamp this verified state
        @{
            schema           = 1
            bootstrap_version = $BootstrapVersion
            manifest_hash    = $manifestHash
            variant          = $v
            paddle_effective = $paddleV
            conda_root       = $condaRoot
            envs             = @{ main = $mainPy; paddle = $paddlePy }
            checked_at       = (Get-Date).ToString("o")
        } | ConvertTo-Json | Set-Content $stampPath -Encoding utf8
        Write-Host "Dependencies OK - starting OCR Compare..." -ForegroundColor Green
    }

    # ---- launch (direct python.exe, no `conda run` overhead; app/main.py's
    # ensure_conda_bin_on_path() fixes PATH/TESSDATA_PREFIX for the workers)
    if (-not $NoLaunch) {
        $env:PYTHONPATH = $root
        $envDir = Split-Path -Parent $mainPy
        $env:PATH = "$envDir\Library\bin;$envDir\Scripts;$envDir;" + $env:PATH
        Stop-Transcript | Out-Null
        & $mainPy -m app.main
        $exitCode = $LASTEXITCODE
    } else {
        Stop-Transcript | Out-Null
    }
} catch {
    $exitCode = 1
    Write-Host ""
    Write-Host "OCR Compare launcher failed:" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  Log: $logDir" -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch {}
    if (-not $NoPause) { Read-Host "Press Enter to close" | Out-Null }
}
exit $exitCode

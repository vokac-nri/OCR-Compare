# Shared conda discovery. Dot-source this file, then call Find-CondaExe /
# Get-CondaRoot / Install-Miniforge. Used by bootstrap.ps1, setup_env.ps1 and
# run_app.ps1 so the conda location is never hardcoded.

function Find-CondaExe {
    # CONDA_EXE is set by conda's own activation hooks; trust it first.
    if ($env:CONDA_EXE -and (Test-Path $env:CONDA_EXE)) { return $env:CONDA_EXE }
    $roots = @(
        (Join-Path $env:LOCALAPPDATA "miniconda3"),
        (Join-Path $env:LOCALAPPDATA "miniforge3"),
        (Join-Path $env:USERPROFILE  "miniconda3"),
        (Join-Path $env:USERPROFILE  "miniforge3")
    )
    foreach ($root in $roots) {
        $exe = Join-Path $root "Scripts\conda.exe"
        if (Test-Path $exe) { return $exe }
    }
    # PATH may expose conda.exe directly or the condabin\conda.bat shim.
    $cmd = Get-Command conda.exe, conda.bat -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) {
        $src = $cmd.Source
        if ($src -like "*.exe") { return $src }
        $exe = Join-Path (Split-Path -Parent (Split-Path -Parent $src)) "Scripts\conda.exe"
        if (Test-Path $exe) { return $exe }
    }
    return $null
}

function Get-CondaRoot([string]$CondaExe) {
    # <root>\Scripts\conda.exe -> <root>
    return Split-Path -Parent (Split-Path -Parent $CondaExe)
}

function Install-Miniforge {
    # Miniforge = conda preconfigured for conda-forge only; never touches the
    # ToS-gated repo.anaconda.com channels, so no .condarc surgery is needed.
    $url = "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe"
    $installer = Join-Path $env:TEMP "Miniforge3-Windows-x86_64.exe"
    $target = Join-Path $env:LOCALAPPDATA "miniforge3"
    Write-Host "Downloading Miniforge (~90 MB) from GitHub..." -ForegroundColor Cyan
    $prev = $ProgressPreference; $ProgressPreference = "SilentlyContinue"  # 10x faster Invoke-WebRequest
    try { Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing }
    finally { $ProgressPreference = $prev }
    Write-Host "Installing Miniforge to $target (silent, a few minutes)..." -ForegroundColor Cyan
    # NSIS: /D= must be LAST and UNQUOTED even with spaces in the path, so the
    # argument list is passed as one pre-joined string.
    $arguments = "/S /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /D=$target"
    $proc = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
    if ($proc.ExitCode -ne 0) { throw "Miniforge installer exited with code $($proc.ExitCode)" }
    Remove-Item $installer -ErrorAction SilentlyContinue
    $exe = Join-Path $target "Scripts\conda.exe"
    if (-not (Test-Path $exe)) { throw "Miniforge install finished but $exe not found" }
    return $exe
}

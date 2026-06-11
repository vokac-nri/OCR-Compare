# Reproducible setup for the ocr-compare conda environments (native Windows).
#
#   .\setup_env.ps1                # creates BOTH envs:
#     ocr-compare         - GUI + all engines except the paddle family
#                           (torch CUDA for easyocr/docling)
#     ocr-compare-paddle  - paddleocr / ppstructurev3 / paddleocr-vl
#                           (paddle CUDA + CPU-only torch)
#
# Normally invoked by bootstrap.ps1 (the one-click launcher), which decides the
# variant and whether a full install or a -Repair pass is needed. Run directly
# for manual/dev setup.
#
#   -Variant gpu|cpu   gpu (default): CUDA torch/paddle wheels.
#                      cpu: CPU-only wheels for machines without an NVIDIA GPU.
#   -Repair            skip conda env create/update; just (re)install from the
#                      pinned manifests under requirements\ — pip no-ops fast on
#                      already-satisfied stages, so this only fills real gaps.
#   -PaddleVariant     override the paddle wheel choice (bootstrap passes the
#                      stamped value on repair so a gpu->cpu run_check fallback
#                      isn't "repaired" back to gpu every time).
#
# Two envs because torch-GPU and paddle-GPU cannot coexist in one process on
# Windows: each bundles its own cudnn DLLs and whichever loads first shadows
# the other (WinError 127), and paddleocr imports BOTH (torch via modelscope).
# The paddle env's CPU torch exists only to satisfy that import. The app
# auto-routes paddle engines to the paddle env when it exists.
#
# Install order matters: torch first from its pinned index, then paddle from
# the PaddlePaddle index, then everything else from PyPI, so resolver
# backtracking never replaces the CUDA wheels with CPU ones. The order is
# encoded in the NN- prefixes of the manifest files.
param(
    [switch]$SkipPaddleEnv,
    [ValidateSet('gpu','cpu')][string]$Variant = 'gpu',
    [switch]$Repair,
    [ValidateSet('','gpu','cpu')][string]$PaddleVariant = ''
)
$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot

. (Join-Path $projectRoot "tools\conda_locate.ps1")
$conda = Find-CondaExe
if (-not $conda) { throw "conda not found. Run bootstrap.ps1 (installs Miniforge automatically) or install Miniconda/Miniforge." }
$condaRoot = Get-CondaRoot $conda
$envsDir = Join-Path $condaRoot "envs"

# State/logs live OUTSIDE the repo: the repo is OneDrive-synced and machine-
# local install state must not replicate to other machines.
$stateDir = Join-Path $env:LOCALAPPDATA "OCR-Compare"
New-Item -ItemType Directory -Force (Join-Path $stateDir "logs") | Out-Null
Start-Transcript -Path (Join-Path $stateDir ("logs\setup-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date))) | Out-Null

function Invoke-Conda { & $conda @args; if ($LASTEXITCODE -ne 0) { throw "conda $($args -join ' ') failed ($LASTEXITCODE)" } }
function Get-EnvPython([string]$envName) { Join-Path $envsDir "$envName\python.exe" }
function Invoke-Pip([string]$envName) {
    & (Get-EnvPython $envName) -m pip @($args | ForEach-Object { $_ })
    if ($LASTEXITCODE -ne 0) { throw "pip in $envName failed: $($args -join ' ')" }
}
function Install-Manifest([string]$envName, [string]$file) {
    Invoke-Pip $envName install -r (Join-Path $projectRoot "requirements\$envName\$file")
}

try {
    $mainPy = Get-EnvPython "ocr-compare"

    Write-Host "== [1/6] conda env from environment.yml ==" -ForegroundColor Cyan
    if ($Repair -and (Test-Path $mainPy)) {
        Write-Host "(repair mode: env exists, skipping conda create/update)" -ForegroundColor DarkGray
        # conda-forge pins (requirements\ocr-compare\conda.txt) are normally
        # satisfied by environment.yml; in repair mode verify them cheaply and
        # conda-install only what is actually broken (conda is slow even on
        # no-ops, pip must never touch these — see the manifest comments).
        Get-Content (Join-Path $projectRoot "requirements\ocr-compare\conda.txt") | ForEach-Object {
            if ($_ -match '^\s*([A-Za-z0-9._-]+)==(\S+)') {
                $name = $Matches[1]; $want = $Matches[2]
                $have = & $mainPy -c "import importlib.metadata as m; print(m.version('$name').strip())" 2>$null
                if ($LASTEXITCODE -ne 0 -or "$have".Trim() -ne $want) {
                    Write-Host "repairing conda package $name=$want (have: $have)" -ForegroundColor Yellow
                    Invoke-Conda install -y -n ocr-compare -c conda-forge --override-channels "$($name.ToLower())=$want"
                }
            }
        }
    } else {
        $envExists = (& $conda env list) -match '^\s*ocr-compare\s'
        if ($envExists) {
            Invoke-Conda env update -n ocr-compare -f (Join-Path $projectRoot "environment.yml") --prune
        } else {
            Invoke-Conda env create -f (Join-Path $projectRoot "environment.yml")
        }
        Invoke-Pip ocr-compare install --upgrade pip
    }

    Write-Host "== [2/6] torch ($Variant wheels) ==" -ForegroundColor Cyan
    Install-Manifest ocr-compare "01-torch.$Variant.txt"

    # Effective paddle wheel: explicit override > requested variant; a failed
    # GPU run_check downgrades it to cpu below.
    $paddleEffective = if ($PaddleVariant) { $PaddleVariant } else { $Variant }

    Write-Host "== [3/6] paddlepaddle ($paddleEffective) ==" -ForegroundColor Cyan
    if ($paddleEffective -eq 'gpu') {
        try {
            Install-Manifest ocr-compare "02-paddle.gpu.txt"
            & $mainPy -c "import paddle; paddle.utils.run_check()"
            if ($LASTEXITCODE -ne 0) { throw "paddle.utils.run_check() failed" }
        } catch {
            Write-Warning "paddlepaddle-gpu install/verify failed: $_"
            Write-Warning "Falling back to CPU paddlepaddle. Paddle engines (paddleocr, ppstructurev3, paddleocr-vl) will run on CPU - paddleocr-vl will be impractically slow."
            & $mainPy -m pip uninstall -y paddlepaddle-gpu
            Install-Manifest ocr-compare "02-paddle.cpu.txt"
            $paddleEffective = 'cpu'
        }
    } else {
        Install-Manifest ocr-compare "02-paddle.cpu.txt"
    }

    Write-Host "== [4/6] PyPI bulk ==" -ForegroundColor Cyan
    Install-Manifest ocr-compare "03-pypi.txt"

    Write-Host "== [4b/6] sitecustomize SSL workaround ==" -ForegroundColor Cyan
    # OpenSSL 3.6.x (conda-forge) rejects DER cadata, breaking the stdlib's
    # Windows-cert-store loader (ssl.create_default_context) and with it
    # `import paddleocr`. tools\sitecustomize_ssl.py patches the loader to feed
    # certs as PEM one at a time. Installed into the env's site-packages.
    $envSite = & $mainPy -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
    Copy-Item (Join-Path $projectRoot "tools\sitecustomize_ssl.py") (Join-Path $envSite.Trim() "sitecustomize.py") -Force

    Write-Host "== [5/6] environment check ==" -ForegroundColor Cyan
    if ($Repair) {
        # Fast manifest check only; check_env.py loads every engine (minutes).
        & $mainPy (Join-Path $projectRoot "tools\check_deps.py") --manifest-dir (Join-Path $projectRoot "requirements\ocr-compare") --variant $Variant --paddle-variant $paddleEffective --require-sitecustomize --require-cli tesseract pdftotext
        if ($LASTEXITCODE -ne 0) { throw "check_deps.py still reports $LASTEXITCODE problem(s) after repair" }
    } else {
        & $mainPy (Join-Path $projectRoot "tools\check_env.py")
    }

    if (-not $SkipPaddleEnv) {
        Write-Host "== [6/6] isolated paddle env (ocr-compare-paddle) ==" -ForegroundColor Cyan
        if (-not (Test-Path (Get-EnvPython "ocr-compare-paddle"))) {
            Invoke-Conda create -y -n ocr-compare-paddle python=3.11 pip
        }
        # CPU torch FIRST: it only exists to satisfy paddleocr->modelscope->torch,
        # and a CUDA torch here would clash with paddle's cudnn in-process.
        Install-Manifest ocr-compare-paddle "01-torch.txt"
        Install-Manifest ocr-compare-paddle "02-paddle.$paddleEffective.txt"
        # [all] extras: PP-StructureV3 / PaddleOCR-VL pipelines need doc-parser deps.
        Install-Manifest ocr-compare-paddle "03-pypi.txt"
        $pPy = Get-EnvPython "ocr-compare-paddle"
        $pSite = & $pPy -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
        Copy-Item (Join-Path $projectRoot "tools\sitecustomize_ssl.py") (Join-Path $pSite.Trim() "sitecustomize.py") -Force
        # torch FIRST (same DLL-order rule the adapters follow).
        & $pPy -c "import torch, paddle, paddleocr; print('paddle env OK; paddle CUDA:', paddle.device.is_compiled_with_cuda())"
        if ($LASTEXITCODE -ne 0) { throw "paddle env import check failed" }
        Write-Host "The app auto-routes paddleocr/ppstructurev3/paddleocr-vl to this env." -ForegroundColor Yellow
    } else {
        Write-Host "== [6/6] skipped (-SkipPaddleEnv set) ==" -ForegroundColor DarkGray
    }

    # bootstrap.ps1 reads this to stamp which paddle wheel actually landed.
    @{ variant = $Variant; paddle_effective = $paddleEffective } |
        ConvertTo-Json | Set-Content (Join-Path $stateDir "setup_result.json") -Encoding utf8

    Write-Host "`nDone. Launch the app by double-clicking OCR-Compare.exe / Start-OCR-Compare.cmd (or .\run_app.ps1)." -ForegroundColor Green
} finally {
    Stop-Transcript | Out-Null
}

# Launch ocr-compare in its conda environment (dev launcher; end users
# double-click OCR-Compare.exe / Start-OCR-Compare.cmd instead).
. (Join-Path $PSScriptRoot "tools\conda_locate.ps1")
$conda = Find-CondaExe
if (-not $conda) { throw "conda not found. Run bootstrap.ps1 or .\setup_env.ps1 first." }
$env:PYTHONPATH = $PSScriptRoot
& $conda run -n ocr-compare --no-capture-output python -m app.main @args

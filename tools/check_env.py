"""Environment smoke check: verifies every engine imports, reports versions and
GPU status. Each check runs in its own subprocess to mirror the app's runtime
isolation (one worker process per engine job).

Run inside the ocr-compare env:  python tools/check_env.py
Exit code: number of failed checks (0 = all good).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.envpath import ensure_conda_bin_on_path  # noqa: E402

ensure_conda_bin_on_path()

# (label, python snippet printing a version string) — run via `python -c`.
IMPORT_CHECKS = [
    ("pymupdf",       "import fitz, pymupdf4llm; print(fitz.__version__)"),
    ("pypdfium2",     "import pypdfium2, pypdfium2.version as v; print(v.PYPDFIUM_INFO)"),
    ("liteparse",     "import liteparse; from importlib.metadata import version; print(version('liteparse'))"),
    ("pytesseract",   "import pytesseract; print(pytesseract.get_tesseract_version())"),
    ("easyocr",       "import easyocr; from importlib.metadata import version; print(version('easyocr'))"),
    ("paddleocr",     "import paddleocr; print(paddleocr.__version__)"),
    ("rapidocr",      "from rapidocr import RapidOCR; from importlib.metadata import version; print(version('rapidocr'))"),
    ("docling",       "from docling.document_converter import DocumentConverter; from importlib.metadata import version; print(version('docling'))"),
    ("markitdown",    "from markitdown import MarkItDown; from importlib.metadata import version; print(version('markitdown'))"),
    ("rapidfuzz",     "import rapidfuzz; print(rapidfuzz.__version__)"),
    ("PySide6",       "import PySide6; print(PySide6.__version__)"),
]

GPU_CHECKS = [
    ("torch CUDA",    "import torch; print(f'{torch.__version__} cuda={torch.cuda.is_available()}' + (f' ({torch.cuda.get_device_name(0)})' if torch.cuda.is_available() else ''))"),
    ("paddle CUDA",   "import paddle; print(f'{paddle.__version__} cuda={paddle.device.is_compiled_with_cuda()}')"),
]

CLI_CHECKS = [
    ("pdftotext", ["pdftotext", "-v"]),
    ("tesseract", ["tesseract", "--version"]),
]


def run_snippet(label: str, snippet: str, timeout: int = 300) -> tuple[bool, str]:
    try:
        proc = subprocess.run([sys.executable, "-c", snippet],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()
        return False, tail[-1] if tail else f"exit {proc.returncode}"
    out = proc.stdout.strip().splitlines()
    return True, out[-1] if out else "ok"


def main() -> int:
    failures = 0
    print(f"python: {sys.version.split()[0]}  ({sys.executable})\n")

    print("-- engine / library imports (each in its own subprocess) --")
    for label, snippet in IMPORT_CHECKS:
        ok, msg = run_snippet(label, snippet)
        print(f"  {'OK  ' if ok else 'FAIL'}  {label:<12} {msg}")
        failures += 0 if ok else 1

    print("\n-- GPU --")
    for label, snippet in GPU_CHECKS:
        ok, msg = run_snippet(label, snippet)
        print(f"  {'OK  ' if ok else 'FAIL'}  {label:<12} {msg}")
        failures += 0 if ok else 1

    print("\n-- CLI binaries --")
    for label, cmd in CLI_CHECKS:
        path = shutil.which(cmd[0])
        if not path:
            print(f"  FAIL  {label:<12} not on PATH")
            failures += 1
            continue
        proc = subprocess.run(cmd, capture_output=True, text=True)
        line = (proc.stdout or proc.stderr).strip().splitlines()
        print(f"  OK    {label:<12} {line[0] if line else path}")

    print(f"\n{failures} failure(s)")
    return failures


if __name__ == "__main__":
    sys.exit(main())

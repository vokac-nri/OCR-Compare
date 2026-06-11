"""Ensure the conda env's native binaries (tesseract.exe, pdftotext.exe from
conda-forge) win on PATH, no matter how this interpreter was launched.

Without this, a bare python.exe invocation misses <env>\\Library\\bin and
`pdftotext` can silently resolve to Git-for-Windows' ancient bundled build.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_conda_bin_on_path() -> None:
    lib_bin = Path(sys.prefix) / "Library" / "bin"
    if lib_bin.is_dir():
        current = os.environ.get("PATH", "")
        entry = str(lib_bin)
        if not current.lower().startswith(entry.lower() + os.pathsep):
            os.environ["PATH"] = entry + os.pathsep + current
    # conda-forge tesseract looks for ./eng.traineddata unless told otherwise.
    tessdata = Path(sys.prefix) / "share" / "tessdata"
    if tessdata.is_dir() and not os.environ.get("TESSDATA_PREFIX"):
        os.environ["TESSDATA_PREFIX"] = str(tessdata)

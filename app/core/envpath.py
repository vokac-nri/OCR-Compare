"""Ensure the conda env's native binaries (tesseract, pdftotext from
conda-forge) win on PATH, no matter how this interpreter was launched.

Without this, a bare python invocation misses the env's native-bin dir
(<env>\\Library\\bin on Windows, <env>/bin elsewhere) and `pdftotext` can
silently resolve to some ancient system build (e.g. Git-for-Windows' bundled
one).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_conda_bin_on_path() -> None:
    if os.name == "nt":
        native_bin = Path(sys.prefix) / "Library" / "bin"
    else:
        native_bin = Path(sys.prefix) / "bin"
    if native_bin.is_dir():
        current = os.environ.get("PATH", "")
        entry = str(native_bin)
        if not current.lower().startswith(entry.lower() + os.pathsep):
            os.environ["PATH"] = entry + os.pathsep + current
    # conda-forge tesseract looks for ./eng.traineddata unless told otherwise.
    tessdata = Path(sys.prefix) / "share" / "tessdata"
    if tessdata.is_dir() and not os.environ.get("TESSDATA_PREFIX"):
        os.environ["TESSDATA_PREFIX"] = str(tessdata)

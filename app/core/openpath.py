"""Open a file or folder in the platform's default application."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_path(path: str | Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # noqa: S606 - the Windows-native way
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])

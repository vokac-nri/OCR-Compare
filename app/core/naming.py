"""Run/folder/file naming. Pure functions, no filesystem access except
unique_run_dir which only checks existence.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

# Explicit table: strftime("%b") is locale-dependent; run folder names must be
# stable on any Windows locale.
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")

_BAD_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def run_dir_name(now: datetime) -> str:
    """10JUN20261413 — DDMONYYYYHHMM per the output spec."""
    return f"{now.day:02d}{MONTHS[now.month - 1]}{now.year:04d}{now.hour:02d}{now.minute:02d}"


def unique_run_dir(output_root: Path, now: datetime) -> Path:
    """Run dir path, appending _2, _3... if two runs land in the same minute."""
    base = run_dir_name(now)
    candidate = output_root / base
    n = 2
    while candidate.exists():
        candidate = output_root / f"{base}_{n}"
        n += 1
    return candidate


def sanitize_stem(stem: str) -> str:
    s = _BAD_CHARS.sub("_", stem).strip("._-")
    return s[:80] if s else "file"


def file_folder_name(path: Path, taken: set[str]) -> str:
    """'mycooldoc1.pdf' -> 'mycooldoc1_pdf'; collision-suffixed against `taken`
    (case-insensitive, since NTFS is). Caller adds the result to `taken`.
    """
    ext = path.suffix.lstrip(".").lower() or "noext"
    base = f"{sanitize_stem(path.stem)}_{ext}"
    name, n = base, 2
    lowered = {t.lower() for t in taken}
    while name.lower() in lowered:
        name = f"{base}_{n}"
        n += 1
    return name


def output_file_name(engine_id: str, folder_name: str, fmt: str) -> str:
    """'paddleocr-vl', 'mycooldoc1_pdf', 'md' -> 'paddleocr_vl_mycooldoc1_pdf.md'."""
    return f"{engine_id.replace('-', '_')}_{folder_name}.{fmt}"

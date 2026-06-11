"""Re-pin a manifest directory from the live environment.

Rewrites every ``name[extras]==version`` line in the directory's ``*.txt``
manifests to the version actually installed in THIS interpreter's env
(importlib.metadata). Comments, blank lines and ``--index-url``-style options
pass through untouched; pins whose package is not installed are reported as
SKIP and keep their old version.

Dry-run by default (prints the would-be changes); ``--write`` applies them.

Run it with the env the manifests describe, e.g. on mac after a first
``setup_env.sh --unpinned`` install:

    ~/miniforge3/envs/ocr-compare/bin/python tools/freeze_pins.py \\
        --manifest-dir requirements/mac/ocr-compare --write
    ~/miniforge3/envs/ocr-compare-paddle/bin/python tools/freeze_pins.py \\
        --manifest-dir requirements/mac/ocr-compare-paddle --write
"""
from __future__ import annotations

import argparse
import re
import sys
from importlib import metadata
from pathlib import Path

# name[extras]==version, e.g. "markitdown[pdf]==0.1.6" (same as check_deps.py)
_PIN_RE = re.compile(r"^([A-Za-z0-9._-]+)(\[[^\]]*\])?==(.+)$")


def _canonical(name: str) -> str:
    """PEP 503 name normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()


def freeze_file(path: Path, installed: dict[str, str], write: bool) -> int:
    """Returns the number of pins changed in this file."""
    changed = 0
    out_lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        m = _PIN_RE.match(stripped)
        if not stripped or stripped.startswith(("#", "-")) or not m:
            out_lines.append(line)
            continue
        name, extras, old = m.group(1), m.group(2) or "", m.group(3)
        have = installed.get(_canonical(name))
        if have is None:
            print(f"SKIP  {path.name}: {name} not installed, keeping =={old}")
            out_lines.append(line)
        elif have == old:
            out_lines.append(line)
        else:
            print(f"PIN   {path.name}: {name} {old} -> {have}")
            out_lines.append(f"{name}{extras}=={have}")
            changed += 1
    if changed and write:
        path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest-dir", required=True, type=Path)
    ap.add_argument("--write", action="store_true",
                    help="apply changes (default: dry-run)")
    args = ap.parse_args()

    files = sorted(args.manifest_dir.glob("*.txt"))
    if not files:
        print(f"NO-MANIFESTS {args.manifest_dir}")
        return 1

    # .strip(): conda-forge PySide6 ships "Version: 6.11.1 " (trailing space).
    installed = {_canonical(d.metadata["Name"]): (d.version or "").strip()
                 for d in metadata.distributions() if d.metadata["Name"]}

    total = sum(freeze_file(f, installed, args.write) for f in files)
    mode = "updated" if args.write else "would update (dry-run, use --write)"
    print(f"{total} pin(s) {mode} across {len(files)} file(s) "
          f"from env {sys.prefix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

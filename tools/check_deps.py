"""Fast dependency check for one env against its pinned manifests.

Run INSIDE the target env (bootstrap.ps1 / setup_env.ps1 invoke it as
``<env>\\python.exe tools\\check_deps.py --manifest-dir requirements\\ocr-compare
--variant gpu``). Compares installed distributions (importlib.metadata) against
the ``==`` pins; never imports engine packages, so it finishes in well under a
second — this is NOT check_env.py.

Manifest selection: ``NN-*.txt`` stage files plus ``conda.txt``. Files with a
``.gpu.txt`` / ``.cpu.txt`` suffix are included only when they match the
variant; paddle stage files (``02-paddle.*``) match ``--paddle-variant``
instead, which setup_env.ps1 sets to ``cpu`` when the GPU paddle install
failed its run_check and fell back (otherwise the checker would demand
paddlepaddle-gpu forever).

Prints one line per problem (MISSING/MISMATCH name + versions); exit code is
the problem count.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import sysconfig
from importlib import metadata
from pathlib import Path

# name[extras]==version, e.g. "markitdown[pdf]==0.1.6"
_PIN_RE = re.compile(r"^([A-Za-z0-9._-]+)(\[[^\]]*\])?==(.+)$")


def _canonical(name: str) -> str:
    """PEP 503 name normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _cli_path(prefix: Path, exe: str) -> Path:
    """Where a conda-forge CLI lands: <env>\\Library\\bin\\<exe>.exe on
    Windows, <env>/bin/<exe> elsewhere."""
    if os.name == "nt":
        return prefix / "Library" / "bin" / f"{exe}.exe"
    return prefix / "bin" / exe


def _manifest_files(manifest_dir: Path, variant: str, paddle_variant: str) -> list[Path]:
    files = []
    for path in sorted(manifest_dir.glob("*.txt")):
        stem = path.name
        want = paddle_variant if "paddle" in stem else variant
        other = "cpu" if want == "gpu" else "gpu"
        if stem.endswith(f".{other}.txt"):
            continue
        files.append(path)
    return files


def _pins(files: list[Path]) -> dict[str, str]:
    pins: dict[str, str] = {}
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            m = _PIN_RE.match(line)
            if not m:
                print(f"UNPARSEABLE {path.name}: {line}")
                continue
            pins[m.group(1)] = m.group(3)
    return pins


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest-dir", required=True, type=Path)
    ap.add_argument("--variant", choices=("gpu", "cpu"), default="gpu")
    ap.add_argument("--paddle-variant", choices=("gpu", "cpu"), default=None,
                    help="variant for 02-paddle.* files (default: --variant)")
    ap.add_argument("--require-sitecustomize", action="store_true",
                    help="verify the OpenSSL-3.6 sitecustomize.py workaround is installed")
    ap.add_argument("--require-cli", nargs="*", default=[],
                    help="exe names that must exist in the env's native-bin dir")
    args = ap.parse_args()

    problems = 0
    # .strip(): conda-forge PySide6 ships "Version: 6.11.1 " (trailing space).
    installed = {_canonical(d.metadata["Name"]): (d.version or "").strip()
                 for d in metadata.distributions() if d.metadata["Name"]}

    files = _manifest_files(args.manifest_dir, args.variant,
                            args.paddle_variant or args.variant)
    if not files:
        print(f"NO-MANIFESTS {args.manifest_dir}")
        return 1

    for name, want in _pins(files).items():
        have = installed.get(_canonical(name))
        if have is None:
            print(f"MISSING {name}=={want}")
            problems += 1
        elif have != want:
            print(f"MISMATCH {name} have={have} want={want}")
            problems += 1

    if args.require_sitecustomize:
        if not (Path(sysconfig.get_paths()["purelib"]) / "sitecustomize.py").exists():
            print("MISSING sitecustomize.py (OpenSSL 3.6 workaround)")
            problems += 1

    for exe in args.require_cli:
        expected = _cli_path(Path(sys.prefix), exe)
        if not expected.exists():
            print(f"MISSING-CLI {expected}")
            problems += 1

    if problems == 0:
        print(f"OK {len(files)} manifest file(s), env {sys.prefix}")
    return problems


if __name__ == "__main__":
    sys.exit(main())

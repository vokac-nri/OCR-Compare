#!/bin/bash
# One-click launcher for OCR Compare on macOS (Apple Silicon). Double-click
# OCR-Compare.command (a thin wrapper around this script), or run it directly.
# Mirrors bootstrap.ps1; see that file for the full design rationale.
#
# Every launch verifies the install and fixes only what is missing or at the
# wrong version, then starts the GUI:
#   - no conda anywhere      -> downloads Miniforge and installs it silently
#   - envs missing           -> full setup_env.sh (first run: 30-60 min, GBs)
#   - packages missing/wrong -> setup_env.sh --repair (minutes)
#   - everything healthy     -> stamp fast path, app starts in ~2 s
#
# The fast path spawns no conda/pip/python at all: a stamp file records the
# SHA-256 of the pinned manifests (requirements/mac/ + environment.yml) from
# the last verified launch, and while it matches and the env interpreters
# still exist, checking is skipped entirely. Edit any manifest (or pass
# --recheck) and the next launch re-verifies.
#
#   --recheck       ignore the stamp; run the dependency checker now
#   --reinstall     force a full setup_env.sh pass
#   --no-launch     verify/repair only, don't start the GUI
#   --no-pause      don't wait for Enter on failure (for scripted use)
#
# State + logs: ~/Library/Application Support/OCR-Compare/. Delete
# launcher_state.json there to force a full re-check.
#
# bash-3.2-safe (macOS /bin/bash).
set -Eeuo pipefail

# Bump to invalidate every machine's stamp after launcher-logic changes.
BOOTSTRAP_VERSION=1

RECHECK=0
REINSTALL=0
NO_LAUNCH=0
NO_PAUSE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --recheck) RECHECK=1 ;;
        --reinstall) REINSTALL=1 ;;
        --no-launch) NO_LAUNCH=1 ;;
        --no-pause) NO_PAUSE=1 ;;
        *) echo "Unknown flag: $1 (known: --recheck --reinstall --no-launch --no-pause)" >&2; exit 2 ;;
    esac
    shift
done

# ---- platform gate (clear messages before anything else happens)
if [ "$(uname -s)" != "Darwin" ]; then
    echo "bootstrap.sh is the macOS launcher — on Windows use OCR-Compare.exe / bootstrap.ps1." >&2
    exit 1
fi
if [ "$(uname -m)" != "arm64" ]; then
    echo "OCR Compare on macOS requires Apple Silicon (arm64); this Mac reports '$(uname -m)'." >&2
    echo "PyTorch dropped Intel-mac wheels after 2.2, so the pinned torch cannot install here." >&2
    exit 1
fi
MACOS_VERSION="$(sw_vers -productVersion)"
if [ "${MACOS_VERSION%%.*}" -lt 14 ]; then
    echo "OCR Compare requires macOS 14 (Sonoma) or newer (torch 2.12 wheels are macosx_14_0); this Mac runs $MACOS_VERSION." >&2
    exit 1
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR="$HOME/Library/Application Support/OCR-Compare"
LOG_DIR="$STATE_DIR/logs"
STAMP_PATH="$STATE_DIR/launcher_state.json"
mkdir -p "$LOG_DIR"

LOG="$LOG_DIR/bootstrap-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG") 2>&1
(cd "$LOG_DIR" && ls -t bootstrap-*.log 2>/dev/null | tail -n +11 | while IFS= read -r f; do rm -f "$f"; done)

on_error() {
    status=$?
    echo ""
    echo "OCR Compare launcher failed (exit $status)."
    echo "  Log: $LOG"
    if [ "$NO_PAUSE" != 1 ]; then
        read -r -p "Press Enter to close " _ || true
    fi
    exit "$status"
}
trap on_error ERR

manifest_hash() {
    # Hash of every pin source + the launcher version: any edit invalidates
    # the stamp and the next launch re-verifies. Only requirements/mac/ —
    # Windows manifest edits must not churn mac stamps (and vice versa,
    # bootstrap.ps1 excludes requirements/mac/).
    {
        while IFS= read -r f; do
            shasum -a 256 "$f" | awk '{print $1}'
        done < <(find "$ROOT/requirements/mac" -name '*.txt' -print | LC_ALL=C sort)
        shasum -a 256 "$ROOT/environment.yml" | awk '{print $1}'
        echo "v$BOOTSTRAP_VERSION"
    } | shasum -a 256 | awk '{print $1}'
}

stamp_get() {
    # stamp_get <key> -> value (empty if absent). The stamp is flat
    # one-string-key-per-line JSON written by this script, so sed suffices.
    [ -f "$STAMP_PATH" ] || return 0
    sed -n "s/^ *\"$1\": *\"\(.*\)\",*\$/\1/p" "$STAMP_PATH" | head -n 1
}

check_deps() {
    # check_deps <python> <env-name> [extra args...]; returns the problem
    # count (pipefail keeps the checker's exit status through the indenting sed).
    py="$1"
    envname="$2"
    shift 2
    "$py" "$ROOT/tools/check_deps.py" \
        --manifest-dir "$ROOT/requirements/mac/$envname" \
        --variant cpu --paddle-variant cpu "$@" | sed 's/^/  /'
}

MANIFEST_HASH="$(manifest_hash)"

# ---- fast path: stamp says this exact pin set was verified on this machine
FAST=0
MAIN_PY=""
PADDLE_PY=""
if [ "$RECHECK" != 1 ] && [ "$REINSTALL" != 1 ] \
        && [ "$(stamp_get schema)" = "1" ] \
        && [ "$(stamp_get manifest_hash)" = "$MANIFEST_HASH" ]; then
    MAIN_PY="$(stamp_get main_py)"
    PADDLE_PY="$(stamp_get paddle_py)"
    if [ -n "$MAIN_PY" ] && [ -x "$MAIN_PY" ] && [ -n "$PADDLE_PY" ] && [ -x "$PADDLE_PY" ]; then
        FAST=1
        echo "Dependencies verified (cached) - starting OCR Compare..."
    fi
fi

if [ "$FAST" != 1 ]; then
    # ---- conda
    . "$ROOT/tools/conda_locate.sh"
    CONDA="$(find_conda_exe || true)"
    if [ -z "$CONDA" ]; then
        echo "No conda installation found - installing Miniforge (one-time)."
        CONDA="$(install_miniforge)"
    fi
    CONDA_ROOT="$(get_conda_root "$CONDA")"
    MAIN_PY="$CONDA_ROOT/envs/ocr-compare/bin/python"
    PADDLE_PY="$CONDA_ROOT/envs/ocr-compare-paddle/bin/python"

    SETUP_RAN=0
    if [ "$REINSTALL" = 1 ] || [ ! -x "$MAIN_PY" ]; then
        echo "Environments missing or --reinstall set: full setup (first run takes 30-60 min)..."
        /bin/bash "$ROOT/setup_env.sh"
        SETUP_RAN=1
    else
        echo "Checking dependencies against pinned manifests..."
        PROBLEMS=0
        check_deps "$MAIN_PY" ocr-compare --require-cli tesseract pdftotext || PROBLEMS=$?
        if [ "$PROBLEMS" -eq 0 ]; then
            if [ -x "$PADDLE_PY" ]; then
                check_deps "$PADDLE_PY" ocr-compare-paddle || PROBLEMS=$?
            else
                echo "paddle env missing"
                PROBLEMS=1
            fi
        fi
        if [ "$PROBLEMS" -ne 0 ]; then
            echo "Found $PROBLEMS problem(s) - repairing (only missing/outdated pieces are installed)..."
            /bin/bash "$ROOT/setup_env.sh" --repair
            SETUP_RAN=1
        fi
    fi

    if [ "$SETUP_RAN" = 1 ]; then
        # post-setup verification: both envs must now satisfy the manifests
        if ! check_deps "$MAIN_PY" ocr-compare --require-cli tesseract pdftotext; then
            echo "ocr-compare env still fails the dependency check after setup - see output above" >&2
            false
        fi
        if ! check_deps "$PADDLE_PY" ocr-compare-paddle; then
            echo "ocr-compare-paddle env still fails the dependency check after setup - see output above" >&2
            false
        fi
    fi

    # ---- stamp this verified state (flat strings only — stamp_get reads
    # it back with sed)
    cat > "$STAMP_PATH" <<EOF
{
  "schema": "1",
  "bootstrap_version": "$BOOTSTRAP_VERSION",
  "manifest_hash": "$MANIFEST_HASH",
  "variant": "cpu",
  "paddle_effective": "cpu",
  "conda_root": "$CONDA_ROOT",
  "main_py": "$MAIN_PY",
  "paddle_py": "$PADDLE_PY",
  "checked_at": "$(date '+%Y-%m-%dT%H:%M:%S%z')"
}
EOF
    echo "Dependencies OK - starting OCR Compare..."
fi

# ---- launch (direct python, no `conda run` overhead; app/main.py's
# ensure_conda_bin_on_path() fixes PATH/TESSDATA_PREFIX for the workers)
EXIT_CODE=0
if [ "$NO_LAUNCH" != 1 ]; then
    export PYTHONPATH="$ROOT"
    PATH="$(dirname "$MAIN_PY"):$PATH"
    export PATH
    # Cheap insurance: ops torch hasn't implemented on MPS fall back to CPU
    # instead of raising.
    export PYTORCH_ENABLE_MPS_FALLBACK=1
    "$MAIN_PY" -m app.main || EXIT_CODE=$?
fi
exit "$EXIT_CODE"

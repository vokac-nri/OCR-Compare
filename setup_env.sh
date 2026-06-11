#!/bin/bash
# Reproducible setup for the ocr-compare conda environments (macOS, Apple
# Silicon). Mirrors setup_env.ps1 stage-for-stage; see that file for the full
# design rationale.
#
#   bash setup_env.sh              # creates BOTH envs:
#     ocr-compare         - GUI + all engines except the paddle family
#                           (torch with MPS for easyocr/docling)
#     ocr-compare-paddle  - paddleocr / ppstructurev3 / paddleocr-vl
#                           (CPU paddle + torch import-satisfier)
#
# Normally invoked by bootstrap.sh (the one-click launcher). Run directly for
# manual/dev setup.
#
#   --repair            skip conda env create/update; just (re)install from
#                       the pinned manifests under requirements/mac/ — pip
#                       no-ops fast on already-satisfied stages.
#   --skip-paddle-env   skip stage 6 (the isolated paddle env).
#   --unpinned          strip ==version pins before installing, letting pip
#                       resolve freely. Escape hatch for the seeded-from-
#                       Windows pins; afterwards lock what landed with
#                       tools/freeze_pins.py --write (run once per env).
#
# Unlike Windows there is no --variant: mac is single-variant (torch wheels
# include MPS, paddle has no Metal backend so it is always CPU —
# paddle_effective is always "cpu").
#
# Two envs on mac too: zero routing divergence from Windows, and it sidesteps
# the classic torch+paddle duplicate-libomp abort (OMP Error #15).
#
# Install order matters: torch first, then paddle, then everything else, so
# resolver backtracking never replaces the framework wheels. The order is
# encoded in the NN- prefixes of the manifest files.
#
# bash-3.2-safe (macOS /bin/bash).
set -euo pipefail

REPAIR=0
SKIP_PADDLE_ENV=0
UNPINNED=0
while [ $# -gt 0 ]; do
    case "$1" in
        --repair) REPAIR=1 ;;
        --skip-paddle-env) SKIP_PADDLE_ENV=1 ;;
        --unpinned) UNPINNED=1 ;;
        *) echo "Unknown flag: $1 (known: --repair --skip-paddle-env --unpinned)" >&2; exit 2 ;;
    esac
    shift
done

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
. "$PROJECT_ROOT/tools/conda_locate.sh"
CONDA="$(find_conda_exe || true)"
if [ -z "$CONDA" ]; then
    echo "conda not found. Run bootstrap.sh (installs Miniforge automatically) or install Miniconda/Miniforge." >&2
    exit 1
fi
CONDA_ROOT="$(get_conda_root "$CONDA")"
ENVS_DIR="$CONDA_ROOT/envs"

# State/logs live OUTSIDE the repo, in the platform-conventional location.
STATE_DIR="$HOME/Library/Application Support/OCR-Compare"
mkdir -p "$STATE_DIR/logs"
LOG="$STATE_DIR/logs/setup-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG") 2>&1

env_python() {
    echo "$ENVS_DIR/$1/bin/python"
}

install_manifest() {
    # install_manifest <env-name> <manifest-file>
    manifest="$PROJECT_ROOT/requirements/mac/$1/$2"
    target="$manifest"
    if [ "$UNPINNED" = 1 ]; then
        # Strip the ==version suffixes (comment/option lines have none) so
        # pip resolves freely; freeze_pins.py locks the result afterwards.
        target="$(mktemp)"
        sed -E 's/==[^ ]+$//' "$manifest" > "$target"
    fi
    if ! "$(env_python "$1")" -m pip install -r "$target"; then
        echo "" >&2
        echo "pip install failed for manifest: $manifest" >&2
        echo "These pins were seeded from Windows and never verified on a real Mac." >&2
        echo "Recovery (see README 'macOS first run'):" >&2
        echo "  1) bash setup_env.sh --unpinned" >&2
        echo "  2) \"$(env_python "$1")\" tools/freeze_pins.py --manifest-dir requirements/mac/$1 --write" >&2
        echo "  then commit the updated manifests." >&2
        exit 1
    fi
}

MAIN_PY="$(env_python ocr-compare)"

echo "== [1/6] conda env from environment.yml =="
if [ "$REPAIR" = 1 ] && [ -x "$MAIN_PY" ]; then
    echo "(repair mode: env exists, skipping conda create/update)"
    # conda-forge pins (requirements/mac/ocr-compare/conda.txt) are normally
    # satisfied by environment.yml; in repair mode verify them cheaply and
    # conda-install only what is actually broken (conda is slow even on
    # no-ops, pip must never touch these — see the manifest comments).
    while IFS= read -r line; do
        case "$line" in
            \#*) continue ;;
            *==*) ;;
            *) continue ;;
        esac
        name="${line%%==*}"
        want="${line#*==}"
        have="$("$MAIN_PY" -c "import importlib.metadata as m; print(m.version('$name').strip())" 2>/dev/null || true)"
        if [ "$have" != "$want" ]; then
            echo "repairing conda package $name=$want (have: ${have:-none})"
            "$CONDA" install -y -n ocr-compare -c conda-forge --override-channels \
                "$(echo "$name" | tr 'A-Z' 'a-z')=$want"
        fi
    done < "$PROJECT_ROOT/requirements/mac/ocr-compare/conda.txt"
else
    if "$CONDA" env list | grep -Eq '^ocr-compare[[:space:]]'; then
        "$CONDA" env update -n ocr-compare -f "$PROJECT_ROOT/environment.yml" --prune
    else
        "$CONDA" env create -f "$PROJECT_ROOT/environment.yml"
    fi
    "$MAIN_PY" -m pip install --upgrade pip
fi

echo "== [2/6] torch (arm64 wheels, MPS built in) =="
install_manifest ocr-compare 01-torch.txt

echo "== [3/6] paddlepaddle (CPU — paddle has no Metal backend) =="
install_manifest ocr-compare 02-paddle.txt
if ! "$MAIN_PY" -c "import paddle; print('paddle', paddle.__version__, 'OK (CPU)')"; then
    echo "paddle import check failed — see output above" >&2
    exit 1
fi

echo "== [4/6] PyPI bulk =="
install_manifest ocr-compare 03-pypi.txt
# No stage 4b here: the sitecustomize SSL patch (tools/sitecustomize_ssl.py)
# works around a Windows-cert-store + OpenSSL 3.6 bug and is Windows-only.

echo "== [5/6] environment check =="
if [ "$REPAIR" = 1 ]; then
    # Fast manifest check only; check_env.py loads every engine (minutes).
    if ! "$MAIN_PY" "$PROJECT_ROOT/tools/check_deps.py" \
            --manifest-dir "$PROJECT_ROOT/requirements/mac/ocr-compare" \
            --variant cpu --paddle-variant cpu \
            --require-cli tesseract pdftotext; then
        echo "check_deps.py still reports problems after repair — see output above" >&2
        exit 1
    fi
else
    "$MAIN_PY" "$PROJECT_ROOT/tools/check_env.py"
fi

if [ "$SKIP_PADDLE_ENV" != 1 ]; then
    echo "== [6/6] isolated paddle env (ocr-compare-paddle) =="
    PADDLE_PY="$(env_python ocr-compare-paddle)"
    if [ ! -x "$PADDLE_PY" ]; then
        "$CONDA" create -y -n ocr-compare-paddle python=3.11 pip
    fi
    # torch FIRST: it only exists to satisfy paddleocr->modelscope->torch.
    install_manifest ocr-compare-paddle 01-torch.txt
    install_manifest ocr-compare-paddle 02-paddle.txt
    # [all] extras: PP-StructureV3 / PaddleOCR-VL pipelines need doc-parser deps.
    install_manifest ocr-compare-paddle 03-pypi.txt
    # torch FIRST (same import-order rule the adapters follow).
    if ! "$PADDLE_PY" -c "import torch, paddle, paddleocr; print('paddle env OK (CPU)')"; then
        echo "paddle env import check failed — see output above" >&2
        echo "If the error mentions libomp / OMP Error #15, try:" >&2
        echo "  \"$CONDA\" install -y -n ocr-compare-paddle -c conda-forge llvm-openmp" >&2
        exit 1
    fi
    echo "The app auto-routes paddleocr/ppstructurev3/paddleocr-vl to this env."
else
    echo "== [6/6] skipped (--skip-paddle-env set) =="
fi

# bootstrap.sh reads this; on mac the paddle wheel is always CPU.
printf '{\n  "variant": "cpu",\n  "paddle_effective": "cpu"\n}\n' \
    > "$STATE_DIR/setup_result.json"

echo ""
echo "Done. Launch the app by double-clicking OCR-Compare.command (or bash bootstrap.sh)."

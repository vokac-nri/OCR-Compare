# Shared conda discovery for macOS. Source this file, then call
# find_conda_exe / get_conda_root / install_miniforge. Used by bootstrap.sh
# and setup_env.sh so the conda location is never hardcoded.
#
# Functions print their result on stdout; install_miniforge sends progress to
# stderr so callers can capture the path with $(install_miniforge).
# bash-3.2-safe (macOS /bin/bash).

find_conda_exe() {
    # CONDA_EXE is set by conda's own activation hooks; trust it first.
    if [ -n "${CONDA_EXE:-}" ] && [ -x "$CONDA_EXE" ]; then
        echo "$CONDA_EXE"
        return 0
    fi
    for c in "$HOME/miniforge3/bin/conda" \
             "$HOME/miniconda3/bin/conda" \
             "/opt/homebrew/Caskroom/miniforge/base/bin/conda"; do
        if [ -x "$c" ]; then
            echo "$c"
            return 0
        fi
    done
    command -v conda 2>/dev/null && return 0
    return 1
}

get_conda_root() {
    # <root>/bin/conda -> <root>
    dirname "$(dirname "$1")"
}

install_miniforge() {
    # Miniforge = conda preconfigured for conda-forge only; never touches the
    # ToS-gated repo.anaconda.com channels, so no .condarc surgery is needed.
    url="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh"
    installer="${TMPDIR:-/tmp}/Miniforge3-MacOSX-arm64.sh"
    target="$HOME/miniforge3"
    echo "Downloading Miniforge (~80 MB) from GitHub..." >&2
    curl -fsSL "$url" -o "$installer"
    echo "Installing Miniforge to $target (batch mode, a few minutes)..." >&2
    /bin/bash "$installer" -b -p "$target" >&2
    rm -f "$installer"
    exe="$target/bin/conda"
    if [ ! -x "$exe" ]; then
        echo "Miniforge install finished but $exe not found" >&2
        return 1
    fi
    echo "$exe"
}

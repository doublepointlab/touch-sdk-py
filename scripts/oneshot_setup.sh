#!/usr/bin/env bash
set -euo pipefail

# One-shot setup:
# - (optional) clone/update the repo if we’re not already in it
# - ensure `uv` exists (best-effort)
# - create/refresh local `.venv` (Python 3.11)
# - install this repo editable + example deps
# - print commands to run examples
#
# macOS note: `uv python install` can panic in sandboxed runners (crash mentions
# `system-configuration ... Attempted to create a NULL object`). To avoid that on
# first run, we skip `uv python install` when an appropriate interpreter already
# exists on PATH.

REPO_URL="${REPO_URL:-https://github.com/doublepointlab/touch-sdk-py.git}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"

ensure_git() {
  if command -v git >/dev/null 2>&1; then
    return 0
  fi
  echo "git not found; attempting install..."
  if command -v brew >/dev/null 2>&1; then
    brew install git
  elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y && sudo apt-get install -y git
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y git
  elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y git
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm git
  else
    echo "No supported package manager for git. Install git manually and rerun."
    exit 1
  fi
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi
  echo "uv not found; attempting install..."
  if command -v brew >/dev/null 2>&1; then
    brew install uv
  else
    curl -LsSf https://astral.sh/uv/install.sh | sh
  fi

  # Best-effort PATH fixup (common after curl installer).
  if ! command -v uv >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/uv" ]; then
      export PATH="$HOME/.local/bin:$PATH"
    fi
  fi

  if ! command -v uv >/dev/null 2>&1; then
    echo "uv installation did not produce an executable on PATH."
    echo "Try opening a new shell, or add $HOME/.local/bin to PATH."
    exit 1
  fi
}

bootstrap_repo_if_needed() {
  # Prefer: the repo adjacent to this script (normal case).
  local script_dir repo_from_script repo_from_git base_dir target_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  repo_from_script="$(cd "$script_dir/.." && pwd)"
  if [ -f "$repo_from_script/pyproject.toml" ]; then
    echo "$repo_from_script"
    return 0
  fi

  # Fallback: if we’re already inside the repo, use it.
  ensure_git
  repo_from_git="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -n "$repo_from_git" ] && [ -f "$repo_from_git/pyproject.toml" ]; then
    echo "$repo_from_git"
    return 0
  fi

  # Otherwise: clone/update into ./touch-sdk-py from the current working directory.
  base_dir="$(pwd)"
  target_dir="${TARGET_DIR:-$base_dir/touch-sdk-py}"
  if [ -d "$target_dir/.git" ]; then
    echo "Repo already exists at $target_dir; updating..."
    git -C "$target_dir" pull --ff-only
  else
    echo "Cloning into $target_dir..."
    git clone "$REPO_URL" "$target_dir"
  fi
  echo "$target_dir"
}

REPO_DIR="$(bootstrap_repo_if_needed)"
cd "$REPO_DIR"
echo "Repo root: $REPO_DIR"

if [ ! -f "$REPO_DIR/pyproject.toml" ]; then
  echo "Error: expected $REPO_DIR/pyproject.toml to exist. Are you in the right folder?"
  exit 1
fi

ensure_uv

# Use repo-local cache dirs (avoids writing to $HOME).
# Note: this also keeps matplotlib/fontconfig caches out of user home dirs.
export XDG_CACHE_HOME="$REPO_DIR/.cache"
export MPLCONFIGDIR="$REPO_DIR/.mplconfig"
mkdir -p "$XDG_CACHE_HOME" "$MPLCONFIGDIR"

# Fast-path: if a working venv already exists, don't touch uv (helps in sandboxed
# environments where uv may be restricted or crash).
if [ -x "$REPO_DIR/.venv/bin/python" ]; then
  set +e
  "$REPO_DIR/.venv/bin/python" -c "import touch_sdk" >/dev/null 2>&1
  HAVE_WORKING_VENV=$?
  set -e
  if [ "$HAVE_WORKING_VENV" -eq 0 ]; then
    # shellcheck disable=SC1091
    source "$REPO_DIR/.venv/bin/activate"
    python3 -c "import touch_sdk, inspect; print('touch_sdk from:', inspect.getfile(touch_sdk))"
    echo "Run other examples like: python3 examples/basic.py"
    echo "OSC client/server example: python3 examples/osc_client_server.py"
    echo ""
    echo "Next steps (manual):"
    echo "  - Plotter (opens a matplotlib window; runs until you close it): python3 examples/plotter.py"
    echo ""
    echo "Multiple OSC instances:"
    echo "  - Duplicate examples/osc_client_server.py (e.g. osc_client_server_6666_6667.py)"
    echo "  - Change client_port / server_port so each instance uses unique ports (e.g. 6666/6667 -> 6668/6669)"
    exit 0
  fi
fi

# Keep uv-managed Python installs + uv cache inside the repo.
export UV_PYTHON_INSTALL_DIR="$REPO_DIR/.uv-python"
export UV_CACHE_DIR="$REPO_DIR/.uv-cache"
mkdir -p "$UV_PYTHON_INSTALL_DIR" "$UV_CACHE_DIR"

# Best-effort: ensure Python exists.
#
# You can force/skip explicitly:
#   - FORCE_UV_PYTHON_INSTALL=1  -> always try `uv python install`
#   - SKIP_UV_PYTHON_INSTALL=1   -> never try `uv python install`
FORCE_UV_PYTHON_INSTALL="${FORCE_UV_PYTHON_INSTALL:-0}"
SKIP_UV_PYTHON_INSTALL="${SKIP_UV_PYTHON_INSTALL:-0}"

HAVE_PY311=0
if command -v "python${PYTHON_VERSION}" >/dev/null 2>&1; then
  HAVE_PY311=1
elif command -v python3.11 >/dev/null 2>&1; then
  HAVE_PY311=1
fi

if [ "$SKIP_UV_PYTHON_INSTALL" -eq 1 ]; then
  echo "Skipping 'uv python install $PYTHON_VERSION' (SKIP_UV_PYTHON_INSTALL=1)."
elif [ "$FORCE_UV_PYTHON_INSTALL" -eq 1 ] || [ "$HAVE_PY311" -eq 0 ]; then
  set +e
  uv python install "$PYTHON_VERSION"
  UV_PYTHON_INSTALL_EXIT=$?
  set -e
  if [ "$UV_PYTHON_INSTALL_EXIT" -ne 0 ]; then
    echo ""
    echo "Warning: 'uv python install $PYTHON_VERSION' failed."
    echo "If you saw a macOS sandbox panic mentioning 'system-configuration', rerun this"
    echo "script in a regular terminal (Cursor Terminal/iTerm/Terminal.app), or allow the"
    echo "process full access. Continuing with an existing Python $PYTHON_VERSION if available..."
    echo ""
  fi
else
  echo "Found Python $PYTHON_VERSION on PATH; skipping 'uv python install $PYTHON_VERSION'."
fi

# Prefer uv for speed, but fall back to venv+pip when uv is restricted (e.g.
# Cursor sandboxes on macOS) or otherwise fails.
set +e
uv venv --python "$PYTHON_VERSION" --clear ".venv"
UV_VENV_EXIT=$?
set -e

if [ "$UV_VENV_EXIT" -ne 0 ]; then
  echo ""
  echo "Warning: 'uv venv' failed. Falling back to 'python -m venv' + 'pip'."
  echo "This can happen in sandboxed environments (e.g. Cursor) on macOS."
  echo ""

  if command -v "python${PYTHON_VERSION}" >/dev/null 2>&1; then
    PY_EXE="python${PYTHON_VERSION}"
  elif command -v python3.11 >/dev/null 2>&1; then
    PY_EXE="python3.11"
  elif command -v python3 >/dev/null 2>&1; then
    PY_EXE="python3"
  else
    echo "Error: no suitable Python interpreter found on PATH."
    exit 1
  fi

  rm -rf "$REPO_DIR/.venv"
  "$PY_EXE" -m venv "$REPO_DIR/.venv"
  VENV_PY="$REPO_DIR/.venv/bin/python"
  "$VENV_PY" -m pip install --upgrade pip
  "$VENV_PY" -m pip install -e ".[examples]"
else
  VENV_PY="$REPO_DIR/.venv/bin/python"
  uv pip install --python "$VENV_PY" -e ".[examples]"
fi

# shellcheck disable=SC1091
source "$REPO_DIR/.venv/bin/activate"
python3 -c "import touch_sdk, inspect; print('touch_sdk from:', inspect.getfile(touch_sdk))"

echo "Run other examples like: python3 examples/basic.py"
echo "OSC client/server example: python3 examples/osc_client_server.py"
echo ""
echo "Next steps (manual):"
echo "  - Plotter (opens a matplotlib window; runs until you close it): python3 examples/plotter.py"
echo ""
echo "Multiple OSC instances:"
echo "  - Duplicate examples/osc_client_server.py (e.g. osc_client_server_6666_6667.py)"
echo "  - Change client_port / server_port so each instance uses unique ports (e.g. 6666/6667 -> 6668/6669)"

#!/usr/bin/env bash
set -euo pipefail

# Cursor/IDE-friendly wrapper for the repo-local setup.
#
# This exists so docs can point at a stable entrypoint even if we tweak behavior
# for sandboxed environments. All logic lives in scripts/oneshot_setup.sh.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$REPO_DIR/scripts/oneshot_setup.sh"

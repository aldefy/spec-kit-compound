#!/bin/bash
# scripts/dashboard.sh
#
# Launch the spec-kit-compound pipeline dashboard (read-only localhost view).
#
#   ./scripts/dashboard.sh              # serve on the default port
#   ./scripts/dashboard.sh --open       # ...and open a browser
#   ./scripts/dashboard.sh --port 9000  # pick a port
#
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Where dashboard.py lives. In dev this is the repo root; when installed it is
# <project>/.specify/extensions/compound/. Either way the .py sits one level up
# from this scripts/ dir. It does NOT decide which project gets scanned — that
# is dashboard.py's --repo / cwd auto-detect.
SCRIPT_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 not found on PATH" >&2
  exit 1
fi

exec python3 "$SCRIPT_HOME/dashboard.py" "$@"

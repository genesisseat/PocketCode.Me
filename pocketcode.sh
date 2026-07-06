#!/usr/bin/env bash
# pocketcode -- Termux / Linux launcher for PocketCode (Gemini CLI)
# ==================================================================
# Termux global install (run once):
#   cp pocketcode.sh $PREFIX/bin/pocketcode
#   chmod +x $PREFIX/bin/pocketcode
#
# Generic Linux:
#   sudo cp pocketcode.sh /usr/local/bin/pocketcode
#   sudo chmod +x /usr/local/bin/pocketcode

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || echo "${BASH_SOURCE[0]}")")" && pwd)"
ENTRY="$SCRIPT_DIR/pocketcode.py"

if [[ ! -f "$ENTRY" ]]; then
  echo "Error: pocketcode.py not found at $ENTRY" >&2
  echo "       Make sure this script is in the same directory as pocketcode.py." >&2
  exit 1
fi

if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  echo "Error: Python not found. Install with: pkg install python" >&2
  exit 1
fi

exec "$PYTHON" "$ENTRY" "$@"

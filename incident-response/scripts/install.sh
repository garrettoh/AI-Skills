#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${PYTHON:-python3}
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    printf '%s\n' 'Python 3.10+ is required before installation.' >&2
    exit 1
fi
exec "$PYTHON" "$SCRIPT_DIR/install.py" "$@"

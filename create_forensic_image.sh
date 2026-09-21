#!/usr/bin/env bash
# Backwards-compatible name for the compressed E01 acquisition workflow.
set -Eeuo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "$SCRIPT_DIR/acquire_e01.sh" "$@"

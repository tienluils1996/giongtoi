#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$GIONGTOI_ROOT"
exec uv run --no-sync --group dev pytest -q "$@"

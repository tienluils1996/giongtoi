#!/usr/bin/env bash
# So sánh mô hình bằng nghe mù. Ví dụ: ./scripts/bakeoff.sh --voice giong-cua-toi
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$GIONGTOI_ROOT"
out="$(uv run --no-sync giongtoi bakeoff "$@" | tail -1)"
echo "$out"
open "${out#Mở trang nghe mù: }"

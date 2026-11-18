#!/usr/bin/env bash
# Chạy GiọngTôi.
#   ./scripts/run.sh            # web UI, tự mở trình duyệt
#   ./scripts/run.sh app        # cửa sổ ứng dụng
#   ./scripts/run.sh say "Xin chào"   # đọc nhanh ra file
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$GIONGTOI_ROOT"
if [ ! -x "$UV_PROJECT_ENVIRONMENT/bin/python" ]; then
  "$GIONGTOI_ROOT/scripts/setup.sh"
fi
if [ $# -eq 0 ]; then set -- serve --open; fi
# --no-sync: không gỡ các extra đã cài (vd f5)
exec uv run --no-sync giongtoi "$@"

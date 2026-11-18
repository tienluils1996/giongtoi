#!/usr/bin/env bash
# Cài đặt GiọngTôi: uv + Python 3.11 + thư viện. Không cần Homebrew.
#   ./scripts/setup.sh            # engine mặc định VieNeu (nhẹ, không cần PyTorch)
#   ./scripts/setup.sh --with-f5  # thêm F5-TTS (PyTorch, ~1-2 GB) để so sánh mô hình
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$GIONGTOI_ROOT"
mkdir -p "$GIONGTOI_HOME"

EXTRAS_FILE="$GIONGTOI_HOME/.extras"
extras="app $(cat "$EXTRAS_FILE" 2>/dev/null || true)"
for arg in "$@"; do
  case "$arg" in
    --with-f5) extras="$extras f5" ;;
    --without-f5) extras="${extras//f5/}" ;;
    *) echo "Tham số không hợp lệ: $arg"; exit 1 ;;
  esac
done
extras="$(echo "$extras" | tr ' ' '\n' | grep -v '^$' | sort -u | tr '\n' ' ')"
echo "$extras" | tr ' ' '\n' | grep -vx app | tr '\n' ' ' > "$EXTRAS_FILE" || true

if ! command -v uv >/dev/null; then
  echo "→ Cài uv…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
echo "→ Python 3.11"
uv python install 3.11
args=()
for e in $extras; do args+=(--extra "$e"); done
echo "→ Thư viện (extras: $extras)"
# --no-editable: cài bản sao vào .venv để app không phải đọc thư mục OneDrive
uv sync --python 3.11 --no-editable "${args[@]}"
echo "✓ Xong. Chạy app: ./scripts/run.sh"

#!/usr/bin/env bash
# Đẩy code lên GitHub (repo private tienluils1996/giongtoi).
# Nếu repo chưa tồn tại: tạo repo trống (private) tại https://github.com/new
# tên "giongtoi", hoặc cài gh rồi `gh auth login` — script sẽ tự tạo.
set -euo pipefail
cd "$(dirname "$0")/.."
REMOTE="${GIONGTOI_REMOTE:-git@github.com:tienluils1996/giongtoi.git}"
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$REMOTE"
if ! git ls-remote origin >/dev/null 2>&1; then
  if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
    gh repo create tienluils1996/giongtoi --private --description "GiọngTôi — clone giọng nói, đọc tiếng Việt offline trên macOS"
  else
    echo "Repo chưa tồn tại. Tạo repo private tên 'giongtoi' tại https://github.com/new rồi chạy lại."; exit 1
  fi
fi
git push -u origin main

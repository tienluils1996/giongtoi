#!/usr/bin/env bash
# Tạo ~/Applications/GiọngTôi.app — bấm đúp để mở cửa sổ ứng dụng.
# - Dùng applet AppleScript (macOS mới không mở bundle có executable là shell script).
# - Chạy bản sao GiọngTôi cài trong .venv để không cần quyền truy cập OneDrive.
#   Sau khi sửa code, chạy lại script này để cập nhật app.
set -euo pipefail
source "$(dirname "$0")/env.sh"
APP="$HOME/Applications/GiọngTôi.app"
SNAP="$GIONGTOI_DATA_DIR/app"
LOG="$GIONGTOI_DATA_DIR/app.log"
PY="$UV_PROJECT_ENVIRONMENT/bin/python"
[ -x "$PY" ] || "$GIONGTOI_ROOT/scripts/setup.sh"

# cập nhật bản sao GiọngTôi trong .venv (không editable → không đọc OneDrive khi chạy)
uv pip install --python "$PY" --no-deps --reinstall --no-cache "$GIONGTOI_ROOT" >/dev/null
mkdir -p "$SNAP"
cat > "$SNAP/launch.sh" <<LAUNCH
#!/bin/bash
cd "$GIONGTOI_DATA_DIR"
export GIONGTOI_DATA_DIR="$GIONGTOI_DATA_DIR"
exec "$PY" -m giongtoi.cli app >> "$LOG" 2>&1
LAUNCH
chmod +x "$SNAP/launch.sh"

mkdir -p "$HOME/Applications"
rm -rf "$APP"
osacompile -o "$APP" -e "do shell script quoted form of \"$SNAP/launch.sh\" & \" > /dev/null 2>&1 &\""
PL="$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleName GiọngTôi" "$PL"
/usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string GiọngTôi" "$PL" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string local.giongtoi.app" "$PL" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier local.giongtoi.app" "$PL"
/usr/libexec/PlistBuddy -c "Add :NSMicrophoneUsageDescription string GiọngTôi cần micro để ghi âm mẫu giọng của bạn." "$PL" 2>/dev/null || true
[ -f "$GIONGTOI_ROOT/assets/AppIcon.icns" ] && cp "$GIONGTOI_ROOT/assets/AppIcon.icns" "$APP/Contents/Resources/applet.icns"
codesign --force --deep -s - "$APP" >/dev/null 2>&1 || true
echo "✓ Đã tạo $APP (log: $LOG)"

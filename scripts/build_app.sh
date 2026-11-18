#!/usr/bin/env bash
# Tạo ~/Applications/GiọngTôi.app — bấm đúp để mở cửa sổ ứng dụng.
set -euo pipefail
source "$(dirname "$0")/env.sh"
APP="$HOME/Applications/GiọngTôi.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>GiọngTôi</string>
  <key>CFBundleDisplayName</key><string>GiọngTôi</string>
  <key>CFBundleIdentifier</key><string>local.giongtoi.app</string>
  <key>CFBundleVersion</key><string>0.1.0</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundleExecutable</key><string>GiongToi</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>GiọngTôi cần micro để ghi âm mẫu giọng của bạn.</string>
</dict></plist>
PLIST
cat > "$APP/Contents/MacOS/GiongToi" <<LAUNCH
#!/bin/bash
mkdir -p "\$HOME/VoiceCloneData"
exec "$GIONGTOI_ROOT/scripts/run.sh" app >> "\$HOME/VoiceCloneData/app.log" 2>&1
LAUNCH
chmod +x "$APP/Contents/MacOS/GiongToi"
if [ -f "$GIONGTOI_ROOT/assets/AppIcon.icns" ]; then
  cp "$GIONGTOI_ROOT/assets/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
fi
echo "✓ Đã tạo $APP"

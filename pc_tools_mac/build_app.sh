#!/bin/bash
# 生成可被 Spotlight 打开的 AppleScript 应用（真 Mach-O，不是 shell 假包）。
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
APP="$ROOT/爱奇艺Mac小工具.app"

osacompile -o "$TMP/launcher.app" <<'APPLESCRIPT'
on run
  set appPath to POSIX path of (path to me)
  if appPath ends with "/" then set appPath to text 1 thru -2 of appPath
  set AppleScript's text item delimiters to "/"
  set bits to text items of appPath
  set bits to items 1 thru -2 of bits
  set AppleScript's text item delimiters to "/"
  set toolRoot to bits as text
  if toolRoot does not start with "/" then set toolRoot to "/" & toolRoot
  set py to "/opt/homebrew/bin/python3.13"
  set mainPy to toolRoot & "/main.py"
  do shell script "cd " & quoted form of toolRoot & " && export PYTHONPATH=" & quoted form of toolRoot & " && " & quoted form of py & " " & quoted form of mainPy
end run
APPLESCRIPT

rm -rf "$APP"
mv "$TMP/launcher.app" "$APP"

# 图标
if [ -f "$ROOT/pc_tools.ico" ]; then
  mkdir -p "$TMP/icon.iconset"
  sips -s format png "$ROOT/pc_tools.ico" --out "$TMP/icon.png" >/dev/null
  for s in 16 32 128 256 512; do
    sips -z $s $s "$TMP/icon.png" --out "$TMP/icon.iconset/icon_${s}x${s}.png" >/dev/null
    d=$((s * 2))
    sips -z $d $d "$TMP/icon.png" --out "$TMP/icon.iconset/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$TMP/icon.iconset" -o "$APP/Contents/Resources/applet.icns"
fi

/usr/libexec/PlistBuddy -c "Set :CFBundleName 爱奇艺Mac小工具" "$APP/Contents/Info.plist" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName 爱奇艺Mac小工具" "$APP/Contents/Info.plist" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.iqiyi.pc-tools-mac" "$APP/Contents/Info.plist" 2>/dev/null || true

xattr -cr "$APP" 2>/dev/null || true
codesign --force --sign - "$APP" >/dev/null
chmod -R a+rX "$APP"
rm -rf "$TMP"
echo "built $APP"

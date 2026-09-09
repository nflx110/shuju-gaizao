#!/bin/bash
cd "$(dirname "$0")"
# GitHub / 浏览器下载会带隔离属性；只清启动相关文件，不要扫 Package/
xattr -cr "启动.command" "爱奇艺Mac小工具.app" main.py tools 2>/dev/null || true
chmod +x "启动.command" "爱奇艺Mac小工具.app/Contents/MacOS/applet" 2>/dev/null || true
if [ -d "爱奇艺Mac小工具.app" ]; then
  codesign --force --sign - "爱奇艺Mac小工具.app" >/dev/null 2>&1 || true
fi

export PYTHONPATH="$(pwd):$PYTHONPATH"

BREW_PY="/opt/homebrew/bin/python3.13"
if [ -x "$BREW_PY" ]; then
  exec "$BREW_PY" main.py
fi

osascript -e 'display dialog "需要 Homebrew Python 3.13（带 Tk）。请先执行：\nbrew install python@3.13 python-tk@3.13" buttons {"好"} default button 1'
exit 1

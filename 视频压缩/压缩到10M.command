#!/bin/bash
cd "$(dirname "$0")"
xattr -cr "压缩到10M.command" app.py 2>/dev/null || true
chmod +x "压缩到10M.command" 2>/dev/null || true

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "正在安装 ffmpeg（首次需要）…"
  if ! command -v brew >/dev/null 2>&1; then
    osascript -e 'display dialog "需要先安装 Homebrew，再执行：\nbrew install ffmpeg" buttons {"好"} default button 1'
    exit 1
  fi
  brew install ffmpeg || {
    osascript -e 'display dialog "ffmpeg 安装失败，请在终端手动执行：\nbrew install ffmpeg" buttons {"好"} default button 1'
    exit 1
  }
fi

BREW_PY="/opt/homebrew/bin/python3.13"
if [ -x "$BREW_PY" ]; then
  exec "$BREW_PY" app.py
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 app.py
fi

osascript -e 'display dialog "需要 Homebrew Python 3.13（带 Tk）。请先执行：\nbrew install python@3.13 python-tk@3.13" buttons {"好"} default button 1'
exit 1

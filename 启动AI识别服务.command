#!/bin/bash
cd "$(dirname "$0")"
echo "安装依赖（首次需要）…"
npm install
echo ""
echo "启动后用浏览器打开提示的地址。"
echo "建议设置：export CURSOR_API_KEY=你的密钥"
echo ""
node shot_ai_server.mjs
read -n 1 -s -r -p "按任意键关闭…"

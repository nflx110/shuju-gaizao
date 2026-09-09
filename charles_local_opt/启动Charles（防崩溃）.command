#!/bin/zsh
# 本机优化启动 Charles：限制 Java 堆、清理旧证书、避免会话无限涨内存。
cd "$(dirname "$0")"
/usr/bin/python3 optimize_charles.py
echo ""
echo "窗口可关闭。"
read -r "?按回车退出 "

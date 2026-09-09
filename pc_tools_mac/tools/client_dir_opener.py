# -*- coding: utf-8 -*-
from tkinter import messagebox
from tools.public_tool import get_client_install_dir, open_folder


def open_install_dir() -> None:
    """打开客户端安装目录。"""
    try:
        install_dir = get_client_install_dir()
        open_folder(install_dir)
    except Exception as e:
        messagebox.showerror("错误", f"无法打开客户端安装目录: {e}")

# -*- coding: utf-8 -*-
from tools.public_tool import get_lstyle_dir, open_folder
import os
from tkinter import messagebox


def open_appdata_dir() -> None:
    """打开 LStyle / AppData 目标目录。"""
    try:
        lstyle_dir = get_lstyle_dir()
        if not os.path.exists(lstyle_dir):
            messagebox.showwarning("提示", f"目录不存在：{lstyle_dir}")
            return
        open_folder(lstyle_dir)
    except Exception as e:
        messagebox.showerror("错误", f"无法打开AppData目录: {e}")

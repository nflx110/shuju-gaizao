# -*- coding: utf-8 -*-
import os
import tkinter as tk
from tkinter import ttk
from tools.logconfig_tool import execute as write_logconfig
from tools.public_tool import (
    UI_FONT,
    kill_pc_process,
    get_iqiyi_data_dir,
    get_lstyle_dir,
    delete_dir_files,
    calculate_dpi_scaled_size,
)


class ClientCacheCleaner:
    def __init__(self, root):
        self.root = root
        self.result = None
        self.create_dialog()

    def create_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("选择清理类型")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.update_idletasks()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()
        dialog_width = max(int(main_width * 0.55), 320)
        dialog_height = max(int(main_height * 0.42), 180)
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        x = main_x + (main_width - dialog_width) // 2
        y = main_y + (main_height - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        font = (UI_FONT, calculate_dpi_scaled_size(11))
        ttk.Label(dialog, text="请选择要执行的清理操作：", font=font).pack(pady=(18, 12))
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=8)
        ttk.Button(
            btn_frame,
            text="清除全部缓存",
            style="TButton",
            command=lambda: self.on_select("all", dialog),
        ).pack(side="left", padx=8)
        ttk.Button(
            btn_frame,
            text="清除LWA缓存",
            command=lambda: self.on_select("lwa", dialog),
        ).pack(side="left", padx=8)
        dialog.update_idletasks()
        dialog.lift()
        dialog.focus_force()
        dialog.wait_window()

    def on_select(self, choice, dialog):
        self.result = choice
        dialog.destroy()

    def execute_cleanup(self):
        if self.result is None:
            return False, "cancelled"
        kill_pc_process()
        try:
            if self.result == "all":
                appdata_dir = get_iqiyi_data_dir()
                lstyle_dir = get_lstyle_dir()
                delete_dir_files(appdata_dir)
                os.makedirs(lstyle_dir, exist_ok=True)
                write_logconfig()
                return True, "全部缓存清除完成"
            appdata_dir = get_iqiyi_data_dir()
            if not appdata_dir:
                return False, "无法获取AppData目录"
            lstyle_dir = get_lstyle_dir()
            lwa_cache_path = os.path.join(lstyle_dir, "cache")
            if os.path.exists(lwa_cache_path):
                delete_dir_files(lwa_cache_path)
                return True, "LWA缓存清除完成"
            return True, "LWA缓存不存在，无需清理"
        except Exception as e:
            return False, f"清除失败: {e}"

    @staticmethod
    def execute(root):
        cleaner = ClientCacheCleaner(root)
        return cleaner.execute_cleanup()

# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox
from tools.public_tool import (
    UI_FONT,
    kill_pc_process,
    calculate_dpi_scaled_size,
    show_progress_window,
    open_client,
)
from tools.mac_packages import (
    CHANNELS,
    develop_channel_path,
    format_jfrog_time,
    list_versions,
    download_and_install,
)


class PackageVersionSelector:
    """Mac 安装包版本选择：develop 下 Trunk / Release / AppStore。"""

    def __init__(self, parent_window):
        self.parent = parent_window
        self.dialog = None
        self.version_ids = []

    def show(self):
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("选择 Mac 客户端安装包")
        self.parent.update_idletasks()
        window_width = max(int(self.parent.winfo_width() * 0.95), 720)
        window_height = max(int(self.parent.winfo_height() * 0.95), 480)
        self.dialog.geometry(f"{window_width}x{window_height}")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        font = (UI_FONT, calculate_dpi_scaled_size(12))
        style = ttk.Style(self.dialog)
        style.configure(
            "LargeTitle.TLabelframe.Label",
            font=(UI_FONT, calculate_dpi_scaled_size(12)),
        )

        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        split_frame = ttk.Frame(main_frame)
        split_frame.pack(fill="both", expand=True)
        split_frame.grid_rowconfigure(0, weight=1)
        split_frame.grid_columnconfigure(0, weight=1)
        split_frame.grid_columnconfigure(1, weight=2)

        left_box = ttk.LabelFrame(split_frame, text="包类型", style="LargeTitle.TLabelframe")
        right_box = ttk.LabelFrame(split_frame, text="构建版本", style="LargeTitle.TLabelframe")
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        right_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        left_box.grid_rowconfigure(0, weight=1)
        left_box.grid_columnconfigure(0, weight=1)
        right_box.grid_rowconfigure(0, weight=1)
        right_box.grid_columnconfigure(0, weight=1)

        self.type_list = tk.Listbox(
            left_box,
            font=font,
            exportselection=False,
            highlightthickness=0,
            selectmode="browse",
        )
        type_scroll = tk.Scrollbar(left_box, orient="vertical", command=self.type_list.yview, width=14)
        self.type_list.configure(yscrollcommand=type_scroll.set)
        self.type_list.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        type_scroll.grid(row=0, column=1, sticky="ns", pady=6, padx=(0, 6))

        self.ver_list = tk.Listbox(
            right_box,
            font=font,
            exportselection=False,
            highlightthickness=0,
            selectmode="browse",
        )
        ver_scroll = tk.Scrollbar(right_box, orient="vertical", command=self.ver_list.yview, width=14)
        self.ver_list.configure(yscrollcommand=ver_scroll.set)
        self.ver_list.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        ver_scroll.grid(row=0, column=1, sticky="ns", pady=6, padx=(0, 6))

        labels = {
            "Trunk": "Trunk（测试包）",
            "Release": "Release（正式包）",
            "AppStore": "AppStore",
        }
        for ch in CHANNELS:
            self.type_list.insert("end", labels[ch])
        self.type_list.selection_set(0)
        self.type_list.bind("<<ListboxSelect>>", self._on_type_selected)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=8)
        ttk.Button(btn_frame, text="安装", command=self._install_selected_package).pack(
            side="right", padx=6
        )
        ttk.Button(btn_frame, text="取消", command=self.dialog.destroy).pack(side="right", padx=6)
        self._load_versions(CHANNELS[0])
        self.dialog.wait_window()

    def _selected_channel(self) -> str:
        sel = self.type_list.curselection()
        if not sel:
            return ""
        return CHANNELS[sel[0]]

    def _on_type_selected(self, _event=None):
        ch = self._selected_channel()
        if ch:
            self._load_versions(ch)

    def _load_versions(self, channel: str):
        self.ver_list.delete(0, "end")
        self.version_ids = []
        try:
            versions = list_versions(develop_channel_path(channel))
        except Exception as e:
            messagebox.showerror("错误", f"获取版本列表失败: {e}")
            return
        for item in versions:
            version = (item.get("name") or "").rstrip("/")
            if not version:
                continue
            dt = format_jfrog_time(item.get("lastModified"))
            display = f"{version}  ({dt})" if dt else version
            self.ver_list.insert("end", display)
            self.version_ids.append(version)
        if self.version_ids:
            self.ver_list.selection_set(0)
            self.ver_list.see(0)

    def _install_selected_package(self):
        major = self._selected_channel()
        sel = self.ver_list.curselection()
        if not major or not sel:
            messagebox.showerror("错误", "请选择完整的版本信息")
            return
        minor = self.version_ids[sel[0]]
        if not messagebox.askyesno("确认安装", f"确定要安装 {major} / {minor} 吗？"):
            return

        def install_task(progress):
            try:
                kill_pc_process()
                return download_and_install(
                    develop_channel_path(major), minor, major, progress=progress
                )
            except Exception as e:
                return False, str(e)

        res, err = show_progress_window(self.dialog, "安装", install_task)
        if err:
            messagebox.showerror("错误", f"安装客户端失败: {err}")
            return
        ok, msg = res if isinstance(res, tuple) else (False, str(res))
        if not ok:
            messagebox.showerror("错误", f"安装客户端失败: {msg}")
            return
        if isinstance(msg, str) and msg.endswith(".app"):
            if messagebox.askyesno("确认", "安装完成, 是否打开客户端?"):
                open_client()
        elif msg:
            messagebox.showinfo("提示", msg)
        self.dialog.destroy()


def show_package_version_selector(parent_window):
    selector = PackageVersionSelector(parent_window)
    selector.show()

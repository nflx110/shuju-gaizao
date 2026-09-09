# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.ttk import Style
from tools.public_tool import UI_FONT, calculate_dpi_scaled_size
from tools.mac_packages import CHANNELS, develop_channel_path, latest_version, install_latest


def show_install_selection_dialog(parent_window):
    selected = {"branch": None}
    dialog = tk.Toplevel(parent_window)
    dialog.title("选择安装类型")
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    window_width = 460
    window_height = 300
    dialog.geometry(
        f"{window_width}x{window_height}+{(screen_width - window_width) // 2}+{(screen_height - window_height) // 2}"
    )
    dialog.transient(parent_window)
    dialog.grab_set()
    dialog.resizable(False, False)
    font = (UI_FONT, calculate_dpi_scaled_size(11))
    style = Style(dialog)
    style.configure("Large.TRadiobutton", font=font)

    install_type = tk.StringVar(value="Trunk")
    dates = {}
    for ch in CHANNELS:
        try:
            ver, dt = latest_version(develop_channel_path(ch))
            dates[ch] = f"{ver} {dt}".strip()
        except Exception:
            dates[ch] = ""

    ttk.Radiobutton(
        dialog,
        text=f"1. 安装最新 Trunk 测试包 ({dates.get('Trunk', '')})",
        variable=install_type,
        value="Trunk",
        style="Large.TRadiobutton",
    ).pack(anchor="w", padx=16, pady=4)
    ttk.Radiobutton(
        dialog,
        text=f"2. 安装最新 Release 正式包 ({dates.get('Release', '')})",
        variable=install_type,
        value="Release",
        style="Large.TRadiobutton",
    ).pack(anchor="w", padx=16, pady=4)
    ttk.Radiobutton(
        dialog,
        text="3. 手动输入 git 分支",
        variable=install_type,
        value="custom",
        style="Large.TRadiobutton",
    ).pack(anchor="w", padx=16, pady=4)

    branch_frame = ttk.Frame(dialog)
    branch_frame.pack(fill="x", padx=24, pady=4)
    ttk.Label(branch_frame, text="分支(如 PCAAPP-6132):").pack(side="left")
    branch_var = tk.StringVar()
    branch_entry = ttk.Entry(branch_frame, textvariable=branch_var, state="disabled")
    branch_entry.pack(side="left", fill="x", expand=True, padx=8)

    def toggle_branch_entry(*args):
        if install_type.get() == "custom":
            branch_entry.config(state="normal")
            branch_entry.focus()
        else:
            branch_entry.config(state="disabled")

    install_type.trace_add("write", toggle_branch_entry)

    def on_confirm():
        selected_type = install_type.get()
        if selected_type == "custom":
            branch = branch_var.get().strip()
            if not branch:
                messagebox.showerror("错误", "请输入分支名称")
                return
            selected["branch"] = branch
        else:
            selected["branch"] = selected_type
        dialog.destroy()

    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(pady=12)
    ttk.Button(btn_frame, text="确认", command=on_confirm).pack(side="left", padx=8)
    ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side="left", padx=8)
    parent_window.update_idletasks()
    dialog.wait_window()
    return selected["branch"]


def install_latest_package(branch: str, progress=None):
    try:
        return install_latest(branch, progress=progress)
    except Exception as e:
        return False, str(e)

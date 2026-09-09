# -*- coding: utf-8 -*-
"""爱奇艺 Mac 小工具。"""
import os
import sys
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.public_tool import (
    show_loading_window,
    show_progress_window,
    tool_root,
    open_client,
    kill_pc_process,
    restart_client,
    bind_mousewheel,
)

UI_FONT = "PingFang SC"
BG = "#E8F8EF"
CARD = "#FFFFFF"
TEXT = "#163326"
MUTED = "#4E7A62"
HEADER_TOP = "#00C853"
HEADER_BOT = "#00A83E"
TILE_W = 168
TILE_H = 82


def _mix_hex(color: str, other: str = "#FFFFFF", ratio: float = 0.18) -> str:
    def to_rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))

    a, b = to_rgb(color), to_rgb(other)
    rgb = tuple(int(a[i] * (1 - ratio) + b[i] * ratio) for i in range(3))
    return "#{:02X}{:02X}{:02X}".format(*rgb)


class ActionTile(tk.Frame):
    """固定尺寸彩色卡片，只有卡片本身可点。"""

    def __init__(self, parent, title, subtitle, command, accent="#00C853"):
        super().__init__(parent, bg=BG, width=TILE_W, height=TILE_H)
        self.pack_propagate(False)
        self._command = command
        self._busy = False
        self._accent = accent
        self._hover = _mix_hex(accent, "#FFFFFF", 0.82)
        self._card = CARD
        self._inner = tk.Frame(self, bg=CARD, highlightthickness=0)
        self._inner.pack(fill="both", expand=True)
        self._stripe = tk.Frame(self._inner, bg=accent, width=6)
        self._stripe.pack(side="left", fill="y")
        self._body = tk.Frame(self._inner, bg=CARD)
        self._body.pack(side="left", fill="both", expand=True)
        self._title = tk.Label(
            self._body,
            text=title,
            bg=CARD,
            fg=TEXT,
            font=(UI_FONT, 13, "bold"),
            anchor="w",
        )
        self._sub = tk.Label(
            self._body,
            text=subtitle,
            bg=CARD,
            fg=MUTED,
            font=(UI_FONT, 10),
            anchor="w",
            wraplength=140,
            justify="left",
        )
        self._title.pack(fill="x", padx=10, pady=(14, 0))
        self._sub.pack(fill="x", padx=10, pady=(2, 0))
        for w in (self, self._inner, self._stripe, self._body, self._title, self._sub):
            w.bind("<Button-1>", self._on_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _paint(self, bg):
        self._inner.configure(bg=bg)
        self._body.configure(bg=bg)
        self._title.configure(bg=bg)
        self._sub.configure(bg=bg)

    def _on_enter(self, _event=None):
        if not self._busy:
            self._paint(self._hover)
            self.configure(cursor="hand2")

    def _on_leave(self, _event=None):
        self._paint(self._card)

    def _on_click(self, _event=None):
        if self._busy:
            return
        self._busy = True
        self._paint(_mix_hex(self._accent, "#FFFFFF", 0.7))
        try:
            self._command()
        finally:
            self.after(280, self._unlock)

    def _unlock(self):
        self._busy = False
        self._paint(self._card)


class ToolboxApp:
    def __init__(self, root):
        self.root = root
        self.root.title("爱奇艺 Mac 小工具")
        self.root.configure(bg=BG)
        self.set_main_window_size()
        self.set_window_icon()
        self.create_main_interface()

    def set_main_window_size(self):
        width, height = 760, 620
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 4
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(720, 520)

    def set_window_icon(self):
        icon_path = os.path.join(tool_root(), "pc_tools.ico")
        try:
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

    def create_main_interface(self):
        header = tk.Frame(self.root, bg=HEADER_TOP, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)
        bar = tk.Frame(header, bg="#FFD54F", height=4)
        bar.pack(fill="x", side="bottom")
        tk.Label(
            header,
            text="爱奇艺 Mac 小工具",
            bg=HEADER_TOP,
            fg="#FFFFFF",
            font=(UI_FONT, 18, "bold"),
        ).pack(side="left", padx=20, pady=(8, 4))
        tk.Label(
            header,
            text="v0.95-mac",
            bg=HEADER_TOP,
            fg="#E8FFE8",
            font=(UI_FONT, 11),
        ).pack(side="right", padx=20, pady=(8, 4))

        footer = tk.Label(
            self.root,
            text="包地址  iqiyi-generic-pca-ci/mac/develop",
            bg=BG,
            fg="#2E7D4F",
            font=(UI_FONT, 10),
            anchor="w",
        )
        footer.pack(fill="x", side="bottom", padx=20, pady=(0, 12))

        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(wrap, orient="vertical", command=canvas.yview, width=14)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=BG)
        body_id = canvas.create_window((0, 0), window=body, anchor="nw")

        def _on_body(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas(event):
            canvas.itemconfigure(body_id, width=event.width)

        body.bind("<Configure>", _on_body)
        canvas.bind("<Configure>", _on_canvas)
        bind_mousewheel(canvas, canvas)
        bind_mousewheel(body, canvas)

        groups = [
            (
                "客户端",
                "#00C853",
                [
                    ("安装目录", "打开 爱奇艺.app", self.open_client_dir, "#00C853"),
                    ("数据目录", "打开 LStyle", self.open_appdata_dir, "#00BFA5"),
                    ("环境信息", "版本 / 设备号 / hosts", self.get_env_info, "#66BB6A"),
                    ("LWA 包信息", "查看 current / dev 版本", self.open_lwa_replacer, "#26A69A"),
                    ("版本排期", "PC 迭代日历", self.open_version_calendar, "#3D8BFF"),
                ],
            ),
            (
                "日志与缓存",
                "#FF8A3D",
                [
                    ("拷贝日志", "导出到 Package", self.copy_logs, "#FF8A3D"),
                    ("删除日志", "清空 .log 文件", self.delete_logs, "#FF6F61"),
                    ("配置日志", "写入 logconfig.ini", self.config_logs, "#FFB300"),
                    ("清除缓存", "清理本地缓存", self.clear_client_cache, "#FF7043"),
                ],
            ),
            (
                "安装包",
                "#3D8BFF",
                [
                    ("安装最新包", "Trunk / Release", self.install_package, "#3D8BFF"),
                    ("选择安装包", "按构建版本安装", self.open_package_selector, "#00BCD4"),
                    ("卸载本地包", "删除 爱奇艺.app", self.uninstall_local, "#FF6F61"),
                    ("退出客户端", "结束本地进程", self.quit_client, "#FF8A3D"),
                    ("重启客户端", "退出后再打开", self.restart_local, "#00C853"),
                ],
            ),
            (
                "后端",
                "#A855F7",
                [
                    ("接口签名", "计算 sign", self.calculate_signature, "#A855F7"),
                    ("QAMP 数量", "拉取监控用例", self.open_qamp_monitor, "#EC4899"),
                ],
            ),
        ]
        for title, color, actions in groups:
            self._add_group(body, title, color, actions)

        tk.Frame(body, bg=BG, height=8).pack(fill="x")

    def _add_group(self, parent, title, color, actions):
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="x", padx=20, pady=(12, 2))
        title_row = tk.Frame(wrap, bg=BG)
        title_row.pack(fill="x", pady=(0, 8))
        tk.Frame(title_row, bg=color, width=8, height=16).pack(side="left", padx=(0, 8))
        tk.Label(
            title_row,
            text=title,
            bg=BG,
            fg=color,
            font=(UI_FONT, 12, "bold"),
            anchor="w",
        ).pack(side="left")
        row = tk.Frame(wrap, bg=BG)
        row.pack(fill="x")
        for i, (name, subtitle, command, accent) in enumerate(actions):
            tile = ActionTile(row, name, subtitle, command, accent)
            tile.grid(row=i // 4, column=i % 4, padx=(0, 10), pady=(0, 8), sticky="nw")

    def open_client_dir(self):
        from tools.client_dir_opener import open_install_dir

        open_install_dir()

    def open_appdata_dir(self):
        from tools.appdata_dir_opener import open_appdata_dir

        open_appdata_dir()

    def open_lwa_replacer(self):
        from tools.lwa_replacer import LWAReplacerWindow

        LWAReplacerWindow(self.root)

    def open_version_calendar(self):
        from tools.version_calendar import show_version_calendar

        show_version_calendar(self.root)

    def uninstall_local(self):
        from tools.mac_packages import uninstall_local_app

        if not messagebox.askyesno("确认卸载", "将结束进程并删除 /Applications 里的爱奇艺.app，确定吗？"):
            return
        ok, msg = uninstall_local_app()
        if ok:
            messagebox.showinfo("完成", msg)
        else:
            messagebox.showerror("失败", msg)

    def quit_client(self):
        if not messagebox.askyesno("确认退出", "结束本机爱奇艺客户端进程？"):
            return
        kill_pc_process()
        messagebox.showinfo("完成", "客户端已退出")

    def restart_local(self):
        if not messagebox.askyesno("确认重启", "退出后重新打开爱奇艺客户端？"):
            return
        restart_client()

    def copy_logs(self):
        from tools import log_copier

        res, err = show_loading_window(self.root, "拷贝日志中", log_copier.execute)
        if err:
            messagebox.showerror("错误", f"拷贝失败: {err}")
            return
        ok, msg = res if isinstance(res, tuple) else (False, str(res))
        if not ok:
            messagebox.showerror("错误", msg)

    def delete_logs(self):
        try:
            from tools import log_deleter

            res, err = show_loading_window(self.root, "删除日志", log_deleter.clear_log_files)
            if err:
                raise err
            messagebox.showinfo("成功", res or "日志删除完成")
        except Exception as e:
            messagebox.showerror("错误", f"删除日志失败: {e}")

    def config_logs(self):
        from tools.logconfig_tool import execute

        res, msg = execute()
        if res:
            messagebox.showinfo("成功", msg)
        else:
            messagebox.showerror("错误", msg)

    def install_package(self):
        try:
            from tools import package_installer

            branch = package_installer.show_install_selection_dialog(self.root)
            if not branch:
                return
            res, err = show_progress_window(
                self.root,
                f"安装 {branch} 分支包",
                lambda progress: package_installer.install_latest_package(branch, progress),
            )
            if err:
                raise err
            ok, msg = res if isinstance(res, tuple) else (False, str(res))
            if not ok:
                messagebox.showerror("错误", msg)
            elif isinstance(msg, str) and msg.endswith(".app"):
                if messagebox.askyesno("确认", "安装完成, 是否打开客户端?"):
                    open_client()
            elif msg:
                messagebox.showinfo("提示", msg)
        except Exception as e:
            messagebox.showerror("错误", f"安装客户端失败: {e}")

    def clear_client_cache(self):
        from tools.client_cache_cleaner import ClientCacheCleaner

        cleaner = ClientCacheCleaner(self.root)
        if cleaner.result is None:
            return
        res, err = show_loading_window(self.root, "清除客户端缓存", cleaner.execute_cleanup)
        if err:
            messagebox.showerror("错误", f"清除客户端缓存失败: {err}")
            return
        ok, msg = res if isinstance(res, tuple) else (False, str(res))
        if msg == "cancelled":
            return
        if not ok:
            messagebox.showerror("错误", f"清除客户端缓存失败: {msg}")
            return
        if messagebox.askyesno("确认", "清除缓存完成, 是否打开客户端？"):
            open_client()

    def open_package_selector(self):
        try:
            from tools.package_version_selector import show_package_version_selector

            show_package_version_selector(self.root)
        except Exception as e:
            messagebox.showerror("错误", f"打开客户端安装包选择器失败: {e}")

    def get_env_info(self):
        from tools.env_info import get_env_info

        get_env_info(self.root)

    def calculate_signature(self):
        from tools.sign_calculator import SignCalculatorWindow

        SignCalculatorWindow(self.root, "接口签名计算")

    def open_qamp_monitor(self):
        try:
            from tools.qamp_monitor_tool import calculate_monitor_count

            count, err = show_loading_window(
                self.root, "获取QAMP监控数量", calculate_monitor_count
            )
            if err:
                raise err
            messagebox.showinfo("成功", f"监控数量 {count} 条")
        except Exception as e:
            messagebox.showerror("错误", f"获取监控数量失败: {e}")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    root = tk.Tk()
    ToolboxApp(root)
    root.mainloop()

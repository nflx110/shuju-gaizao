#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""贴在 Charles 工具栏空位上的一键开关：Rewrite / Map / DNS / 断点。

通过 Charles 官方 Web Interface（http://control.charles）开关工具，不改官方 app。
"""

from __future__ import annotations

import subprocess
import sys
import time
import tkinter as tk
import urllib.error
import urllib.request
from dataclasses import dataclass

PROXY_PORT = 8888
CONTROL = "http://control.charles"
POLL_MS = 1200
BAR_H = 30
OFFSET_X = 208
RIGHT_MARGIN = 168
OFFSET_Y = 38

ON_BG, ON_FG = "#2F6FED", "#FFFFFF"
OFF_BG, OFF_FG = "#E4E4E4", "#333333"
BAR_BG = "#F2F2F2"
MUTED = "#888888"


@dataclass(frozen=True)
class Tool:
    label: str
    path: str  # /tools/rewrite


TOOLS = (
    Tool("Rewrite", "/tools/rewrite"),
    Tool("Map远程", "/tools/map-remote"),
    Tool("Map本地", "/tools/map-local"),
    Tool("DNS", "/tools/dns-spoofing"),
    Tool("断点", "/tools/breakpoints"),
)


def opener() -> urllib.request.OpenerDirector:
    proxy = f"http://127.0.0.1:{PROXY_PORT}"
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    )


def fetch(path: str, timeout: float = 2.0) -> str:
    url = CONTROL + path
    req = urllib.request.Request(url, headers={"User-Agent": "charles-local-opt"})
    with opener().open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def parse_enabled(html: str) -> bool | None:
    low = html.lower()
    if "web interface is disabled" in low:
        return None
    if "status: enabled" in low:
        return True
    if "status: disabled" in low:
        return False
    return None


def tool_enabled(path: str) -> bool | None:
    try:
        return parse_enabled(fetch(path + "/"))
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def set_tool(path: str, enable: bool) -> None:
    suffix = "/enable" if enable else "/disable"
    fetch(path + suffix)


def charles_bounds() -> tuple[int, int, int, int] | None:
    script = """
    tell application "System Events"
      if not (exists process "Charles") then return ""
      tell process "Charles"
        if (count of windows) is 0 then return ""
        set pos to position of window 1
        set sz to size of window 1
        return (item 1 of pos as integer as text) & "," & (item 2 of pos as integer as text) & "," & (item 1 of sz as integer as text) & "," & (item 2 of sz as integer as text)
      end tell
    end tell
    """
    try:
        out = subprocess.check_output(
            ["osascript", "-e", script], text=True, timeout=1.5
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    if not out or "," not in out:
        return None
    try:
        x, y, w, h = (int(float(p)) for p in out.split(","))
        if w < 200 or h < 80:
            return None
        return x, y, w, h
    except ValueError:
        return None


def charles_running() -> bool:
    try:
        subprocess.check_call(
            ["pgrep", "-f", "/Applications/Charles.app/Contents/MacOS/Charles"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


class ToggleBar:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Charles 开关")
        self.root.configure(bg=BAR_BG)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        # macOS Tk 需要先隐藏再去标题栏，否则会留下系统标题占高
        self.root.withdraw()
        try:
            self.root.tk.call(
                "::tk::unsupported::MacWindowStyle",
                "style",
                self.root._w,
                "plain",
                "noTitleBar",
            )
        except tk.TclError:
            pass
        try:
            self.root.overrideredirect(True)
        except tk.TclError:
            pass
        self.root.deiconify()

        self.frame = tk.Frame(self.root, bg=BAR_BG, padx=4, pady=2)
        self.frame.pack(fill="both", expand=True)

        self.grip = tk.Label(
            self.frame, text="⋮⋮", bg=BAR_BG, fg=MUTED, font=("Menlo", 11), cursor="hand2"
        )
        self.grip.pack(side="left", padx=(0, 4))
        self.grip.bind("<ButtonPress-1>", self._start_drag)
        self.grip.bind("<B1-Motion>", self._on_drag)
        self.grip.bind("<Double-Button-1>", self._toggle_follow)

        self.status = tk.Label(
            self.frame, text="连接中", bg=BAR_BG, fg=MUTED, font=("PingFang SC", 10)
        )
        self.status.pack(side="right", padx=(6, 2))

        self.buttons: dict[str, tk.Label] = {}
        self.states: dict[str, bool | None] = {t.path: None for t in TOOLS}
        self.follow = True
        self.drag_x = 0
        self.drag_y = 0
        self.missing_since: float | None = None

        for tool in TOOLS:
            btn = tk.Label(
                self.frame,
                text=tool.label,
                font=("PingFang SC", 11, "bold"),
                padx=8,
                pady=3,
                cursor="hand2",
                bg=OFF_BG,
                fg=OFF_FG,
            )
            btn.pack(side="left", padx=2)
            btn.bind("<Button-1>", lambda e, t=tool: self._clicked(t))
            self.buttons[tool.path] = btn

        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.after(400, self._tick)

    def _start_drag(self, event: tk.Event) -> None:
        self.follow = False
        self.drag_x = event.x_root - self.root.winfo_x()
        self.drag_y = event.y_root - self.root.winfo_y()

    def _on_drag(self, event: tk.Event) -> None:
        x = event.x_root - self.drag_x
        y = event.y_root - self.drag_y
        self.root.geometry(f"+{x}+{y}")

    def _toggle_follow(self, _event: tk.Event) -> None:
        self.follow = not self.follow
        self.status.config(text="跟随开" if self.follow else "已解锁，可拖")

    def _paint(self, path: str, on: bool | None) -> None:
        btn = self.buttons[path]
        if on is True:
            btn.config(bg=ON_BG, fg=ON_FG)
        else:
            btn.config(bg=OFF_BG, fg=OFF_FG)

    def _clicked(self, tool: Tool) -> None:
        cur = self.states.get(tool.path)
        if cur is None:
            # 未知时默认去打开
            want = True
        else:
            want = not cur
        try:
            set_tool(tool.path, want)
            self.states[tool.path] = want
            self._paint(tool.path, want)
            self.status.config(text=("已开" if want else "已关") + " " + tool.label, fg="#1B7A3A")
        except Exception as exc:
            self.status.config(text=f"失败：{exc.__class__.__name__}", fg="#B42318")

    def _dock(self) -> None:
        if not self.follow:
            return
        bounds = charles_bounds()
        if not bounds:
            return
        x, y, w, _h = bounds
        bar_w = max(420, w - OFFSET_X - RIGHT_MARGIN)
        bar_w = min(bar_w, 560)
        bx = x + OFFSET_X
        by = y + OFFSET_Y
        self.root.geometry(f"{bar_w}x{BAR_H}+{bx}+{by}")

    def _tick(self) -> None:
        running = charles_running()
        if not running:
            if self.missing_since is None:
                self.missing_since = time.time()
                self.status.config(text="Charles 未开", fg="#B42318")
            elif time.time() - self.missing_since > 10:
                self.root.destroy()
                return
            self.root.after(POLL_MS, self._tick)
            return
        self.missing_since = None
        self._dock()

        any_ok = False
        disabled_ui = False
        for tool in TOOLS:
            state = tool_enabled(tool.path)
            if state is None:
                html_fail = True
            else:
                html_fail = False
                any_ok = True
            if state is None:
                # 分辨是接口没开还是工具页异常：只查一次 rewrite 文案不够，用状态字
                pass
            self.states[tool.path] = state
            self._paint(tool.path, state)

        if any_ok:
            self.status.config(text="蓝=开  灰=关  双击⋮跟随", fg=MUTED)
        else:
            # 再确认是不是 Web Interface 关闭
            try:
                html = fetch("/")
                if "disabled" in html.lower():
                    disabled_ui = True
            except Exception:
                disabled_ui = False
            if disabled_ui:
                self.status.config(text="请先开 Proxy → Web Interface", fg="#B42318")
            else:
                self.status.config(text="等待 Charles…", fg=MUTED)

        self.root.after(POLL_MS, self._tick)

    def run(self) -> None:
        self.root.geometry(f"520x{BAR_H}+200+80")
        self.root.mainloop()


def main() -> int:
    # 等 Charles 起来
    for _ in range(40):
        if charles_running():
            break
        time.sleep(0.25)
    ToggleBar().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""跨平台公共方法。Mac 上对接爱奇艺客户端，Windows 行为保持兼容。"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Callable, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk

JFROG_BASE_URL = "http://jfrog.cloud.qiyi.domain/"
UI_FONT = "PingFang SC" if sys.platform == "darwin" else "SimHei"

MAC_APP_CANDIDATES = (
    "/Applications/爱奇艺.app",
    "/Applications/iQIYI.app",
    "/Applications/Iqiyi.app",
)


def _is_mac() -> bool:
    return sys.platform == "darwin"


def kill_pc_process() -> None:
    """结束爱奇艺客户端相关进程。"""
    if _is_mac():
        names = ("qiyimac", "爱奇艺", "iQIYI")
        for name in names:
            try:
                subprocess.run(
                    ["killall", "-9", name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception as e:
                print(f"终止进程 {name} 失败: {e}")
        try:
            subprocess.run(
                ["osascript", "-e", 'quit app "爱奇艺"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass
        time.sleep(0.4)
        return

    processes_to_kill = [
        "QiyiService.exe",
        "WebView2Ready.exe",
        "QyClient.exe",
        "QyFragment.exe",
        "QyKernel.exe",
        "QyPlayer.exe",
    ]
    for process in processes_to_kill:
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.run(
                ["taskkill", "/F", "/IM", process],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=flags,
            )
            service_name = process.replace(".exe", "")
            subprocess.run(
                ["sc", "stop", service_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=flags,
            )
        except Exception as e:
            print(f"终止进程 {process} 失败: {e}")


def get_dpi_scale_factor() -> float:
    if _is_mac():
        return 1.0
    try:
        import ctypes

        sys.getwindowsversion()
        try:
            ctypes.WinDLL("shcore").SetProcessDpiAwareness(1)
        except Exception as e:
            print(f"设置DPI感知失败: {e}")
        user32 = ctypes.windll.user32
        hdc = user32.GetDC(0)
        dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
        user32.ReleaseDC(0, hdc)
        return max(1.0, round(dpi_x / 96.0, 2))
    except Exception:
        return 1.0


def calculate_dpi_scaled_size(base_size: int) -> int:
    return int(round(base_size * get_dpi_scale_factor()))


def open_folder(path: str) -> Tuple[bool, str]:
    if not os.path.exists(path):
        return False, f"文件夹不存在: {path}"
    try:
        if _is_mac():
            subprocess.run(["open", path], check=True)
        elif os.name == "nt":
            subprocess.run(["explorer.exe", os.path.normpath(path)])
        else:
            subprocess.run(["xdg-open", path])
        return True, ""
    except Exception as e:
        return False, f"打开文件夹失败: {e}"


def show_progress_window(parent_window, title: str, target_func: Callable):
    """后台执行 target_func(progress)，progress(status=, current=, total=) 更新进度。"""
    result_holder = {"value": None, "error": None}
    parent_width = max(parent_window.winfo_width(), 360)
    parent_height = max(parent_window.winfo_height(), 200)
    loading_width = max(int(parent_width * 0.55), 420)
    loading_height = max(int(parent_height * 0.32), 150)
    x = parent_window.winfo_x() + (parent_width - loading_width) // 2
    y = parent_window.winfo_y() + (parent_height - loading_height) // 2

    win = tk.Toplevel(parent_window)
    win.title(title)
    win.transient(parent_window)
    win.resizable(False, False)
    win.grab_set()
    win.geometry(f"{loading_width}x{loading_height}+{x}+{y}")

    frame = ttk.Frame(win)
    frame.pack(fill="both", expand=True, padx=18, pady=16)
    status_lbl = ttk.Label(frame, text="准备中…", font=(UI_FONT, calculate_dpi_scaled_size(12)))
    status_lbl.pack(anchor="w", pady=(4, 8))
    bar = ttk.Progressbar(frame, mode="determinate", maximum=100)
    bar.pack(fill="x")
    detail_lbl = ttk.Label(frame, text="", font=(UI_FONT, calculate_dpi_scaled_size(10)))
    detail_lbl.pack(anchor="w", pady=(8, 0))

    last_ui = {"t": 0.0}

    def progress(status: str = None, current: int = None, total: int = None):
        def apply():
            if status:
                status_lbl.config(text=status)
            if current is None:
                return
            if total and total > 0:
                try:
                    bar.stop()
                except Exception:
                    pass
                pct = min(100, int(current * 100 / total))
                bar.config(mode="determinate", maximum=100)
                bar["value"] = pct
                if total >= 1024:
                    detail_lbl.config(
                        text=f"{current / 1048576:.1f} / {total / 1048576:.1f} MB    {pct}%"
                    )
                else:
                    detail_lbl.config(text=f"{pct}%")
            else:
                bar.config(mode="indeterminate")
                try:
                    bar.start(12)
                except Exception:
                    pass

        now = time.time()
        done = bool(total and current is not None and current >= total)
        status_only = current is None
        if not done and not status_only and now - last_ui["t"] < 0.08:
            return
        last_ui["t"] = now
        try:
            win.after(0, apply)
        except Exception:
            pass

    def background_task():
        try:
            result_holder["value"] = target_func(progress)
        except Exception as e:
            result_holder["error"] = e
        finally:
            try:
                win.after(0, win.destroy)
            except Exception:
                pass

    threading.Thread(target=background_task, daemon=True).start()
    win.wait_window()
    return result_holder["value"], result_holder["error"]


def show_loading_window(parent_window, title: str, target_func: Callable, *args, **kwargs):
    """显示加载窗口并在后台执行目标函数，返回 (result, error)。"""
    result_holder = {"value": None, "error": None}

    parent_width = max(parent_window.winfo_width(), 300)
    parent_height = max(parent_window.winfo_height(), 200)
    loading_width = max(int(parent_width * 0.45), 280)
    loading_height = max(int(parent_height * 0.28), 120)
    parent_x = parent_window.winfo_x()
    parent_y = parent_window.winfo_y()
    x = parent_x + (parent_width - loading_width) // 2
    y = parent_y + (parent_height - loading_height) // 2

    win = tk.Toplevel(parent_window)
    win.title(title)
    win.transient(parent_window)
    win.resizable(False, False)
    win.grab_set()
    win.geometry(f"{loading_width}x{loading_height}+{x}+{y}")

    frame = ttk.Frame(win)
    frame.pack(fill="both", expand=True, padx=16, pady=16)
    ttk.Label(
        frame,
        text="处理中，请稍候...",
        font=(UI_FONT, calculate_dpi_scaled_size(12)),
    ).pack(pady=(8, 12))
    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.pack(fill="x")
    progress.start(10)

    def background_task():
        try:
            result_holder["value"] = target_func(*args, **kwargs)
        except Exception as e:
            result_holder["error"] = e
        finally:
            win.after(0, win.destroy)

    thread = threading.Thread(target=background_task, daemon=True)
    thread.start()
    win.wait_window()
    return result_holder["value"], result_holder["error"]


def get_appdata_dir() -> str:
    if _is_mac():
        return os.path.expanduser("~/Library/Application Support")
    return os.getenv("APPDATA") or ""


def get_lstyle_dir() -> str:
    if _is_mac():
        return os.path.join(get_appdata_dir(), "LStyle")
    base = get_appdata_dir()
    if not base:
        return ""
    return os.path.join(base, "IQIYI Video", "LStyle")


def get_iqiyi_data_dir() -> str:
    """Windows 上的 IQIYI Video 目录；Mac 上等价于 LStyle。"""
    if _is_mac():
        return get_lstyle_dir()
    base = get_appdata_dir()
    if not base:
        return ""
    return os.path.join(base, "IQIYI Video")


def get_client_install_dir() -> str:
    if _is_mac():
        for path in MAC_APP_CANDIDATES:
            if os.path.isdir(path):
                return path
        return ""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\App Paths\PPStream.exe",
        )
        value, _ = winreg.QueryValueEx(key, None)
        return os.path.dirname(value)
    except Exception:
        return ""


def get_client_version() -> str:
    install_dir = get_client_install_dir()
    if not install_dir:
        return ""
    if _is_mac():
        plist = os.path.join(install_dir, "Contents", "Info.plist")
        try:
            out = subprocess.check_output(
                ["defaults", "read", plist, "CFBundleShortVersionString"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            if out:
                return out
        except Exception:
            pass
        try:
            out = subprocess.check_output(
                ["defaults", "read", plist, "CFBundleVersion"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            if out:
                return out
        except Exception:
            pass
        return os.path.basename(install_dir)
    return os.path.basename(install_dir.rstrip("\\/"))


def get_mac_resources_dir() -> str:
    install_dir = get_client_install_dir()
    if install_dir:
        return os.path.join(install_dir, "Contents", "Resources")
    return ""


def _mac_executable(app_path: str) -> str:
    plist = os.path.join(app_path, "Contents", "Info.plist")
    name = ""
    try:
        name = subprocess.check_output(
            ["defaults", "read", plist, "CFBundleExecutable"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        name = ""
    if name:
        return os.path.join(app_path, "Contents", "MacOS", name)
    macos_dir = os.path.join(app_path, "Contents", "MacOS")
    if os.path.isdir(macos_dir):
        for item in os.listdir(macos_dir):
            path = os.path.join(macos_dir, item)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
    return ""


def allow_app_to_run(app_path: str) -> None:
    """内网包是 Apple Development 证书，本机无法直接打开，需清隔离并改签 ad-hoc。"""
    if not app_path or not os.path.isdir(app_path):
        return
    macos_dir = os.path.join(app_path, "Contents", "MacOS")
    entitlements = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adhoc.entitlements")
    subprocess.run(
        ["xattr", "-cr", app_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    subprocess.run(
        ["xattr", "-r", "-d", "com.apple.quarantine", app_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    subprocess.run(
        ["chmod", "-R", "u+w", app_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if os.path.isdir(macos_dir):
        subprocess.run(
            ["chmod", "-R", "a+x", macos_dir],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    sign_cmd = ["codesign", "--force", "--sign", "-"]
    if os.path.isfile(entitlements):
        sign_cmd.extend(["--entitlements", entitlements])
    sign_cmd.append(app_path)
    signed = subprocess.run(
        sign_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if signed.returncode != 0:
        quoted_app = shlex.quote(app_path)
        quoted_ent = shlex.quote(entitlements)
        extra = f" --entitlements {quoted_ent}" if os.path.isfile(entitlements) else ""
        script = (
            f"xattr -cr {quoted_app} && chmod -R u+w {quoted_app} && "
            f"codesign --force --sign -{extra} {quoted_app}"
        )
        escaped = script.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(
            ["osascript", "-e", f'do shell script "{escaped}" with administrator privileges'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def restart_client() -> None:
    kill_pc_process()
    time.sleep(0.8)
    open_client()


def open_client() -> None:
    if _is_mac():
        app = get_client_install_dir()
        if app:
            allow_app_to_run(app)
            opened = subprocess.run(["open", app], capture_output=True, text=True)
            if opened.returncode == 0:
                return
            exe = _mac_executable(app)
            if exe and os.path.isfile(exe):
                subprocess.Popen(
                    [exe],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return
        subprocess.Popen(["open", "-a", "爱奇艺"])
        return
    client_path = get_client_install_dir()
    if client_path:
        os.startfile(os.path.join(client_path, "QyClient.exe"))


def author(url: str) -> None:
    password_url = (
        "http://itpwd.qiyi.domain/api/GetPassword"
        "?domainuser=IIGpca_qa_autosender&token=93r9wype5a954c9s"
    )
    req = urllib.request.Request(password_url, headers={"User-Agent": "pc-tools-mac"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        res_text = resp.read().decode("utf-8")
    pcapassword = json.loads(res_text)["password"]
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, url, "IIGpca_qa_autosender", pcapassword)
    handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
    opener = urllib.request.build_opener(handler)
    urllib.request.install_opener(opener)
    ssl._create_default_https_context = ssl._create_unverified_context


def _compare_version(a: str, b: str) -> int:
    la = a.replace("/", "").split(".")
    lb = b.replace("/", "").split(".")
    max_len = max(len(la), len(lb))
    for i in range(max_len):
        try:
            a_val = int(la[i]) if i < len(la) else 0
        except (IndexError, ValueError):
            a_val = 0
        try:
            b_val = int(lb[i]) if i < len(lb) else 0
        except (IndexError, ValueError):
            b_val = 0
        if a_val > b_val:
            return 1
        if a_val < b_val:
            return -1
    return 0


def jfrog_path(branch: str) -> Tuple[str, str]:
    def reg(url: str) -> Tuple[List[str], List[str]]:
        author(url)
        req = urllib.request.urlopen(url, timeout=20)
        data = req.read().decode("utf-8")
        version_patt = re.compile(
            r'<a href="[^"]+">([\dXx]+\.[\dXx]+\.[\dXx]+(?:\.[\dXx]+)?)/</a>'
            r"\s+\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}\s+-",
            re.IGNORECASE,
        )
        date_patt = re.compile(r"\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}")
        matches = version_patt.findall(data)
        date_matches = date_patt.findall(data)
        matches = list(dict.fromkeys(matches))
        return matches, date_matches

    def get_max_version(version_list: List[str], n: int = 4) -> str:
        result = version_list[0]
        for item in version_list[1:]:
            if _compare_version(item, result) > 0:
                result = item
        cleaned = result.replace("/", "")
        parts = cleaned.split(".")
        while len(parts) < n:
            parts.append("0")
        return ".".join(parts[:n]) if n else cleaned

    version_list, date_list = reg(f"{JFROG_BASE_URL}{branch}")
    if not version_list:
        return "", ""
    max_version = get_max_version(version_list, 4).replace("/", "")
    try:
        max_version_index = version_list.index(max_version + "/")
        if max_version_index < 0:
            raise ValueError
    except Exception:
        try:
            max_version_index = next(
                i
                for i, v in enumerate(version_list)
                if v.replace("/", "") == max_version
            )
        except Exception:
            max_version_index = 0
    try:
        raw_date = date_list[max_version_index]
        max_version_date = datetime.strptime(raw_date, "%d-%b-%Y %H:%M").strftime(
            "%m.%d %H:%M"
        )
    except Exception:
        max_version_date = ""
    return f"{branch}{max_version}/", max_version_date


def create_dirs_with_package(dir_path: str) -> str:
    pkg = os.path.join(dir_path, "Package")
    if not os.path.isdir(pkg):
        os.mkdir(pkg)
    return pkg


def tool_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


JFROG_UI_API = JFROG_BASE_URL + "ui/api/v1/ui/nativeBrowser/"
MAC_PKG_ROOT = "iqiyi-generic-pca-ci/mac"
MAC_PKG_DEVELOP = MAC_PKG_ROOT + "/develop"


def jfrog_native_children(path: str) -> list:
    """列出 Artifactory nativeBrowser 子项，path 形如 repo/dir/。"""
    rel = path.strip("/")
    url = JFROG_UI_API + rel
    author(url)
    req = urllib.request.Request(url, headers={"User-Agent": "pc-tools-mac"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("children") or []


def download_file(
    package_name: str,
    whole_branch: str = "",
    branch: str = "",
    progress: Optional[Callable] = None,
) -> str:
    try:
        url = whole_branch if whole_branch else f"{JFROG_BASE_URL}{branch}"
        if not url.endswith("/"):
            url += "/"
        print(url)
        author(url)
        jfrog_file = url + package_name
        print(jfrog_file)
        create_dirs_with_package(tool_root())
        local_path = os.path.join(tool_root(), "Package", package_name)
        print(local_path)
        if os.path.exists(local_path):
            print("即将删除文件")
            os.remove(local_path)
        req = urllib.request.Request(jfrog_file, headers={"User-Agent": "pc-tools-mac"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            chunk = 256 * 1024
            if progress:
                progress(status=f"正在下载 {package_name}", current=0, total=total or None)
            with open(local_path, "wb") as f:
                while True:
                    buf = resp.read(chunk)
                    if not buf:
                        break
                    f.write(buf)
                    downloaded += len(buf)
                    if progress:
                        progress(current=downloaded, total=total)
        size = os.path.getsize(local_path)
        if size < 1_000_000:
            os.remove(local_path)
            raise RuntimeError(
                f"下载文件过小（{size} 字节），多半是 JFrog 上的空包：{package_name}"
            )
        if progress:
            progress(status="下载完成", current=size, total=size)
        time.sleep(0.2)
        return local_path
    except Exception as e:
        raise RuntimeError(f"下载失败: {e}\n请确认版本号和分支选择是否正确") from e


def delete_dir_files(dir_path: str) -> None:
    if not os.path.isdir(dir_path):
        return
    for item in os.listdir(dir_path):
        item_path = os.path.join(dir_path, item)
        try:
            if os.path.isdir(item_path):
                delete_dir_files(item_path)
                os.rmdir(item_path)
            else:
                os.remove(item_path)
        except Exception:
            if os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=True)
            else:
                try:
                    os.remove(item_path)
                except Exception:
                    pass


def bind_mousewheel(widget, canvas: tk.Canvas) -> None:
    def on_wheel(event):
        delta = getattr(event, "delta", 0)
        if delta:
            step = -1 if delta > 0 else 1
            if abs(delta) >= 120:
                step = int(-delta / 120)
            canvas.yview_scroll(step, "units")
        elif getattr(event, "num", None) == 4:
            canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            canvas.yview_scroll(1, "units")
        return "break"

    widget.bind("<MouseWheel>", on_wheel)
    widget.bind("<Button-4>", on_wheel)
    widget.bind("<Button-5>", on_wheel)


if __name__ == "__main__":
    print(jfrog_path("iqiyi-pca-repo/baseline/main/"))

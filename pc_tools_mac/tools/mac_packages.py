# -*- coding: utf-8 -*-
"""Mac 客户端包：iqiyi-generic-pca-ci/mac/develop/{Trunk,Release,AppStore}。"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from datetime import datetime
from typing import List, Optional, Tuple

from tools.public_tool import (
    JFROG_BASE_URL,
    MAC_APP_CANDIDATES,
    MAC_PKG_DEVELOP,
    MAC_PKG_ROOT,
    allow_app_to_run,
    download_file,
    jfrog_native_children,
    kill_pc_process,
    open_folder,
)

CHANNELS = ("Trunk", "Release", "AppStore")


def format_jfrog_time(ms) -> str:
    try:
        ts = int(ms)
        if ts > 10_000_000_000:
            ts = ts / 1000
        return datetime.fromtimestamp(ts).strftime("%m.%d %H:%M")
    except Exception:
        return ""


def list_versions(channel_path: str) -> List[dict]:
    children = jfrog_native_children(channel_path)
    folders = [c for c in children if c.get("folder") and c.get("name")]
    folders.sort(key=lambda c: c.get("lastModified") or 0, reverse=True)
    return folders


def latest_version(channel_path: str) -> Tuple[str, str]:
    folders = list_versions(channel_path)
    if not folders:
        return "", ""
    name = folders[0]["name"].rstrip("/")
    return name, format_jfrog_time(folders[0].get("lastModified"))


def develop_channel_path(channel: str) -> str:
    return f"{MAC_PKG_DEVELOP}/{channel}"


def _is_dmg_name(name: str) -> bool:
    return bool(name) and name.endswith(".dmg")


def pick_dmg_name(folder_path: str, channel: str) -> str:
    children = jfrog_native_children(folder_path)
    files = [c for c in children if not c.get("folder")]

    def named(*prefixes: str):
        out = []
        for c in files:
            name = c.get("name") or ""
            if not _is_dmg_name(name):
                continue
            if any(name.startswith(p) for p in prefixes):
                out.append(c)
        return out

    if channel == "AppStore":
        preferred = named("iqiyi_appstore_mac_")
        fallback = []
    else:
        preferred = named("iqiyi_mac_")
        fallback = named("iqiyi_appstore_mac_")

    def usable(items):
        return [c for c in items if (c.get("size") or 0) > 1_000_000]

    cands = usable(preferred) or usable(fallback)
    if not cands:
        names = [f"{c.get('name')} ({c.get('size') or 0}B)" for c in files]
        raise RuntimeError(
            "未找到可用的 dmg（现有文件可能是 0 字节空包）:\n" + "\n".join(names)
        )
    cands.sort(key=lambda c: c.get("size") or 0, reverse=True)
    return cands[0]["name"]


def resolve_custom_channel(branch: str) -> str:
    """手动输入 git 分支或相对路径，优先取其 Trunk。"""
    rel = branch.strip().strip("/")
    if rel in CHANNELS:
        return develop_channel_path(rel)
    path = f"{MAC_PKG_ROOT}/{rel}"
    children = jfrog_native_children(path)
    names = {(c.get("name") or "").rstrip("/") for c in children if c.get("folder")}
    if "Trunk" in names:
        return f"{path}/Trunk"
    if "Release" in names:
        return f"{path}/Release"
    return path


def _mount_points_from_attach_output(text: str) -> List[str]:
    mounts = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"\s+", line)
        for part in reversed(parts):
            if part.startswith("/Volumes/"):
                mounts.append(part)
                break
    return mounts


def _find_app_in_mounts(mounts: List[str]) -> Optional[str]:
    for mount in mounts:
        try:
            names = os.listdir(mount)
        except Exception:
            continue
        for name in names:
            if name.endswith(".app"):
                return os.path.join(mount, name)
    return None


def _looks_like_dmg(path: str) -> bool:
    try:
        size = os.path.getsize(path)
    except OSError:
        return False
    if size < 1_000_000:
        return False
    with open(path, "rb") as f:
        head = f.read(16)
    if head.startswith(b"<!DOCTYPE") or head.startswith(b"<html") or head.startswith(b"{"):
        return False
    return True


def _copy_app_bundle(src: str, dest: str) -> None:
    if os.path.exists(dest):
        shutil.rmtree(dest)
    copied = subprocess.run(["ditto", src, dest], capture_output=True, text=True)
    if copied.returncode != 0:
        raise PermissionError(copied.stderr or copied.stdout or "ditto 复制失败")


def install_mac_dmg(dmg_path: str, progress=None) -> Tuple[bool, str]:
    mounts: List[str] = []
    if not _looks_like_dmg(dmg_path):
        size = os.path.getsize(dmg_path) if os.path.exists(dmg_path) else 0
        return False, (
            f"下载的不是有效 dmg（{size} 字节）。\n"
            "JFrog 上对应的 iqiyi_mac_*.dmg 经常是空文件，请重试；"
            "工具会自动改用 iqiyi_appstore_mac_*.dmg。"
        )
    try:
        subprocess.run(
            ["xattr", "-c", dmg_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if progress:
            progress(status="正在挂载安装包…")
        raw = subprocess.check_output(
            ["hdiutil", "attach", dmg_path, "-nobrowse"],
            stderr=subprocess.STDOUT,
            text=True,
        )
        mounts = _mount_points_from_attach_output(raw)
        app_src = _find_app_in_mounts(mounts)
        if not app_src:
            subprocess.Popen(["open", dmg_path])
            open_folder(os.path.dirname(dmg_path))
            return True, f"已下载并打开 dmg，未找到 .app，请手动安装:\n{dmg_path}"

        dest = os.path.join("/Applications", os.path.basename(app_src))
        if progress:
            progress(status="正在安装到应用程序…")
        try:
            _copy_app_bundle(app_src, dest)
        except PermissionError:
            script = (
                f"rm -rf {shlex.quote(dest)} && ditto {shlex.quote(app_src)} {shlex.quote(dest)}"
            )
            escaped = script.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.run(
                ["osascript", "-e", f'do shell script "{escaped}" with administrator privileges'],
                check=True,
            )
        if progress:
            progress(status="正在处理安全属性，完成后可直接打开…")
        allow_app_to_run(dest)
        return True, dest
    except subprocess.CalledProcessError as e:
        return False, f"挂载或安装失败: {e.output if e.output else e}"
    except Exception as e:
        return False, str(e)
    finally:
        for mp in mounts:
            subprocess.run(
                ["hdiutil", "detach", mp, "-quiet"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def download_and_install(
    channel_path: str, version: str, channel: str, progress=None
) -> Tuple[bool, str]:
    if progress:
        progress(status="正在查找安装包…")
    folder = f"{channel_path.rstrip('/')}/{version}"
    dmg_name = pick_dmg_name(folder, channel)
    local = download_file(
        dmg_name,
        whole_branch=f"{JFROG_BASE_URL}{folder}/",
        progress=progress,
    )
    return install_mac_dmg(local, progress=progress)


def install_latest(channel_or_branch: str, progress=None) -> Tuple[bool, str]:
    try:
        if progress:
            progress(status="正在查找最新版本…")
        if channel_or_branch in CHANNELS:
            channel = channel_or_branch
            path = develop_channel_path(channel)
        else:
            path = resolve_custom_channel(channel_or_branch)
            channel = "AppStore" if path.rstrip("/").endswith("AppStore") else "Trunk"
        version, _ = latest_version(path)
        if not version:
            return False, f"未找到可用版本: {path}"
        kill_pc_process()
        return download_and_install(path, version, channel, progress=progress)
    except Exception as e:
        return False, str(e)


def uninstall_local_app() -> Tuple[bool, str]:
    kill_pc_process()
    removed = []
    errors = []
    for dest in MAC_APP_CANDIDATES:
        if not os.path.isdir(dest):
            continue
        try:
            shutil.rmtree(dest)
            removed.append(dest)
        except PermissionError:
            script = f"rm -rf {shlex.quote(dest)}"
            escaped = script.replace("\\", "\\\\").replace('"', '\\"')
            try:
                subprocess.run(
                    ["osascript", "-e", f'do shell script "{escaped}" with administrator privileges'],
                    check=True,
                )
                removed.append(dest)
            except Exception as e:
                errors.append(f"{dest}: {e}")
        except Exception as e:
            errors.append(f"{dest}: {e}")
    if removed and not errors:
        return True, "已卸载：\n" + "\n".join(removed)
    if removed:
        return True, "已卸载：\n" + "\n".join(removed) + "\n部分失败：\n" + "\n".join(errors)
    if errors:
        return False, "卸载失败：\n" + "\n".join(errors)
    return False, "未找到已安装的爱奇艺.app"

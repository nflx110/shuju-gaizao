# -*- coding: utf-8 -*-
import json
import os
import shutil
import zipfile
from tkinter import messagebox
from tools.public_tool import (
    kill_pc_process,
    get_client_install_dir,
    get_lstyle_dir,
    get_mac_resources_dir,
    jfrog_path,
    download_file,
    open_client,
    tool_root,
)


BRANCH_MAP = {
    "c": "iqiyi-pca-repo/webapp/current/",
    "d": "iqiyi-pca-repo/webapp/dev/",
    "n": "iqiyi-pca-repo/webapp/next/",
    "p": "iqiyi-pca-repo/webapp/patch/",
}


def _write_lwa_config(version: str) -> None:
    resources = get_mac_resources_dir()
    if not resources:
        return
    cfg_path = os.path.join(resources, "lwa_config.json")
    data = {"version": {"iqiyi_webapp": version}}
    try:
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("version", {})["iqiyi_webapp"] = version
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception:
        local_cfg = os.path.join(get_lstyle_dir(), "lwa_config.json")
        os.makedirs(os.path.dirname(local_cfg), exist_ok=True)
        with open(local_cfg, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


def replace_lwa_by_option(option: str, version: str = ""):
    """根据选项（c/d/n/p）替换对应版本的 LWA 资源。"""
    try:
        kill_pc_process()
        branch_name = BRANCH_MAP.get(option, BRANCH_MAP["c"])
        if version:
            download_path = f"{branch_name}{version}/"
        else:
            download_path, _ = jfrog_path(branch_name)
        if not download_path:
            return False, "未找到对应 LWA 版本"
        download_file("iqiyi_webapp.zip", branch=download_path)
        src_zip_path = os.path.join(tool_root(), "Package", "iqiyi_webapp.zip")
        if not os.path.exists(src_zip_path):
            src_zip_path = os.path.join(os.getcwd(), "Package", "iqiyi_webapp.zip")

        app_dir = get_client_install_dir()
        if not app_dir:
            return False, "未找到客户端安装地址"

        lwa_ver = version or download_path.rstrip("/").split("/")[-1]
        resources = get_mac_resources_dir()
        copied_to_app = False
        if resources and os.path.isdir(resources):
            target_zip = os.path.join(resources, "iqiyi_webapp.zip")
            try:
                shutil.copy2(src_zip_path, target_zip)
                _write_lwa_config(lwa_ver)
                copied_to_app = True
            except Exception:
                copied_to_app = False

        # 同时解压到 LStyle，兼容从数据目录读取 LWA 的逻辑
        target_dir = os.path.join(get_lstyle_dir(), "localwebapp", "iqiyi_webapp")
        shutil.rmtree(target_dir, ignore_errors=True)
        os.makedirs(target_dir, exist_ok=True)
        with zipfile.ZipFile(src_zip_path, "r") as zip_ref:
            zip_ref.extractall(target_dir)

        extra = ""
        if not copied_to_app:
            extra = (
                "\n\n未能写入 /Applications/爱奇艺.app（可能需要权限）。"
                f"\nzip 已解压到：{target_dir}\n也可手动替换 Resources/iqiyi_webapp.zip"
            )

        result = messagebox.askyesno("确认", "LWA替换完成，是否打开客户端？" + extra)
        if result:
            open_client()
        return True, ""
    except Exception as e:
        return False, f"版本替换失败！{e}"

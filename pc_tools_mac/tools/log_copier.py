# -*- coding: utf-8 -*-
import os
import shutil
import time
from tools.public_tool import get_lstyle_dir, open_folder, tool_root


INI_FILES = ("PPStream.ini", "Qyplayer.ini", "QySetting.ini", "QyUpdate.ini")


def create_target_dir() -> str:
    current_time_str = time.strftime("%Y%m%d%H%M")
    target_dir = os.path.join(tool_root(), "Package", current_time_str)
    os.makedirs(target_dir, exist_ok=True)
    return target_dir


def copy_log_files():
    source_dir = get_lstyle_dir()
    if not os.path.isdir(source_dir):
        return False, f"日志源目录不存在: {source_dir}", ""
    target_dir = create_target_dir()
    log_files = [f for f in os.listdir(source_dir) if f.lower().endswith(".log")]
    ini_files = [f for f in INI_FILES if os.path.exists(os.path.join(source_dir, f))]
    files = log_files + ini_files
    if not files:
        return False, "源目录未找到.log文件和.ini文件: " + source_dir, target_dir
    copied_count = 0
    error_files = []
    for filename in files:
        source_path = os.path.join(source_dir, filename)
        target_path = os.path.join(target_dir, filename)
        try:
            shutil.copy2(source_path, target_path)
            copied_count += 1
        except Exception as e:
            error_files.append(f"{filename}: {e}")
    result_msg = f"成功复制 {copied_count}/{len(files)} 个日志文件到:\n{target_dir}"
    if error_files:
        result_msg += "\n\n以下文件复制失败:\n" + "\n".join(error_files)
    return True, result_msg, target_dir


def execute():
    success, msg, target_dir = copy_log_files()
    if success and target_dir:
        open_folder(target_dir)
    return success, msg

# -*- coding: utf-8 -*-
import os
from tools.public_tool import kill_pc_process, get_lstyle_dir


def get_log_source_dir() -> str:
    log_dir = get_lstyle_dir()
    if not log_dir:
        raise RuntimeError("无法获取 LStyle 目录")
    return log_dir


def clear_log_files():
    """清空日志文件内容（支持被占用文件）。"""
    kill_pc_process()
    source_dir = get_log_source_dir()
    if not os.path.exists(source_dir):
        return f"日志源目录不存在: {source_dir}"
    log_files = [f for f in os.listdir(source_dir) if f.lower().endswith(".log")]
    cleared_count = 0
    failed_files = []
    for filename in log_files:
        file_path = os.path.join(source_dir, filename)
        try:
            with open(file_path, "w", encoding="utf-8", errors="ignore"):
                pass
            cleared_count += 1
        except Exception as e:
            failed_files.append(f"{filename} ({e})")
    if not log_files:
        return "未找到 .log 文件"
    if failed_files and cleared_count == 0:
        return "所有日志文件清空失败:\n" + "\n".join(failed_files)
    message = f"成功清空 {cleared_count} 个日志文件"
    if failed_files:
        message += "\n\n以下文件清空失败:\n" + "\n".join(failed_files)
    return message

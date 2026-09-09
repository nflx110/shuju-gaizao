# -*- coding: utf-8 -*-
import os
from tools.public_tool import get_lstyle_dir


def execute():
    lstyle_dir = get_lstyle_dir()
    if not os.path.isdir(lstyle_dir):
        os.makedirs(lstyle_dir, exist_ok=True)
    file_path = os.path.join(lstyle_dir, "logconfig.ini")
    if os.path.exists(file_path):
        os.remove(file_path)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("[debug]\nlog=1\nbrowser=1\n[test]\nclientid=h1\n")
    return True, "已写入 logconfig.ini"

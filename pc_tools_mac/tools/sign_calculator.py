# -*- coding: utf-8 -*-
import hashlib
import time
import tkinter as tk
from tkinter import ttk, messagebox
from urllib.parse import urlparse, parse_qs, urlencode, unquote, quote
from tools.public_tool import UI_FONT, calculate_dpi_scaled_size


class SignCalculatorWindow(tk.Toplevel):
    def __init__(self, parent, title="Sign Calculator"):
        super().__init__(parent)
        self.result_entry = None
        self.result_var = None
        self.input_entry = None
        self.title(title)
        parent.update_idletasks()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        window_width = max(int(parent_width * 0.9), 640)
        window_height = max(int(parent_height * 0.45), 220)
        x = parent_x + (parent_width - window_width) // 2
        y = parent_y + (parent_height - window_height) // 2
        screen_width = parent.winfo_screenwidth()
        screen_height = parent.winfo_screenheight()
        x = max(0, min(x, screen_width - window_width))
        y = max(0, min(y, screen_height - window_height))
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.resizable(True, True)
        self.create_widgets()

    def create_widgets(self):
        input_frame = ttk.Frame(self)
        input_frame.pack(fill="x", padx=12, pady=(16, 8))
        ttk.Label(
            input_frame,
            text="输入接口:",
            font=(UI_FONT, calculate_dpi_scaled_size(11)),
        ).pack(side="left")
        self.input_entry = ttk.Entry(input_frame)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=8)

        result_frame = ttk.Frame(self)
        result_frame.pack(fill="x", padx=12, pady=8)
        ttk.Label(
            result_frame,
            text="输出结果:",
            font=(UI_FONT, calculate_dpi_scaled_size(11)),
        ).pack(side="left")
        self.result_var = tk.StringVar()
        self.result_entry = ttk.Entry(result_frame, textvariable=self.result_var, state="readonly")
        self.result_entry.pack(side="left", fill="x", expand=True, padx=8)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=12)
        ttk.Button(btn_frame, text="计算", command=self.calculate_sign).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="复制结果", command=self.copy_result).pack(side="left", padx=8)

    def calculate_sign(self):
        original_url = self.input_entry.get().strip()
        if not original_url:
            messagebox.showwarning("提示", "请输入文本内容")
            return
        parts = original_url.split("/")
        module = parts[4] if len(parts) > 4 else ""
        if module not in ("player", "tvg", "aid"):
            module = parts[3] if len(parts) > 3 else module
        parsed_url = urlparse(original_url)
        url_before_params = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?"
        params = parse_qs(parsed_url.query, keep_blank_values=True)
        keys = list(params.keys())
        values = [value[0] if value else "" for value in params.values()]
        if "sign" in keys:
            index = keys.index("sign")
            keys.pop(index)
            values.pop(index)
        sorted_keys_values = sorted(zip(keys, values))
        sorted_query_string = urlencode(sorted_keys_values)
        if module == "player":
            key_name, secret_key = "key", "tPa%$xSY?5_287mN"
        elif module == "tvg":
            key_name, secret_key = "secret_key", "howcuteitis"
        elif module == "aid":
            key_name, secret_key = "key", "2cCq2fgeDNG-Eb8B%d]S.Ch<c]@uVN95"
        else:
            key_name, secret_key = "secret_key", "howcuteitis"
        sign_src = unquote(sorted_query_string) + f"&{key_name}={secret_key}"
        sign = hashlib.md5(sign_src.encode("utf-8")).hexdigest().upper()
        url = url_before_params + sorted_query_string + "&sign=" + quote(sign, safe=":/?&=")
        secret_key_part = f"&{key_name}={secret_key}"
        result = url.replace(secret_key_part, "")
        if module == "aid":
            result += "&timestamp=" + str(int(time.time()))
        self.result_var.set(result)

    def copy_result(self):
        result = self.result_var.get()
        if not result:
            messagebox.showwarning("提示", "无结果可复制")
            return
        self.clipboard_clear()
        self.clipboard_append(result)
        self.update()
        messagebox.showinfo("提示", "结果已复制到剪贴板")

# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox
from tools.update_lwa import replace_lwa_by_option
from tools.public_tool import (
    UI_FONT,
    show_loading_window,
    jfrog_path,
    calculate_dpi_scaled_size,
    get_client_install_dir,
)
from tools.env_info import _read_lwa_version


BRANCH_COLORS = {
    "current": "#00C853",
    "dev": "#FF8A3D",
    "next": "#3D8BFF",
    "patch": "#A855F7",
}


class LWAReplacerWindow(tk.Toplevel):
    """查看各分支 LWA 包信息，需要时再替换。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("LWA 包信息")
        self.configure(bg="#E8F8EF")
        self.option_map = {
            "current": "c",
            "dev": "d",
            "next": "n",
            "patch": "p",
        }
        self.version_numbers = {}
        self.tips = "可选：输入指定版本号（如 17.074.25886），不填则用上面选中的最新包"
        for option in self.option_map:
            try:
                path, date = jfrog_path(f"iqiyi-pca-repo/webapp/{option}/")
                version = path.rstrip("/").split("/")[-1] if path else "获取失败"
                self.version_numbers[option] = (version, date)
            except Exception:
                self.version_numbers[option] = ("获取失败", "")
        self._setup_window_geometry()
        self.create_widgets()

    def _setup_window_geometry(self):
        parent_width = max(self.parent.winfo_width(), 520)
        parent_height = max(self.parent.winfo_height(), 400)
        window_width = max(int(parent_width * 0.78), 520)
        window_height = max(int(parent_height * 0.82), 420)
        x = self.parent.winfo_x() + (parent_width - window_width) // 2
        y = self.parent.winfo_y() + (parent_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.minsize(500, 400)

    def _local_lwa(self) -> str:
        try:
            text = _read_lwa_version(get_client_install_dir())
            if text:
                return text.replace("lwa版本号: ", "").strip()
        except Exception:
            pass
        return "未读到"

    def create_widgets(self):
        header = tk.Frame(self, bg="#00C853", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="LWA 包信息",
            bg="#00C853",
            fg="white",
            font=(UI_FONT, 16, "bold"),
        ).pack(anchor="w", padx=18, pady=(10, 0))
        tk.Label(
            header,
            text=f"本机当前版本  {self._local_lwa()}",
            bg="#00C853",
            fg="#E8FFE8",
            font=(UI_FONT, 11),
        ).pack(anchor="w", padx=18, pady=(2, 8))

        body = tk.Frame(self, bg="#E8F8EF")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        tk.Label(
            body,
            text="仓库最新包  iqiyi-pca-repo/webapp",
            bg="#E8F8EF",
            fg="#2E7D4F",
            font=(UI_FONT, 11, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        self.version_var = tk.StringVar(value="current")
        for option in self.option_map:
            self._add_branch_card(body, option)

        self.custom_input = ttk.Entry(body, font=(UI_FONT, calculate_dpi_scaled_size(11)))
        self.custom_input.pack(fill="x", pady=(12, 4))
        self.custom_input.insert(0, self.tips)
        self.custom_input.bind("<FocusIn>", self._on_input_focus_in)
        self.custom_input.bind("<FocusOut>", self._on_input_focus_out)

        btn_row = tk.Frame(body, bg="#E8F8EF")
        btn_row.pack(fill="x", pady=(12, 0))
        tk.Button(
            btn_row,
            text="关闭",
            command=self.destroy,
            bg="#FFFFFF",
            fg="#163326",
            relief="flat",
            padx=16,
            pady=6,
            font=(UI_FONT, 11),
            cursor="hand2",
        ).pack(side="right")
        tk.Button(
            btn_row,
            text="替换到本机",
            command=self.execute_replacement,
            bg="#00C853",
            fg="white",
            relief="flat",
            padx=16,
            pady=6,
            font=(UI_FONT, 11, "bold"),
            cursor="hand2",
            highlightthickness=0,
        ).pack(side="right", padx=(0, 8))

    def _add_branch_card(self, parent, option):
        accent = BRANCH_COLORS.get(option, "#00C853")
        version, date = self.version_numbers.get(option, ("获取失败", ""))
        card = tk.Frame(parent, bg="white", highlightthickness=0)
        card.pack(fill="x", pady=4)
        stripe = tk.Frame(card, bg=accent, width=6)
        stripe.pack(side="left", fill="y")
        inner = tk.Frame(card, bg="white")
        inner.pack(side="left", fill="both", expand=True, padx=10, pady=8)
        rb = tk.Radiobutton(
            inner,
            text=option,
            value=option,
            variable=self.version_var,
            bg="white",
            fg=accent,
            font=(UI_FONT, 12, "bold"),
            selectcolor="white",
            activebackground="white",
            highlightthickness=0,
            cursor="hand2",
        )
        rb.pack(side="left")
        info = f"{version}"
        if date:
            info += f"    {date}"
        tk.Label(
            inner,
            text=info,
            bg="white",
            fg="#163326",
            font=(UI_FONT, 12),
            anchor="w",
        ).pack(side="left", padx=12)

    def _on_input_focus_in(self, event):
        if self.custom_input.get() == self.tips:
            self.custom_input.delete(0, tk.END)

    def _on_input_focus_out(self, event):
        if not self.custom_input.get().strip():
            self.custom_input.insert(0, self.tips)

    def execute_replacement(self):
        selected_option = self.version_var.get()
        branch_code = self.option_map.get(selected_option, "c")
        custom_text = self.custom_input.get()
        if custom_text == self.tips:
            custom_text = ""
        custom_text = custom_text.strip()
        try:
            res, err = show_loading_window(
                self,
                "更新LWA",
                replace_lwa_by_option,
                branch_code,
                custom_text,
            )
            if err:
                raise err
            result, msg = res if isinstance(res, tuple) else (False, str(res))
            if result:
                messagebox.showinfo("成功", f"LWA {selected_option}版本替换完成！")
                self.destroy()
            else:
                messagebox.showerror("失败", msg or "错误")
        except Exception as e:
            messagebox.showerror("错误", f"LWA更新失败: {e}")

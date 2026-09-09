# -*- coding: utf-8 -*-
"""子窗口共用的浅色清晰样式。"""
import tkinter as tk
from tkinter import ttk

from tools.public_tool import UI_FONT

BG = "#F3F6F4"
CARD = "#FFFFFF"
TEXT = "#1C2B22"
MUTED = "#66786E"
LINE = "#D9E4DC"
HEADER = "#1F8A4C"
ACCENT = "#1F8A4C"
WARN_BG = "#FFF4D6"
WARN_FG = "#8A5A00"
OK_BG = "#E3F7EA"
OK_FG = "#1B7A3A"
BAD_BG = "#FDECEC"
BAD_FG = "#B42318"


def place_window(win, parent, ratio=0.9, min_w=560, min_h=420):
    parent.update_idletasks()
    pw = max(parent.winfo_width(), min_w)
    ph = max(parent.winfo_height(), min_h)
    w = max(int(pw * ratio), min_w)
    h = max(int(ph * ratio), min_h)
    x = parent.winfo_x() + max(0, (pw - w) // 2)
    y = parent.winfo_y() + max(20, (ph - h) // 8)
    win.geometry(f"{w}x{h}+{x}+{y}")
    win.minsize(min_w, min_h)
    win.configure(bg=BG)


def header_bar(parent, title, subtitle=""):
    bar = tk.Frame(parent, bg=HEADER, height=72 if subtitle else 56)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    tk.Label(bar, text=title, bg=HEADER, fg="white", font=(UI_FONT, 18, "bold")).pack(
        anchor="w", padx=22, pady=(12, 0 if subtitle else 12)
    )
    if subtitle:
        tk.Label(bar, text=subtitle, bg=HEADER, fg="#D7F5E4", font=(UI_FONT, 11)).pack(
            anchor="w", padx=22, pady=(2, 12)
        )
    return bar


def card(parent, **grid):
    box = tk.Frame(
        parent,
        bg=CARD,
        highlightthickness=1,
        highlightbackground=LINE,
        highlightcolor=LINE,
    )
    if grid:
        box.grid(**grid)
    return box


def section_title(parent, text):
    tk.Label(
        parent, text=text, bg=BG, fg=MUTED, font=(UI_FONT, 11, "bold"), anchor="w"
    ).pack(fill="x", pady=(0, 8))


def pill(parent, text, kind="ok"):
    colors = {
        "ok": (OK_BG, OK_FG),
        "warn": (WARN_BG, WARN_FG),
        "bad": (BAD_BG, BAD_FG),
        "muted": ("#EEF2F0", MUTED),
    }
    bg, fg = colors.get(kind, colors["muted"])
    lbl = tk.Label(
        parent,
        text=f"  {text}  ",
        bg=bg,
        fg=fg,
        font=(UI_FONT, 10, "bold"),
    )
    return lbl


def ghost_button(parent, text, command):
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=CARD,
        fg=TEXT,
        relief="flat",
        highlightthickness=1,
        highlightbackground=LINE,
        padx=16,
        pady=7,
        font=(UI_FONT, 11),
        cursor="hand2",
    )


def primary_button(parent, text, command):
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=HEADER,
        fg="white",
        relief="flat",
        highlightthickness=0,
        padx=16,
        pady=7,
        font=(UI_FONT, 11, "bold"),
        cursor="hand2",
        activebackground="#187A43",
        activeforeground="white",
    )


def style_tree(win):
    style = ttk.Style(win)
    style.configure(
        "Clear.Treeview",
        font=(UI_FONT, 12),
        rowheight=34,
        background=CARD,
        fieldbackground=CARD,
        foreground=TEXT,
        borderwidth=0,
    )
    style.configure(
        "Clear.Treeview.Heading",
        font=(UI_FONT, 11, "bold"),
        background="#EAF3ED",
        foreground=MUTED,
        relief="flat",
    )
    style.map(
        "Clear.Treeview",
        background=[("selected", "#D8F3E3")],
        foreground=[("selected", TEXT)],
    )
    return style

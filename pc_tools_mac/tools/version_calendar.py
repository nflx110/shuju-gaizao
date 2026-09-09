# -*- coding: utf-8 -*-
"""prjone 版本排期：爱奇艺视频 PC 端迭代计划。"""
from __future__ import annotations

import json
import subprocess
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox

from tools.ui_theme import (
    BG,
    CARD,
    MUTED,
    TEXT,
    card,
    ghost_button,
    header_bar,
    place_window,
    primary_button,
    style_tree,
)

PRJONE = "http://prjone.cloud.qiyi.domain"
CALENDAR_ID = 17
DEFAULT_VERSION_ID = 1804
CALENDAR_API = f"{PRJONE}/release_manage/api2/calendar/{CALENDAR_ID}"
VERSION_ITEMS_API = f"{PRJONE}/release_manage/api2/calendar/getVersionItemListWithDate?ids="
VERSION_PAGE = f"{PRJONE}/calendar/version/"

STATUS_TEXT = {
    "released": "已发布",
    "draft": "草稿",
    "doing": "进行中",
}


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "pc-tools-mac"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_calendar():
    data = _get_json(CALENDAR_API)
    versions = list(data.get("versionList") or [])
    versions.sort(
        key=lambda v: (v.get("itemLatest") or "", v.get("ID") or 0),
        reverse=True,
    )
    return data, versions


def fetch_version_items(version_id: int):
    data = _get_json(VERSION_ITEMS_API + str(version_id))
    if not isinstance(data, list):
        return []
    data.sort(key=lambda x: (x.get("startDate") or "", x.get("item") or ""))
    return data


def _status_label(raw: str) -> str:
    return STATUS_TEXT.get((raw or "").lower(), raw or "—")


class VersionCalendarWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("版本排期")
        self.versions = []
        place_window(self, parent, 0.96, 780, 520)
        style_tree(self)
        self._build()
        self.after(80, self._load)

    def _build(self):
        self.sub_bar = header_bar(self, "版本排期", "爱奇艺视频 PC 端迭代计划")
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=16)
        body.grid_columnconfigure(0, weight=5)
        body.grid_columnconfigure(1, weight=6)
        body.grid_rowconfigure(1, weight=1)

        tk.Label(body, text="版本", bg=BG, fg=MUTED, font=("PingFang SC", 11, "bold"), anchor="w").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        tk.Label(body, text="排期节点", bg=BG, fg=MUTED, font=("PingFang SC", 11, "bold"), anchor="w").grid(
            row=0, column=1, sticky="w", padx=(14, 0), pady=(0, 8)
        )

        left = card(body, row=1, column=0, sticky="nsew")
        right = card(body, row=1, column=1, sticky="nsew", padx=(14, 0))
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.ver_tree = ttk.Treeview(
            left,
            columns=("ver", "span", "status"),
            show="headings",
            style="Clear.Treeview",
            selectmode="browse",
        )
        self.ver_tree.heading("ver", text="版本")
        self.ver_tree.heading("span", text="周期")
        self.ver_tree.heading("status", text="状态")
        self.ver_tree.column("ver", width=110, anchor="w")
        self.ver_tree.column("span", width=210, anchor="w")
        self.ver_tree.column("status", width=70, anchor="center")
        vs = tk.Scrollbar(left, orient="vertical", command=self.ver_tree.yview, width=12)
        self.ver_tree.configure(yscrollcommand=vs.set)
        self.ver_tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        vs.grid(row=0, column=1, sticky="ns", pady=10, padx=(0, 8))
        self.ver_tree.bind("<<TreeviewSelect>>", self._on_select)

        self.item_tree = ttk.Treeview(
            right,
            columns=("name", "start", "end"),
            show="headings",
            style="Clear.Treeview",
            selectmode="browse",
        )
        self.item_tree.heading("name", text="节点")
        self.item_tree.heading("start", text="开始")
        self.item_tree.heading("end", text="结束")
        self.item_tree.column("name", width=160, anchor="w")
        self.item_tree.column("start", width=110, anchor="center")
        self.item_tree.column("end", width=110, anchor="center")
        isc = tk.Scrollbar(right, orient="vertical", command=self.item_tree.yview, width=12)
        self.item_tree.configure(yscrollcommand=isc.set)
        self.item_tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        isc.grid(row=0, column=1, sticky="ns", pady=10, padx=(0, 8))

        self.detail = tk.Label(
            body,
            text="",
            bg=BG,
            fg=TEXT,
            font=("PingFang SC", 11),
            anchor="w",
            justify="left",
        )
        self.detail.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", padx=18, pady=(0, 16))
        ghost_button(btns, "关闭", self.destroy).pack(side="right")
        primary_button(btns, "浏览器打开", self._open_browser).pack(side="right", padx=(0, 8))

    def _load(self):
        try:
            data, versions = fetch_calendar()
        except Exception as e:
            messagebox.showerror("错误", f"获取版本排期失败: {e}")
            return
        title = data.get("title") or "爱奇艺视频 PC 端迭代计划"
        for child in self.sub_bar.winfo_children():
            if isinstance(child, tk.Label) and child.cget("fg") == "#D7F5E4":
                child.config(text=title)
                break
        self.versions = versions
        for item in self.ver_tree.get_children():
            self.ver_tree.delete(item)
        select = None
        for v in versions:
            vid = str(v.get("ID") or "")
            name = v.get("version") or vid
            start = v.get("itemEarliest") or ""
            end = v.get("itemLatest") or ""
            span = f"{start}  ~  {end}" if start or end else "—"
            status = _status_label(v.get("versionStatus"))
            self.ver_tree.insert("", "end", iid=vid, values=(name, span, status))
            if v.get("ID") == DEFAULT_VERSION_ID:
                select = vid
        if versions:
            select = select or str(versions[0].get("ID"))
            self.ver_tree.selection_set(select)
            self.ver_tree.see(select)
            self._show_items(select)

    def _selected_version(self):
        sel = self.ver_tree.selection()
        if not sel:
            return None
        vid = int(sel[0])
        for v in self.versions:
            if v.get("ID") == vid:
                return v
        return None

    def _on_select(self, _event=None):
        v = self._selected_version()
        if not v:
            return
        self._show_items(v.get("ID"))

    def _show_items(self, version_id):
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        v = self._selected_version()
        if v:
            pms = (v.get("pmsVersion") or "").strip()
            extra = f"    PMS  {pms}" if pms else ""
            self.detail.config(
                text=f"{v.get('version') or ''}    {v.get('itemEarliest') or ''} ~ {v.get('itemLatest') or ''}    {_status_label(v.get('versionStatus'))}{extra}"
            )
        if not version_id:
            return
        try:
            items = fetch_version_items(int(version_id))
        except Exception as e:
            self.item_tree.insert("", "end", values=(f"加载失败: {e}", "", ""))
            return
        if not items:
            self.item_tree.insert("", "end", values=("该版本暂无排期节点", "", ""))
            return
        for it in items:
            self.item_tree.insert(
                "",
                "end",
                values=(it.get("item") or "", it.get("startDate") or "", it.get("endDate") or ""),
            )

    def _open_browser(self):
        v = self._selected_version()
        vid = v.get("ID") if v else DEFAULT_VERSION_ID
        subprocess.Popen(["open", VERSION_PAGE + str(vid)])


def show_version_calendar(parent):
    VersionCalendarWindow(parent)

# -*- coding: utf-8 -*-
import configparser
import os
import tkinter as tk
from tools.public_tool import (
    UI_FONT,
    get_client_install_dir,
    get_client_version,
    get_appdata_dir,
    get_lstyle_dir,
    get_mac_resources_dir,
)

_is_mac = os.name != "nt"

POLICY_HOST = "policy.video.iqiyi.com"
POLICY_LINE = "10.62.255.141 policy.video.iqiyi.com"
MESH_ONLINE = "106.38.178.216 mesh.if.iqiyi.com"
MESH_TEST = "106.38.178.246 mesh.if.iqiyi.com"
PCW_MAP = [
    ("10.62.88.47", "线上环境"),
    ("10.62.88.48", "patch环境"),
    ("10.62.88.49", "dev环境"),
    ("10.62.88.50", "next环境"),
    ("10.62.88.51", "current环境"),
    ("10.62.88.52", "test4环境"),
    ("10.62.88.53", "test5环境"),
]


def _hosts_path() -> str:
    return "/etc/hosts" if _is_mac else r"C:\Windows\System32\drivers\etc\hosts"


def _psnetwork_path() -> str:
    if _is_mac:
        return os.path.join(get_lstyle_dir(), "psnetwork.ini")
    return r"C:\Users\Public\QiYi\QiyiHCDN\Config\PSNetwork.ini"


def _read_lwa_version(client_dir: str) -> str:
    lwa_version = ""
    try:
        if _is_mac:
            cfg = os.path.join(get_mac_resources_dir(), "lwa_config.json")
            if os.path.exists(cfg):
                import json

                with open(cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ver = (data.get("version") or {}).get("iqiyi_webapp") or ""
                if ver:
                    return "lwa版本号: " + ver
        target_dir = os.path.join(get_appdata_dir(), "IQIYI Video", "localwebapp", "iqiyi_webapp")
        if os.path.isdir(target_dir):
            subfolders = [
                f for f in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, f))
            ]
            if subfolders:
                numeric = next((f for f in subfolders if f[0].isdigit()), "")
                if numeric:
                    lwa_version = "lwa版本号: " + numeric
    except Exception:
        pass
    if lwa_version:
        return lwa_version
    try:
        if _is_mac:
            return ""
        lwa_ini_dir = os.path.join(client_dir, "skin", "LwaRes", "lwa_config.ini")
        with open(lwa_ini_dir, "r", encoding="utf-8", errors="ignore") as file:
            for line in file:
                if "iqiyi_webapp" in line:
                    return "lwa版本号: " + line.split("=", 1)[-1].strip()
    except Exception:
        pass
    return ""


def _host_lines(hosts_content: str, domain: str):
    lines = []
    for i, line in enumerate(hosts_content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if domain in stripped:
            lines.append((i, stripped))
    return lines


def _plain_lwa(client_dir: str) -> str:
    raw = _read_lwa_version(client_dir)
    return raw.replace("lwa版本号: ", "").strip() if raw else "未读到"


def _collect_env():
    client_dir = get_client_install_dir()
    if not client_dir:
        client_ver = "未安装"
        lwa_ver = "—"
        device_id = "—"
    else:
        client_ver = get_client_version() or "未知"
        lwa_ver = _plain_lwa(client_dir)
        try:
            config = configparser.ConfigParser()
            config.read(_psnetwork_path(), encoding="utf-8")
            device_id = config.get("Network", "clientid", fallback="") or "—"
        except Exception:
            device_id = "—"

    try:
        with open(_hosts_path(), "r", encoding="utf-8", errors="ignore") as f:
            hosts_content = f.read()
    except Exception:
        hosts_content = ""

    hosts = []
    policy_hits = _host_lines(hosts_content, POLICY_HOST)
    if not policy_hits:
        hosts.append(
            {
                "name": "policy",
                "kind": "warn",
                "badge": "未绑定",
                "detail": f"建议加上：{POLICY_LINE}",
            }
        )
    elif len(policy_hits) > 1:
        hosts.append(
            {
                "name": "policy",
                "kind": "bad",
                "badge": "重复绑定",
                "detail": "\n".join(x[1] for x in policy_hits),
            }
        )
    else:
        line = policy_hits[0][1]
        if "10.62.255.141" not in line:
            hosts.append(
                {
                    "name": "policy",
                    "kind": "warn",
                    "badge": "IP 不正确",
                    "detail": f"当前：{line}\n应为：{POLICY_LINE}",
                }
            )
        else:
            hosts.append({"name": "policy", "kind": "ok", "badge": "正常", "detail": line})

    mesh_hits = _host_lines(hosts_content, "mesh.if.iqiyi.com")
    if not mesh_hits:
        hosts.append({"name": "mesh", "kind": "warn", "badge": "未绑定", "detail": "请确认 hosts"})
    else:
        text = mesh_hits[0][1]
        if "106.38.178.216" in text:
            hosts.append({"name": "mesh", "kind": "ok", "badge": "线上环境", "detail": text})
        elif "106.38.178.246" in text:
            hosts.append({"name": "mesh", "kind": "ok", "badge": "测试环境", "detail": text})
        elif "106.38.178." in text:
            hosts.append({"name": "mesh", "kind": "ok", "badge": "预发环境", "detail": text})
        else:
            hosts.append({"name": "mesh", "kind": "warn", "badge": "未知环境", "detail": text})

    pcw_hits = _host_lines(hosts_content, "www.iqiyi.com")
    if not pcw_hits:
        hosts.append({"name": "pcw", "kind": "warn", "badge": "未绑定", "detail": "请确认 hosts"})
    else:
        text = pcw_hits[0][1]
        matched = None
        for ip, name in PCW_MAP:
            if ip in text:
                matched = name
                break
        if matched:
            hosts.append({"name": "pcw", "kind": "ok", "badge": matched, "detail": text})
        else:
            hosts.append({"name": "pcw", "kind": "warn", "badge": "未知环境", "detail": text})

    return {
        "client": client_ver,
        "lwa": lwa_ver,
        "device": device_id,
        "hosts": hosts,
    }


def get_env_info(parent):
    from tools.ui_theme import (
        BG,
        CARD,
        MUTED,
        TEXT,
        card,
        ghost_button,
        header_bar,
        pill,
        place_window,
        section_title,
    )

    info = _collect_env()
    win = tk.Toplevel(parent)
    win.title("环境信息")
    place_window(win, parent, 0.88, 580, 520)
    header_bar(win, "环境信息", "客户端版本、LWA、设备号和 hosts")

    wrap = tk.Frame(win, bg=BG)
    wrap.pack(fill="both", expand=True)
    canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
    scroll = tk.Scrollbar(wrap, orient="vertical", command=canvas.yview, width=12)
    canvas.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    body = tk.Frame(canvas, bg=BG)
    body_id = canvas.create_window((0, 0), window=body, anchor="nw")

    def _on_body(_e=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas(e):
        canvas.itemconfigure(body_id, width=e.width)

    body.bind("<Configure>", _on_body)
    canvas.bind("<Configure>", _on_canvas)

    inner = tk.Frame(body, bg=BG)
    inner.pack(fill="both", expand=True, padx=20, pady=16)

    section_title(inner, "客户端")
    row = tk.Frame(inner, bg=BG)
    row.pack(fill="x", pady=(0, 16))
    for i, (label, value) in enumerate(
        (("版本", info["client"]), ("LWA", info["lwa"]), ("设备号", info["device"]))
    ):
        box = card(row)
        box.grid(row=0, column=i, sticky="nsew", padx=(0, 10) if i < 2 else 0)
        row.grid_columnconfigure(i, weight=1)
        tk.Label(box, text=label, bg=CARD, fg=MUTED, font=(UI_FONT, 10), anchor="w").pack(
            fill="x", padx=14, pady=(12, 0)
        )
        val = tk.Entry(
            box,
            font=(UI_FONT, 13, "bold"),
            fg=TEXT,
            bg=CARD,
            relief="flat",
            highlightthickness=0,
            readonlybackground=CARD,
        )
        val.insert(0, value)
        val.config(state="readonly")
        val.pack(fill="x", padx=14, pady=(4, 14))

    section_title(inner, "Hosts")
    for item in info["hosts"]:
        box = card(inner)
        box.pack(fill="x", pady=(0, 10))
        top = tk.Frame(box, bg=CARD)
        top.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(
            top, text=item["name"], bg=CARD, fg=TEXT, font=(UI_FONT, 13, "bold")
        ).pack(side="left")
        pill(top, item["badge"], item["kind"]).pack(side="right")
        tk.Label(
            box,
            text=item["detail"],
            bg=CARD,
            fg=MUTED,
            font=(UI_FONT, 11),
            anchor="w",
            justify="left",
            wraplength=520,
        ).pack(fill="x", padx=14, pady=(0, 12))

    btns = tk.Frame(win, bg=BG)
    btns.pack(fill="x", padx=20, pady=(0, 16))
    ghost_button(btns, "关闭", win.destroy).pack(side="right")
    win.grab_set()


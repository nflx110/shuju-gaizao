#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仅本机优化 Charles：限制堆内存、卡住会话体积、丢掉失效 Ignore、清旧证书。

不改 /Applications/Charles.app（避免破坏官方签名和 ProxyHelper）。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HOME = Path.home()
PREFS = HOME / "Library/Preferences/com.xk72.charles.config"
PROFILE = HOME / "Library/Application Support/Charles/profiles/default.cfg.xml"
CERTS = HOME / "Library/Application Support/Charles/certs"
BACKUP_DIR = HOME / "Library/Application Support/Charles/backup"
MARKER_HOST = "charles-local-opt.invalid"
CERT_KEEP_DAYS = 14
MAX_TRANSACTIONS = 3000
# 读 mixer/query 用等宽小字：原先 Default 20 号会把表格撑得很空
DISPLAY_FONT = "Menlo"
DISPLAY_FONT_SIZE = 13
LOOK_AND_FEEL_FONT_SIZE = 13

IGNORE_HOSTS_XML = f"""    <ignoreHosts>
      <locationPatterns>
        <locationMatch>
          <location>
            <host>{MARKER_HOST}</host>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <protocol>http</protocol>
            <host>*</host>
            <path>/videos</path>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <protocol>https</protocol>
            <host>*</host>
            <path>/videos</path>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <protocol>https</protocol>
            <host>*</host>
            <path>/videos/vts</path>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <host>data.video.iqiyi.com</host>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <host>*.video.iqiyi.com</host>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <host>ocsp.apple.com</host>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <host>*.mzstatic.com</host>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <host>swscan.apple.com</host>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <host>*.gvt1.com</host>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <host>*.gvt2.com</host>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <host>update.googleapis.com</host>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <host>*.crashlytics.com</host>
          </location>
        </locationMatch>
        <locationMatch>
          <location>
            <host>*.app-measurement.com</host>
          </location>
        </locationMatch>
      </locationPatterns>
    </ignoreHosts>"""

SSL_ALL_PORTS = re.compile(
    r"\s*<locationMatch>\s*"
    r"<location>\s*"
    r"<host>\*</host>\s*"
    r"<port>\*</port>\s*"
    r"</location>\s*"
    r"</locationMatch>",
    re.S,
)

MAX_TX_RE = re.compile(
    r"(<string>sequence\.maxTransactions</string>\s*<int>)(\d+)(</int>)",
    re.S,
)


def log(msg: str) -> None:
    print(msg, flush=True)


def charles_pids() -> list[str]:
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "/Applications/Charles.app/Contents/MacOS/Charles"],
            text=True,
        )
        return [p for p in out.split() if p]
    except subprocess.CalledProcessError:
        return []


def quit_charles(timeout: float = 25.0) -> None:
    pids = charles_pids()
    if not pids:
        log("Charles 未在运行。")
        return
    log(f"正在退出 Charles（pid {', '.join(pids)}），避免它把旧配置写回来…")
    subprocess.run(
        ["osascript", "-e", 'tell application "Charles" to quit'],
        check=False,
        capture_output=True,
        text=True,
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not charles_pids():
            log("Charles 已退出。")
            time.sleep(0.8)
            return
        time.sleep(0.4)
    # 仍在：可能卡在保存对话框，温和结束 Java 进程
    for pid in charles_pids():
        try:
            os.kill(int(pid), 15)
        except OSError:
            pass
    time.sleep(2)
    if charles_pids():
        raise SystemExit("Charles 仍未退出。请手动退出后再运行本脚本。")
    log("Charles 已结束。")


def backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"{path.name}.{stamp}.bak"
    shutil.copy2(path, dest)
    log(f"已备份 {path.name} → {dest}")
    return dest


def disable_breakpoint(xml: str, host: str, path_substr: str) -> tuple[str, bool]:
    # 不跨 breakpoint 边界，避免误伤相邻规则
    inner = r"(?:(?!</breakpoint>).)"
    pattern = re.compile(
        r"(<breakpoint>)("
        + inner
        + r"*<host>"
        + re.escape(host)
        + r"</host>"
        + inner
        + r"*<path>[^<]*"
        + re.escape(path_substr)
        + r"[^<]*</path>"
        + inner
        + r"*)(</breakpoint>)",
        re.S,
    )

    def repl(m: re.Match[str]) -> str:
        body = m.group(2)
        if "<enabled>false</enabled>" in body:
            return m.group(0)
        if "<enabled>true</enabled>" in body:
            body = body.replace("<enabled>true</enabled>", "<enabled>false</enabled>", 1)
        else:
            body = body.rstrip() + "\n              <enabled>false</enabled>\n            "
        return m.group(1) + body + m.group(3)

    new, n = pattern.subn(repl, xml, count=1)
    return new, n > 0 and new != xml


def patch_xml(xml: str) -> tuple[str, list[str]]:
    notes: list[str] = []

    if SSL_ALL_PORTS.search(xml):
        xml = SSL_ALL_PORTS.sub("", xml, count=1)
        notes.append("去掉 SSL Proxying 的 *:*（保留 *:443）")

    ignore_block = ""
    if "<ignoreHosts>" in xml:
        ignore_block = xml.split("<ignoreHosts>", 1)[1].split("</ignoreHosts>", 1)[0]
    if MARKER_HOST not in ignore_block:
        xml2, n = re.subn(
            r"<ignoreHosts>.*?</ignoreHosts>",
            IGNORE_HOSTS_XML,
            xml,
            count=1,
            flags=re.S,
        )
        if n:
            xml = xml2
            notes.append("清理失效 Ignore 规则，并启用视频/系统更新流量排除")
    else:
        notes.append("Ignore 规则已是优化版，跳过")

    def tx_repl(m: re.Match[str]) -> str:
        cur = int(m.group(2))
        if cur == 0:
            notes.append(f"会话条数上限 0（无限）→ {MAX_TRANSACTIONS}")
            return f"{m.group(1)}{MAX_TRANSACTIONS}{m.group(3)}"
        notes.append(f"会话条数上限保持 {cur}")
        return m.group(0)

    if MAX_TX_RE.search(xml):
        xml = MAX_TX_RE.sub(tx_repl, xml, count=1)
    elif "<userInterfaceConfiguration>" in xml:
        insert = (
            "    <properties>\n"
            "      <entry>\n"
            "        <string>sequence.maxTransactions</string>\n"
            f"        <int>{MAX_TRANSACTIONS}</int>\n"
            "      </entry>\n"
            "    </properties>\n"
        )
        if "<properties>" in xml[xml.find("<userInterfaceConfiguration>"):xml.find("</userInterfaceConfiguration>")]:
            xml = xml.replace(
                "</properties>\n  </userInterfaceConfiguration>",
                "      <entry>\n"
                "        <string>sequence.maxTransactions</string>\n"
                f"        <int>{MAX_TRANSACTIONS}</int>\n"
                "      </entry>\n"
                "    </properties>\n  </userInterfaceConfiguration>",
                1,
            )
            notes.append(f"补上会话条数上限 {MAX_TRANSACTIONS}")
        else:
            xml = xml.replace(
                "  </userInterfaceConfiguration>",
                insert + "  </userInterfaceConfiguration>",
                1,
            )
            notes.append(f"补上会话条数上限 {MAX_TRANSACTIONS}")
    else:
        notes.append("未找到 sequence.maxTransactions，跳过")

    xml, changed = disable_breakpoint(xml, "data.video.iqiyi.com", ".mp4")
    if changed:
        notes.append("关闭大视频 Breakpoint（mp4），避免拦截片源卡死")
    xml, changed = disable_breakpoint(xml, "sc.appvipshop.com", "/vips-mobile-tracker/router.do")
    if changed:
        notes.append("关闭无关的唯品会 Breakpoint")

    xml, ui_notes = patch_ui(xml)
    notes.extend(ui_notes)

    xml, remote_on = enable_web_interface(xml)
    if remote_on:
        notes.append("打开 Charles Web Interface，供一键开关 Rewrite/Map/DNS")

    return xml, notes


def enable_web_interface(xml: str) -> tuple[str, bool]:
    if "<remoteControlConfiguration>" not in xml:
        return xml, False
    inner = xml.split("<remoteControlConfiguration>", 1)[1].split(
        "</remoteControlConfiguration>", 1
    )[0]
    if "<enabled>true</enabled>" in inner:
        return xml, False
    block = (
        "  <remoteControlConfiguration>\n"
        "    <enabled>true</enabled>\n"
        "    <allowAnonymous>true</allowAnonymous>\n"
        "  </remoteControlConfiguration>"
    )
    new, n = re.subn(
        r"<remoteControlConfiguration>.*?</remoteControlConfiguration>",
        block,
        xml,
        count=1,
        flags=re.S,
    )
    return new, n > 0



def _upsert_ui_tag(xml: str, tag: str, value: str, after_tag: str) -> tuple[str, bool]:
    pat = re.compile(rf"<{tag}>.*?</{tag}>", re.S)
    replacement = f"<{tag}>{value}</{tag}>"
    if pat.search(xml):
        new, n = pat.subn(replacement, xml, count=1)
        return new, n > 0 and new != xml
    anchor = re.compile(rf"(<{after_tag}>.*?</{after_tag}>)")
    if anchor.search(xml):
        new, n = anchor.subn(rf"\1\n    {replacement}", xml, count=1)
        return new, n > 0
    return xml, False


def patch_ui(xml: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    if "<userInterfaceConfiguration>" not in xml:
        return xml, notes

    before = xml
    xml, ch = _upsert_ui_tag(xml, "displayFont", DISPLAY_FONT, "displayFont")
    xml, ch2 = _upsert_ui_tag(xml, "displayFontSize", str(DISPLAY_FONT_SIZE), "displayFont")
    xml, ch3 = _upsert_ui_tag(
        xml, "lookAndFeelFontSize", str(LOOK_AND_FEEL_FONT_SIZE), "displayFontSize"
    )
    xml, ch4 = _upsert_ui_tag(xml, "showLineNumbers", "true", "combineRequestAndResponse")
    xml, ch5 = _upsert_ui_tag(xml, "lineWrap", "false", "showLineNumbers")
    xml, ch6 = _upsert_ui_tag(xml, "highlightTreeChanges", "true", "queryParamHighlight")
    xml, ch7 = _upsert_ui_tag(xml, "queryParamHighlight", "COLOR", "queryParamHighlight")
    if xml != before:
        notes.append(
            f"界面改为 {DISPLAY_FONT} {DISPLAY_FONT_SIZE} 号等宽、行号打开，Query/JSON 更密更好对"
        )
    elif ch or ch2 or ch3 or ch4 or ch5 or ch6 or ch7:
        notes.append("界面字体已是优化版")
    return xml, notes


def patch_config(path: Path) -> None:
    if not path.exists():
        log(f"不存在，跳过：{path}")
        return
    original = path.read_text(encoding="utf-8", errors="replace")
    patched, notes = patch_xml(original)
    if patched == original:
        log(f"{path.name}：无需再改（{'; '.join(notes) or '无变更'}）")
        return
    path.write_text(patched, encoding="utf-8")
    log(f"{path.name} 已写入：")
    for n in notes:
        log(f"  - {n}")


def cleanup_certs(keep_days: int = CERT_KEEP_DAYS) -> None:
    if not CERTS.is_dir():
        log("没有 certs 目录，跳过。")
        return
    cutoff = time.time() - keep_days * 86400
    removed = 0
    kept = 0
    for p in CERTS.iterdir():
        if not p.is_file():
            continue
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
            else:
                kept += 1
        except OSError:
            kept += 1
    log(f"证书清理：删除 {removed} 个（超过 {keep_days} 天），保留 {kept} 个。")


def java_opts() -> str:
    # Charles 自带 JRE 没有 java.instrument，不能用 -javaagent
    return (
        "-Xms256m -Xmx2048m -XX:SoftMaxHeapSize=1536m "
        "-XX:ZUncommitDelay=30 -XX:+UseStringDeduplication"
    )


def launch_charles() -> None:
    opts = java_opts()
    env = os.environ.copy()
    env["JAVA_TOOL_OPTIONS"] = opts
    env["_JAVA_OPTIONS"] = opts
    log("使用本地 JVM 参数启动 Charles：")
    log(f"  {opts}")
    subprocess.run(["launchctl", "setenv", "JAVA_TOOL_OPTIONS", opts], check=False)
    subprocess.run(["launchctl", "setenv", "_JAVA_OPTIONS", opts], check=False)
    subprocess.run(
        [
            "open",
            "--env",
            f"JAVA_TOOL_OPTIONS={opts}",
            "--env",
            f"_JAVA_OPTIONS={opts}",
            "-a",
            "Charles",
        ],
        check=False,
        env=env,
    )
    launch_tool_toggles()


def launch_tool_toggles() -> None:
    here = Path(__file__).resolve().parent
    script = here / "tool_toggles.py"
    if not script.exists():
        return
    py = Path("/opt/homebrew/bin/python3.13")
    exe = str(py) if py.exists() else sys.executable
    # 避免叠多个开关条
    subprocess.run(["pkill", "-f", "charles_local_opt/tool_toggles.py"], check=False)
    time.sleep(0.2)
    subprocess.Popen(
        [exe, str(script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    log("已打开一键开关条（Rewrite / Map / DNS），会贴在 Charles 工具栏空位上。")


def main() -> int:
    args = set(sys.argv[1:])
    do_quit = "--no-quit" not in args
    do_launch = "--no-launch" not in args
    do_certs = "--no-certs" not in args

    log("=== Charles 本机优化 ===")
    if do_quit:
        quit_charles()

    backup_file(PREFS)
    backup_file(PROFILE)
    patch_config(PREFS)
    patch_config(PROFILE)

    if do_certs:
        cleanup_certs()

    if do_launch:
        launch_charles()
        log("已启动。请用本脚本或「启动Charles（防崩溃）.command」打开，不要直接点 Dock 里的旧图标（那样没有内存上限）。")
    log("完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

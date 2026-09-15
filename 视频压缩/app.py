# -*- coding: utf-8 -*-
"""把录屏压到指定大小（默认 10MB）以内。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

UI_FONT = "PingFang SC"
BG = "#F4F1EA"
CARD = "#FFFDF8"
TEXT = "#1C1914"
MUTED = "#6B6458"
LINE = "#DDD6C8"
HEADER = "#3F37C9"
ACCENT = "#4361EE"
OK = "#1F7A4D"
BAD = "#B42318"

TARGET_MB = 10
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm")


def _which(name: str) -> str:
    extra = ["/opt/homebrew/bin", "/usr/local/bin"]
    path = os.environ.get("PATH", "")
    os.environ["PATH"] = ":".join(extra + [path])
    found = shutil.which(name)
    if found:
        return found
    for folder in extra:
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""


FFMPEG = _which("ffmpeg")
FFPROBE = _which("ffprobe")


def human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def human_duration(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def probe(path: str) -> dict:
    raw = subprocess.check_output(
        [
            FFPROBE,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            path,
        ],
        stderr=subprocess.STDOUT,
    )
    data = json.loads(raw.decode("utf-8", "replace"))
    fmt = data.get("format") or {}
    video = {}
    has_audio = False
    for stream in data.get("streams") or []:
        if stream.get("codec_type") == "video" and not video:
            video = stream
        elif stream.get("codec_type") == "audio":
            has_audio = True
    fps = 30.0
    rate = str(video.get("r_frame_rate") or "30/1")
    if "/" in rate:
        a, b = rate.split("/", 1)
        if float(b):
            fps = float(a) / float(b)
    return {
        "duration": float(fmt.get("duration") or 0),
        "size": int(fmt.get("size") or os.path.getsize(path)),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": fps,
        "has_audio": has_audio,
    }


def _pick_scale(width: int, height: int, video_bps: int) -> tuple[int, int]:
    """低码率时缩小分辨率，避免糊成一团。"""
    if width <= 0 or height <= 0:
        return 1280, 720
    max_w = width
    if video_bps < 1_200_000 and width > 1280:
        max_w = 1280
    if video_bps < 700_000 and width > 960:
        max_w = 960
    if video_bps < 400_000 and width > 854:
        max_w = 854
    if video_bps < 220_000 and width > 640:
        max_w = 640
    if max_w >= width:
        return width, height
    h = int(round(height * (max_w / width)))
    h -= h % 2
    return max_w - (max_w % 2), max(h, 2)


def _pick_fps(src_fps: float, video_bps: int) -> int:
    fps = int(round(src_fps)) or 30
    if video_bps < 800_000:
        fps = min(fps, 20)
    if video_bps < 350_000:
        fps = min(fps, 15)
    return max(fps, 12)


def _run_ffmpeg(cmd: list[str], duration: float, on_progress) -> None:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    tail: list[str] = []
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        tail.append(line)
        if len(tail) > 20:
            tail.pop(0)
        if line.startswith("out_time_ms="):
            try:
                ms = int(line.split("=", 1)[1])
                if duration > 0:
                    on_progress(min(ms / 1_000_000 / duration, 0.99))
            except ValueError:
                pass
        elif line.startswith("progress=") and line.endswith("end"):
            on_progress(1.0)
    code = proc.wait()
    if code != 0:
        detail = "\n".join(tail[-8:]) or f"退出码 {code}"
        raise RuntimeError(detail)


def compress_to_limit(
    src: str,
    dst: str,
    target_mb: float,
    on_log,
    on_progress,
) -> int:
    info = probe(src)
    duration = info["duration"]
    if duration <= 0.2:
        raise RuntimeError("读不到视频时长")

    # 预留封装开销，按 92% 目标码率压，保证落在限额内
    budget = int(target_mb * 1024 * 1024 * 0.92)
    total_bps = int(budget * 8 / duration)
    audio_bps = 48_000 if info["has_audio"] else 0
    video_bps = max(total_bps - audio_bps, 120_000)
    out_w, out_h = _pick_scale(info["width"], info["height"], video_bps)
    fps = _pick_fps(info["fps"], video_bps)
    vf = f"scale={out_w}:{out_h}:flags=lanczos,fps={fps}"

    on_log(
        f"原片 {human_size(info['size'])} · {human_duration(duration)} · "
        f"{info['width']}x{info['height']} @{info['fps']:.0f}fps"
    )
    on_log(
        f"目标 ≤{target_mb:g}MB · 视频 {video_bps // 1000}kbps · "
        f"{out_w}x{out_h} @{fps}fps"
        + (" · 保留音频 48kbps" if audio_bps else " · 无音轨")
    )

    work = tempfile.mkdtemp(prefix="vcompress-")
    passlog = os.path.join(work, "ffmpeg2pass")
    common = [
        FFMPEG,
        "-hide_banner",
        "-y",
        "-i",
        src,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-b:v",
        str(video_bps),
        "-maxrate",
        str(int(video_bps * 1.15)),
        "-bufsize",
        str(video_bps * 2),
        "-vf",
        vf,
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
    ]

    try:
        on_log("第 1 遍：分析画面…")
        pass1 = common + [
            "-pass",
            "1",
            "-passlogfile",
            passlog,
            "-an",
            "-f",
            "null",
            os.devnull,
        ]
        _run_ffmpeg(pass1, duration, lambda p: on_progress(p * 0.45))

        on_log("第 2 遍：写出压缩文件…")
        pass2 = common + ["-pass", "2", "-passlogfile", passlog]
        if info["has_audio"]:
            pass2 += ["-c:a", "aac", "-b:a", str(audio_bps), "-ac", "1"]
        else:
            pass2 += ["-an"]
        pass2.append(dst)
        _run_ffmpeg(pass2, duration, lambda p: on_progress(0.45 + p * 0.55))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    size = os.path.getsize(dst)
    limit = int(target_mb * 1024 * 1024)
    if size > limit:
        os.remove(dst)
        raise RuntimeError(
            f"压完仍有 {human_size(size)}，超过 {target_mb:g}MB。可以再把目标调低一点重试。"
        )
    on_progress(1.0)
    on_log(f"完成：{human_size(size)}  →  {dst}")
    return size


class CompressApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.src = ""
        self.busy = False
        self._build()

    def _build(self):
        root = self.root
        root.title("录屏压缩到 10MB")
        root.configure(bg=BG)
        w, h = 560, 520
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 5
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.minsize(520, 460)

        header = tk.Frame(root, bg=HEADER, height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="录屏压缩到 10MB",
            bg=HEADER,
            fg="#FFFFFF",
            font=(UI_FONT, 18, "bold"),
        ).pack(anchor="w", padx=22, pady=(14, 0))
        tk.Label(
            header,
            text="适合微信 / 工单附件。原文件不动，在旁边生成 *_10M.mp4",
            bg=HEADER,
            fg="#D7DBFF",
            font=(UI_FONT, 11),
        ).pack(anchor="w", padx=22, pady=(2, 12))

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=16)

        pick = tk.Frame(body, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        pick.pack(fill="x")
        tk.Button(
            pick,
            text="选择视频",
            command=self.choose_file,
            bg=ACCENT,
            fg="white",
            relief="flat",
            padx=14,
            pady=7,
            font=(UI_FONT, 12, "bold"),
            cursor="hand2",
            activebackground="#3651D4",
            activeforeground="white",
        ).pack(side="left", padx=12, pady=12)
        self.file_lbl = tk.Label(
            pick,
            text="还没选文件，也可把视频拖进窗口",
            bg=CARD,
            fg=MUTED,
            font=(UI_FONT, 12),
            anchor="w",
            wraplength=360,
            justify="left",
        )
        self.file_lbl.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.info_lbl = tk.Label(
            body,
            text="",
            bg=BG,
            fg=TEXT,
            font=(UI_FONT, 12),
            anchor="w",
            justify="left",
        )
        self.info_lbl.pack(fill="x", pady=(12, 0))

        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(10, 0))
        tk.Label(row, text="上限", bg=BG, fg=MUTED, font=(UI_FONT, 12)).pack(side="left")
        self.target_var = tk.StringVar(value=str(TARGET_MB))
        tk.Entry(
            row,
            textvariable=self.target_var,
            width=6,
            font=(UI_FONT, 12),
            relief="solid",
            bd=1,
            highlightthickness=0,
        ).pack(side="left", padx=8)
        tk.Label(row, text="MB", bg=BG, fg=MUTED, font=(UI_FONT, 12)).pack(side="left")

        self.go_btn = tk.Button(
            body,
            text="开始压缩",
            command=self.start,
            bg=HEADER,
            fg="white",
            relief="flat",
            padx=16,
            pady=8,
            font=(UI_FONT, 13, "bold"),
            cursor="hand2",
            activebackground="#332FA8",
            activeforeground="white",
        )
        self.go_btn.pack(fill="x", pady=(14, 8))

        self.bar = tk.Canvas(body, height=10, bg=LINE, highlightthickness=0)
        self.bar.pack(fill="x")
        self._bar_fill = self.bar.create_rectangle(0, 0, 0, 10, fill=ACCENT, width=0)

        self.log = tk.Text(
            body,
            height=10,
            bg=CARD,
            fg=TEXT,
            font=("Menlo", 11),
            relief="flat",
            highlightthickness=1,
            highlightbackground=LINE,
            wrap="word",
        )
        self.log.pack(fill="both", expand=True, pady=(10, 0))
        self.log.configure(state="disabled")

        root.drop_target_register = getattr(root, "drop_target_register", None)
        try:
            root.tk.call("package", "require", "tkdnd")
        except tk.TclError:
            pass
    def choose_file(self):
        path = filedialog.askopenfilename(
            title="选择要压缩的录屏",
            filetypes=[
                ("视频", "*.mp4 *.mov *.mkv *.m4v *.avi *.webm"),
                ("全部", "*.*"),
            ],
        )
        if path:
            self._set_src(path)

    def _set_src(self, path: str):
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            return
        if os.path.splitext(path)[1].lower() not in VIDEO_EXTS:
            messagebox.showwarning("提示", "请选视频文件（mp4 / mov 等）")
            return
        self.src = path
        self.file_lbl.configure(text=os.path.basename(path), fg=TEXT)
        try:
            info = probe(path)
            self.info_lbl.configure(
                text=(
                    f"当前 {human_size(info['size'])}  ·  {human_duration(info['duration'])}  ·  "
                    f"{info['width']}×{info['height']}  ·  {info['fps']:.0f}fps"
                )
            )
        except Exception as e:
            self.info_lbl.configure(text=f"读文件信息失败：{e}")

    def _append(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_progress(self, ratio: float):
        self.bar.update_idletasks()
        w = self.bar.winfo_width()
        self.bar.coords(self._bar_fill, 0, 0, max(0, int(w * ratio)), 10)

    def start(self):
        if self.busy:
            return
        if not FFMPEG or not FFPROBE:
            messagebox.showerror(
                "缺少 ffmpeg",
                "本机还没有 ffmpeg。请在终端执行：\n\nbrew install ffmpeg",
            )
            return
        if not self.src:
            messagebox.showinfo("提示", "先选一个视频")
            return
        try:
            target = float(self.target_var.get().strip())
        except ValueError:
            messagebox.showwarning("提示", "上限请填数字，例如 10")
            return
        if target <= 0:
            messagebox.showwarning("提示", "上限必须大于 0")
            return

        base, ext = os.path.splitext(self.src)
        tag = f"{int(target) if target == int(target) else target}M"
        dst = f"{base}_{tag}.mp4"
        if os.path.abspath(dst) == os.path.abspath(self.src):
            dst = f"{base}_compressed.mp4"

        self.busy = True
        self.go_btn.configure(state="disabled", text="压缩中…")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._set_progress(0)

        def work():
            try:

                def log(msg):
                    self.root.after(0, lambda m=msg: self._append(m))

                def prog(p):
                    self.root.after(0, lambda r=p: self._set_progress(r))

                size = compress_to_limit(self.src, dst, target, log, prog)
                self.root.after(0, lambda: self._done(True, dst, size, target))
            except Exception as e:
                self.root.after(0, lambda: self._done(False, dst, 0, target, str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _done(self, ok: bool, dst: str, size: int, target: float, err: str = ""):
        self.busy = False
        self.go_btn.configure(state="normal", text="开始压缩")
        if ok:
            self._append("")
            self._append(f"已压到 {human_size(size)}，低于 {target:g}MB。")
            if messagebox.askyesno("完成", f"已生成 {human_size(size)}\n\n{dst}\n\n要在 Finder 里打开吗？"):
                subprocess.run(["open", "-R", dst], check=False)
        else:
            self._append(f"失败：{err}")
            messagebox.showerror("压缩失败", err)


def _cli(src: str, target_mb: float) -> int:
    if not FFMPEG or not FFPROBE:
        print("缺少 ffmpeg，请先执行：brew install ffmpeg")
        return 1
    src = os.path.abspath(src)
    if not os.path.isfile(src):
        print(f"找不到文件：{src}")
        return 1
    base, _ = os.path.splitext(src)
    tag = f"{int(target_mb) if target_mb == int(target_mb) else target_mb}M"
    dst = f"{base}_{tag}.mp4"
    print(f"输入：{src}")
    print(f"输出：{dst}")
    last = [0.0]

    def log(msg):
        print(msg)

    def prog(p):
        if p - last[0] >= 0.05 or p >= 1:
            last[0] = p
            print(f"进度 {p * 100:.0f}%")

    size = compress_to_limit(src, dst, target_mb, log, prog)
    print(f"已压到 {human_size(size)}")
    return 0


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        src = args[0]
        target = float(args[1]) if len(args) > 1 else float(TARGET_MB)
        try:
            sys.exit(_cli(src, target))
        except Exception as e:
            print(f"失败：{e}")
            sys.exit(1)
    root = tk.Tk()
    CompressApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从本机 Charles 实时拉取抓包，筛选后做 mixer response 对比。"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HOST = "127.0.0.1"
PORT = 8765
CHARLES_PROXY = "http://127.0.0.1:8888"
EXPORT_URLS = (
    "http://control.charles/session/export-json",
    "http://control.charles/session/export?format=json",
)
MAX_STORE = 4000
MAX_BODY = 2_000_000
FETCH_INTERVAL = 8

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

_lock = threading.Lock()
_cache = {
    "ok": False,
    "reason": "尚未拉取",
    "fetched_at": 0,
    "entries": {},  # id -> dict
    "order": [],
    "raw_count": 0,
    "match_count": 0,
}


def _via_proxy(url: str, timeout: float = 45) -> tuple[int, bytes, str]:
    proxy = urllib.request.ProxyHandler({"http": CHARLES_PROXY, "https": CHARLES_PROXY})
    opener = urllib.request.build_opener(proxy)
    req = urllib.request.Request(url, headers={"User-Agent": "charles-mixer/1.0"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, data, ctype
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b"", e.headers.get("Content-Type", "") if e.headers else ""


def decode_body(node: dict | None) -> str:
    if not node or not isinstance(node, dict):
        return ""
    body = node.get("body")
    raw = b""
    if body is None:
        return ""
    if isinstance(body, str):
        raw = body.encode("utf-8", "replace")
        encoding = ""
    elif isinstance(body, dict):
        text = body.get("text") or body.get("encodedText") or ""
        encoding = str(body.get("encoding") or "")
        enc_meta = body.get("encoded")
        if isinstance(enc_meta, dict):
            encoding = str(enc_meta.get("encoding") or encoding)
        if str(encoding).lower() == "base64" and text:
            try:
                raw = base64.b64decode(text)
            except Exception:
                raw = str(text).encode("utf-8", "replace")
        else:
            raw = str(text).encode("utf-8", "replace")
    else:
        return str(body)
    ce = str(node.get("contentEncoding") or "").lower()
    if raw[:2] == b"\x1f\x8b" or "gzip" in ce:
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
    charset = node.get("charset") or "utf-8"
    try:
        return raw.decode(str(charset), "replace")
    except Exception:
        return raw.decode("utf-8", "replace")


def decode_har_content(content: dict | None) -> str:
    if not content:
        return ""
    text = content.get("text") or ""
    if content.get("encoding") == "base64" and text:
        try:
            raw = base64.b64decode(text)
        except Exception:
            return str(text)
        if raw[:2] == b"\x1f\x8b":
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
        return raw.decode("utf-8", "replace")
    return str(text)


def ad_hint(text: str) -> tuple[str, str]:
    sample = text[:80000]
    zones = list(dict.fromkeys(re.findall(r'"adZoneId"\s*:\s*"?(\d+)', sample)))[:8]
    tpls = list(dict.fromkeys(re.findall(r'"templateType"\s*:\s*"([^"]+)"', sample)))[:6]
    return ",".join(zones), ",".join(tpls)


def make_id(method: str, url: str, started: str, status: int, body: str, client: str = "") -> str:
    h = hashlib.sha1(
        f"{method}|{url}|{started}|{status}|{client}|{len(body)}|{body[:80]}".encode("utf-8", "replace")
    )
    return h.hexdigest()[:16]


def pick_ua(headers) -> str:
    if not isinstance(headers, list):
        return ""
    for it in headers:
        if isinstance(it, dict) and str(it.get("name") or "").lower() == "user-agent":
            return str(it.get("value") or "")[:120]
    return ""


def classify_source(client: str, ua: str) -> str:
    ip = (client or "").split("%")[0].strip().lower()
    ual = (ua or "").lower()
    phone_ua = any(
        x in ual
        for x in ("iphone", "android", "harmony", "huawei", "okhttp", "dalvik", "mobile safari")
    )
    if ip in ("127.0.0.1", "::1", "localhost", "0:0:0:0:0:0:0:1", "::ffff:127.0.0.1"):
        return "手机" if phone_ua else "本机"
    if ip.startswith(
        (
            "192.168.",
            "10.",
            "172.16.",
            "172.17.",
            "172.18.",
            "172.19.",
            "172.20.",
            "172.21.",
            "172.22.",
            "172.23.",
            "172.24.",
            "172.25.",
            "172.26.",
            "172.27.",
            "172.28.",
            "172.29.",
            "172.30.",
            "172.31.",
        )
    ):
        return "手机"
    if phone_ua:
        return "手机"
    return "本机" if ip else "未知"


def request_headers(req: dict) -> list:
    if not isinstance(req, dict):
        return []
    h = req.get("header") or req.get("headers") or {}
    if isinstance(h, dict):
        return h.get("headers") or []
    if isinstance(h, list):
        return h
    return []


def normalize_charles_entry(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    host = item.get("host") or ""
    path = item.get("path") or ""
    query = item.get("query") or ""
    scheme = item.get("scheme") or item.get("protocol") or "https"
    port = item.get("actualPort") or item.get("port") or ""
    url = item.get("originalUrl") or item.get("url")
    if not url:
        netloc = host
        if port and str(port) not in ("80", "443", ""):
            netloc = f"{host}:{port}"
        url = f"{scheme}://{netloc}{path}" if host else (path or "(unknown)")
        if query:
            url += ("?" if "?" not in url else "&") + query
    req = item.get("request") if isinstance(item.get("request"), dict) else {}
    resp = item.get("response") if isinstance(item.get("response"), dict) else {}
    body = decode_body(resp)[:MAX_BODY]
    times = item.get("times") if isinstance(item.get("times"), dict) else {}
    started = str(times.get("start") or item.get("startDate") or item.get("startTime") or "")
    rec = str(item.get("status") or "")
    status = resp.get("status") or item.get("responseStatus") or 0
    try:
        status = int(status)
    except Exception:
        status = 0
    method = item.get("method") or req.get("method") or ("CONNECT" if item.get("tunnel") else "GET")
    ua = pick_ua(request_headers(req))
    client = str(item.get("clientAddress") or item.get("client") or "")
    source = classify_source(client, ua)
    zones, tpls = ad_hint(body)
    eid = make_id(method, url, started, status, body, client)
    return {
        "id": eid,
        "method": method,
        "host": host,
        "path": path,
        "url": url,
        "status": status,
        "rec": rec,
        "started": started,
        "size": len(body),
        "zones": zones,
        "templates": tpls,
        "body": body,
        "client": client,
        "source": source,
        "ua": ua,
        "ssl": bool(item.get("ssl") or scheme == "https"),
    }


def normalize_har_entry(item: dict) -> dict | None:
    req = item.get("request") or {}
    resp = item.get("response") or {}
    url = req.get("url") or ""
    parsed = urlparse(url)
    body = decode_har_content(resp.get("content"))[:MAX_BODY]
    started = item.get("startedDateTime") or ""
    method = req.get("method") or "GET"
    status = resp.get("status") or 0
    ua = pick_ua(req.get("headers") or [])
    client = str(item.get("clientIPAddress") or "")
    source = classify_source(client, ua)
    zones, tpls = ad_hint(body)
    eid = make_id(method, url, started, int(status or 0), body, client)
    return {
        "id": eid,
        "method": method,
        "host": parsed.hostname or "",
        "path": parsed.path or "",
        "url": url,
        "status": int(status or 0),
        "rec": "",
        "started": started,
        "size": len(body),
        "zones": zones,
        "templates": tpls,
        "body": body,
        "client": client,
        "source": source,
        "ua": ua,
        "ssl": parsed.scheme == "https",
    }


def parse_session_payload(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8", "replace").lstrip("\ufeff")
    if "Web Interface is disabled" in text or "Web Interface Settings" in text and "<h1>Charles Web Interface</h1>" in text:
        raise RuntimeError("web_interface_disabled")
    if text.lstrip().startswith("<"):
        raise RuntimeError("not_json")
    data = json.loads(text)
    out = []
    if isinstance(data, list):
        for item in data:
            n = normalize_charles_entry(item)
            if n:
                out.append(n)
        return out
    if isinstance(data, dict):
        if "log" in data and isinstance(data["log"], dict):
            for item in data["log"].get("entries") or []:
                n = normalize_har_entry(item)
                if n:
                    out.append(n)
            return out
        # 有的版本包一层
        for key in ("charles", "session", "entries", "requests"):
            if isinstance(data.get(key), list):
                for item in data[key]:
                    n = normalize_charles_entry(item) or normalize_har_entry(item)
                    if n:
                        out.append(n)
                return out
    raise RuntimeError("unknown_format")


def match_filter(entry: dict, query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return True
    hay = " ".join(
        [
            entry.get("method", ""),
            entry.get("host", ""),
            entry.get("path", ""),
            entry.get("url", ""),
            entry.get("zones", ""),
            entry.get("templates", ""),
            entry.get("source", ""),
            entry.get("client", ""),
            entry.get("ua", ""),
        ]
    ).lower()
    return all(part in hay for part in q.split())


def fetch_charles() -> tuple[bool, str, list[dict], int]:
    last_err = "unreachable"
    for url in EXPORT_URLS:
        try:
            code, data, _ = _via_proxy(url)
        except Exception as e:
            last_err = str(e)
            continue
        if code != 200:
            last_err = f"http_{code}"
            continue
        try:
            entries = parse_session_payload(data)
            return True, "ok", entries, len(entries)
        except RuntimeError as e:
            last_err = str(e)
            if last_err == "web_interface_disabled":
                return False, last_err, [], 0
            continue
        except Exception as e:
            last_err = str(e)
            continue
    return False, last_err, [], 0


def refresh_cache(query: str) -> dict:
    with _lock:
        now = time.time()
        if now - _cache["fetched_at"] < FETCH_INTERVAL and _cache["fetched_at"]:
            return snapshot(query)
    ok, reason, entries, raw_count = fetch_charles()
    with _lock:
        _cache["ok"] = ok
        _cache["reason"] = reason
        _cache["fetched_at"] = time.time()
        _cache["raw_count"] = raw_count
        if ok:
            store = _cache["entries"]
            order = []
            for e in entries:
                store[e["id"]] = e
                order.append(e["id"])
            # 只保留本轮 + 最近，避免无限涨
            keep = order[-MAX_STORE:]
            _cache["order"] = keep
            _cache["entries"] = {i: store[i] for i in keep if i in store}
            _cache["match_count"] = len(keep)
        return snapshot(query)


def snapshot(query: str) -> dict:
    items = []
    for eid in reversed(_cache["order"]):
        e = _cache["entries"].get(eid)
        if not e:
            continue
        if not match_filter(e, query):
            continue
        items.append(
            {
                "id": e["id"],
                "method": e["method"],
                "host": e["host"],
                "path": e["path"],
                "url": e["url"],
                "status": e["status"],
                "started": e["started"],
                "size": e["size"],
                "zones": e["zones"],
                "templates": e["templates"],
                "client": e.get("client", ""),
                "source": e.get("source", ""),
                "ua": e.get("ua", ""),
            }
        )
    phone_n = sum(1 for x in items if x.get("source") == "手机")
    local_n = sum(1 for x in items if x.get("source") == "本机")
    return {
        "ok": _cache["ok"],
        "reason": _cache["reason"],
        "fetched_at": _cache["fetched_at"],
        "raw_count": _cache["raw_count"],
        "shown": len(items),
        "phone": phone_n,
        "local": local_n,
        "items": items[:MAX_STORE],
    }


def ingest_bytes(raw: bytes) -> int:
    entries = parse_session_payload(raw)
    with _lock:
        store = _cache["entries"]
        order = list(_cache["order"])
        for e in entries:
            store[e["id"]] = e
            if e["id"] not in order:
                order.append(e["id"])
        order = order[-MAX_STORE:]
        _cache["order"] = order
        _cache["entries"] = {i: store[i] for i in order if i in store}
        _cache["ok"] = True
        _cache["reason"] = "imported"
        _cache["fetched_at"] = time.time()
        _cache["raw_count"] = len(entries)
        _cache["match_count"] = len(order)
    return len(entries)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if path in ("/", "/index.html"):
            self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/api/status":
            # 轻量探测，不拉整包
            try:
                code, data, _ = _via_proxy("http://control.charles/", timeout=4)
                text = data.decode("utf-8", "replace")
                disabled = "Web Interface is disabled" in text
                self._json(
                    200,
                    {
                        "charles": True,
                        "web_interface": (code == 200) and not disabled,
                        "disabled": disabled,
                        "proxy": CHARLES_PROXY,
                    },
                )
            except Exception as e:
                self._json(200, {"charles": False, "web_interface": False, "error": str(e), "proxy": CHARLES_PROXY})
            return
        if path == "/api/entries":
            query = unquote(qs.get("q", [""])[0])
            try:
                data = refresh_cache(query)
                self._json(200, data)
            except Exception as e:
                self._json(500, {"ok": False, "reason": str(e), "items": []})
            return
        if path == "/api/entry":
            eid = qs.get("id", [""])[0]
            with _lock:
                e = _cache["entries"].get(eid)
            if not e:
                self._json(404, {"ok": False, "reason": "not_found"})
                return
            pretty = e["body"]
            try:
                pretty = json.dumps(json.loads(e["body"]), ensure_ascii=False, indent=2)
            except Exception:
                pass
            self._json(200, {**{k: v for k, v in e.items() if k != "body"}, "body": pretty, "ok": True})
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/import":
            self._send(404, b"not found", "text/plain")
            return
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            count = ingest_bytes(raw)
            self._json(200, {"ok": True, "count": count})
        except Exception as e:
            self._json(400, {"ok": False, "reason": str(e)})


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"缺少 {INDEX}")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Charles Mixer 对比已启动： http://{HOST}:{PORT}")
    print("请先在 Charles 打开：Proxy → Web Interface Settings → Enable Web Interface（建议允许匿名）")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()

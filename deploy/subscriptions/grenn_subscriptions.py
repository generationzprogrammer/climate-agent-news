#!/usr/bin/env python3
"""GRENN weekly-briefing subscriptions on the zerocarbonx.cn server (2026-11-06).

The original project's subscription service (Cloudflare Workers / Pages, KV list, GitHub Actions mailer) only accepts
https://generationzprogrammer.github.io and is unreachable from mainland China, so the COP31 page on zerocarbonx.cn
registers here instead (user: 由服务器自己发). Same request / response contract as the original Worker
(cloudflare/subscription-worker): POST {email, list, language} → {ok, status: subscribed|unsubscribed, language}.

  serve          HTTP service on 127.0.0.1:8796, behind nginx at /api/subscriptions/ (systemd grenn-subscriptions)
  send-weekly    mail the weekly briefing (data/current/weekly_report.json, the original project's text and wording
                 via climate_agent.delivery.build_weekly_message) to every active address, one message per recipient,
                 grouped by language; each address is mailed once per edition (the report's end_date), so a rerun
                 only retries failures (timer grenn-subscriptions-weekly: Mondays 08:00, retries 10:00 / 14:00)
  status         counts and the last edition (no addresses)
  test-mail ADDR send one test message to ADDR (checks the SMTP settings)

The list lives only in $GRENN_SUBS_HOME/subscribers.db (default /srv/grenn/subscriptions, mode 700, never served).
SMTP settings: $GRENN_SUBS_HOME/smtp.env (CLIMATE_SMTP_HOST / PORT / SECURITY / USERNAME / PASSWORD / SENDER, the
original project's names; root-only file, read by systemd). Every message carries a personal one-click unsubscribe link
(HMAC token, RFC 8058 List-Unsubscribe-Post).
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import sys
import time
from collections import deque
from datetime import date, datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

HOME = Path(os.environ.get("GRENN_SUBS_HOME", "/srv/grenn/subscriptions"))
DB = HOME / "subscribers.db"
SECRET = HOME / "secret"
SMTP_ENV = HOME / "smtp.env"
SITE = os.environ.get("GRENN_SITE_URL", "https://zerocarbonx.cn/").rstrip("/") + "/"
DATA = Path(os.environ.get("GRENN_DATA_DIR", "/srv/grenn/data/current"))
APP_SRC = Path(os.environ.get("GRENN_APP_SRC", "/srv/grenn/app/current/src"))
ORIGINS = {"https://zerocarbonx.cn", "https://www.zerocarbonx.cn"}
LIST = "climate-weekly"
EMAIL = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$")  # the original Worker's rule
PER_IP, PER_IP_WINDOW, GLOBAL_PER_HOUR = 10, 600, 300


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS subscribers (
            email TEXT PRIMARY KEY, language TEXT NOT NULL DEFAULT 'zh', active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS deliveries (
            edition TEXT NOT NULL, email TEXT NOT NULL, sent_at TEXT NOT NULL, PRIMARY KEY (edition, email));
    """)
    return conn


def secret() -> bytes:
    if not SECRET.exists():
        HOME.mkdir(parents=True, exist_ok=True)
        fd = os.open(SECRET, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(secrets.token_hex(32))
    return SECRET.read_text().strip().encode()


def token(email: str) -> str:
    return hmac.new(secret(), email.encode(), hashlib.sha256).hexdigest()[:32]


def unsubscribe_url(email: str) -> str:
    return f"{SITE}api/subscriptions/unsubscribe?e={quote(email)}&t={token(email)}"


def register(email: str, language: str, active: bool) -> None:
    with connect() as conn:
        stamp = now()
        conn.execute("""INSERT INTO subscribers (email, language, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(email) DO UPDATE SET active = excluded.active, updated_at = excluded.updated_at,
                        language = CASE WHEN excluded.active = 1 THEN excluded.language ELSE subscribers.language END""",
                     (email, language, int(active), stamp, stamp))


# ---------------------------------------------------------------- HTTP service

_hits: dict[str, deque] = {}
_global: deque = deque()


def limited(ip: str) -> bool:
    t = time.monotonic()
    q = _hits.setdefault(ip, deque())
    while q and t - q[0] > PER_IP_WINDOW:
        q.popleft()
    while _global and t - _global[0] > 3600:
        _global.popleft()
    if len(q) >= PER_IP or len(_global) >= GLOBAL_PER_HOUR:
        return True
    q.append(t)
    _global.append(t)
    if len(_hits) > 5000:
        _hits.clear()
    return False


PAGE = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><body style="margin:0;font:16px/1.7 system-ui,sans-serif;background:#eef2f6;color:#26303b">
<main style="max-width:560px;margin:12vh auto;padding:32px;background:#fff;box-shadow:0 8px 30px rgba(38,48,59,.08)">
<h1 style="font-size:22px;margin:0 0 12px">{title}</h1><p style="margin:0 0 20px">{body}</p>
<a href="{site}cop31/" style="color:#c8372d">格润气候治理 · GREEN →</a></main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "grenn-subscriptions"

    def log_message(self, fmt, *args):  # no addresses or query strings in the journal
        sys.stderr.write(f"{self.command} {urlsplit(self.path).path} {args[1] if len(args) > 1 else ''}\n")

    def _origin(self) -> str:
        origin = (self.headers.get("Origin") or "").rstrip("/")
        return origin if origin in ORIGINS else ""

    def _send(self, status: int, body: bytes, kind: str, origin: str = "") -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: dict, status: int = 200, origin: str = "") -> None:
        self._send(status, json.dumps(payload).encode(), "application/json; charset=utf-8", origin)

    def _page(self, title: str, body: str, status: int = 200) -> None:
        self._send(status, PAGE.format(title=html.escape(title), body=body, site=SITE).encode(), "text/html; charset=utf-8")

    def do_OPTIONS(self):
        origin = self._origin()
        if not origin:
            return self._json({"error": "origin_not_allowed"}, 403)
        self.send_response(204)
        for key, value in (("Access-Control-Allow-Origin", origin), ("Access-Control-Allow-Methods", "POST, OPTIONS"),
                           ("Access-Control-Allow-Headers", "content-type"), ("Access-Control-Max-Age", "86400"), ("Vary", "Origin")):
            self.send_header(key, value)
        self.end_headers()

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/health":
            return self._json({"ok": True, "service": "grenn-subscriptions", "languages": ["zh", "en"]})
        if url.path == "/unsubscribe":
            return self._one_click(url, confirm=False)
        return self._json({"error": "not_found"}, 404)

    def do_POST(self):
        url = urlsplit(self.path)
        if url.path == "/unsubscribe" and "t=" in (url.query or ""):
            return self._one_click(url, confirm=True)  # RFC 8058 one-click from a mail client
        origin = self._origin()
        if not origin:
            return self._json({"error": "origin_not_allowed"}, 403)
        if url.path not in ("/subscribe", "/unsubscribe"):
            return self._json({"error": "not_found"}, 404, origin)
        if limited(self.headers.get("X-Real-IP") or self.client_address[0]):
            return self._json({"error": "rate_limited"}, 429, origin)
        length = int(self.headers.get("Content-Length") or 0)
        if length > 2048:
            return self._json({"error": "request_too_large"}, 413, origin)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            assert isinstance(body, dict)
        except (ValueError, AssertionError, UnicodeDecodeError):
            return self._json({"error": "invalid_json"}, 400, origin)
        email = str(body.get("email") or "").strip().lower()
        if not EMAIL.match(email) or len(email) > 254:
            return self._json({"error": "invalid_email"}, 400, origin)
        if body.get("list") not in (None, LIST):
            return self._json({"error": "invalid_list"}, 400, origin)
        language = body.get("language") or "zh"
        if language not in ("zh", "en"):
            return self._json({"error": "invalid_language"}, 400, origin)
        if url.path == "/unsubscribe":
            register(email, language, active=False)
            return self._json({"ok": True, "status": "unsubscribed"}, 200, origin)
        register(email, language, active=True)
        return self._json({"ok": True, "status": "subscribed", "language": language}, 201, origin)

    def _one_click(self, url, confirm: bool):
        query = parse_qs(url.query or "")
        email = (query.get("e") or [""])[0].strip().lower()
        given = (query.get("t") or [""])[0]
        if not email or not hmac.compare_digest(given, token(email)):
            return self._page("链接无效 · Invalid link", "退订链接无效或已损坏，请在网站「订阅」中填写邮箱后点「退订」。<br>"
                              "This link is not valid. Please use Unsubscribe on the website.", 400)
        if not confirm:
            # a GET only shows the button: mail scanners that prefetch links must not unsubscribe anyone
            action = html.escape(f"{SITE}api/subscriptions/unsubscribe?{url.query}")
            return self._page("退订气候周报 · Unsubscribe",
                              f"确认不再接收发往 <b>{html.escape(email)}</b> 的每周气候情报周报？<br>"
                              f"Stop the weekly climate briefing for this address?</p>"
                              f"<form method=post action=\"{action}\"><button style=\"padding:10px 22px;border:0;"
                              f"border-radius:999px;background:#26303b;color:#fff;font:inherit;cursor:pointer\">"
                              f"确认退订 · Unsubscribe</button></form><p>")
        register(email, "zh", active=False)
        return self._page("已退订 · Unsubscribed", "该邮箱将不再收到每周气候情报周报。如需恢复，可在网站重新订阅。<br>"
                          "This address will no longer receive the weekly briefing.")


def serve(port: int) -> None:
    connect().close()
    secret()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    print(f"listening on 127.0.0.1:{port}", flush=True)
    httpd.serve_forever()


# ---------------------------------------------------------------- weekly mail

def load_smtp() -> None:
    if os.environ.get("CLIMATE_SMTP_HOST") or not SMTP_ENV.is_file():
        return
    try:
        lines = SMTP_ENV.read_text(encoding="utf-8").splitlines()
    except PermissionError:
        return
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def smtp_ready() -> bool:
    load_smtp()
    return bool(os.environ.get("CLIMATE_SMTP_HOST") and (os.environ.get("CLIMATE_SMTP_SENDER") or os.environ.get("CLIMATE_SMTP_USERNAME")))


def mail(recipient: str, subject: str, text: str, unsubscribe: str | None) -> None:
    """The original project's publish_email (same settings and headers) plus a one-click unsubscribe link."""
    host = os.environ["CLIMATE_SMTP_HOST"]
    port = int(os.getenv("CLIMATE_SMTP_PORT", "465"))
    username = os.getenv("CLIMATE_SMTP_USERNAME", "")
    password = os.getenv("CLIMATE_SMTP_PASSWORD", "")
    sender = os.getenv("CLIMATE_SMTP_SENDER", username)
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1] if "@" in sender else None)
    message["Reply-To"] = sender
    message["Auto-Submitted"] = "auto-generated"
    message["Precedence"] = "bulk"
    address = re.sub(r"^.*<([^>]+)>.*$", r"\1", sender)
    if unsubscribe:
        message["List-Unsubscribe"] = f"<{unsubscribe}>, <mailto:{address}?subject=unsubscribe>"
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    else:
        message["List-Unsubscribe"] = f"<mailto:{address}?subject=unsubscribe>"
    message.set_content(text)
    security = os.getenv("CLIMATE_SMTP_SECURITY", "ssl" if port == 465 else "starttls").lower()
    client = smtplib.SMTP_SSL(host, port, timeout=60, context=ssl.create_default_context()) if security == "ssl" \
        else smtplib.SMTP(host, port, timeout=60)
    with client:
        if security == "starttls":
            client.starttls(context=ssl.create_default_context())
        if username:
            client.login(username, password)
        client.send_message(message)


def weekly_text(report: dict, language: str) -> tuple[str, str]:
    sys.path.insert(0, str(APP_SRC))
    from climate_agent.delivery import build_weekly_message  # the original project's wording
    text = build_weekly_message(report, SITE, language=language)
    if language == "en" and not (DATA / "weekly_report_en.pdf").exists():
        # the original project has not published the English weekly PDF yet: point to the English daily brief instead
        text = re.sub(r"^English weekly PDF: .*$", f"English daily brief (PDF): {SITE}data/daily_brief_en.pdf", text, flags=re.M)
    meta = report.get("meta", {})
    subject = (f"GREEN Weekly Climate Briefing | {meta.get('end_date', '')}" if language == "en"
               else meta.get("title", "国际气候情报周报"))
    return subject, text


def send_weekly(force: bool = False, dry_run: bool = False) -> dict:
    report = json.loads((DATA / "weekly_report.json").read_text(encoding="utf-8"))
    edition = str(report.get("meta", {}).get("end_date") or "")
    try:
        age = (date.today() - date.fromisoformat(edition)).days
    except ValueError:
        return {"status": "skipped", "reason": "weekly_report_has_no_end_date"}
    if age > 3 and not force:
        return {"status": "skipped", "reason": "weekly_report_is_stale", "edition": edition}
    if not dry_run and not smtp_ready():
        return {"status": "skipped", "reason": "smtp_not_configured", "settings": str(SMTP_ENV)}
    with connect() as conn:
        rows = conn.execute("""SELECT email, language FROM subscribers WHERE active = 1 AND email NOT IN
                               (SELECT email FROM deliveries WHERE edition = ?) ORDER BY created_at""", (edition,)).fetchall()
    result = {"status": "ok", "edition": edition, "pending": len(rows), "sent": 0, "failed": 0, "failure_types": {}}
    if dry_run:
        result["by_language"] = {lang: sum(1 for _, l in rows if l == lang) for lang in ("zh", "en")}
        return result
    texts = {lang: weekly_text(report, lang) for lang in {l for _, l in rows}}
    unsub_line = {"zh": "一键退订（仅对本邮箱有效）：", "en": "One-click unsubscribe (this address only): "}
    for email, language in rows:
        subject, text = texts[language]
        link = unsubscribe_url(email)
        body = f"{text}\n{unsub_line.get(language, unsub_line['zh'])}{link}\n"
        for attempt in range(2):
            try:
                mail(email, subject, body, link)
                with connect() as conn:
                    conn.execute("INSERT OR IGNORE INTO deliveries VALUES (?, ?, ?)", (edition, email, now()))
                result["sent"] += 1
                break
            except (OSError, smtplib.SMTPException) as exc:
                if attempt:
                    result["failed"] += 1
                    key = type(exc).__name__
                    result["failure_types"][key] = result["failure_types"].get(key, 0) + 1
                else:
                    time.sleep(5)
        time.sleep(1.5)  # stay under the mail provider's sending rate
    if result["failed"]:
        result["status"] = "partial"
    return result


def status() -> dict:
    with connect() as conn:
        active = dict(conn.execute("SELECT language, COUNT(*) FROM subscribers WHERE active = 1 GROUP BY language").fetchall())
        inactive = conn.execute("SELECT COUNT(*) FROM subscribers WHERE active = 0").fetchone()[0]
        last = conn.execute("SELECT edition, COUNT(*), MAX(sent_at) FROM deliveries GROUP BY edition ORDER BY edition DESC LIMIT 1").fetchone()
    return {"active": sum(active.values()), "active_by_language": active, "unsubscribed": inactive,
            "smtp_configured": smtp_ready(), "last_edition": {"edition": last[0], "sent": last[1], "at": last[2]} if last else None}


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = cli.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8796)
    w = sub.add_parser("send-weekly")
    w.add_argument("--force", action="store_true", help="send even if the weekly report is older than three days")
    w.add_argument("--dry-run", action="store_true", help="count the pending recipients, send nothing")
    sub.add_parser("status")
    t = sub.add_parser("test-mail")
    t.add_argument("address")
    args = cli.parse_args(argv)
    if args.command == "serve":
        serve(args.port)
        return 0
    if args.command == "test-mail":
        if not smtp_ready():
            print(json.dumps({"status": "error", "reason": "smtp_not_configured", "settings": str(SMTP_ENV)}))
            return 1
        mail(args.address.strip(), "GREEN 订阅邮件测试 · test", "这是一封测试邮件：格润气候周报的发信设置可用。\n"
             "This is a test message: the GREEN weekly briefing mail settings work.\n", None)
        print(json.dumps({"status": "sent"}))
        return 0
    out = send_weekly(args.force, args.dry_run) if args.command == "send-weekly" else status()
    print(json.dumps(out, ensure_ascii=False))
    return 1 if out.get("status") == "partial" else 0


if __name__ == "__main__":
    sys.exit(main())

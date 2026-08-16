#!/usr/bin/env python3
"""Privacy-conscious visit counter for the Hemusci Skills footer."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


HOST = os.environ.get("HEMUSCI_ANALYTICS_HOST", "127.0.0.1")
PORT = int(os.environ.get("HEMUSCI_ANALYTICS_PORT", "8787"))
DB_PATH = Path(os.environ.get("HEMUSCI_ANALYTICS_DB", "/var/lib/hemusci-analytics/visits.sqlite3"))
SECRET_PATH = Path(os.environ.get("HEMUSCI_ANALYTICS_SECRET", "/var/lib/hemusci-analytics/secret"))
START_DATE = os.environ.get("HEMUSCI_ANALYTICS_START_DATE", "2026-08-16")
DEDUP_SECONDS = int(os.environ.get("HEMUSCI_ANALYTICS_DEDUP_SECONDS", "1800"))
CHINA_TZ = timezone(timedelta(hours=8))
ALLOWED_ORIGINS = {
    "https://hemusci.com",
    "https://www.hemusci.com",
    "http://hemusci.com",
    "http://www.hemusci.com",
}


def china_now() -> datetime:
    return datetime.now(CHINA_TZ)


def ensure_secret() -> bytes:
    SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SECRET_PATH.exists():
        SECRET_PATH.write_text(secrets.token_hex(32), encoding="ascii")
        SECRET_PATH.chmod(0o600)
    return SECRET_PATH.read_text(encoding="ascii").strip().encode("ascii")


SECRET = ensure_secret()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def initialize() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_stats (
                day TEXT PRIMARY KEY,
                views INTEGER NOT NULL DEFAULT 0 CHECK (views >= 0),
                unique_visitors INTEGER NOT NULL DEFAULT 0 CHECK (unique_visitors >= 0)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS visitor_days (
                day TEXT NOT NULL,
                visitor_hash TEXT NOT NULL,
                last_seen INTEGER NOT NULL,
                PRIMARY KEY (day, visitor_hash)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO metadata(key, value) VALUES('start_date', ?)",
            (START_DATE,),
        )
        connection.execute("PRAGMA optimize")


def visitor_hash(day: str, ip_address: str, user_agent: str) -> str:
    payload = f"{day}|{ip_address}|{user_agent[:320]}".encode("utf-8", "replace")
    return hmac.new(SECRET, payload, hashlib.sha256).hexdigest()


def record_visit(ip_address: str, user_agent: str) -> None:
    now = china_now()
    day = now.date().isoformat()
    now_epoch = int(now.timestamp())
    fingerprint = visitor_hash(day, ip_address, user_agent)
    retention_day = (now.date() - timedelta(days=32)).isoformat()

    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        previous = connection.execute(
            "SELECT last_seen FROM visitor_days WHERE day = ? AND visitor_hash = ?",
            (day, fingerprint),
        ).fetchone()
        is_unique = previous is None
        should_count = is_unique or now_epoch - int(previous["last_seen"]) >= DEDUP_SECONDS

        if is_unique:
            connection.execute(
                "INSERT INTO visitor_days(day, visitor_hash, last_seen) VALUES(?, ?, ?)",
                (day, fingerprint, now_epoch),
            )
        else:
            connection.execute(
                "UPDATE visitor_days SET last_seen = ? WHERE day = ? AND visitor_hash = ?",
                (now_epoch, day, fingerprint),
            )

        if should_count:
            connection.execute(
                """
                INSERT INTO daily_stats(day, views, unique_visitors)
                VALUES(?, 1, ?)
                ON CONFLICT(day) DO UPDATE SET
                    views = views + 1,
                    unique_visitors = unique_visitors + excluded.unique_visitors
                """,
                (day, 1 if is_unique else 0),
            )

        connection.execute("DELETE FROM visitor_days WHERE day < ?", (retention_day,))


def read_stats() -> dict[str, object]:
    now = china_now()
    today = now.date()
    days = [(today - timedelta(days=offset)) for offset in range(6, -1, -1)]
    day_keys = [item.isoformat() for item in days]

    with connect() as connection:
        total = int(connection.execute("SELECT COALESCE(SUM(views), 0) FROM daily_stats").fetchone()[0])
        today_row = connection.execute(
            "SELECT views, unique_visitors FROM daily_stats WHERE day = ?",
            (today.isoformat(),),
        ).fetchone()
        start_row = connection.execute(
            "SELECT value FROM metadata WHERE key = 'start_date'"
        ).fetchone()
        placeholders = ",".join("?" for _ in day_keys)
        trend_rows = connection.execute(
            f"SELECT day, views FROM daily_stats WHERE day IN ({placeholders})",
            day_keys,
        ).fetchall()

    trend_map = {row["day"]: int(row["views"]) for row in trend_rows}
    start = date.fromisoformat(start_row["value"] if start_row else START_DATE)
    return {
        "total": total,
        "today": int(today_row["views"]) if today_row else 0,
        "visitors": int(today_row["unique_visitors"]) if today_row else 0,
        "days_online": max(1, (today - start).days + 1),
        "trend": [
            {"day": item.isoformat(), "label": f"{item.month}/{item.day}", "views": trend_map.get(item.isoformat(), 0)}
            for item in days
        ],
        "updated_at": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "HemusciAnalytics/1.0"

    def log_message(self, format_string: str, *args: object) -> None:
        print(f"{self.log_date_time_string()} {self.address_string()} {format_string % args}", flush=True)

    def send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def request_path(self) -> str:
        return urlsplit(self.path).path

    def origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return not origin or origin in ALLOWED_ORIGINS

    def client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()[:96]
        return self.client_address[0][:96]

    def do_GET(self) -> None:
        if self.request_path() == "/healthz":
            self.send_json(200, {"status": "ok"})
            return
        if self.request_path() != "/api/visits":
            self.send_json(404, {"error": "not_found"})
            return
        self.send_json(200, read_stats())

    def do_POST(self) -> None:
        if self.request_path() != "/api/visits":
            self.send_json(404, {"error": "not_found"})
            return
        if not self.origin_allowed():
            self.send_json(403, {"error": "origin_not_allowed"})
            return
        record_visit(self.client_ip(), self.headers.get("User-Agent", "unknown"))
        self.send_json(200, read_stats())


def main() -> None:
    initialize()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f"Hemusci analytics listening on http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

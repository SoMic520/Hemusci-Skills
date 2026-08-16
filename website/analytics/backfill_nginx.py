#!/usr/bin/env python3
"""One-time aggregate backfill from existing Nginx logs without retaining raw IPs."""

from __future__ import annotations

import gzip
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from hemusci_analytics import CHINA_TZ, connect, initialize


LOG_DIR = Path("/var/log/nginx")
PAGE_PATHS = {"/skills/", "/skills/index.html"}
BOT_PATTERN = re.compile(r"bot|spider|crawler|curl|wget|python-requests|uptime|monitor", re.I)
LINE_PATTERN = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] '
    r'"(?P<method>GET|HEAD) (?P<target>\S+) HTTP/[^"]+" '
    r'(?P<status>\d{3}) \S+ "[^"]*" "(?P<agent>[^"]*)"'
)


def open_log(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def main() -> int:
    initialize()
    daily_views: dict[str, int] = defaultdict(int)
    daily_visitors: dict[str, set[str]] = defaultdict(set)

    log_paths = sorted(LOG_DIR.glob("access.log*"), key=lambda path: path.name)
    for path in log_paths:
        try:
            with open_log(path) as handle:
                for line in handle:
                    match = LINE_PATTERN.match(line)
                    if not match or match.group("status") not in {"200", "304"}:
                        continue
                    target = match.group("target").split("?", 1)[0]
                    agent = match.group("agent")
                    if target not in PAGE_PATHS or BOT_PATTERN.search(agent):
                        continue
                    timestamp = datetime.strptime(match.group("timestamp"), "%d/%b/%Y:%H:%M:%S %z")
                    day = timestamp.astimezone(CHINA_TZ).date().isoformat()
                    daily_views[day] += 1
                    daily_visitors[day].add(f"{match.group('ip')}|{agent[:160]}")
        except OSError as error:
            print(f"warning: skipped {path}: {error}")

    with connect() as connection:
        already_done = connection.execute(
            "SELECT value FROM metadata WHERE key = 'nginx_backfilled_at'"
        ).fetchone()
        if already_done:
            print(f"status=SKIP already_backfilled_at={already_done['value']}")
            return 0

        for day, views in daily_views.items():
            connection.execute(
                """
                INSERT INTO daily_stats(day, views, unique_visitors)
                VALUES(?, ?, ?)
                ON CONFLICT(day) DO UPDATE SET
                    views = MAX(daily_stats.views, excluded.views),
                    unique_visitors = MAX(daily_stats.unique_visitors, excluded.unique_visitors)
                """,
                (day, views, len(daily_visitors[day])),
            )
        if daily_views:
            first_day = min(daily_views)
            connection.execute(
                "UPDATE metadata SET value = MIN(value, ?) WHERE key = 'start_date'",
                (first_day,),
            )
        completed_at = datetime.now(CHINA_TZ).isoformat(timespec="seconds")
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES('nginx_backfilled_at', ?)",
            (completed_at,),
        )
        connection.execute("PRAGMA optimize")

    print(
        f"status=PASS files={len(log_paths)} days={len(daily_views)} "
        f"views={sum(daily_views.values())} unique_day_visitors={sum(map(len, daily_visitors.values()))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

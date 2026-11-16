#!/usr/bin/env python3
"""zerocarbonx.cn page views for the site's 累计访问量 curve (2026-11-14).

Why: data/site_metrics.json's visitor_cumulative comes from the original project's Cloudflare Web Analytics, which
counts the old github.io address only (and in steps of ten: it is sampled). Since the site moved to zerocarbonx.cn
(2026-11-01) visits happen here, where nothing counted them: the curve stopped at 1,980 on 2026-11-05.

What is counted: one page view = one browser that loaded a page far enough to run its script — a GET of
/data/site_metrics.json (app.js asks for it once per page load, on the main site and the COP31 page) answered 200 or
304, by a client that calls itself a browser. Crawlers and scanners do not run scripts, so they are left out without
guessing at user agents; headless test browsers and the usual tool agents are excluded by name. Only daily totals are
kept (no addresses): /srv/grenn/data/visits.json. nginx keeps 14 days of logs, so each run merges what the logs still
hold into that file and never lowers a day.

    grenn_visits.py count                 update visits.json from /var/log/nginx/access.log*, print the totals
    grenn_visits.py apply SITE_METRICS    count, then add this site's views to the file's visitor_cumulative
                                          (the original series is kept beside it as visitor_cumulative_upstream)
sync-data.sh runs `apply` on every new data snapshot (as root: the logs are not world-readable). Standard library only.
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import re
import sys
from pathlib import Path

LOGS = os.environ.get("GRENN_ACCESS_LOGS", "/var/log/nginx/access.log*")
STORE = Path(os.environ.get("GRENN_VISITS", "/srv/grenn/data/visits.json"))
BEACON = "/data/site_metrics.json"
LINE = re.compile(r'^(\S+) \S+ \S+ \[(\d{2})/(\w{3})/(\d{4}):[^\]]+\] "(\S+) (\S+) [^"]*" (\d{3}) \S+ "[^"]*" "([^"]*)"')
MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}
NOT_A_READER = re.compile(r"headless|bot\b|bot/|crawl|spider|slurp|scan|measurement|monitor|curl|wget|python|go-http|java/|okhttp|"
                          r"axios|node|libwww|httpclient|preview|lighthouse|pagespeed|phantom|selenium|playwright|puppeteer", re.I)


def count_logs(pattern: str = None) -> dict:
    """{day: [views, distinct addresses]} from the access logs (dates as the log writes them: server time)."""
    views, seen = {}, {}
    for name in sorted(glob.glob(pattern or LOGS)):
        opener = gzip.open if name.endswith(".gz") else open
        try:
            with opener(name, "rt", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    m = LINE.match(line)
                    if not m:
                        continue
                    address, day, month, year, method, path, status, agent = m.groups()
                    if method != "GET" or status not in ("200", "304") or path.split("?", 1)[0] != BEACON:
                        continue
                    if not agent.startswith("Mozilla/") or NOT_A_READER.search(agent) or address in ("127.0.0.1", "::1"):
                        continue
                    key = f"{year}-{MONTHS.get(month, 0):02d}-{day}"
                    views[key] = views.get(key, 0) + 1
                    seen.setdefault(key, set()).add(address)
        except OSError as error:
            print(f"visits: {name}: {error}", file=sys.stderr)
    return {day: [views[day], len(seen[day])] for day in views}


def load_store(path: Path = None) -> dict:
    try:
        records = json.loads((path or STORE).read_text("utf-8")).get("records", [])
    except (OSError, ValueError):
        return {}
    return {r["date"]: [int(r.get("views") or 0), int(r.get("uniques") or 0)] for r in records if r.get("date")}


def update_store(counted: dict, path: Path = None) -> dict:
    """Merge today's reading of the logs into the kept daily totals; a day's total never goes down."""
    path = path or STORE
    days = load_store(path)
    for day, (views, uniques) in counted.items():
        old = days.get(day, [0, 0])
        days[day] = [max(old[0], views), max(old[1], uniques)]
    payload = {"metric": "browser page loads of zerocarbonx.cn (GET /data/site_metrics.json by script-running browsers)",
               "records": [{"date": day, "views": days[day][0], "uniques": days[day][1]} for day in sorted(days)]}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    return days


def merged_series(upstream: list, days: dict) -> list:
    """upstream (the original project's cumulative series) + this site's own views, cumulative, on the same dates.
    Views dated after the series' last day (the server's clock runs ahead of UTC) are counted on that last day."""
    out, total, ordered, at = [], 0, sorted(days), 0
    for index, point in enumerate(upstream):
        last = index == len(upstream) - 1
        while at < len(ordered) and (last or ordered[at] <= point["date"]):
            total += days[ordered[at]][0]
            at += 1
        out.append({"date": point["date"], "value": int(point["value"]) + total})
    return out


def apply(metrics_path: Path, days: dict) -> dict:
    payload = json.loads(metrics_path.read_text("utf-8"))
    upstream = payload.get("visitor_cumulative_upstream") or payload.get("visitor_cumulative") or []
    if not upstream:
        return {"applied": False, "reason": "no visitor_cumulative"}
    payload["visitor_cumulative_upstream"] = upstream
    payload["visitor_cumulative"] = merged_series(upstream, days)
    own = sum(v[0] for v in days.values())
    payload["visitor_sources"] = {
        "upstream": {"what": "Cloudflare Web Analytics of the original github.io address (sampled)", "total": int(upstream[-1]["value"])},
        "site": {"what": "browser page loads of zerocarbonx.cn from the server log", "total": own, "since": min(days) if days else None},
    }
    note = "访问曲线 = 原 github.io 地址的 Cloudflare 统计 + zerocarbonx.cn 服务器日志中的浏览器页面加载次数（不含爬虫与自动化测试）。"
    payload["notes"] = [n for n in payload.get("notes", []) if not n.startswith("访问曲线 = ")] + [note]
    tmp = metrics_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    os.replace(tmp, metrics_path)
    return {"applied": True, "upstream": int(upstream[-1]["value"]), "site": own, "total": payload["visitor_cumulative"][-1]["value"]}


def main(argv: list) -> int:
    if len(argv) < 2 or argv[1] not in ("count", "apply") or (argv[1] == "apply" and len(argv) != 3):
        print(__doc__.split("\n\n")[-1], file=sys.stderr)
        return 2
    days = update_store(count_logs())
    report = {"days": len(days), "site_views": sum(v[0] for v in days.values()), "last": max(days) if days else None}
    if argv[1] == "apply":
        report.update(apply(Path(argv[2]), days))
    print("visits:", json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

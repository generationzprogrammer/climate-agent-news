from __future__ import annotations

import json
import os
import urllib.request
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path


def _daterange(start: date, end: date) -> list[date]:
    days = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def _parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def corpus_cumulative_series(corpus_path: Path, *, today: date | None = None, days: int = 92) -> list[dict]:
    today = today or datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    counts: Counter[date] = Counter()
    before = 0
    if corpus_path.exists():
        with corpus_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                published = _parse_day(record.get("published_date") or record.get("published_at_utc"))
                if not published:
                    continue
                if published < start:
                    before += 1
                elif published <= today:
                    counts[published] += 1
    cumulative = before
    series = []
    for day in _daterange(start, today):
        cumulative += counts[day]
        series.append({"date": day.isoformat(), "value": cumulative})
    return series


def load_visitor_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    records = payload.get("records", payload if isinstance(payload, list) else [])
    return [record for record in records if record.get("date")]


def save_visitor_history(path: Path, records: list[dict]) -> dict:
    merged: dict[str, dict] = {}
    for record in records:
        day = str(record.get("date") or "")[:10]
        if not day:
            continue
        merged[day] = {
            "date": day,
            "views": int(record.get("views") or 0),
            "uniques": int(record.get("uniques") or 0),
        }
    ordered = [merged[day] for day in sorted(merged)]
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": datetime.now(UTC).isoformat(), "records": ordered[-120:]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def visitor_cumulative_series(visitor_path: Path, *, today: date | None = None, days: int = 92) -> list[dict]:
    today = today or datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    records = load_visitor_history(visitor_path)
    counts = {
        _parse_day(record.get("date")): int(record.get("views") or record.get("uniques") or 0)
        for record in records
    }
    counts.pop(None, None)
    cumulative = sum(value for day, value in counts.items() if day and day < start)
    series = []
    for day in _daterange(start, today):
        cumulative += counts.get(day, 0)
        series.append({"date": day.isoformat(), "value": cumulative})
    return series


def write_site_metrics(corpus_path: Path, visitor_path: Path, output_path: Path) -> dict:
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "window_days": 92,
        "archive_cumulative": corpus_cumulative_series(corpus_path),
        "visitor_cumulative": visitor_cumulative_series(visitor_path),
        "notes": [
            "档案曲线按历史语料库 published_date 聚合，表示本站已积累文本记录的累计规模。",
            "访客曲线来自 GitHub Traffic API 已写回的 visitor_history.json；GitHub 只提供近期流量，系统会从启用后开始累积。",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def update_github_visitor_history(path: Path, *, repo: str | None = None, token: str | None = None) -> dict:
    repo = repo or os.getenv("GITHUB_REPOSITORY")
    token = token or os.getenv("GITHUB_TOKEN")
    if not repo or not token:
        return {"status": "skipped", "reason": "missing_repo_or_token"}
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/traffic/views?per=day",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ClimateText-Lab/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    existing = load_visitor_history(path)
    incoming = [
        {
            "date": str(item.get("timestamp", ""))[:10],
            "views": int(item.get("count") or 0),
            "uniques": int(item.get("uniques") or 0),
        }
        for item in payload.get("views", [])
    ]
    saved = save_visitor_history(path, [*existing, *incoming])
    return {"status": "ok", "records": len(saved["records"])}


def update_cloudflare_visitor_history(
    path: Path,
    *,
    account_id: str,
    api_token: str,
    hostname: str,
    days: int = 92,
) -> dict:
    """Read privacy-preserving Web Analytics page loads into daily history."""
    if not account_id or not api_token or not hostname:
        return {"status": "skipped", "reason": "missing_cloudflare_configuration"}
    end_day = datetime.now(UTC).date()
    start_day = end_day - timedelta(days=max(1, days) - 1)
    query = """
    query DailyPageviews($accountTag: string!, $filter: AccountRumPageloadEventsAdaptiveGroupsFilter_InputObject!) {
      viewer {
        accounts(filter: {accountTag: $accountTag}) {
          series: rumPageloadEventsAdaptiveGroups(
            limit: 1000
            orderBy: [date_ASC]
            filter: $filter
          ) {
            count
            dimensions { date }
          }
        }
      }
    }
    """
    body = json.dumps({
        "query": query,
        "variables": {
            "accountTag": account_id,
            "filter": {
                "AND": [
                    {
                        "datetime_geq": f"{start_day.isoformat()}T00:00:00Z",
                        "datetime_leq": f"{end_day.isoformat()}T23:59:59Z",
                    },
                    {"requestHost": hostname},
                    {"bot": 0},
                ]
            },
        },
    }).encode("utf-8")
    request = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/graphql",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "User-Agent": "ClimateText-Lab/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("errors"):
        messages = "; ".join(str(item.get("message") or "GraphQL error") for item in payload["errors"][:3])
        raise RuntimeError(f"Cloudflare analytics query failed: {messages[:300]}")
    accounts = (((payload.get("data") or {}).get("viewer") or {}).get("accounts") or [])
    if not accounts:
        raise RuntimeError("Cloudflare analytics query returned no accessible account")
    incoming = [
        {
            "date": str((item.get("dimensions") or {}).get("date") or "")[:10],
            "views": int(item.get("count") or 0),
            "uniques": 0,
        }
        for item in accounts[0].get("series", [])
        if (item.get("dimensions") or {}).get("date")
    ]
    saved = save_visitor_history(path, [*load_visitor_history(path), *incoming])
    return {
        "status": "ok",
        "provider": "cloudflare_web_analytics",
        "records": len(saved["records"]),
        "latest_views": incoming[-1]["views"] if incoming else 0,
    }

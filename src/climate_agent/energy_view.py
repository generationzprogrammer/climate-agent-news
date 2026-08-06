from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .corpus_analytics import is_energy_record


ENERGY_DATASET_NAME = "EnergyTech-100000"


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _record_day(record: dict) -> str:
    parsed = _parse_time(record.get("published_at"))
    return parsed.date().isoformat() if parsed else str(record.get("published_at") or "")[:10]


def _energy_records(archive: dict) -> list[dict]:
    records = [record for record in archive.get("records", []) if is_energy_record(record)]
    return sorted(records, key=lambda row: row.get("published_at") or "", reverse=True)


def build_energy_archive(archive: dict, *, limit: int = 100000) -> dict:
    records = _energy_records(archive)[:limit]
    topics = Counter(topic for record in records for topic in (record.get("topics") or []))
    places = Counter(
        place.get("name_zh")
        for record in records
        for place in (record.get("places") or [])
        if place.get("name_zh")
    )
    return {
        "schema_version": archive.get("schema_version", "1.0"),
        "dataset_name": ENERGY_DATASET_NAME,
        "updated_at": archive.get("updated_at") or datetime.now(UTC).isoformat(),
        "limit": limit,
        "total": len(records),
        "statistics": {
            "source_total": archive.get("total", 0),
            "energy_records": len(records),
            "top_topics": topics.most_common(8),
            "top_places": places.most_common(8),
        },
        "records": records,
    }


def _select_daily(records: list[dict], *, limit: int = 10) -> tuple[list[dict], str | None]:
    days = [day for day in (_record_day(record) for record in records) if day]
    if not days:
        return [], None
    latest = max(days)
    selected = [record for record in records if _record_day(record) == latest]
    if len(selected) < limit:
        seen = {record.get("canonical_url") for record in selected}
        for record in records:
            if len(selected) >= limit:
                break
            if record.get("canonical_url") in seen:
                continue
            selected.append(record)
            seen.add(record.get("canonical_url"))
    return selected[:limit], latest


def _within_week(records: list[dict], latest_day: str | None) -> list[dict]:
    if not latest_day:
        return []
    latest = datetime.fromisoformat(latest_day).replace(tzinfo=UTC)
    left = latest - timedelta(days=6)
    return [
        record for record in records
        if (parsed := _parse_time(record.get("published_at"))) and left.date() <= parsed.date() <= latest.date()
    ]


def _map_events(records: list[dict], *, prefix: str, limit: int = 40) -> list[dict]:
    events = []
    for record in records:
        place = next(
            (place for place in record.get("places") or [] if place.get("name_zh") and place.get("lon") is not None and place.get("lat") is not None),
            None,
        )
        if not place:
            continue
        events.append({
            "marker_id": f"{prefix}_{len(events)}_{record.get('record_id')}",
            "article_id": record.get("article_id"),
            "place": place.get("name_zh"),
            "lon": place.get("lon"),
            "lat": place.get("lat"),
            "theme": record.get("theme_zh") or ((record.get("topics") or ["能源技术"])[0]),
            "title_zh": record.get("title_zh") or record.get("title_original"),
            "summary_zh": record.get("summary_zh") or record.get("summary_source"),
            "source_name": record.get("source_name"),
            "published_at": record.get("published_at"),
            "url": record.get("canonical_url"),
        })
        if len(events) >= limit:
            return events
    return events


def build_energy_dashboard(climate_payload: dict, energy_archive: dict) -> dict:
    records = energy_archive.get("records", [])
    daily, latest_day = _select_daily(records, limit=10)
    weekly = _within_week(records, latest_day)
    payload = dict(climate_payload)
    payload["meta"] = {
        **climate_payload.get("meta", {}),
        "product": "能源技术趋势与文本数据库",
        "mode": "energy",
        "date": latest_day or climate_payload.get("meta", {}).get("date"),
        "latest_news_date": latest_day,
        "dataset_version": energy_archive.get("updated_at"),
        "notice": "能源技术模式基于同一归档中的能源转型、能源技术趋势与数字能源相关记录自动筛选；样本分布不等同于产业真实投资规模。",
    }
    payload["archive"] = {
        "dataset_name": energy_archive["dataset_name"],
        "updated_at": energy_archive.get("updated_at"),
        "total": energy_archive.get("total", 0),
        "limit": energy_archive.get("limit", 100000),
        "statistics": energy_archive.get("statistics", {}),
    }
    payload["metrics"] = {**climate_payload.get("metrics", {}), "archive_total": energy_archive.get("total", 0)}
    payload["intelligence"] = daily
    payload["map_events_today"] = _map_events(daily, prefix="energy_today", limit=24)
    payload["map_events_week"] = _map_events(weekly, prefix="energy_week", limit=40)
    payload["map_events"] = payload["map_events_today"]
    payload["phrases"] = [
        record.get("poster_phrase") or record.get("theme_zh") or record.get("title_zh")
        for record in daily[:8]
        if record.get("poster_phrase") or record.get("theme_zh") or record.get("title_zh")
    ]
    return payload


def write_energy_view(climate_payload: dict, archive: dict, data_dir: Path, *, limit: int = 100000) -> dict:
    energy_archive = build_energy_archive(archive, limit=limit)
    energy_dashboard = build_energy_dashboard(climate_payload, energy_archive)
    (data_dir / "energy_archive.json").write_text(json.dumps(energy_archive, ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "energy_dashboard.json").write_text(json.dumps(energy_dashboard, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"archive": energy_archive, "dashboard": energy_dashboard}

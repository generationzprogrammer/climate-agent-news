from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path


CONTINENT_ZH = {
    "Asia": "亚洲",
    "North America": "北美洲",
    "South America": "南美洲",
    "Europe": "欧洲",
    "Africa": "非洲",
    "Oceania": "大洋洲",
    "Antarctica": "南极洲",
    "Global/Unspecified": "全球/未标注",
}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _date_value(item: dict) -> str:
    if item.get("published_date"):
        return str(item["published_date"])[:10]
    value = str(item.get("published_at_utc") or item.get("published_at") or "")
    return value[:10] if len(value) >= 10 else ""


def _month_value(day: str) -> str:
    return day[:7] if len(day) >= 7 else ""


def _top(counter: Counter, limit: int, *, exclude: set[str] | None = None) -> list[dict]:
    exclude = exclude or set()
    return [
        {"name": name, "count": count}
        for name, count in counter.most_common()
        if name and name not in exclude
    ][:limit]


def _source_label(value: str | None) -> str:
    if not value:
        return "未标注来源"
    if value.startswith("google:"):
        return value.replace("google:", "", 1).strip().title()
    return value.replace("www.", "")


def build_corpus_analytics(corpus_path: Path, manifest_path: Path | None = None) -> dict:
    """Aggregate the historical JSONL corpus into compact web-chart data."""
    rows = _read_jsonl(corpus_path)
    if not rows:
        return {
            "schema_version": "1.0",
            "dataset": "Global Climate Change Key Intelligence Text Database",
            "records": 0,
            "status": "empty",
        }

    date_counts: Counter[str] = Counter()
    month_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    country_counts: Counter[str] = Counter()
    continent_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    country_topic_counts: dict[tuple[str, str], int] = defaultdict(int)
    quality_flags = Counter()

    for item in rows:
        day = _date_value(item)
        if day:
            date_counts[day] += 1
            month = _month_value(day)
            if month:
                month_counts[month] += 1

        topics = [str(topic) for topic in item.get("topics") or [] if topic]
        countries = [str(country) for country in item.get("country_tags") or [] if country]
        continents = [
            CONTINENT_ZH.get(str(continent), str(continent))
            for continent in (item.get("continent_tags") or [])
            if continent
        ]
        if not countries:
            countries = ["未标注"]
        if not continents:
            continents = ["全球/未标注"]

        topic_counts.update(topics or ["气候综合"])
        country_counts.update(countries)
        continent_counts.update(continents)
        source_counts[_source_label(item.get("source_domain") or item.get("source_name"))] += 1
        flags = item.get("quality_flags") or {}
        if isinstance(flags, dict):
            quality_flags.update(key for key, value in flags.items() if value)

        for country in countries:
            if country == "未标注":
                continue
            for topic in topics[:4] or ["气候综合"]:
                country_topic_counts[(country, topic)] += 1

    dates = sorted(date_counts)
    months = sorted(month_counts)
    top_countries = _top(country_counts, 12, exclude={"未标注"})
    top_topics = _top(topic_counts, 10)
    matrix_countries = [item["name"] for item in top_countries[:8]]
    matrix_topics = [item["name"] for item in top_topics[:6]]
    matrix = [
        {
            "country": country,
            "topic": topic,
            "count": country_topic_counts.get((country, topic), 0),
        }
        for country in matrix_countries
        for topic in matrix_topics
    ]
    manifest = {}
    if manifest_path and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}

    return {
        "schema_version": "1.0",
        "dataset": manifest.get("dataset", "Global Climate Change Key Intelligence Text Database"),
        "grain": manifest.get("grain", "one canonical URL per news record"),
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "records": len(rows),
        "date_start": dates[0] if dates else None,
        "date_end": dates[-1] if dates else None,
        "days_covered": len(date_counts),
        "avg_per_day": round(len(rows) / max(1, len(date_counts)), 2),
        "country_tagged_records": len(rows) - country_counts.get("未标注", 0),
        "country_tagged_rate": round((len(rows) - country_counts.get("未标注", 0)) / max(1, len(rows)), 4),
        "topic_count": len(topic_counts),
        "country_count": len([name for name in country_counts if name != "未标注"]),
        "source_count": len(source_counts),
        "monthly_records": [{"month": month, "count": month_counts[month]} for month in months],
        "top_topics": top_topics,
        "top_countries": top_countries,
        "continents": _top(continent_counts, 8),
        "top_sources": _top(source_counts, 10),
        "country_topic_matrix": {
            "countries": matrix_countries,
            "topics": matrix_topics,
            "cells": matrix,
        },
        "quality_flags": _top(quality_flags, 8),
        "notes": [
            "国家/地区标签只在文本或地点字段明确出现时生成，未强行推断。",
            "GDELT 被限流时使用 Google News RSS 作为历史新闻兜底源；所有记录按 canonical URL 去重。",
            "图表用于描述语料库样本分布，不等同于全球气候事件真实发生频率。",
        ],
    }


def write_corpus_analytics(corpus_path: Path, output_path: Path, manifest_path: Path | None = None) -> dict:
    analytics = build_corpus_analytics(corpus_path, manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(analytics, ensure_ascii=False, indent=2), encoding="utf-8")
    return analytics

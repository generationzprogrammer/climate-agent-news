from __future__ import annotations

import json
import math
import re
import uuid
from collections import Counter
from datetime import UTC, date, datetime, timedelta, timezone

from .db import Database
from .pipeline import decode_event, module_manifest
from .summary_utils import intelligence_keywords, is_generic_summary, is_generic_title


TOPIC_ZH_ALIASES = {
    "UNFCCC进程": "国际气候谈判",
    "国家承诺/NDC": "国家气候承诺",
    "减缓与能源": "能源与排放",
    "适应与损失损害": "气候适应",
    "碳市场/Article 6": "国际碳市场",
    "透明度与盘点": "履约与全球盘点",
    "气候综合": "气候动态",
}

BEIJING_TZ = timezone(timedelta(hours=8))


def _decode_json(value: str | None, fallback):
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def _published_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(BEIJING_TZ).date()


def _continent(item: dict) -> str:
    places = item.get("places") or []
    if not places:
        return "未标注"
    place = places[0]
    name = str(place.get("name_zh") or "")
    lat = float(place.get("lat") or 0)
    lon = float(place.get("lon") or 0)
    if "南极" in name or lat <= -60:
        return "南极洲"
    if any(term in name for term in ("澳大利亚", "新西兰", "太平洋", "大洋洲")):
        return "大洋洲"
    if any(term in name for term in ("巴西", "南美", "拉丁美洲", "亚马孙", "阿根廷", "智利", "秘鲁", "哥伦比亚")):
        return "南美洲"
    if any(term in name for term in ("美国", "加拿大", "墨西哥", "北美", "加勒比")):
        return "北美洲"
    if any(term in name for term in ("非洲", "刚果", "乌干达", "西非", "南非", "肯尼亚", "尼日利亚")):
        return "非洲"
    if any(term in name for term in ("欧洲", "英国", "法国", "德国", "西班牙", "意大利")):
        return "欧洲"
    if any(term in name for term in ("中国", "印度", "日本", "韩国", "东南亚", "印度尼西亚", "菲律宾")):
        return "亚洲"
    if -170 <= lon <= -30 and lat >= 12:
        return "北美洲"
    if -90 <= lon <= -30 and lat < 12:
        return "南美洲"
    if -25 <= lon <= 60 and -38 <= lat <= 37:
        return "非洲"
    if -25 <= lon <= 60 and lat > 37:
        return "欧洲"
    if 110 <= lon <= 180 and lat < -8:
        return "大洋洲"
    if 25 <= lon <= 180:
        return "亚洲"
    return "全球/其他"


def _source_key(item: dict) -> str:
    return item.get("source_name") or item.get("source_id") or "未知来源"


def _title_units(item: dict) -> set[str]:
    text = str(item.get("title_original") or item.get("title_zh") or "").lower()
    latin = re.findall(r"[a-z0-9]+", text)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    return set(latin) | {chinese[index:index + 2] for index in range(max(0, len(chinese) - 1))}


def _near_duplicate(left: dict, right: dict) -> bool:
    left_units, right_units = _title_units(left), _title_units(right)
    if not left_units or not right_units:
        return False
    overlap = len(left_units & right_units) / len(left_units | right_units)
    shorter = min(len(left_units), len(right_units))
    containment = len(left_units & right_units) / shorter
    return overlap >= 0.72 or (shorter >= 6 and containment >= 0.88)


def _deduplicate_items(items: list[dict], existing: list[dict] | None = None) -> list[dict]:
    kept = list(existing or [])
    result: list[dict] = []
    canonical_urls = {item.get("canonical_url") for item in kept if item.get("canonical_url")}
    for item in sorted(
        items,
        key=lambda row: (row.get("relevance_score", 0), row.get("published_at") or ""),
        reverse=True,
    ):
        canonical_url = item.get("canonical_url")
        if canonical_url and canonical_url in canonical_urls:
            continue
        if any(_near_duplicate(item, previous) for previous in kept):
            continue
        result.append(item)
        kept.append(item)
        if canonical_url:
            canonical_urls.add(canonical_url)
    return result


def balanced_select(
    items: list[dict],
    limit: int,
    *,
    already_selected: list[dict] | None = None,
) -> list[dict]:
    """Keep quality primary while limiting avoidable source/continent dominance."""
    context = list(already_selected or [])
    pool = _deduplicate_items(items, context)
    selected: list[dict] = []
    source_counts: Counter[str] = Counter(_source_key(item) for item in context)
    continent_counts: Counter[str] = Counter(_continent(item) for item in context)
    total_target = max(1, limit + len(context))
    source_cap = max(2, math.ceil(total_target * 0.20))
    continent_cap = max(3, math.ceil(total_target * 0.30))
    unlabelled_cap = max(2, math.ceil(total_target * 0.20))
    dated_days = [_published_day(item.get("published_at")) for item in pool + context]
    latest_day = max((day for day in dated_days if day), default=None)
    while pool and len(selected) < limit:
        strict = [
            item for item in pool
            if source_counts[_source_key(item)] < source_cap
            and continent_counts[_continent(item)] < (
                unlabelled_cap if _continent(item) == "未标注" else continent_cap
            )
        ]
        candidates = strict or [item for item in pool if source_counts[_source_key(item)] < source_cap] or pool

        def adjusted(item: dict) -> tuple[float, str]:
            source = _source_key(item)
            continent = _continent(item)
            score = float(item.get("relevance_score") or 0)
            score += min(8, float(item.get("authority") or 0))
            score -= source_counts[source] * 18
            score -= continent_counts[continent] * (6 if continent == "未标注" else 8)
            if continent not in continent_counts and continent != "未标注":
                score += 16
            if source not in source_counts:
                score += 7
            published_day = _published_day(item.get("published_at"))
            if latest_day and published_day:
                score += max(0, 6 - (latest_day - published_day).days) * 3
            return score, item.get("published_at") or ""

        choice = max(candidates, key=adjusted)
        pool.remove(choice)
        selected.append(choice)
        source_counts[_source_key(choice)] += 1
        continent_counts[_continent(choice)] += 1
    return selected


def select_latest_day(items: list[dict], *, limit: int = 12) -> list[dict]:
    dated = [(item, _published_day(item.get("published_at"))) for item in items]
    latest = max((day for _, day in dated if day), default=None)
    if not latest:
        return []
    return balanced_select([item for item, day in dated if day == latest], limit)


def select_daily_window(
    items: list[dict],
    *,
    limit: int = 10,
    lookback_days: int = 7,
    min_items: int = 8,
    min_sources: int = 3,
    min_fresh_items: int = 3,
    min_fresh_sources: int = 2,
) -> list[dict]:
    """Select the freshest publication-ready Beijing window.

    Early-morning crawls can contain only a few wire-service duplicates from the
    new calendar day. Publishing those records alone makes the map empty and
    replaces a complete edition with a partial one. The public edition therefore
    prefers a complete single day, but when the latest day has several genuine
    sources it is allowed to lead the edition and borrow high-quality records
    from the recent archive to keep the briefing useful and visibly current.
    """
    dated = [(item, _published_day(item.get("published_at"))) for item in items]
    latest = max((day for _, day in dated if day), default=None)
    if not latest:
        return []
    first_day = latest - timedelta(days=max(0, lookback_days - 1))
    candidates: list[tuple[date, list[dict], int, int]] = []
    recent_items = [item for item, day in dated if day and first_day <= day <= latest]
    for publication_day in sorted(
        {day for _, day in dated if day and first_day <= day <= latest},
        reverse=True,
    ):
        day_items = _deduplicate_items([item for item, day in dated if day == publication_day])
        selected = balanced_select(day_items, limit)
        source_total = len({_source_key(item) for item in selected})
        mapped_total = sum(bool(item.get("places")) for item in selected)
        candidates.append((publication_day, selected, source_total, mapped_total))
        if len(selected) >= min_items and source_total >= min_sources and mapped_total:
            return sorted(selected, key=lambda item: item.get("published_at") or "", reverse=True)
        if (
            publication_day == latest
            and len(selected) >= min_fresh_items
            and source_total >= min_fresh_sources
            and mapped_total
        ):
            fillers = balanced_select(
                [item for item in recent_items if _published_day(item.get("published_at")) != latest],
                max(0, limit - len(selected)),
                already_selected=selected,
            )
            blended = selected + fillers
            if len(blended) >= min_items and len({_source_key(item) for item in blended}) >= min_sources:
                return sorted(blended, key=lambda item: item.get("published_at") or "", reverse=True)

    if not candidates:
        return []
    _, selected, _, _ = max(
        candidates,
        key=lambda row: (min(len(row[1]), limit), row[2], row[3], row[0]),
    )
    return sorted(selected, key=lambda item: item.get("published_at") or "", reverse=True)


def count_backfilled_items(items: list[dict]) -> int:
    days = [_published_day(item.get("published_at")) for item in items]
    days = [day for day in days if day]
    latest_day = max(days, default=None)
    if not latest_day:
        return 0
    return sum(_published_day(item.get("published_at")) != latest_day for item in items)


def select_latest_week(items: list[dict], *, limit: int = 48) -> list[dict]:
    dated = [(item, _published_day(item.get("published_at"))) for item in items]
    latest = max((day for _, day in dated if day), default=None)
    if not latest:
        return []
    first_day = latest - timedelta(days=6)
    return balanced_select([item for item, day in dated if day and first_day <= day <= latest], limit)


def _publishable_candidates(db: Database) -> list[dict]:
    base_query = """
        SELECT a.*, s.name AS source_name, s.source_type, s.authority
        FROM articles a JOIN sources s ON s.source_id=a.source_id
        {where_clause}
        ORDER BY a.relevance_score DESC,
                 CASE WHEN a.published_at_utc IS NULL THEN 1 ELSE 0 END,
                 a.published_at_utc DESC
        LIMIT 600
    """
    rows = db.rows(base_query.format(where_clause=""))
    items = []
    for row in rows:
        metadata = _decode_json(row.pop("metadata_json"), {})
        row["topics"] = [TOPIC_ZH_ALIASES.get(topic, topic) for topic in _decode_json(row.pop("topics_json"), [])]
        row["numbers"] = _decode_json(row.pop("numbers_json"), [])
        row["summary_zh"] = metadata.get("summary_zh")
        row["theme_zh"] = metadata.get("theme_zh") or (row["topics"][0] if row["topics"] else "气候动态")
        row["why_zh"] = metadata.get("importance_zh") or metadata.get("why_zh", "进入人工复核队列。")
        row["places"] = metadata.get("places", [])
        row["poster_phrase"] = metadata.get("poster_phrase") or row["theme_zh"]
        row["translation_status"] = metadata.get("translation_status", "pending")
        row["fact_status"] = metadata.get("fact_status", "source_claim_unverified")
        row["published_at"] = row.pop("published_at_utc")
        signal = f"{row['title_original']} {row['canonical_url']}".lower()
        decision_score = int(row["relevance_score"])
        if row["source_id"] in {"OFF001", "OFF006"}:
            decision_score += 12
            if row["translation_status"] == "pending":
                row["why_zh"] = f"联合国系统来源发布；{row['why_zh']}"
        if any(term in signal for term in (
            "unfccc", "cop3", "ndc", "climate finance", "loss and damage",
            "emitting countries", "methane", "government", "law", "funding",
            "regulator", "target", "net zero", "electrification",
        )):
            decision_score += 10
        if any(term in signal for term in ("commentisfree", "commentary", "op-ed", "opinion", " quotes from ", "world cup")):
            decision_score -= 18
            if row["translation_status"] == "pending":
                row["why_zh"] = "该条以观点、引语汇编或非谈判叙事为主，仅作舆情背景，不作为事实结论。"
            row["fact_status"] = "opinion_or_context"
        row["relevance_score"] = max(0, min(100, decision_score))
        items.append(row)
    items.sort(key=lambda item: (item["relevance_score"], item.get("published_at") or ""), reverse=True)
    # The public dashboard never falls back to English source abstracts. If the
    # latest crawl is still awaiting translation, retain the latest publishable
    # Chinese snapshot instead of rendering empty or low-quality cards.
    publishable = [
        item for item in items
        if item.get("title_zh")
        and not is_generic_title(item.get("title_zh"))
        and (
            (item.get("summary_zh") and not is_generic_summary(item.get("summary_zh")))
            or len(intelligence_keywords(item)) >= 2
        )
    ]
    return publishable[:120]


def _live_intelligence(db: Database) -> list[dict]:
    return select_daily_window(_publishable_candidates(db))


def publishable_intelligence(db: Database) -> list[dict]:
    """Public, quality-gated candidates used by both the briefing and archive."""
    return _publishable_candidates(db)


def _official_data(db: Database) -> dict:
    ndcs = db.rows("""
        SELECT document_id,party,title,version,status,publication_date,language,detail_url,file_url
        FROM official_documents WHERE kind='ndc'
        ORDER BY publication_date DESC, party LIMIT 10
    """)
    decisions = db.rows("""
        SELECT document_id,title,symbol,body,session,cop_number,publication_date,detail_url,file_url,metadata_json
        FROM official_documents WHERE kind='decision'
        ORDER BY cop_number DESC, symbol LIMIT 14
    """)
    for item in decisions:
        item["why_zh"] = _decode_json(item.pop("metadata_json"), {}).get("why_zh", "")
    metrics = db.rows("""
        SELECT m.label_zh,m.value_text,m.scope_text,m.source_url,d.title,d.symbol
        FROM official_metrics m JOIN official_documents d ON d.document_id=m.document_id
        ORDER BY m.sort_order
    """)
    counts = db.rows("SELECT kind, COUNT(*) AS n FROM official_documents GROUP BY kind")
    return {
        "counts": {row["kind"]: row["n"] for row in counts},
        "recent_ndcs": ndcs,
        "key_decisions": decisions,
        "summary_metrics": metrics,
    }


def _map_events(items: list[dict], *, max_events: int = 80) -> list[dict]:
    events: list[dict] = []
    for item in items:
        for index, place in enumerate(item.get("places", [])):
            if not all(key in place for key in ("name_zh", "lon", "lat")):
                continue
            events.append({
                "marker_id": f"{item['article_id']}_{index}",
                "article_id": item["article_id"],
                "place": place["name_zh"],
                "lon": place["lon"],
                "lat": place["lat"],
                "theme": item.get("theme_zh") or "气候动态",
                "title_zh": item.get("title_zh") or item["title_original"],
                "summary_zh": item.get("summary_zh") or "",
                "source_name": item["source_name"],
                "published_at": item["published_at"],
                "url": item["canonical_url"],
            })
            if len(events) >= max_events:
                return events
    return events


def apply_archive_windows(payload: dict, archive: dict) -> dict:
    """Make the public windows derive from the cumulative, quality-gated archive."""
    records = archive.get("records") or []
    today_items = select_daily_window(records, limit=10)
    week_items = select_latest_week(records, limit=60)
    if not today_items:
        return payload
    latest_day = max(
        (_published_day(item.get("published_at")) for item in today_items),
        default=None,
    )
    publication_day = datetime.now(BEIJING_TZ).date()
    payload["intelligence"] = today_items
    payload["map_events_today"] = _map_events(today_items)
    payload["map_events_week"] = _map_events(week_items)
    payload["map_events"] = payload["map_events_today"]
    payload["meta"]["date"] = publication_day.isoformat()
    payload["meta"]["latest_news_date"] = latest_day.isoformat() if latest_day else payload["meta"]["date"]
    selected_days = [_published_day(item.get("published_at")) for item in today_items]
    selected_days = [day for day in selected_days if day]
    payload["meta"]["daily_window_start"] = min(selected_days).isoformat() if selected_days else payload["meta"]["date"]
    payload["meta"]["daily_target"] = 10
    payload["meta"]["daily_backfilled"] = count_backfilled_items(today_items)
    payload["meta"]["daily_complete_day"] = payload["meta"]["daily_backfilled"] == 0
    payload["meta"]["daily_sources"] = len({_source_key(item) for item in today_items})
    payload["meta"]["daily_continents"] = len({_continent(item) for item in today_items if _continent(item) != "未标注"})
    payload["metrics"]["high_priority"] = sum(item.get("relevance_score", 0) >= 70 for item in today_items)
    topics = Counter(topic for item in today_items for topic in item.get("topics", []))
    payload["topics"] = [{"name": name, "weight": count} for name, count in topics.most_common()]
    payload["phrases"] = [
        {
            "text": item.get("poster_phrase") or item.get("title_zh") or item.get("title_original"),
            "theme": item.get("theme_zh") or "气候动态",
            "weight": max(1, 10 - index),
        }
        for index, item in enumerate(today_items[:8])
    ]
    return payload


def dashboard_payload(db: Database) -> dict:
    source_rows = db.rows("SELECT * FROM sources ORDER BY enabled DESC, authority DESC, name")
    candidates = _publishable_candidates(db)
    intelligence = select_daily_window(candidates, limit=10)
    weekly_intelligence = select_latest_week(candidates)
    demo_rows = db.rows("SELECT * FROM events ORDER BY urgency DESC, published_at DESC")
    demo_events = sorted((decode_event(row) for row in demo_rows), key=lambda x: x["priority"], reverse=True)
    enabled = [row for row in source_rows if row["enabled"]]
    regions = Counter(row["region"] or "其他" for row in enabled)
    phases = Counter(row["phase"] for row in source_rows)
    topics = Counter(topic for item in intelligence for topic in item["topics"])
    if not topics:
        topics.update(tag for event in demo_events for tag in event["tags"])
    today = datetime.now(BEIJING_TZ).date()
    cop31 = date(2026, 11, 9)
    latest_runs = db.rows("""
        SELECT f.source_id,f.status,f.finished_at,f.items_seen,f.error_message
        FROM fetch_runs f
        WHERE f.run_id=(SELECT f2.run_id FROM fetch_runs f2 WHERE f2.source_id=f.source_id ORDER BY f2.finished_at DESC LIMIT 1)
        ORDER BY f.source_id
    """)
    run_ok = sum(row["status"] in {"success", "empty"} for row in latest_runs)
    year_counts = {int(row["year"]): row["n"] for row in db.rows("""
        SELECT CAST(substr(publication_date,1,4) AS INTEGER) AS year, COUNT(*) AS n
        FROM official_documents
        WHERE publication_date IS NOT NULL AND CAST(substr(publication_date,1,4) AS INTEGER) BETWEEN 2016 AND 2026
        GROUP BY year
    """)}
    official = _official_data(db)
    live = bool(intelligence)
    map_events_today = _map_events(intelligence)
    map_events_week = _map_events(weekly_intelligence)
    intelligence_days = [_published_day(item.get("published_at")) for item in intelligence]
    intelligence_days = [day for day in intelligence_days if day]
    backfilled = count_backfilled_items(intelligence)
    phrases = [
        {
            "text": item.get("poster_phrase") or item["title_zh"],
            "theme": item.get("theme_zh") or "气候动态",
            "weight": max(1, 10 - index),
        }
        for index, item in enumerate(intelligence[:8])
    ]
    return {
        "meta": {
            "product": "国际气候情报与高质量中文文本数据库",
            "date": today.isoformat(),
            "generated_at": datetime.now(UTC).isoformat(),
            "timezone": "Asia/Shanghai",
            "demo_mode": not live,
            "notice": (
                f"今日简报按北京时间每日生成；新闻素材优先采用最新自然日，若当天合格记录不足，则用近 7 天高质量记录补足至约 10 条。动态 P0 入口最近成功 {run_ok} 个。标题和摘要是来源陈述，尚需人工核验。"
                if live else "尚未执行在线同步，以下事件仅用于界面演示；UNFCCC 本地档案可独立浏览。"
            ),
            "latest_news_date": max(intelligence_days, default=today).isoformat(),
            "daily_window_start": min(intelligence_days, default=today).isoformat(),
            "daily_target": 10,
            "daily_backfilled": backfilled,
            "daily_complete_day": backfilled == 0,
            "daily_sources": len({_source_key(item) for item in intelligence}),
            "daily_continents": len({_continent(item) for item in intelligence if _continent(item) != "未标注"}),
        },
        "metrics": {
            "source_total": len(source_rows),
            "source_enabled": len(enabled),
            "p0_connected": run_ok,
            "p0_total": sum(row["phase"] == "P0" and row["enabled"] for row in source_rows),
            "official_enabled": sum("官方" in row["source_type"] or "政府" in row["source_type"] for row in enabled),
            "languages": len({lang for row in source_rows for lang in json.loads(row["languages_json"])}),
            "article_total": db.rows("SELECT COUNT(*) AS n FROM articles")[0]["n"],
            "high_priority": sum(item["relevance_score"] >= 70 for item in intelligence),
            "official_documents": sum(official["counts"].values()),
            "cop31_countdown": (cop31 - today).days,
        },
        "intelligence": intelligence,
        "map_events": map_events_today,
        "map_events_today": map_events_today,
        "map_events_week": map_events_week,
        "phrases": phrases,
        "events": [] if live else demo_events,
        "topics": [{"name": name, "weight": count} for name, count in topics.most_common()],
        "coverage": [{"name": name, "count": count} for name, count in regions.most_common(8)],
        "phases": [{"name": name, "count": phases.get(name, 0)} for name in ("P0", "P1", "P2", "Discovery")],
        "source_health": latest_runs,
        "official": official,
        "modules": module_manifest(),
        "history": [
            {"year": year, "status": "已导入" if year_counts.get(year) else "待补齐", "coverage": year_counts.get(year, 0)}
            for year in range(2016, 2027)
        ],
    }


def render_markdown(payload: dict) -> str:
    meta = payload["meta"]
    lines = [
        f"# 国际气候情报今日简报｜{meta['date']}", "", f"> {meta['notice']}", "",
        "## 今日重要情报", "",
    ]
    for index, item in enumerate(payload.get("intelligence", []), 1):
        title = item.get("title_zh") or item["title_original"]
        summary = item.get("summary_zh") or "来源仅提供标题，概要待人工补充。"
        theme = item.get("theme_zh") or "气候动态"
        lines.extend([
            f"### {index}. [{theme}] {title}", "",
            summary, "",
            f"- 来源：{item['source_name']}｜{item.get('published_at') or '时间待核'}",
            f"- 为什么值得关注：{item['why_zh']}",
            f"- 状态：{'观点/背景材料' if item['fact_status'] == 'opinion_or_context' else '来源陈述，未作独立事实核验'}",
            f"- 原文：{item['canonical_url']}", "",
        ])
    if not payload.get("intelligence"):
        for index, event in enumerate(payload.get("events", []), 1):
            lines.extend([
                f"### {index}. {event['title_zh']}｜演示", "",
                f"- 事实：{event['fact']}", f"- 系统研判：{event['assessment']}", "",
            ])
    lines.extend(["## 数据边界", "", "新闻标题与中文概要不等于已独立核实的事实；涉及数字、承诺和立场时，请通过原文链接回到原始文件复核。", ""])
    return "\n".join(lines)


def save_brief(db: Database, payload: dict) -> dict:
    brief_date = payload["meta"]["date"]
    existing = db.rows("SELECT COALESCE(MAX(version), 0) AS version FROM briefs WHERE brief_date=?", (brief_date,))
    version = int(existing[0]["version"]) + 1
    brief_id = f"brief_{uuid.uuid4().hex[:16]}"
    markdown = render_markdown(payload)
    db.execute(
        "INSERT INTO briefs (brief_id,brief_date,version,title,markdown,created_at) VALUES (?,?,?,?,?,?)",
        (brief_id, brief_date, version, f"国际气候情报今日简报｜{brief_date}", markdown, datetime.now(UTC).isoformat()),
    )
    return {"brief_id": brief_id, "version": version, "markdown": markdown}

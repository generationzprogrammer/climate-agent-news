from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import UTC, date, datetime

from .db import Database
from .pipeline import decode_event, module_manifest


TOPIC_ZH_ALIASES = {
    "UNFCCC进程": "国际气候谈判",
    "国家承诺/NDC": "国家气候承诺",
    "减缓与能源": "能源与排放",
    "适应与损失损害": "气候适应",
    "碳市场/Article 6": "国际碳市场",
    "透明度与盘点": "履约与全球盘点",
    "气候综合": "气候动态",
}


def _decode_json(value: str | None, fallback):
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def _live_intelligence(db: Database) -> list[dict]:
    base_query = """
        SELECT a.*, s.name AS source_name, s.source_type, s.authority
        FROM articles a JOIN sources s ON s.source_id=a.source_id
        {where_clause}
        ORDER BY a.relevance_score DESC,
                 CASE WHEN a.published_at_utc IS NULL THEN 1 ELSE 0 END,
                 a.published_at_utc DESC
        LIMIT 80
    """
    rows = db.rows(base_query.format(
        where_clause="WHERE datetime(a.published_at_utc) >= datetime('now','-72 hours')"
    ))
    archived_rows = db.rows(base_query.format(where_clause=""))
    seen_ids = {row["article_id"] for row in rows}
    rows.extend(row for row in archived_rows if row["article_id"] not in seen_ids)
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
        if any(term in signal for term in ("commentisfree", "opinion", " quotes from ", "world cup")):
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
    publishable = [item for item in items if item.get("title_zh") and item.get("summary_zh")]
    return publishable[:24]


def publishable_intelligence(db: Database) -> list[dict]:
    """Public, quality-gated candidates used by both the briefing and archive."""
    return _live_intelligence(db)


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


def dashboard_payload(db: Database) -> dict:
    source_rows = db.rows("SELECT * FROM sources ORDER BY enabled DESC, authority DESC, name")
    intelligence = _live_intelligence(db)
    demo_rows = db.rows("SELECT * FROM events ORDER BY urgency DESC, published_at DESC")
    demo_events = sorted((decode_event(row) for row in demo_rows), key=lambda x: x["priority"], reverse=True)
    enabled = [row for row in source_rows if row["enabled"]]
    regions = Counter(row["region"] or "其他" for row in enabled)
    phases = Counter(row["phase"] for row in source_rows)
    topics = Counter(topic for item in intelligence for topic in item["topics"])
    if not topics:
        topics.update(tag for event in demo_events for tag in event["tags"])
    today = date.today()
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
    map_events = []
    for item in intelligence[:10]:
        for index, place in enumerate(item.get("places", [])):
            map_events.append({
                "marker_id": f"{item['article_id']}_{index}",
                "article_id": item["article_id"],
                "place": place["name_zh"],
                "lon": place["lon"],
                "lat": place["lat"],
                "theme": item["theme_zh"],
                "title_zh": item.get("title_zh") or item["title_original"],
                "summary_zh": item.get("summary_zh") or "中文编译待完成。",
                "source_name": item["source_name"],
                "published_at": item["published_at"],
                "url": item["canonical_url"],
            })
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
            "product": "高质量气候新闻文本数据与智能分子平台",
            "date": today.isoformat(),
            "generated_at": datetime.now(UTC).isoformat(),
            "timezone": "Asia/Shanghai",
            "demo_mode": not live,
            "notice": (
                f"滚动 72 小时元数据已接入；8 个 P0 入口最近成功 {run_ok} 个。标题和短摘录是来源陈述，尚需人工核验。"
                if live else "尚未执行在线同步，以下事件仅用于界面演示；UNFCCC 本地档案可独立浏览。"
            ),
        },
        "metrics": {
            "source_total": len(source_rows),
            "source_enabled": len(enabled),
            "p0_connected": run_ok,
            "p0_total": 8,
            "official_enabled": sum("官方" in row["source_type"] or "政府" in row["source_type"] for row in enabled),
            "languages": len({lang for row in source_rows for lang in json.loads(row["languages_json"])}),
            "article_total": db.rows("SELECT COUNT(*) AS n FROM articles")[0]["n"],
            "high_priority": sum(item["relevance_score"] >= 70 for item in intelligence),
            "official_documents": sum(official["counts"].values()),
            "cop31_countdown": (cop31 - today).days,
        },
        "intelligence": intelligence[:10],
        "map_events": map_events,
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
        f"# 国际气候谈判情报简报｜{meta['date']}", "", f"> {meta['notice']}", "",
        "## 今日具体情报", "",
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
        (brief_id, brief_date, version, f"国际气候谈判情报简报｜{brief_date}", markdown, datetime.now(UTC).isoformat()),
    )
    return {"brief_id": brief_id, "version": version, "markdown": markdown}

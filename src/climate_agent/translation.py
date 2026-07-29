from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from .db import Database
from .providers import OpenAICompatibleModel


GEO_TERMS = {
    "china": ("中国", 105.0, 35.0),
    "beijing": ("中国", 105.0, 35.0),
    "united states": ("美国", -100.0, 39.0),
    " u.s.": ("美国", -100.0, 39.0),
    "texas": ("美国得州", -99.0, 31.0),
    "united kingdom": ("英国", -2.0, 54.0),
    " uk ": ("英国", -2.0, 54.0),
    "europe": ("欧洲", 10.0, 51.0),
    "africa": ("非洲", 22.0, 2.0),
    "west africa": ("西非", -4.0, 8.0),
    "congo": ("刚果盆地", 18.0, -1.0),
    "brazil": ("巴西", -52.0, -10.0),
    "india": ("印度", 78.0, 22.0),
    "indonesia": ("印度尼西亚", 118.0, -2.0),
    "australia": ("澳大利亚", 134.0, -25.0),
    "canada": ("加拿大", -106.0, 56.0),
    "turkey": ("土耳其", 35.0, 39.0),
    "germany": ("德国", 10.0, 51.0),
    "france": ("法国", 2.0, 46.0),
    "philippines": ("菲律宾", 122.0, 13.0),
    "uganda": ("乌干达", 32.0, 1.0),
    "mexico": ("墨西哥", -102.0, 23.0),
    "latin america": ("拉丁美洲", -66.0, -15.0),
    "amazon": ("亚马孙地区", -62.0, -4.0),
    "argentina": ("阿根廷", -64.0, -34.0),
    "chile": ("智利", -71.0, -33.0),
    "peru": ("秘鲁", -76.0, -10.0),
    "colombia": ("哥伦比亚", -74.0, 4.0),
    "antarctica": ("南极洲", 0.0, -78.0),
    "antarctic": ("南极洲", 0.0, -78.0),
    "greenland": ("格陵兰", -42.0, 72.0),
    "new zealand": ("新西兰", 174.0, -41.0),
    "pacific islands": ("太平洋岛国", 165.0, -10.0),
    "south africa": ("南非", 24.0, -29.0),
    "kenya": ("肯尼亚", 37.0, 0.0),
    "nigeria": ("尼日利亚", 8.0, 9.0),
    "japan": ("日本", 138.0, 37.0),
    "south korea": ("韩国", 128.0, 36.0),
}


def detect_places(text: str) -> list[dict]:
    haystack = f" {text.lower()} "
    places = []
    seen = set()
    for term, (name, lon, lat) in GEO_TERMS.items():
        if term in haystack and name not in seen:
            places.append({"name_zh": name, "lon": lon, "lat": lat})
            seen.add(name)
    return places[:3]


def source_balanced_rows(rows: list[dict], limit: int) -> list[dict]:
    """Preserve quality order while preventing one publisher from filling the queue."""
    buckets: dict[str, list[dict]] = {}
    order: list[str] = []
    for row in rows:
        source_id = row.get("source_id") or "unknown"
        if source_id not in buckets:
            buckets[source_id] = []
            order.append(source_id)
        buckets[source_id].append(row)
    selected: list[dict] = []
    while len(selected) < limit and any(buckets.values()):
        for source_id in order:
            if buckets[source_id] and len(selected) < limit:
                selected.append(buckets[source_id].pop(0))
    return selected


def translate_pending(db: Database, model: OpenAICompatibleModel, *, limit: int = 20) -> dict:
    rows = db.rows("""
        SELECT article_id,source_id,title_original,summary_source,canonical_url,metadata_json
        FROM articles
        WHERE (title_zh IS NULL OR trim(title_zh)='')
          AND datetime(published_at_utc) >= datetime('now','-7 days')
        ORDER BY relevance_score DESC,published_at_utc DESC LIMIT ?
    """, (max(limit * 4, limit),))
    rows = source_balanced_rows(rows, limit)
    translated = 0
    failed = []
    system = """你是面向中国资深气候政策与外交工作者的中文编译编辑。把输入新闻准确、克制地编译为中文。
只输出 JSON 对象，键为 translations，值为数组。每项必须包含 article_id、title_zh、summary_zh、theme_zh、importance_zh、poster_phrase。
要求：标题自然简洁；摘要 60–120 个汉字并保留数字的对象、单位和比较关系；theme_zh 使用自然中文短语，如“甲烷减排”“气候资金”“极端高温”，不要使用生硬分类词；importance_zh 说明政策或谈判意义并标明观点/事实边界；poster_phrase 不超过 14 个汉字。不得补充输入中不存在的事实。"""
    for start in range(0, len(rows), 5):
        batch = rows[start:start + 5]
        payload = {"articles": [{
            "article_id": row["article_id"],
            "title": row["title_original"],
            "summary": (row.get("summary_source") or "")[:1200],
            "url": row["canonical_url"],
        } for row in batch]}
        try:
            result = model.complete_json(system, payload)
            outputs = {item["article_id"]: item for item in result.get("translations", [])}
        except Exception as exc:
            failed.extend({"article_id": row["article_id"], "error": str(exc)[:200]} for row in batch)
            continue
        with db.connect() as conn:
            for row in batch:
                item = outputs.get(row["article_id"])
                if not item or not re.search(r"[\u4e00-\u9fff]", item.get("title_zh", "")):
                    failed.append({"article_id": row["article_id"], "error": "invalid_translation"})
                    continue
                try:
                    metadata = json.loads(row.get("metadata_json") or "{}")
                except json.JSONDecodeError:
                    metadata = {}
                metadata.update({
                    "summary_zh": item["summary_zh"],
                    "theme_zh": item["theme_zh"],
                    "importance_zh": item["importance_zh"],
                    "poster_phrase": item["poster_phrase"],
                    "places": detect_places(f"{row['title_original']} {row.get('summary_source') or ''}"),
                    "translation_status": "model_generated_needs_review",
                    "translated_at": datetime.now(UTC).isoformat(),
                })
                conn.execute(
                    "UPDATE articles SET title_zh=?,metadata_json=? WHERE article_id=?",
                    (item["title_zh"], json.dumps(metadata, ensure_ascii=False), row["article_id"]),
                )
                translated += 1
    return {"pending": len(rows), "translated": translated, "failed": failed}

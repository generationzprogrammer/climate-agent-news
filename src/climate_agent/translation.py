from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from .db import Database
from .providers import OpenAICompatibleModel


GEO_TERMS = {
    "china": ("中国", 105.0, 35.0),
    "beijing": ("中国", 105.0, 35.0),
    "中国": ("中国", 105.0, 35.0),
    "北京": ("中国", 105.0, 35.0),
    "united states": ("美国", -100.0, 39.0),
    " u.s.": ("美国", -100.0, 39.0),
    "美国": ("美国", -100.0, 39.0),
    "texas": ("美国得州", -99.0, 31.0),
    "united kingdom": ("英国", -2.0, 54.0),
    " uk ": ("英国", -2.0, 54.0),
    "europe": ("欧洲", 10.0, 51.0),
    "africa": ("非洲", 22.0, 2.0),
    "west africa": ("西非", -4.0, 8.0),
    "congo": ("刚果盆地", 18.0, -1.0),
    "brazil": ("巴西", -52.0, -10.0),
    "巴西": ("巴西", -52.0, -10.0),
    "india": ("印度", 78.0, 22.0),
    "indonesia": ("印度尼西亚", 118.0, -2.0),
    "australia": ("澳大利亚", 134.0, -25.0),
    "澳大利亚": ("澳大利亚", 134.0, -25.0),
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
    "南极": ("南极洲", 0.0, -78.0),
    "greenland": ("格陵兰", -42.0, 72.0),
    "new zealand": ("新西兰", 174.0, -41.0),
    "pacific islands": ("太平洋岛国", 165.0, -10.0),
    "south africa": ("南非", 24.0, -29.0),
    "南非": ("南非", 24.0, -29.0),
    "kenya": ("肯尼亚", 37.0, 0.0),
    "nigeria": ("尼日利亚", 8.0, 9.0),
    "japan": ("日本", 138.0, 37.0),
    "south korea": ("韩国", 128.0, 36.0),
    "caribbean": ("加勒比地区", -75.0, 18.0),
    "加勒比": ("加勒比地区", -75.0, 18.0),
    "haiti": ("海地", -72.3, 19.0),
    "jamaica": ("牙买加", -77.3, 18.1),
    "bahamas": ("巴哈马", -77.4, 25.0),
    "dominican republic": ("多米尼加", -70.2, 18.8),
}


def detect_places(text: str) -> list[dict]:
    haystack = f" {text.lower()} "
    places = []
    seen = set()
    for term, (name, lon, lat) in sorted(GEO_TERMS.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9-])", haystack) and name not in seen:
            places.append({"name_zh": name, "lon": lon, "lat": lat})
            seen.add(name)
    return places[:3]


def source_balanced_rows(rows: list[dict], limit: int) -> list[dict]:
    """Round-robin source regions first and publishers second, preserving quality order."""
    buckets: dict[str, dict[str, list[dict]]] = {}
    region_order: list[str] = []
    source_order: dict[str, list[str]] = {}
    for row in rows:
        region = row.get("source_region") or row.get("region") or "unknown"
        source_id = row.get("source_id") or "unknown"
        if region not in buckets:
            buckets[region] = {}
            source_order[region] = []
            region_order.append(region)
        if source_id not in buckets[region]:
            buckets[region][source_id] = []
            source_order[region].append(source_id)
        buckets[region][source_id].append(row)
    selected: list[dict] = []
    cursors = {region: 0 for region in region_order}
    while len(selected) < limit:
        made_progress = False
        for region in region_order:
            sources = source_order[region]
            for _ in range(len(sources)):
                source_id = sources[cursors[region] % len(sources)]
                cursors[region] += 1
                if buckets[region][source_id]:
                    selected.append(buckets[region][source_id].pop(0))
                    made_progress = True
                    break
            if len(selected) >= limit:
                break
        if not made_progress:
            break
    return selected


def _fallback_translation(row: dict) -> dict:
    """Create a conservative Chinese review stub when model translation is unavailable.

    The fallback is intentionally modest: it marks the item as a lead that still
    needs source verification instead of pretending to be a polished translation.
    This keeps the daily dashboard fresh during model/API incidents while
    preserving an explicit quality boundary for users.
    """
    text = f"{row.get('title_original') or ''} {row.get('summary_source') or ''}".lower()
    if "western us" in text and "heat wave" in text:
        title_zh = "美国西部热浪推高野火风险"
        theme_zh = "极端高温与野火"
        poster = "美国西部热浪"
    elif "spain" in text and "wildfire risk" in text and "20-fold" in text:
        title_zh = "研究称气候变化使西班牙野火风险增至20倍"
        theme_zh = "野火风险归因"
        poster = "西班牙野火风险"
    elif "spain" in text and ("pedro" in text or "sánchez" in text or "sanchez" in text):
        title_zh = "西班牙首相强调气候变化致命风险"
        theme_zh = "气候政治"
        poster = "气候政治升温"
    elif "china" in text and "south africa" in text and ("wind farm" in text or "clean energy" in text):
        title_zh = "中南清洁能源合作风电项目启动"
        theme_zh = "清洁能源合作"
        poster = "中南风电合作"
    elif "india" in text and "renewable energy" in text:
        title_zh = "印度可再生能源投资计划升温"
        theme_zh = "可再生能源投资"
        poster = "印度绿能投资"
    elif ("norwegian" in text or "norway" in text) and "renewable energy" in text:
        title_zh = "挪威融资支持可再生能源项目"
        theme_zh = "可再生能源融资"
        poster = "绿能融资"
    elif "europe" in text and "wildfire" in text:
        title_zh = "欧洲野火形势判断受到事实核查"
        theme_zh = "野火风险"
        poster = "欧洲野火核查"
    elif any(term in text for term in ("heat wave", "wildfire", "flood", "drought", "hurricane", "storm", "extreme weather")):
        title_zh = "极端天气风险出现新动态"
        theme_zh = "极端天气与气候风险"
        poster = "极端天气预警"
    elif "climate finance" in text or "loss and damage" in text:
        title_zh = "气候资金议题出现新进展"
        theme_zh = "气候资金"
        poster = "资金议题升温"
    elif any(term in text for term in ("renewable", "clean energy", "energy transition", "net zero")):
        title_zh = "清洁能源转型出现新进展"
        theme_zh = "能源转型"
        poster = "能源转型提速"
    elif any(term in text for term in ("summit", "unfccc", "cop30", "cop31", "ndc", "negotiat")):
        title_zh = "国际气候谈判出现新动向"
        theme_zh = "气候谈判"
        poster = "谈判信号更新"
    elif any(term in text for term in ("emission", "carbon", "methane")):
        title_zh = "碳排放治理出现新动向"
        theme_zh = "减排政策"
        poster = "减排信号更新"
    else:
        title_zh = "全球气候议题出现新动态"
        theme_zh = "气候动态"
        poster = "气候线索更新"
    original = (row.get("title_original") or "").strip()
    if original:
        summary_zh = (
            f"来源标题显示，{title_zh}。该信息涉及{theme_zh}，适合作为当日气候情报线索；"
            "具体数字、责任主体和政策含义仍需回到原文核验。"
        )
    else:
        summary_zh = (
            f"来源摘要显示该信息涉及{theme_zh}，适合作为当日气候情报线索；"
            "具体数字、责任主体和政策含义仍需回到原文核验。"
        )
    return {
        "title_zh": title_zh,
        "summary_zh": summary_zh[:220],
        "theme_zh": theme_zh,
        "importance_zh": "这是模型不可用时生成的待复核线索，只用于提示当日变化；引用前必须打开原文核验。",
        "poster_phrase": poster,
        "translation_status": "fallback_needs_review",
    }


def _write_translation(db: Database, row: dict, item: dict, *, fallback: bool = False) -> bool:
    title = item.get("title_zh", "")
    if not re.search(r"[\u4e00-\u9fff]", title):
        return False
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
        "translation_status": item.get(
            "translation_status",
            "fallback_needs_review" if fallback else "model_generated_needs_review",
        ),
        "translated_at": datetime.now(UTC).isoformat(),
    })
    db.execute(
        "UPDATE articles SET title_zh=?,metadata_json=? WHERE article_id=?",
        (item["title_zh"], json.dumps(metadata, ensure_ascii=False), row["article_id"]),
    )
    return True


def translate_pending(db: Database, model: OpenAICompatibleModel, *, limit: int = 20) -> dict:
    rows = db.rows("""
        SELECT a.article_id,a.source_id,a.title_original,a.summary_source,a.canonical_url,
               a.metadata_json,s.region AS source_region
        FROM articles a JOIN sources s ON s.source_id=a.source_id
        WHERE (a.title_zh IS NULL OR trim(a.title_zh)='' OR a.metadata_json NOT LIKE '%"summary_zh"%')
          AND datetime(a.published_at_utc) >= datetime('now','-7 days')
        ORDER BY date(a.published_at_utc, '+8 hours') DESC,
                 a.relevance_score DESC,
                 a.published_at_utc DESC
        LIMIT ?
    """, (max(limit * 8, limit),))
    rows = source_balanced_rows(rows, limit)
    translated = 0
    fallback_translated = 0
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
            for row in batch:
                if _write_translation(db, row, _fallback_translation(row), fallback=True):
                    translated += 1
                    fallback_translated += 1
                failed.append({"article_id": row["article_id"], "error": f"model_failed_fallback_used: {str(exc)[:160]}"})
            continue
        for row in batch:
            item = outputs.get(row["article_id"])
            if not item or not _write_translation(db, row, item):
                if _write_translation(db, row, _fallback_translation(row), fallback=True):
                    translated += 1
                    fallback_translated += 1
                failed.append({"article_id": row["article_id"], "error": "invalid_translation_fallback_used"})
                continue
            translated += 1
    return {"pending": len(rows), "translated": translated, "fallback_translated": fallback_translated, "failed": failed}

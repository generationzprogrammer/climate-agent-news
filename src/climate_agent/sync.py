from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from .collector import NormalizedArticle, fetch_resource, parse_feed, parse_gdelt
from .db import Database


P0_SOURCE_IDS = ("INT001", "INT002", "INT010", "INT013", "INT014", "OFF001", "OFF006", "API001")

TOPIC_RULES = {
    "国际气候谈判": ("unfccc", "cop30", "cop31", "climate talks", "climate summit", "negotiat"),
    "国家气候承诺": ("ndc", "nationally determined", "climate target", "2035 target"),
    "气候资金": ("climate finance", "green climate fund", "loss and damage", "adaptation fund", "finance goal"),
    "能源与排放": ("emission", "renewable", "fossil fuel", "coal", "methane", "energy transition"),
    "气候适应": ("adaptation", "loss and damage", "resilience", "climate disaster"),
    "国际碳市场": ("article 6", "carbon market", "carbon credit", "emissions trading"),
    "履约与全球盘点": ("global stocktake", "transparency", "biennial transparency", "btr"),
}

NUMBER_PATTERN = re.compile(
    r"(?<!\w)(?:US\$|\$|€|£)?\d+(?:[,.]\d+)*(?:\s?(?:%|bn|billion|million|trillion|GW|MW|Gt|Mt|°C|C))?",
    re.IGNORECASE,
)


def _analyse(article: NormalizedArticle, authority: int) -> dict:
    haystack = f"{article.title} {article.summary_from_source or ''}".lower()
    topics = [name for name, terms in TOPIC_RULES.items() if any(term in haystack for term in terms)]
    numbers = list(dict.fromkeys(NUMBER_PATTERN.findall(haystack)))[:6]
    score = min(100, authority * 8 + len(topics) * 12 + min(len(numbers), 3) * 4)
    if any(term in haystack for term in ("china", "chinese", "beijing")):
        score = min(100, score + 12)
    if article.source_id in {"OFF001", "OFF006"}:
        score = min(100, score + 8)
    if "国际气候谈判" in topics or "国家气候承诺" in topics:
        why_zh = "直接涉及多边气候进程或国家承诺，建议核对正式文件与缔约方口径。"
    elif "气候资金" in topics:
        why_zh = "涉及资金规模、责任或机制安排，可能影响资金谈判与对外表述。"
    elif "气候适应" in topics:
        why_zh = "涉及适应或损失损害议题，需关注发展中国家诉求与资金落地。"
    else:
        why_zh = "命中气候政策或能源转型关键词，进入人工复核队列。"
    return {"topics": topics or ["气候综合"], "numbers": numbers, "score": score, "why_zh": why_zh}


def _article_rows(articles: list[NormalizedArticle], source: dict) -> tuple[list[dict], dict]:
    now = datetime.now(UTC)
    rows = []
    rejected = {"future_date": 0, "duplicate_url": 0}
    seen: set[str] = set()
    for article in articles[:150]:
        if article.canonical_url in seen:
            rejected["duplicate_url"] += 1
            continue
        seen.add(article.canonical_url)
        if article.published_at_utc:
            published = datetime.fromisoformat(article.published_at_utc)
            if published > now + timedelta(days=1):
                rejected["future_date"] += 1
                continue
        analysis = _analyse(article, int(source["authority"]))
        rows.append({
            "article_id": article.article_id,
            "source_id": article.source_id,
            "source_url": article.source_url,
            "canonical_url": article.canonical_url,
            "title_original": article.title,
            "title_zh": None,
            "summary_source": article.summary_from_source,
            "published_at_utc": article.published_at_utc,
            "language": article.language,
            "rights_status": article.rights_status,
            "content_hash": article.content_hash,
            "fetched_at": now.isoformat(),
            "relevance_score": analysis["score"],
            "topics": analysis["topics"],
            "numbers": analysis["numbers"],
            "metadata": {
                "why_zh": analysis["why_zh"],
                "extraction_method": article.extraction_method,
                "parser_version": article.parser_version,
                "fact_status": "source_claim_unverified",
            },
        })
    return rows, {
        "accepted": len(rows),
        "missing_dates": sum(not row["published_at_utc"] for row in rows),
        "rejected": {key: value for key, value in rejected.items() if value},
        "metadata_only": True,
    }


def _gdelt_url(endpoint: str) -> str:
    params = {
        "query": '("climate change" OR UNFCCC OR "climate finance" OR NDC)',
        "mode": "ArtList",
        "maxrecords": "25",
        "format": "json",
        "sort": "DateDesc",
        "timespan": "24h",
    }
    return f"{endpoint}?{urlencode(params)}"


def sync_p0(db: Database, source_ids: tuple[str, ...] = P0_SOURCE_IDS) -> dict:
    results = []
    for source_id in source_ids:
        source_rows = db.rows("SELECT * FROM sources WHERE source_id=?", (source_id,))
        if not source_rows:
            results.append({"source_id": source_id, "status": "failed", "error": "source_not_configured"})
            continue
        source = source_rows[0]
        endpoint = source.get("machine_url")
        started = datetime.now(UTC)
        run = {
            "run_id": f"fetch_{uuid.uuid4().hex}",
            "source_id": source_id,
            "endpoint": endpoint or "",
            "started_at": started.isoformat(),
            "finished_at": started.isoformat(),
            "status": "failed",
        }
        try:
            if not endpoint or "{" in endpoint:
                raise ValueError("source has no directly callable endpoint")
            request_url = _gdelt_url(endpoint) if source_id == "API001" else endpoint
            response = fetch_resource(
                request_url,
                max_bytes=3_000_000,
                accept="application/json" if source_id == "API001" else "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9",
            )
            languages = json.loads(source["languages_json"])
            articles = parse_gdelt(response.payload) if source_id == "API001" else parse_feed(
                response.payload, source_id, languages[0] if languages else None,
            )
            rows, quality = _article_rows(articles, source)
            counts = db.upsert_articles(rows)
            run.update({
                "status": "success" if rows else "empty",
                "http_status": response.status,
                "content_type": response.content_type,
                "response_bytes": response.size,
                "items_seen": counts["seen"],
                "items_new": counts["new"],
                "items_updated": counts["updated"],
                "quality": quality,
            })
        except Exception as exc:  # each source is an isolated failure domain
            run.update({
                "error_class": type(exc).__name__,
                "error_message": str(exc)[:500],
                "quality": {"accepted": 0, "metadata_only": True},
            })
        finally:
            run["finished_at"] = datetime.now(UTC).isoformat()
            db.record_fetch_run(run)
            results.append({
                "source_id": source_id,
                "name": source.get("name"),
                "status": run["status"],
                "items_seen": run.get("items_seen", 0),
                "items_new": run.get("items_new", 0),
                "error": run.get("error_message"),
            })
    succeeded = sum(item["status"] in {"success", "empty"} for item in results)
    return {
        "status": "ok" if succeeded == len(results) else "partial",
        "sources_ok": succeeded,
        "sources_total": len(results),
        "articles_total": sum(item["items_seen"] for item in results),
        "results": results,
    }

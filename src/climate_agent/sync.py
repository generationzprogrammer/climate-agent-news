from __future__ import annotations

import json
import re
import time
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

from .collector import NormalizedArticle, fetch_resource, parse_feed, parse_gdelt
from .db import Database


P0_SOURCE_IDS = (
    "INT001", "INT002", "INT007", "INT008", "INT009", "INT010", "INT013",
    "INT014", "INT019", "INT020", "OFF001", "OFF006", "OFF013", "OFF014",
    "API001", "API005", "API004",
)

GDELT_SOURCE_IDS = {"API001", "API005"}
GOOGLE_NEWS_SOURCE_IDS = {"API004"}
GOOGLE_NEWS_EXCLUDE_TERMS = (
    "sesame", "nickalive", "movie", "celebrity", "sports", "football",
    "basketball", "baseball", "golf", "tennis", "horoscope", "recipe",
)

# Several short searches are more reliable than one long Boolean expression in
# Google News RSS.  They also make the daily recall less dependent on GDELT,
# which periodically returns HTTP 429 from shared GitHub Actions runners.
GOOGLE_NEWS_QUERIES = (
    '("climate change" OR "climate policy" OR "climate finance" OR emissions) when:1d',
    '(heatwave OR "extreme heat" OR wildfire OR drought OR flooding) climate when:1d',
    '("clean energy" OR "renewable energy" OR solar OR wind OR battery OR "power grid") '
    '(policy OR project OR investment OR technology) when:1d',
    '(China OR "United States" OR Africa OR "Latin America" OR Australia) '
    '("climate change" OR "energy transition" OR "clean energy") when:1d',
)

GDELT_PROFILES = {
    "API001": {
        "query": '("climate change" OR UNFCCC OR "climate finance" OR NDC)',
        "maxrecords": "25",
        "timespan": "24h",
    },
    # Keep the regional query narrow and lightweight.  A seven-day window caused
    # repeated HTTP 429 responses and could also starve the global GDELT query.
    "API005": {
        "query": (
            '("climate change" OR "carbon neutrality" OR "carbon market" OR '
            'emissions OR renewable OR "zero-carbon") '
            '(domain:news.cn OR domain:gov.cn OR domain:mee.gov.cn OR '
            'domain:cma.gov.cn OR domain:dialogue.earth)'
        ),
        "maxrecords": "25",
        "timespan": "24h",
    },
}

NASA_EARTH_TERMS = (
    "climate", "wildfire", "smoke", "heat", "drought", "flood", "storm",
    "hurricane", "ice", "glacier", "antarctic", "ocean", "earth observatory",
)

CHINA_CLIMATE_TERMS = (
    "china", "chinese", "beijing", "climate", "carbon", "emission", "renewable",
    "zero-carbon", "low-carbon", "green transition", "energy transition",
    "中国", "气候", "碳", "排放", "可再生能源", "零碳", "低碳", "绿色转型",
    "能源转型", "节能降碳", "极端天气", "防洪", "红树林",
)

CHINA_DISCOVERY_DOMAINS = (
    "news.cn", "gov.cn", "mee.gov.cn", "cma.gov.cn", "dialogue.earth",
)

TOPIC_RULES = {
    "国际气候谈判": ("unfccc", "cop30", "cop31", "climate talks", "climate summit", "negotiat"),
    "国家气候承诺": ("ndc", "nationally determined", "climate target", "2035 target"),
    "气候资金": ("climate finance", "green climate fund", "loss and damage", "adaptation fund", "finance goal"),
    "能源与排放": (
        "emission", "renewable", "fossil fuel", "coal", "methane", "energy transition",
        "clean energy", "clean power", "solar", "wind power", "battery", "energy storage", "power grid",
    ),
    "气候适应": (
        "adaptation", "loss and damage", "resilience", "climate disaster",
        "extreme weather", "heat wave", "heatwave", "extreme heat", "wildfire", "wildfires",
        "drought", "flood", "flooding", "storm", "hurricane",
    ),
    "国际碳市场": ("article 6", "carbon market", "carbon credit", "emissions trading"),
    "履约与全球盘点": ("global stocktake", "transparency", "biennial transparency", "btr"),
}

CLIMATE_SIGNAL_TERMS = (
    "climate", "unfccc", "cop30", "cop31", "ndc", "emission", "carbon",
    "net zero", "renewable", "fossil fuel", "methane", "energy transition",
    "climate finance", "loss and damage", "adaptation", "resilience",
    "heat wave", "heatwave", "extreme heat", "wildfire", "wildfires", "drought",
    "flood", "flooding", "storm", "hurricane",
    "green cooperation", "green transition", "clean energy", "global warming",
    "battery", "energy storage", "power grid", "geothermal", "hydrogen", "solar",
    "wind power", "clean power",
    "energy startup", "energy company", "clean technology", "fusion energy",
    "气候", "碳", "排放", "可再生能源", "净零", "低碳", "绿色转型",
    "高温", "热浪", "野火", "干旱", "洪水", "风暴", "飓风",
)

NUMBER_PATTERN = re.compile(
    r"(?<!\w)(?:US\$|\$|€|£)?\d+(?:[,.]\d+)*(?:\s?(?:%|bn|billion|million|trillion|GW|MW|Gt|Mt|°C|C))?",
    re.IGNORECASE,
)


def _analyse(article: NormalizedArticle, authority: int) -> dict:
    haystack = f"{article.title} {article.summary_from_source or ''}".lower()
    topics = [name for name, terms in TOPIC_RULES.items() if any(term in haystack for term in terms)]
    numbers = list(dict.fromkeys(NUMBER_PATTERN.findall(haystack)))[:6]
    has_climate_signal = any(term in haystack for term in CLIMATE_SIGNAL_TERMS)
    score = min(100, authority * 8 + len(topics) * 12 + min(len(numbers), 3) * 4)
    if has_climate_signal:
        score = min(100, score + 18)
    elif not topics:
        score = min(score, 38)
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


def _source_scope_match(article: NormalizedArticle, source_id: str) -> bool:
    """Apply narrow source-specific gates where a feed/API is broader than climate."""
    title = article.title.lower()
    if source_id == "OFF014":
        path = urlparse(article.canonical_url).path.lower()
        return path.startswith("/earth/") and any(term in title for term in NASA_EARTH_TERMS)
    if source_id == "API005":
        host = (urlparse(article.canonical_url).hostname or "").lower()
        allowed_domain = any(host == domain or host.endswith(f".{domain}") for domain in CHINA_DISCOVERY_DOMAINS)
        return allowed_domain and any(term in title for term in CHINA_CLIMATE_TERMS)
    if source_id == "API004":
        if any(term in title for term in GOOGLE_NEWS_EXCLUDE_TERMS):
            return False
        return any(term in title for term in CLIMATE_SIGNAL_TERMS)
    return True


def _article_rows(articles: list[NormalizedArticle], source: dict) -> tuple[list[dict], dict]:
    now = datetime.now(UTC)
    rows = []
    rejected = {"future_date": 0, "duplicate_url": 0, "out_of_scope": 0}
    seen: set[str] = set()
    for article in articles[:150]:
        if not _source_scope_match(article, article.source_id):
            rejected["out_of_scope"] += 1
            continue
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
                "publisher_name": article.publisher_name,
                "fact_status": "source_claim_unverified",
            },
        })
    return rows, {
        "accepted": len(rows),
        "missing_dates": sum(not row["published_at_utc"] for row in rows),
        "rejected": {key: value for key, value in rejected.items() if value},
        "metadata_only": True,
    }


def _gdelt_url(endpoint: str, source_id: str) -> str:
    profile = GDELT_PROFILES[source_id]
    params = {
        "query": profile["query"],
        "mode": "ArtList",
        "maxrecords": profile["maxrecords"],
        "format": "json",
        "sort": "DateDesc",
        "timespan": profile["timespan"],
    }
    return f"{endpoint}?{urlencode(params)}"


def _google_news_url(endpoint: str, query: str | None = None) -> str:
    query = query or GOOGLE_NEWS_QUERIES[0]
    params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    return endpoint.format(
        query=urlencode({"q": query})[2:],
        hl=params["hl"],
        gl=params["gl"],
        ceid=params["ceid"],
    )


def _google_news_urls(endpoint: str) -> list[str]:
    return [_google_news_url(endpoint, query) for query in GOOGLE_NEWS_QUERIES]


def sync_p0(db: Database, source_ids: tuple[str, ...] = P0_SOURCE_IDS) -> dict:
    results = []
    last_gdelt_request = 0.0
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
            if not endpoint or ("{" in endpoint and source_id not in GOOGLE_NEWS_SOURCE_IDS):
                raise ValueError("source has no directly callable endpoint")
            if source_id in GDELT_SOURCE_IDS:
                wait_seconds = max(0.0, 6.0 - (time.monotonic() - last_gdelt_request))
                if wait_seconds:
                    time.sleep(wait_seconds)
                request_url = _gdelt_url(endpoint, source_id)
                last_gdelt_request = time.monotonic()
            elif source_id in GOOGLE_NEWS_SOURCE_IDS:
                request_url = _google_news_url(endpoint)
            else:
                request_url = endpoint
            request_urls = _google_news_urls(endpoint) if source_id in GOOGLE_NEWS_SOURCE_IDS else [request_url]
            responses = []
            request_errors = []
            for url in request_urls:
                try:
                    responses.append(fetch_resource(
                        url,
                        max_bytes=3_000_000,
                        accept="application/json" if source_id in GDELT_SOURCE_IDS else "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9",
                    ))
                except Exception as exc:
                    request_errors.append(f"{type(exc).__name__}: {str(exc)[:120]}")
            if not responses:
                raise RuntimeError("all discovery requests failed: " + "; ".join(request_errors))
            languages = json.loads(source["languages_json"])
            if source_id in GDELT_SOURCE_IDS:
                articles = parse_gdelt(responses[0].payload, source_id)
            else:
                articles = []
                for response in responses:
                    articles.extend(parse_feed(response.payload, source_id, languages[0] if languages else None))
            rows, quality = _article_rows(articles, source)
            counts = db.upsert_articles(rows)
            run.update({
                "status": "success" if rows else "empty",
                "http_status": max(response.status for response in responses),
                "content_type": responses[0].content_type,
                "response_bytes": sum(response.size for response in responses),
                "items_seen": counts["seen"],
                "items_new": counts["new"],
                "items_updated": counts["updated"],
                "quality": {
                    **quality,
                    "requests_succeeded": len(responses),
                    "requests_total": len(request_urls),
                    "request_errors": request_errors,
                },
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

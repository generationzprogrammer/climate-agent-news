from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse

from .collector import NormalizedArticle, fetch_resource, parse_gdelt
from .collector import parse_feed
from .db import Database
from .sync import _analyse, _source_scope_match
from .translation import detect_places
from .taxonomy import country_codes_for, event_tags_for, organization_tags_for


HISTORICAL_SOURCE_ID = "HIST_GDELT"
HISTORICAL_SOURCE_NAME = "GDELT historical climate backfill"
DEFAULT_QUERY = (
    '("climate change" OR "global warming" OR UNFCCC OR "climate finance" OR '
    'NDC OR "net zero" OR "carbon emissions" OR "renewable energy" OR '
    '"fossil fuel" OR methane OR wildfire OR "heat wave" OR drought OR flood)'
)
DEFAULT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
GOOGLE_NEWS_ENDPOINT = "https://news.google.com/rss/search"
GOOGLE_TOPIC_QUERIES = (
    '"climate change"',
    '"climate finance"',
    '"renewable energy"',
    '"carbon emissions"',
    '"wildfire" climate',
    '"drought" climate',
    '"flood" climate',
    'UNFCCC climate',
    'NDC climate',
    '"methane emissions"',
    '"loss and damage" climate',
    '"global warming"',
    '"extreme weather"',
    '"clean energy"',
    '"fossil fuels" climate',
    '"carbon market"',
    '"climate policy"',
    '"climate summit"',
    '"climate adaptation"',
    '"heatwave" climate',
)
COUNTRY_TERM_TAGS = {
    "United States": ("united states", "u.s.", " us ", "america", "american", "biden", "trump", "california", "texas", "florida", "washington"),
    "China": ("china", "chinese", "beijing", "xi jinping"),
    "India": ("india", "indian", "new delhi"),
    "Brazil": ("brazil", "brazilian", "amazon"),
    "Canada": ("canada", "canadian"),
    "Australia": ("australia", "australian"),
    "United Kingdom": ("united kingdom", " uk ", "britain", "british", "england", "scotland"),
    "European Union": ("european union", " eu "),
    "Europe": ("europe", "european"),
    "France": ("france", "french", "paris"),
    "Germany": ("germany", "german", "berlin"),
    "Spain": ("spain", "spanish"),
    "Italy": ("italy", "italian"),
    "Norway": ("norway", "norwegian"),
    "Sweden": ("sweden", "swedish"),
    "Russia": ("russia", "russian", "moscow"),
    "Ukraine": ("ukraine", "ukrainian"),
    "Japan": ("japan", "japanese", "tokyo"),
    "South Korea": ("south korea", "korean", "seoul"),
    "Indonesia": ("indonesia", "indonesian"),
    "South Africa": ("south africa",),
    "Kenya": ("kenya", "kenyan"),
    "Nigeria": ("nigeria", "nigerian"),
    "Egypt": ("egypt", "egyptian"),
    "Morocco": ("morocco", "moroccan"),
    "Saudi Arabia": ("saudi", "saudi arabia"),
    "United Arab Emirates": ("uae", "united arab emirates", "dubai"),
    "Turkey": ("turkey", "turkish"),
    "Mexico": ("mexico", "mexican"),
    "Chile": ("chile", "chilean"),
    "Argentina": ("argentina", "argentinian"),
    "Colombia": ("colombia", "colombian"),
    "Peru": ("peru", "peruvian"),
    "Pakistan": ("pakistan", "pakistani"),
    "Bangladesh": ("bangladesh", "bangladeshi"),
    "Philippines": ("philippines", "philippine"),
    "Vietnam": ("vietnam", "vietnamese"),
    "Thailand": ("thailand", "thai"),
    "Malaysia": ("malaysia", "malaysian"),
    "New Zealand": ("new zealand",),
    "Pacific Islands": ("pacific islands", "small island", "sids"),
    "Caribbean": ("caribbean", "jamaica", "haiti", "bahamas", "dominican republic"),
    "Antarctica": ("antarctica", "antarctic"),
    "Africa": ("africa", "african"),
    "Latin America": ("latin america",),
}

COUNTRY_CONTINENT = {
    "United States": "North America", "Canada": "North America", "Mexico": "North America", "Caribbean": "North America",
    "Brazil": "South America", "Chile": "South America", "Argentina": "South America", "Colombia": "South America", "Peru": "South America", "Latin America": "South America",
    "United Kingdom": "Europe", "European Union": "Europe", "Europe": "Europe", "France": "Europe", "Germany": "Europe", "Spain": "Europe", "Italy": "Europe", "Norway": "Europe", "Sweden": "Europe", "Russia": "Europe", "Ukraine": "Europe",
    "China": "Asia", "India": "Asia", "Japan": "Asia", "South Korea": "Asia", "Indonesia": "Asia", "Saudi Arabia": "Asia", "United Arab Emirates": "Asia", "Turkey": "Asia", "Pakistan": "Asia", "Bangladesh": "Asia", "Philippines": "Asia", "Vietnam": "Asia", "Thailand": "Asia", "Malaysia": "Asia",
    "South Africa": "Africa", "Kenya": "Africa", "Nigeria": "Africa", "Egypt": "Africa", "Morocco": "Africa", "Africa": "Africa",
    "Australia": "Oceania", "New Zealand": "Oceania", "Pacific Islands": "Oceania",
    "Antarctica": "Antarctica",
}
COUNTRY_LABEL_ZH = {
    "United States": "美国",
    "China": "中国",
    "India": "印度",
    "Brazil": "巴西",
    "Canada": "加拿大",
    "Australia": "澳大利亚",
    "United Kingdom": "英国",
    "European Union": "欧盟",
    "Europe": "欧洲",
    "France": "法国",
    "Germany": "德国",
    "Spain": "西班牙",
    "Italy": "意大利",
    "Norway": "挪威",
    "Sweden": "瑞典",
    "Russia": "俄罗斯",
    "Ukraine": "乌克兰",
    "Japan": "日本",
    "South Korea": "韩国",
    "Indonesia": "印度尼西亚",
    "South Africa": "南非",
    "Kenya": "肯尼亚",
    "Nigeria": "尼日利亚",
    "Egypt": "埃及",
    "Morocco": "摩洛哥",
    "Saudi Arabia": "沙特阿拉伯",
    "United Arab Emirates": "阿联酋",
    "Turkey": "土耳其",
    "Mexico": "墨西哥",
    "Chile": "智利",
    "Argentina": "阿根廷",
    "Colombia": "哥伦比亚",
    "Peru": "秘鲁",
    "Pakistan": "巴基斯坦",
    "Bangladesh": "孟加拉国",
    "Philippines": "菲律宾",
    "Vietnam": "越南",
    "Thailand": "泰国",
    "Malaysia": "马来西亚",
    "New Zealand": "新西兰",
    "Pacific Islands": "太平洋岛国",
    "Caribbean": "加勒比地区",
    "Antarctica": "南极洲",
    "Africa": "非洲",
    "Latin America": "拉丁美洲",
}
COUNTRY_CONTINENT.update({
    COUNTRY_LABEL_ZH[country]: continent
    for country, continent in list(COUNTRY_CONTINENT.items())
    if country in COUNTRY_LABEL_ZH
})
DEFAULT_TARGET_PER_DAY = 8
DEFAULT_ARCHIVE_LIMIT = 100000


def ensure_historical_schema(db: Database) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS historical_articles (
            record_id TEXT PRIMARY KEY,
            canonical_url TEXT NOT NULL UNIQUE,
            source_id TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_domain TEXT,
            title_original TEXT NOT NULL,
            summary_source TEXT,
            language TEXT,
            published_at_utc TEXT NOT NULL,
            published_date TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            quarter TEXT NOT NULL,
            relevance_score INTEGER NOT NULL,
            topics_json TEXT NOT NULL,
            numbers_json TEXT NOT NULL,
            places_json TEXT NOT NULL,
            country_tags_json TEXT NOT NULL,
            continent_tags_json TEXT NOT NULL,
            quality_flags_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_historical_date ON historical_articles(published_date)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_historical_domain ON historical_articles(source_domain)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_historical_score ON historical_articles(relevance_score DESC)")


def _month_windows(start: date, end: date) -> list[tuple[date, date]]:
    windows = []
    current = date(start.year, start.month, 1)
    while current <= end:
        next_month = date(current.year + (current.month // 12), (current.month % 12) + 1, 1)
        left = max(start, current)
        right = min(end, next_month - timedelta(days=1))
        if left <= right:
            windows.append((left, right))
        current = next_month
    return windows


def _gdelt_backfill_url(endpoint: str, start: date, end: date, *, query: str, maxrecords: int) -> str:
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "sort": "HybridRel",
        "maxrecords": str(maxrecords),
        "startdatetime": f"{start:%Y%m%d}000000",
        "enddatetime": f"{end:%Y%m%d}235959",
    }
    return f"{endpoint}?{urlencode(params)}"


def _google_backfill_url(start: date, end: date, *, query: str) -> str:
    google_query = f"{query} after:{start.isoformat()} before:{(end + timedelta(days=1)).isoformat()}"
    params = {
        "q": google_query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }
    return f"{GOOGLE_NEWS_ENDPOINT}?{urlencode(params)}"


def _week_windows(start: date, end: date) -> list[tuple[date, date]]:
    windows = []
    current = start
    while current <= end:
        right = min(end, current + timedelta(days=6))
        windows.append((current, right))
        current = right + timedelta(days=1)
    return windows


def _continent_from_places(places: list[dict]) -> list[str]:
    tags = []
    for place in places:
        name = str(place.get("name_zh") or "")
        lon = float(place.get("lon") or 0)
        lat = float(place.get("lat") or 0)
        if lat <= -60 or "南极" in name:
            tags.append("Antarctica")
        elif -170 <= lon <= -30 and lat >= 12:
            tags.append("North America")
        elif -90 <= lon <= -30 and lat < 12:
            tags.append("South America")
        elif -25 <= lon <= 60 and lat > 37:
            tags.append("Europe")
        elif -25 <= lon <= 60 and -38 <= lat <= 37:
            tags.append("Africa")
        elif 110 <= lon <= 180 and lat < -8:
            tags.append("Oceania")
        elif 25 <= lon <= 180:
            tags.append("Asia")
    return list(dict.fromkeys(tags or ["Global/Unspecified"]))


def _google_source_label(title: str) -> str | None:
    if " - " not in title:
        return None
    label = title.rsplit(" - ", 1)[-1].strip()
    return label[:80] or None


def _country_tags_from_text(text: str) -> list[str]:
    haystack = f" {text.lower()} "
    tags = []
    for country, terms in COUNTRY_TERM_TAGS.items():
        for term in terms:
            pattern = rf"(?<![a-z0-9]){re.escape(term.lower().strip())}(?![a-z0-9-])"
            if re.search(pattern, haystack):
                tags.append(COUNTRY_LABEL_ZH.get(country, country))
                break
    standard = [tag["name_zh"] for tag in country_codes_for(text)]
    return list(dict.fromkeys(standard + tags))


def _continent_tags_from_countries(country_tags: list[str]) -> list[str]:
    tags = [COUNTRY_CONTINENT[country] for country in country_tags if country in COUNTRY_CONTINENT]
    return list(dict.fromkeys(tags or ["Global/Unspecified"]))


def article_to_historical_record(article: NormalizedArticle, *, fetched_at: str, start: date | None = None, end: date | None = None) -> dict | None:
    if not article.published_at_utc:
        return None
    scope_source = "API004" if article.source_id == "API004" else "API001"
    if not _source_scope_match(article, scope_source):
        return None
    analysis = _analyse(article, authority=4)
    if analysis["score"] < 45:
        return None
    published = datetime.fromisoformat(article.published_at_utc.replace("Z", "+00:00")).astimezone(UTC)
    if start and published.date() < start:
        return None
    if end and published.date() > end:
        return None
    text = f"{article.title} {article.summary_from_source or ''}"
    places = detect_places(text)
    domain = (urlparse(article.canonical_url).hostname or "").lower()
    if article.source_id == "API004":
        source_label = _google_source_label(article.title)
        if source_label:
            domain = f"google:{source_label.lower()}"
    country_tags = list(dict.fromkeys([place.get("name_zh") for place in places if place.get("name_zh")] + _country_tags_from_text(text))) or ["未标注"]
    country_codes = country_codes_for(text, places=places, country_tags=country_tags)
    source_name = HISTORICAL_SOURCE_NAME
    if article.source_id == "API004":
        source_name = _google_source_label(article.title) or "Google News RSS historical fallback"
    return {
        "record_id": article.article_id,
        "canonical_url": article.canonical_url,
        "source_id": article.source_id if article.source_id == "API004" else HISTORICAL_SOURCE_ID,
        "source_name": source_name,
        "source_domain": domain,
        "title_original": article.title,
        "summary_source": article.summary_from_source,
        "language": article.language,
        "published_at_utc": published.isoformat(),
        "published_date": published.date().isoformat(),
        "year": published.year,
        "month": published.month,
        "quarter": f"{published.year}Q{((published.month - 1) // 3) + 1}",
        "relevance_score": analysis["score"],
        "topics": analysis["topics"],
        "numbers": analysis["numbers"],
        "places": places,
        "country_tags": country_tags,
        "country_codes": country_codes,
        "organization_tags": organization_tags_for(text),
        "event_tags": event_tags_for(text),
        "continent_tags": _continent_from_places(places) if places else _continent_tags_from_countries(country_tags),
        "quality_flags": {
            "metadata_only": True,
            "has_country_tag": country_tags != ["未标注"],
            "has_number": bool(analysis["numbers"]),
            "source_claim_unverified": True,
        },
        "metadata": {
            "rights_status": article.rights_status,
            "extraction_method": article.extraction_method,
            "parser_version": article.parser_version,
            "backfill_method": "gdelt_monthly_8_per_day",
            "fallback_source": "google_news_rss" if article.source_id == "API004" else None,
        },
        "fetched_at": fetched_at,
    }


def archive_item_to_historical_record(item: dict, *, fetched_at: str) -> dict | None:
    if not item.get("canonical_url") or not item.get("published_at") or not item.get("title_original"):
        return None
    try:
        published = datetime.fromisoformat(str(item["published_at"]).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None
    places = list(item.get("places") or [])
    domain = (urlparse(item["canonical_url"]).hostname or "").lower()
    text = f"{item.get('title_original') or ''} {item.get('summary_source') or ''} {item.get('summary_zh') or ''}"
    country_tags = list(dict.fromkeys([place.get("name_zh") for place in places if place.get("name_zh")] + _country_tags_from_text(text))) or ["未标注"]
    country_codes = country_codes_for(text, places=places, country_tags=country_tags)
    return {
        "record_id": item.get("article_id") or item.get("record_id"),
        "canonical_url": item["canonical_url"],
        "source_id": item.get("source_id") or "ARCHIVE",
        "source_name": item.get("source_name") or "Existing quality archive",
        "source_domain": domain,
        "title_original": item["title_original"],
        "summary_source": item.get("summary_source"),
        "language": item.get("language"),
        "published_at_utc": published.isoformat(),
        "published_date": published.date().isoformat(),
        "year": published.year,
        "month": published.month,
        "quarter": f"{published.year}Q{((published.month - 1) // 3) + 1}",
        "relevance_score": int(item.get("relevance_score") or item.get("quality", {}).get("score") or 45),
        "topics": list(item.get("topics") or []),
        "numbers": list(item.get("numbers") or []),
        "places": places,
        "country_tags": country_tags,
        "country_codes": country_codes,
        "organization_tags": organization_tags_for(text),
        "event_tags": event_tags_for(text),
        "continent_tags": _continent_from_places(places) if places else _continent_tags_from_countries(country_tags),
        "quality_flags": {
            "metadata_only": True,
            "has_country_tag": country_tags != ["未标注"],
            "has_number": bool(item.get("numbers")),
            "source_claim_unverified": item.get("fact_status") != "official_source_claim",
            "seeded_from_quality_archive": True,
        },
        "metadata": {
            "rights_status": "metadata_only",
            "translation_status": item.get("translation_status"),
            "backfill_method": "existing_quality_archive_seed",
            "title_zh": item.get("title_zh"),
            "summary_zh": item.get("summary_zh"),
        },
        "fetched_at": fetched_at,
    }


def seed_historical_from_archive(db: Database, archive_path: Path, *, fetched_at: str, limit: int) -> dict:
    if not archive_path.exists():
        return {"seen": 0, "new": 0, "updated": 0, "path": str(archive_path), "status": "missing"}
    try:
        archive = json.loads(archive_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"seen": 0, "new": 0, "updated": 0, "path": str(archive_path), "status": "invalid"}
    records = [
        record for record in (
            archive_item_to_historical_record(item, fetched_at=fetched_at)
            for item in archive.get("records", [])
        )
        if record
    ][:limit]
    counts = upsert_historical_records(db, records)
    return {"status": "ok", "path": str(archive_path), **counts}


def upsert_historical_records(db: Database, records: list[dict]) -> dict[str, int]:
    ensure_historical_schema(db)
    if not records:
        return {"seen": 0, "new": 0, "updated": 0}
    urls = [record["canonical_url"] for record in records]
    existing = set()
    with db.connect() as conn:
        for start in range(0, len(urls), 500):
            batch = urls[start:start + 500]
            placeholders = ",".join("?" for _ in batch)
            for row in conn.execute(
                f"SELECT canonical_url FROM historical_articles WHERE canonical_url IN ({placeholders})",
                tuple(batch),
            ):
                existing.add(row["canonical_url"])
        sql = """
            INSERT INTO historical_articles (
                record_id,canonical_url,source_id,source_name,source_domain,title_original,
                summary_source,language,published_at_utc,published_date,year,month,quarter,
                relevance_score,topics_json,numbers_json,places_json,country_tags_json,
                continent_tags_json,quality_flags_json,metadata_json,fetched_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(canonical_url) DO UPDATE SET
                source_domain=excluded.source_domain,
                title_original=excluded.title_original,
                summary_source=excluded.summary_source,
                language=excluded.language,
                published_at_utc=excluded.published_at_utc,
                published_date=excluded.published_date,
                year=excluded.year,
                month=excluded.month,
                quarter=excluded.quarter,
                relevance_score=excluded.relevance_score,
                topics_json=excluded.topics_json,
                numbers_json=excluded.numbers_json,
                places_json=excluded.places_json,
                country_tags_json=excluded.country_tags_json,
                continent_tags_json=excluded.continent_tags_json,
                quality_flags_json=excluded.quality_flags_json,
                metadata_json=excluded.metadata_json,
                fetched_at=excluded.fetched_at
        """
        conn.executemany(sql, [(
            r["record_id"], r["canonical_url"], r["source_id"], r["source_name"], r["source_domain"],
            r["title_original"], r.get("summary_source"), r.get("language"), r["published_at_utc"],
            r["published_date"], r["year"], r["month"], r["quarter"], r["relevance_score"],
            json.dumps(r["topics"], ensure_ascii=False), json.dumps(r["numbers"], ensure_ascii=False),
            json.dumps(r["places"], ensure_ascii=False), json.dumps(r["country_tags"], ensure_ascii=False),
            json.dumps(r["continent_tags"], ensure_ascii=False), json.dumps(r["quality_flags"], ensure_ascii=False),
            json.dumps(r["metadata"], ensure_ascii=False), r["fetched_at"],
        ) for r in records])
    return {
        "seen": len(records),
        "new": sum(record["canonical_url"] not in existing for record in records),
        "updated": sum(record["canonical_url"] in existing for record in records),
    }


def clear_historical_records(db: Database) -> None:
    ensure_historical_schema(db)
    db.execute("DELETE FROM historical_articles")


def refresh_historical_tags(db: Database) -> dict[str, int]:
    """Rebuild country/continent tags for already-ingested historical records."""
    ensure_historical_schema(db)
    rows = db.rows("""
        SELECT record_id,title_original,summary_source,places_json,quality_flags_json
        FROM historical_articles
    """)
    updates = []
    tagged = 0
    for row in rows:
        try:
            places = json.loads(row["places_json"] or "[]")
        except json.JSONDecodeError:
            places = []
        text = f"{row['title_original'] or ''} {row['summary_source'] or ''}"
        place_countries = [place.get("name_zh") for place in places if place.get("name_zh")]
        country_tags = list(dict.fromkeys(place_countries + _country_tags_from_text(text))) or ["未标注"]
        continent_tags = _continent_from_places(places) if places else _continent_tags_from_countries(country_tags)
        try:
            quality_flags = json.loads(row["quality_flags_json"] or "{}")
        except json.JSONDecodeError:
            quality_flags = {}
        quality_flags["has_country_tag"] = country_tags != ["未标注"]
        if quality_flags["has_country_tag"]:
            tagged += 1
        updates.append((
            json.dumps(country_tags, ensure_ascii=False),
            json.dumps(continent_tags, ensure_ascii=False),
            json.dumps(quality_flags, ensure_ascii=False),
            row["record_id"],
        ))
    with db.connect() as conn:
        conn.executemany(
            """
            UPDATE historical_articles
            SET country_tags_json=?, continent_tags_json=?, quality_flags_json=?
            WHERE record_id=?
            """,
            updates,
        )
    return {"records": len(rows), "tagged": tagged, "untagged": len(rows) - tagged}


def export_historical_jsonl(
    db: Database,
    output: Path,
    *,
    limit: int = DEFAULT_ARCHIVE_LIMIT,
    target_per_day: int = DEFAULT_TARGET_PER_DAY,
    prune_sqlite: bool = True,
) -> dict:
    ensure_historical_schema(db)
    rows = db.rows("""
        SELECT * FROM historical_articles
        ORDER BY published_date, relevance_score DESC, published_at_utc DESC
    """)
    selected: list[dict] = []
    selected_ids: set[str] = set()
    per_day: dict[str, int] = defaultdict(int)
    for row in rows:
        day = row["published_date"]
        if per_day[day] >= target_per_day:
            continue
        selected.append(row)
        selected_ids.add(row["record_id"])
        per_day[day] += 1
    if len(selected) < limit:
        surplus = sorted(
            [row for row in rows if row["record_id"] not in selected_ids],
            key=lambda row: (row.get("relevance_score") or 0, row.get("published_at_utc") or ""),
            reverse=True,
        )
        for row in surplus:
            selected.append(row)
            selected_ids.add(row["record_id"])
            if len(selected) >= limit:
                break
    selected = sorted(
        selected,
        key=lambda row: (row.get("published_at_utc") or "", row.get("relevance_score") or 0),
        reverse=True,
    )[:limit]
    if prune_sqlite:
        keep = {row["record_id"] for row in selected}
        remove_ids = [
            row["record_id"] for row in db.rows("SELECT record_id FROM historical_articles")
            if row["record_id"] not in keep
        ]
        with db.connect() as conn:
            for start in range(0, len(remove_ids), 500):
                batch = remove_ids[start:start + 500]
                placeholders = ",".join("?" for _ in batch)
                conn.execute(f"DELETE FROM historical_articles WHERE record_id IN ({placeholders})", tuple(batch))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in selected:
            item = dict(row)
            for key in ("topics", "numbers", "places", "country_tags", "continent_tags", "quality_flags", "metadata"):
                item[key] = json.loads(item.pop(f"{key}_json"))
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    return {"output": str(output), "records": len(selected), "days": len(per_day), "target_per_day": target_per_day}


def backfill_history(
    db: Database,
    *,
    start: date,
    end: date,
    endpoint: str = DEFAULT_ENDPOINT,
    query: str = DEFAULT_QUERY,
    target_per_day: int = DEFAULT_TARGET_PER_DAY,
    maxrecords_per_month: int = 250,
    limit: int = DEFAULT_ARCHIVE_LIMIT,
    max_months: int | None = None,
    sleep_seconds: float = 1.0,
    output_jsonl: Path | None = None,
    seed_archive_path: Path | None = None,
    google_fallback: bool = True,
    provider: str = "auto",
    reset: bool = False,
) -> dict:
    ensure_historical_schema(db)
    if reset:
        clear_historical_records(db)
    fetched_at = datetime.now(UTC).isoformat()
    totals = {"seen": 0, "accepted": 0, "new": 0, "updated": 0, "failed_windows": 0}
    archive_seed = seed_historical_from_archive(db, seed_archive_path, fetched_at=fetched_at, limit=limit) if seed_archive_path else None
    windows = _month_windows(start, end)
    if max_months:
        windows = windows[-max_months:]
    per_day: dict[str, list[dict]] = defaultdict(list)
    errors = []
    provider_counts = defaultdict(int)
    for left, right in windows:
        articles: list[NormalizedArticle] = []
        if provider != "google":
            try:
                url = _gdelt_backfill_url(endpoint, left, right, query=query, maxrecords=maxrecords_per_month)
                payload = fetch_resource(url, accept="application/json", retries=1).payload
                articles = parse_gdelt(payload, "API001")
                provider_counts["gdelt"] += 1
            except Exception as exc:
                errors.append({"window": f"{left}/{right}", "provider": "gdelt", "error": str(exc)[:200]})
                if provider == "gdelt" or not google_fallback:
                    totals["failed_windows"] += 1
                    continue
        if provider == "google" or (provider == "auto" and not articles):
            google_failed = 0
            google_windows = [(left, right)] if (right - left).days <= 31 else _week_windows(left, right)
            for week_left, week_right in google_windows:
                queries = GOOGLE_TOPIC_QUERIES if (week_left, week_right) == (left, right) else (query,)
                for google_query in queries:
                    try:
                        url = _google_backfill_url(week_left, week_right, query=google_query)
                        payload = fetch_resource(url, accept="application/rss+xml, application/xml, text/xml", retries=1).payload
                        articles.extend(parse_feed(payload, "API004", "en"))
                        provider_counts["google_news_rss"] += 1
                        if sleep_seconds:
                            time.sleep(sleep_seconds)
                    except Exception as google_exc:
                        google_failed += 1
                        errors.append({"window": f"{week_left}/{week_right}", "provider": "google_news_rss", "query": google_query, "error": str(google_exc)[:200]})
            if google_failed:
                totals["failed_windows"] += google_failed
            if not articles:
                continue
        totals["seen"] += len(articles)
        for article in articles:
            record = article_to_historical_record(article, fetched_at=fetched_at, start=left, end=right)
            if not record:
                continue
            day_records = per_day[record["published_date"]]
            day_records.append(record)
            day_records.sort(key=lambda item: item["relevance_score"], reverse=True)
            del day_records[target_per_day:]
        if sleep_seconds:
            time.sleep(sleep_seconds)
    records = sorted(
        (record for day in per_day.values() for record in day),
        key=lambda item: (item["published_at_utc"], item["relevance_score"]),
        reverse=True,
    )[:limit]
    counts = upsert_historical_records(db, records)
    totals.update({"accepted": len(records), "new": counts["new"], "updated": counts["updated"]})
    export = export_historical_jsonl(
        db,
        output_jsonl or db.path.parent / "climate_text_corpus.jsonl",
        limit=limit,
        target_per_day=target_per_day,
    )
    manifest = {
        "dataset": "Global Climate Change Key Intelligence Text Database",
        "grain": "one canonical URL per news record",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "target_per_day": target_per_day,
        "limit": limit,
        "generated_at": datetime.now(UTC).isoformat(),
        "totals": totals,
        "archive_seed": archive_seed,
        "jsonl": export,
        "provider_windows": dict(provider_counts),
        "errors": errors[:20],
        "tags": ["published_date", "year", "month", "quarter", "topics", "country_tags", "country_codes", "continent_tags", "organization_tags", "event_tags", "source_domain", "numbers"],
    }
    manifest_path = (output_jsonl or db.path.parent / "climate_text_corpus.jsonl").with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest

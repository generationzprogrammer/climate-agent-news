from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlparse

from .summary_utils import intelligence_keywords, is_generic_summary, is_generic_title


ARCHIVE_VERSION = "1.0"
DEFAULT_ARCHIVE_LIMIT = 100000
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
LOW_VALUE_NEWS_TERMS = (
    "buck moon", "sesame workshop", "sesame street", "nickalive",
    "movie", "celebrity", "sports", "football", "basketball", "baseball",
    "analyst coverage count",
)
MOJIBAKE_MARKERS = ("锟", "�", "Ã", "Â", "娴嬭瘯", "待翻译")
CARIBBEAN_PLACE = {"name_zh": "加勒比地区", "lon": -75.0, "lat": 18.0}
NEW_MEXICO_PLACE = {"name_zh": "美国新墨西哥州", "lon": -106.0, "lat": 34.5}


def _text_is_publishable(value: str | None, *, minimum_chinese: int = 2) -> bool:
    if not value or any(marker in value for marker in MOJIBAKE_MARKERS):
        return False
    return len(CHINESE_RE.findall(value)) >= minimum_chinese


def _https_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return parsed._replace(scheme="https").geturl()


def _story_title_key(item: dict) -> str:
    """Return a conservative title fingerprint for syndicated-copy detection."""
    title = str(item.get("title_original") or "").strip()
    if not title:
        title = str(item.get("title_zh") or "").strip()
        if is_generic_title(title):
            return ""
    normalised = unicodedata.normalize("NFKC", title).lower()
    normalised = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", normalised)
    return normalised if len(normalised) >= 24 else ""


def _url_key(value: str | None) -> str:
    return (_https_url(value) or "").rstrip("/")


def _published_datetime(item: dict) -> datetime | None:
    value = str(item.get("published_at") or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _same_story(left: dict, right: dict) -> bool:
    left_url = _url_key(left.get("canonical_url"))
    right_url = _url_key(right.get("canonical_url"))
    if left_url and right_url and left_url == right_url:
        return True
    left_key, right_key = _story_title_key(left), _story_title_key(right)
    if not left_key or left_key != right_key:
        return False
    left_time, right_time = _published_datetime(left), _published_datetime(right)
    return not left_time or not right_time or abs((left_time - right_time).total_seconds()) <= 72 * 3600


def _observation(item: dict) -> dict:
    return {
        "article_id": item.get("article_id") or item.get("record_id"),
        "canonical_url": _https_url(item.get("canonical_url")) or item.get("canonical_url"),
        "source_id": item.get("source_id"),
        "source_name": item.get("source_name"),
        "published_at": item.get("published_at"),
    }


def _merge_duplicate(primary: dict, duplicate: dict) -> dict:
    """Keep one public record while retaining every traceable observation."""
    urls = [primary.get("canonical_url"), *(primary.get("alternate_urls") or []), duplicate.get("canonical_url")]
    primary["alternate_urls"] = list(dict.fromkeys(
        url for url in (_https_url(value) for value in urls) if url and url != primary.get("canonical_url")
    ))[:12]
    observations = [*(primary.get("duplicate_observations") or []), _observation(duplicate)]
    unique: dict[str, dict] = {}
    for item in observations:
        key = str(item.get("canonical_url") or item.get("article_id") or "")
        if key and key != primary.get("canonical_url"):
            unique[key] = item
    primary["duplicate_observations"] = list(unique.values())[:12]
    return primary


def _collapse_archive_records(records: list[dict]) -> tuple[list[dict], int]:
    survivors: list[dict] = []
    by_url: dict[str, dict] = {}
    by_title: dict[str, list[dict]] = {}
    collapsed = 0
    for record in sorted(
        records,
        key=lambda row: (row.get("published_at") or "", row.get("last_archived_at") or ""),
        reverse=True,
    ):
        url_key = _url_key(record.get("canonical_url"))
        title_key = _story_title_key(record)
        duplicate_of = by_url.get(url_key) if url_key else None
        if not duplicate_of and title_key:
            duplicate_of = next((kept for kept in by_title.get(title_key, []) if _same_story(kept, record)), None)
        if duplicate_of:
            _merge_duplicate(duplicate_of, record)
            collapsed += 1
        else:
            survivors.append(record)
            if url_key:
                by_url[url_key] = record
            if title_key:
                by_title.setdefault(title_key, []).append(record)
    return survivors, collapsed


def _record_scope_passes(item: dict) -> bool:
    text = _geo_text(item)
    if any(term in text for term in LOW_VALUE_NEWS_TERMS):
        return False
    if item.get("source_id") == "OFF014":
        return urlparse(item.get("canonical_url") or "").path.lower().startswith("/earth/")
    return True


def _geo_text(item: dict) -> str:
    return " ".join(str(item.get(key) or "") for key in (
        "title_original", "title_zh", "summary_source", "summary_zh", "canonical_url"
    )).lower()


def _repair_places(item: dict) -> list[dict]:
    """Migrate obvious old keyword-geocoding mistakes in public archives."""
    text = _geo_text(item)
    places = list(item.get("places") or [])[:4]
    if "new mexico" in text or "美国新墨西哥" in text:
        return [NEW_MEXICO_PLACE]
    if "caribbean" in text or "加勒比" in text:
        return [CARIBBEAN_PLACE]
    return places


def _repair_geocoding_text(item: dict) -> dict:
    text = _geo_text(item)
    if "new mexico" not in text and "美国新墨西哥" not in text:
        return item
    repaired = dict(item)
    for key in ("summary_zh", "why_zh"):
        value = repaired.get(key)
        if isinstance(value, str):
            repaired[key] = value.replace("涉及墨西哥", "涉及美国新墨西哥州")
    return repaired


def quality_result(item: dict) -> dict:
    """Return a deterministic public-data gate and an explainable score."""
    checks = {
        "canonical_https": bool(_https_url(item.get("canonical_url"))),
        "original_title": bool((item.get("title_original") or "").strip()),
        "chinese_title": _text_is_publishable(item.get("title_zh")) and not is_generic_title(item.get("title_zh")),
        "substantive_content": (
            _text_is_publishable(item.get("summary_zh"), minimum_chinese=18)
            and not is_generic_summary(item.get("summary_zh"))
        ) or len(intelligence_keywords(item)) >= 2,
        "published_time": bool(item.get("published_at")),
        "source_trace": bool(item.get("source_name") and item.get("source_id")),
    }
    authority = max(0, min(5, int(item.get("authority") or 0)))
    relevance = max(0, min(100, int(item.get("relevance_score") or 0)))
    translation_status = item.get("translation_status") or "pending"
    score = round(authority * 9 + relevance * 0.35)
    if translation_status == "human_reviewed":
        score += 15
    elif translation_status == "model_generated_needs_review":
        score += 7
    if item.get("fact_status") == "opinion_or_context":
        score -= 8
    score = max(0, min(100, score))
    passed = all(checks.values()) and authority >= 3 and relevance >= 45
    tier = "A" if passed and translation_status == "human_reviewed" else "B" if passed else "C"
    return {"passed": passed, "score": score, "tier": tier, "checks": checks}


def _record(item: dict, now: str, previous: dict | None = None) -> dict:
    item = _repair_geocoding_text(item)
    quality = quality_result(item)
    url = _https_url(item.get("canonical_url")) or item.get("canonical_url")
    topics = list(dict.fromkeys(item.get("topics") or []))[:6]
    numbers = list(dict.fromkeys(item.get("numbers") or []))[:6]
    places = _repair_places(item)
    return {
        "record_id": item.get("article_id"),
        "article_id": item.get("article_id"),
        "canonical_url": url,
        "source_url": _https_url(item.get("source_url")) or url,
        "source_id": item.get("source_id"),
        "source_name": item.get("source_name"),
        "source_type": item.get("source_type"),
        "authority": int(item.get("authority") or 0),
        "relevance_score": int(item.get("relevance_score") or 0),
        "title_original": item.get("title_original"),
        "title_zh": item.get("title_zh"),
        "summary_source": item.get("summary_source"),
        "summary_zh": item.get("summary_zh"),
        "theme_zh": item.get("theme_zh") or (topics[0] if topics else "气候动态"),
        "why_zh": item.get("why_zh"),
        "language": item.get("language"),
        "published_at": item.get("published_at"),
        "fetched_at": item.get("fetched_at"),
        "topics": topics,
        "numbers": numbers,
        "places": places,
        "translation_status": item.get("translation_status"),
        "fact_status": item.get("fact_status"),
        "content_hash": item.get("content_hash"),
        "poster_phrase": item.get("poster_phrase"),
        "company_entities": list(item.get("company_entities") or [])[:8],
        "alternate_urls": list((previous or {}).get("alternate_urls") or [])[:12],
        "duplicate_observations": list((previous or {}).get("duplicate_observations") or [])[:12],
        "quality": quality,
        "molecule": {
            "identity": item.get("article_id"),
            "source_atom": {
                "name": item.get("source_name"),
                "authority": int(item.get("authority") or 0),
                "type": item.get("source_type"),
            },
            "evidence_atom": {
                "fact_status": item.get("fact_status"),
                "translation_status": item.get("translation_status"),
                "quality_tier": quality["tier"],
            },
            "topic_atoms": topics,
            "number_atoms": numbers,
            "geo_atoms": [place.get("name_zh") for place in places if place.get("name_zh")],
            "decision_atom": item.get("why_zh"),
        },
        "first_archived_at": (previous or {}).get("first_archived_at", now),
        "last_archived_at": now,
    }


def load_archive(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": ARCHIVE_VERSION, "records": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": ARCHIVE_VERSION, "records": []}
    return data if isinstance(data, dict) and isinstance(data.get("records"), list) else {
        "schema_version": ARCHIVE_VERSION,
        "records": [],
    }


def update_archive(path: Path, candidates: list[dict], *, limit: int = DEFAULT_ARCHIVE_LIMIT) -> dict:
    if not 1 <= limit <= DEFAULT_ARCHIVE_LIMIT:
        raise ValueError(f"archive limit must be between 1 and {DEFAULT_ARCHIVE_LIMIT}")
    existing = load_archive(path)
    existing_records, duplicates_collapsed = _collapse_archive_records([
        record for record in existing.get("records", []) if record.get("canonical_url") and _record_scope_passes(record)
    ])
    by_url = {
        _url_key(record.get("canonical_url")): record
        for record in existing_records
    }
    by_title: dict[str, list[dict]] = {}
    for record in by_url.values():
        title_key = _story_title_key(record)
        if title_key:
            by_title.setdefault(title_key, []).append(record)
    for record in by_url.values():
        record.update(_repair_geocoding_text(record))
        # Schema 1.0 archives created before 2026-07-29 did not persist this
        # public ranking field. The stored quality score is the safest
        # deterministic migration value and remains above the public gate.
        record.setdefault("relevance_score", int(record.get("quality", {}).get("score") or 45))
        record["places"] = _repair_places(record)
        record["quality"] = quality_result(record)
        if record.get("molecule"):
            record["molecule"]["geo_atoms"] = [
                place.get("name_zh") for place in record["places"] if place.get("name_zh")
            ]
    before = len(existing.get("records", []))
    added = updated = rejected = 0
    now = datetime.now(UTC).isoformat()
    for item in candidates:
        gate = quality_result(item)
        url = _https_url(item.get("canonical_url"))
        if not gate["passed"] or not url or not _record_scope_passes(item):
            rejected += 1
            continue
        previous = by_url.get(_url_key(url))
        record = _record(item, now, previous)
        if previous:
            changed = previous.get("content_hash") != record.get("content_hash") or previous.get("title_zh") != record.get("title_zh")
            updated += int(changed)
        else:
            title_key = _story_title_key(record)
            duplicate_of = next(
                (kept for kept in by_title.get(title_key, []) if _same_story(kept, record)),
                None,
            ) if title_key else None
            if duplicate_of:
                _merge_duplicate(duplicate_of, record)
                duplicates_collapsed += 1
                updated += 1
                continue
            added += 1
        by_url[_url_key(url)] = record
        title_key = _story_title_key(record)
        if title_key:
            by_title[title_key] = [kept for kept in by_title.get(title_key, []) if kept is not previous]
            if record not in by_title[title_key]:
                by_title[title_key].append(record)
    records = sorted(
        by_url.values(),
        key=lambda row: (row.get("published_at") or "", row.get("last_archived_at") or ""),
        reverse=True,
    )
    pruned = max(0, len(records) - limit)
    records = records[:limit]
    tier_counts = {tier: sum(r.get("quality", {}).get("tier") == tier for r in records) for tier in ("A", "B")}
    payload = {
        "schema_version": ARCHIVE_VERSION,
        "dataset_name": "ClimateText-100000",
        "updated_at": now,
        "limit": limit,
        "total": len(records),
        "statistics": {
            "previous_total": before,
            "added": added,
            "updated": updated,
            "rejected": rejected,
            "pruned": pruned,
            "duplicates_collapsed": duplicates_collapsed,
            "tier_a": tier_counts["A"],
            "tier_b": tier_counts["B"],
        },
        "records": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def validate_public_payload(dashboard: dict, archive: dict) -> list[str]:
    errors: list[str] = []
    intelligence = dashboard.get("intelligence") or []
    if not intelligence:
        errors.append("dashboard_has_no_publishable_intelligence")
    if archive.get("total", 0) > DEFAULT_ARCHIVE_LIMIT:
        errors.append("archive_exceeds_100000")
    if archive.get("total") != len(archive.get("records", [])):
        errors.append("archive_total_mismatch")
    max_stale_days = os.getenv("CLIMATE_MAX_STALE_DAYS")
    if max_stale_days and dashboard.get("meta"):
        try:
            page_day = date.fromisoformat(str(dashboard["meta"].get("date")))
            latest_day = date.fromisoformat(str(dashboard["meta"].get("latest_news_date")))
            if (page_day - latest_day).days > int(max_stale_days):
                errors.append(f"latest_news_stale:{latest_day.isoformat()}")
        except (TypeError, ValueError):
            errors.append("latest_news_date_invalid")
    for item in intelligence:
        if not quality_result(item)["passed"]:
            errors.append(f"dashboard_quality_gate_failed:{item.get('article_id')}")
    for record in archive.get("records", []):
        if not _https_url(record.get("canonical_url")):
            errors.append(f"archive_invalid_url:{record.get('record_id')}")
    return errors

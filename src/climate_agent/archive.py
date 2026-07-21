from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse


ARCHIVE_VERSION = "1.0"
DEFAULT_ARCHIVE_LIMIT = 3000
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
MOJIBAKE_MARKERS = ("锟", "�", "Ã", "Â", "娴嬭瘯", "待翻译")


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


def quality_result(item: dict) -> dict:
    """Return a deterministic public-data gate and an explainable score."""
    checks = {
        "canonical_https": bool(_https_url(item.get("canonical_url"))),
        "original_title": bool((item.get("title_original") or "").strip()),
        "chinese_title": _text_is_publishable(item.get("title_zh")),
        "chinese_summary": _text_is_publishable(item.get("summary_zh"), minimum_chinese=18),
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
    quality = quality_result(item)
    url = _https_url(item.get("canonical_url")) or item.get("canonical_url")
    topics = list(dict.fromkeys(item.get("topics") or []))[:6]
    numbers = list(dict.fromkeys(item.get("numbers") or []))[:6]
    places = (item.get("places") or [])[:4]
    return {
        "record_id": item.get("article_id"),
        "article_id": item.get("article_id"),
        "canonical_url": url,
        "source_url": _https_url(item.get("source_url")) or url,
        "source_id": item.get("source_id"),
        "source_name": item.get("source_name"),
        "source_type": item.get("source_type"),
        "authority": int(item.get("authority") or 0),
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
    by_url = {
        record.get("canonical_url"): record
        for record in existing.get("records", [])
        if record.get("canonical_url")
    }
    before = len(by_url)
    added = updated = rejected = 0
    now = datetime.now(UTC).isoformat()
    for item in candidates:
        gate = quality_result(item)
        url = _https_url(item.get("canonical_url"))
        if not gate["passed"] or not url:
            rejected += 1
            continue
        previous = by_url.get(url)
        record = _record(item, now, previous)
        if previous:
            changed = previous.get("content_hash") != record.get("content_hash") or previous.get("title_zh") != record.get("title_zh")
            updated += int(changed)
        else:
            added += 1
        by_url[url] = record
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
        "dataset_name": "ClimateText-3000",
        "updated_at": now,
        "limit": limit,
        "total": len(records),
        "statistics": {
            "previous_total": before,
            "added": added,
            "updated": updated,
            "rejected": rejected,
            "pruned": pruned,
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
        errors.append("archive_exceeds_3000")
    if archive.get("total") != len(archive.get("records", [])):
        errors.append("archive_total_mismatch")
    for item in intelligence:
        if not quality_result(item)["passed"]:
            errors.append(f"dashboard_quality_gate_failed:{item.get('article_id')}")
    for record in archive.get("records", []):
        if not record.get("quality", {}).get("passed"):
            errors.append(f"archive_quality_gate_failed:{record.get('record_id')}")
        if not _https_url(record.get("canonical_url")):
            errors.append(f"archive_invalid_url:{record.get('record_id')}")
    return errors

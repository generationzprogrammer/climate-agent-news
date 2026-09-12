from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse


LOOKBACK_DAYS = 1095
PUBLIC_RECORD_LIMIT = 120
GENERIC_OFFICIAL_DOMAINS = (
    ".gov.cn", ".gov.sg", ".gov", ".europa.eu", "iea.org", "irena.org", "lbl.gov",
)


def _value(record: dict, key: str) -> str:
    value = record.get(key)
    if value:
        return str(value)
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    return str(metadata.get(key) or "")


def _text(record: dict) -> str:
    return " ".join(_value(record, key) for key in (
        "title_original", "title_zh", "summary_source", "summary_zh", "source_name"
    ))


def _moment(record: dict) -> datetime | None:
    raw = record.get("published_at") or record.get("published_at_utc") or record.get("published_date")
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
    except ValueError:
        return None


def _url(record: dict) -> str:
    return str(record.get("canonical_url") or record.get("url") or "").strip()


def _source_name(record: dict) -> str:
    return _value(record, "source_name") or _value(record, "source_zh") or _value(record, "source_en")


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(re.search(re.escape(term), text, re.I) for term in terms if term)


def _matches_desk(text: str, desk: dict) -> bool:
    rule = desk.get("match") or {}
    groups = rule.get("all_groups") or [desk.get("keywords") or []]
    if not all(_contains_any(text, group) for group in groups if group):
        return False
    return not _contains_any(text, rule.get("exclude") or [])


def _category_ids(text: str, desk: dict) -> list[str]:
    matched = [
        category["id"] for category in desk.get("categories", [])
        if _contains_any(text, category.get("keywords") or [])
    ]
    return matched or ["overview"]


def _is_official(record: dict, desk: dict) -> bool:
    domain = (urlparse(_url(record)).hostname or "").lower()
    configured = [
        (urlparse(agency.get("url") or "").hostname or "").lower()
        for agency in desk.get("agencies", [])
    ]
    return any(domain == item or domain.endswith("." + item) for item in configured if item) or any(
        domain.endswith(suffix) or domain == suffix.lstrip(".") for suffix in GENERIC_OFFICIAL_DOMAINS
    )


def _public_record(record: dict, categories: list[str], *, dynamic: bool = True) -> dict | None:
    title_zh, summary_zh = _value(record, "title_zh"), _value(record, "summary_zh")
    url = _url(record)
    moment = _moment(record)
    if not title_zh or not summary_zh or not url or not moment:
        return None
    return {
        "id": record.get("record_id") or record.get("article_id"),
        "published_at": moment.isoformat(),
        "title_zh": title_zh,
        "title_en": _value(record, "title_original"),
        "summary_zh": summary_zh,
        "summary_en": _value(record, "summary_source"),
        "source_zh": _value(record, "source_zh") or _source_name(record),
        "source_en": _value(record, "source_en") or _source_name(record),
        "url": url,
        "category_ids": categories,
        "dynamic": dynamic,
    }


def load_historical_records(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def build_topic_desks(
    climate_archive: dict,
    energy_archive: dict,
    config_path: Path,
    historical_records: list[dict] | None = None,
) -> dict:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=LOOKBACK_DAYS)
    archive_rows = {
        "climate": climate_archive.get("records", []),
        "energy": energy_archive.get("records", []),
    }
    history = historical_records or []
    for desk in payload.get("desks", []):
        seed_records = desk.get("records", [])
        seed_keys = {
            str(row.get("id") or _url(row).split("?")[0]) for row in seed_records
        }
        candidates = [*archive_rows.get(desk.get("mode"), []), *history, *seed_records]
        evidence: list[tuple[dict, datetime, list[str], bool]] = []
        seen: set[str] = set()
        for row in sorted(candidates, key=lambda item: str(item.get("published_at") or item.get("published_at_utc") or ""), reverse=True):
            url, moment = _url(row), _moment(row)
            key = url.split("?")[0]
            row_key = str(row.get("id") or key)
            curated = row_key in seed_keys
            if not url or key in seen or not moment or moment < cutoff or (not curated and not _matches_desk(_text(row), desk)):
                continue
            seen.add(key)
            evidence.append((row, moment, _category_ids(_text(row), desk), curated))

        category_counts = {category["id"]: 0 for category in desk.get("categories", [])}
        category_counts["overview"] = 0
        for _row, _moment_value, categories, _curated in evidence:
            for category in categories:
                category_counts[category] = category_counts.get(category, 0) + 1

        public_records = []
        for row, _moment_value, categories, curated in evidence:
            public = _public_record(row, categories, dynamic=not curated)
            if public:
                public_records.append(public)
            if len(public_records) >= PUBLIC_RECORD_LIMIT:
                break

        latest_30 = sum(moment >= now - timedelta(days=30) for _row, moment, _categories, _curated in evidence)
        prior_30 = sum(now - timedelta(days=60) <= moment < now - timedelta(days=30) for _row, moment, _categories, _curated in evidence)
        sources = {_source_name(row) for row, _moment_value, _categories, _curated in evidence if _source_name(row)}
        official = sum(_is_official(row, desk) for row, _moment_value, _categories, _curated in evidence)
        desk["records"] = public_records
        desk["statistics"] = {
            "evidence_records": len(evidence),
            "public_records": len(public_records),
            "latest_30_days": latest_30,
            "prior_30_days": prior_30,
            "change_percent": None if prior_30 == 0 else round((latest_30 - prior_30) * 100 / prior_30),
            "source_count": len(sources),
            "official_records": official,
            "official_share": round(official * 100 / len(evidence), 1) if evidence else 0,
            "lookback_days": LOOKBACK_DAYS,
        }
        desk["category_counts"] = category_counts
        desk["dynamic_records"] = sum(bool(item.get("dynamic")) for item in public_records)
    payload["generated_at"] = now.isoformat()
    payload["method"] = "Three-year source-linked evidence; 30-day comparison uses publication dates. Counts describe corpus coverage, not real-world event frequency."
    return payload


def write_topic_desks(
    climate_archive: dict,
    energy_archive: dict,
    config_path: Path,
    output_path: Path,
    *,
    corpus_path: Path | None = None,
) -> dict:
    payload = build_topic_desks(
        climate_archive,
        energy_archive,
        config_path,
        load_historical_records(corpus_path),
    )
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

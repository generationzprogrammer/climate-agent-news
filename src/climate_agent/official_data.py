from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

from .collector import fetch_resource
from .db import Database
from .pipeline import stable_id


NDC_MIRROR_URL = "https://raw.githubusercontent.com/openclimatedata/ndcs/main/data/ndcs.csv"
NDC_REGISTRY_URL = "https://unfccc.int/NDCREG"
NDC_REQUIRED_FIELDS = {
    "code", "party", "title", "fileType", "language", "version", "status",
    "submissionDate", "encodedAbsUrl", "originalFilename",
}


def _source_hash(*parts: str | None) -> str:
    value = "\n".join(part or "" for part in parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_ndc_csv(payload: bytes, *, cutoff_year: int | None = None) -> tuple[list[dict], dict]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    fields = set(reader.fieldnames or [])
    missing = sorted(NDC_REQUIRED_FIELDS - fields)
    if missing:
        raise ValueError(f"NDC CSV missing required fields: {', '.join(missing)}")
    imported_at = datetime.now(UTC).isoformat()
    rows: list[dict] = []
    rejected: dict[str, int] = {}
    seen_keys: set[tuple[str, str, str]] = set()
    for raw in reader:
        reason = None
        file_url = (raw.get("encodedAbsUrl") or "").strip()
        submission_date = (raw.get("submissionDate") or "").strip()
        title = (raw.get("title") or "").strip()
        party = (raw.get("party") or "").strip()
        if not title or not party or not file_url:
            reason = "missing_core_field"
        elif urlsplit(file_url).hostname not in {"unfccc.int", "www.unfccc.int"}:
            reason = "non_unfccc_url"
        else:
            try:
                parsed_date = date.fromisoformat(submission_date)
            except ValueError:
                reason = "invalid_date"
            else:
                if parsed_date > date.today():
                    reason = "future_date"
                elif cutoff_year and parsed_date.year < cutoff_year:
                    reason = "before_cutoff"
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        key = (raw["code"].strip(), raw["version"].strip(), submission_date)
        if key in seen_keys:
            rejected["duplicate_version"] = rejected.get("duplicate_version", 0) + 1
            continue
        seen_keys.add(key)
        source_hash = _source_hash(*key, file_url)
        rows.append({
            "document_id": stable_id("ndc", source_hash),
            "kind": "ndc",
            "party": party,
            "title": title,
            "symbol": None,
            "body": "Party submission",
            "session": None,
            "cop_number": None,
            "version": raw["version"].strip(),
            "status": raw["status"].strip(),
            "publication_date": submission_date,
            "language": raw["language"].strip(),
            "detail_url": NDC_REGISTRY_URL,
            "file_url": file_url,
            "source_dataset": "OpenClimateData/ndcs mirror of the UNFCCC NDC Registry",
            "source_hash": source_hash,
            "imported_at": imported_at,
            "metadata": {
                "party_code": raw["code"].strip(),
                "file_type": raw["fileType"].strip(),
                "original_filename": raw["originalFilename"].strip(),
                "transport_url": NDC_MIRROR_URL,
                "authority": "UNFCCC file URL",
            },
        })
    return rows, {
        "accepted": len(rows),
        "rejected": sum(rejected.values()),
        "rejection_reasons": rejected,
        "schema_fields": sorted(fields),
    }


def import_ndcs(db: Database, *, cutoff_year: int | None = None) -> dict:
    if cutoff_year is None:
        cutoff_year = date.today().year - 10
    response = fetch_resource(NDC_MIRROR_URL, accept="text/csv", max_bytes=2_000_000)
    rows, quality = parse_ndc_csv(response.payload, cutoff_year=cutoff_year)
    result = db.upsert_official_documents(rows)
    return {
        **result,
        "cutoff_year": cutoff_year,
        "http_status": response.status,
        "response_bytes": response.size,
        "quality": quality,
        "source": NDC_MIRROR_URL,
    }


def import_curated_unfccc(db: Database, config_dir: Path) -> dict:
    now = datetime.now(UTC).isoformat()
    decision_rows = []
    for item in json.loads((config_dir / "unfccc_key_decisions.json").read_text(encoding="utf-8")):
        source_hash = _source_hash(item["symbol"], item["title"], item["session"])
        decision_rows.append({
            "document_id": stable_id("decision", source_hash),
            "kind": "decision",
            "party": None,
            "title": item["title"],
            "symbol": item["symbol"],
            "body": item["body"],
            "session": item["session"],
            "cop_number": item["cop_number"],
            "version": "adopted",
            "status": "official",
            "publication_date": item["publication_date"],
            "language": "English",
            "detail_url": f"https://unfccc.int/decisions?search3={quote_plus(item['symbol'])}",
            "file_url": item.get("file_url"),
            "source_dataset": "UNFCCC Decisions registry; quality-reviewed key outcome index",
            "source_hash": source_hash,
            "imported_at": now,
            "metadata": {
                "why_zh": item["why_zh"],
                "date_precision": "year",
                "curation_scope": "one high-value outcome per COP, plus selected negotiation-critical decisions",
            },
        })
    decisions = db.upsert_official_documents(decision_rows)

    summary = json.loads((config_dir / "unfccc_summary_metrics.json").read_text(encoding="utf-8"))
    item = summary["document"]
    summary_hash = _source_hash(item["symbol"], item["publication_date"], item["detail_url"])
    document_id = stable_id("summary", summary_hash)
    summaries = db.upsert_official_documents([{
        "document_id": document_id,
        "kind": "summary",
        "party": None,
        "title": item["title"],
        "symbol": item["symbol"],
        "body": "UNFCCC Secretariat",
        "session": "CMA 7",
        "cop_number": 30,
        "version": "published",
        "status": "official",
        "publication_date": item["publication_date"],
        "language": "English",
        "detail_url": item["detail_url"],
        "file_url": item["file_url"],
        "source_dataset": "UNFCCC official document record",
        "source_hash": summary_hash,
        "imported_at": now,
        "metadata": {"scope_zh": item["scope_zh"]},
    }])
    db.execute("DELETE FROM official_metrics WHERE document_id=?", (document_id,))
    for metric in summary["metrics"]:
        metric_id = stable_id("metric", f"{document_id}:{metric['label_zh']}")
        db.execute(
            "INSERT INTO official_metrics (metric_id,document_id,label_zh,value_text,scope_text,source_url,sort_order) VALUES (?,?,?,?,?,?,?)",
            (metric_id, document_id, metric["label_zh"], metric["value_text"], metric["scope_text"], item["detail_url"], metric["sort_order"]),
        )
    return {"decisions": decisions, "summaries": summaries, "metrics": len(summary["metrics"])}

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .historical_backfill import archive_item_to_historical_record


def merge_archive_into_corpus(
    corpus_path: Path,
    manifest_path: Path,
    archive: dict,
    *,
    limit: int = 100000,
) -> dict:
    """Incrementally merge quality-gated daily records into the historical corpus."""
    rows: list[dict] = []
    existing_keys: set[str] = set()
    if corpus_path.exists():
        for line in corpus_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = str(record.get("canonical_url") or record.get("record_id") or "").strip()
            if key:
                rows.append(record)
                existing_keys.add(key)

    now = datetime.now(UTC).isoformat()
    added = 0
    new_rows: list[dict] = []
    for item in archive.get("records") or []:
        record = archive_item_to_historical_record(item, fetched_at=now)
        if not record:
            continue
        key = record["canonical_url"]
        if key in existing_keys:
            continue
        added += 1
        existing_keys.add(key)
        new_rows.append(record)

    # Keep prior rows byte-stable and append only genuinely new articles. This
    # makes the daily corpus update auditable and avoids rewriting years of data.
    new_rows.sort(key=lambda row: (row.get("published_at_utc") or "", row.get("record_id") or ""))
    rows.extend(new_rows)
    if len(rows) > limit:
        rows = sorted(
            rows,
            key=lambda row: (row.get("published_at_utc") or "", row.get("record_id") or ""),
            reverse=True,
        )[:limit]
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    dates = [str(row.get("published_date") or "") for row in rows if row.get("published_date")]
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    manifest.update({
        "schema_version": "1.1",
        "dataset_name": "Global Climate Change Key Intelligence and Text Database",
        "records": len(rows),
        "limit": limit,
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
        "updated_at": now,
        "incremental_archive_merge": {
            "added": added,
            "updated": 0,
            "archive_records_seen": len(archive.get("records") or []),
        },
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"records": len(rows), "added": added, "updated": 0, "updated_at": now}

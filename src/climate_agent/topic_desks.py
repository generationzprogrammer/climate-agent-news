from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _text(record: dict) -> str:
    return " ".join(str(record.get(key) or "") for key in (
        "title_original", "title_zh", "summary_source", "summary_zh", "source_name"
    ))


def build_topic_desks(climate_archive: dict, energy_archive: dict, config_path: Path) -> dict:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    cutoff = datetime.now(UTC) - timedelta(days=365)
    archives = {"climate": climate_archive, "energy": energy_archive}
    for desk in payload.get("desks", []):
        patterns = [re.compile(re.escape(term), re.I) for term in desk.get("keywords", []) if term]
        records = archives.get(desk.get("mode"), {}).get("records", [])
        matched = []
        seen = {str(row.get("url") or "").split("?")[0] for row in desk.get("records", [])}
        for row in sorted(records, key=lambda item: str(item.get("published_at") or ""), reverse=True):
            try:
                moment = datetime.fromisoformat(str(row.get("published_at") or "").replace("Z", "+00:00"))
                if moment.tzinfo is None:
                    moment = moment.replace(tzinfo=UTC)
            except ValueError:
                continue
            url = str(row.get("canonical_url") or "")
            if moment < cutoff or not url or url.split("?")[0] in seen or not any(p.search(_text(row)) for p in patterns):
                continue
            matched.append({
                "id": row.get("record_id") or row.get("article_id"),
                "published_at": row.get("published_at"), "title_zh": row.get("title_zh"),
                "title_en": row.get("title_original"), "summary_zh": row.get("summary_zh"),
                "summary_en": row.get("summary_source"), "source_zh": row.get("source_name"),
                "source_en": row.get("source_name"), "url": url, "dynamic": True,
            })
            seen.add(url.split("?")[0])
        desk["records"] = matched[:30] + desk.get("records", [])
        desk["dynamic_records"] = len(matched)
    payload["generated_at"] = datetime.now(UTC).isoformat()
    return payload


def write_topic_desks(climate_archive: dict, energy_archive: dict, config_path: Path, output_path: Path) -> dict:
    payload = build_topic_desks(climate_archive, energy_archive, config_path)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


CARBON_PATTERN = re.compile(
    r"(?i)(?:china|chinese|中国|全国).{0,80}(?:carbon market|emissions trading|\bETS\b|CCER|"
    r"article\s*6|voluntary carbon|\bVCM\b|\bMRV\b|carbon footprint|碳市场|碳排放权|自愿减排|"
    r"第六条|监测.{0,8}报告.{0,8}核查|产品碳足迹)|(?:carbon market|emissions trading|\bETS\b|"
    r"CCER|article\s*6|碳市场|碳排放权|自愿减排|第六条).{0,80}(?:china|chinese|中国|全国)"
)
SINGAPORE_PATTERN = re.compile(
    r"(?i)singapore|新加坡|National Climate Change Secretariat|\bNCCS\b|"
    r"Prime Minister.?s Office|Ministry of Sustainability and the Environment|"
    r"National Environment Agency|Energy Market Authority"
)


def _text(record: dict[str, Any]) -> str:
    return " ".join(str(record.get(key, "")) for key in (
        "title_original", "title_zh", "summary_source", "summary_zh", "source_name"
    ))


def _recent(record: dict[str, Any], cutoff: datetime) -> bool:
    try:
        value = str(record.get("published_at") or "").replace("Z", "+00:00")
        moment = datetime.fromisoformat(value)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return moment >= cutoff
    except (TypeError, ValueError):
        return False


def build_spotlights(archive: dict[str, Any], config_path: Path) -> dict[str, Any]:
    """Combine reviewed official references with newly archived matching records."""
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    records = [record for record in archive.get("records", []) if record.get("quality", {}).get("passed", True)]
    cutoff = datetime.now(UTC) - timedelta(days=365)
    dynamic = {
        "china_carbon_market": [record for record in records if CARBON_PATTERN.search(_text(record))],
        "singapore": [record for record in records if _recent(record, cutoff) and SINGAPORE_PATTERN.search(_text(record))],
    }
    for section, rows in dynamic.items():
        seen = {
            str(item.get("url") or item.get("canonical_url") or "").split("?")[0].rstrip("/")
            for item in payload[section].get("records", [])
        }
        additions = []
        for record in sorted(rows, key=lambda item: item.get("published_at", ""), reverse=True):
            key = str(record.get("canonical_url") or "").split("?")[0].rstrip("/")
            if not key or key in seen:
                continue
            additions.append({
                "id": record.get("record_id") or record.get("article_id"),
                "published_at": record.get("published_at"),
                "topic": "dynamic",
                "agency": "ARCHIVE",
                "title_zh": record.get("title_zh"),
                "title_en": record.get("title_original"),
                "summary_zh": record.get("summary_zh"),
                "summary_en": record.get("summary_source"),
                "source_zh": record.get("source_name"),
                "source_en": record.get("source_name"),
                "url": record.get("canonical_url"),
                "dynamic": True,
            })
            seen.add(key)
        payload[section]["records"] = additions[:40] + payload[section].get("records", [])
    payload["generated_at"] = datetime.now(UTC).isoformat()
    payload["coverage"] = {
        "singapore_since": cutoff.date().isoformat(),
        "dynamic_china_records": len(dynamic["china_carbon_market"]),
        "dynamic_singapore_records": len(dynamic["singapore"]),
    }
    return payload


def write_spotlights(archive: dict[str, Any], config_path: Path, output_path: Path) -> dict[str, Any]:
    payload = build_spotlights(archive, config_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

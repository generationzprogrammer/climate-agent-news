from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from climate_agent.summary_utils import factual_fallback_summary, is_generic_summary  # noqa: E402


TARGETS = [
    ROOT / "data" / "news_archive.json",
    ROOT / "static" / "data" / "news_archive.json",
    ROOT / "static" / "data" / "dashboard.json",
    ROOT / "static" / "data" / "energy_archive.json",
    ROOT / "static" / "data" / "energy_dashboard.json",
]


def repair_record(record: dict) -> int:
    changed = 0
    if is_generic_summary(record.get("summary_zh")):
        record["summary_zh"] = factual_fallback_summary(record)
        changed += 1
    for key in ("records", "intelligence", "map_events", "map_events_today", "map_events_week"):
        value = record.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    changed += repair_record(item)
    return changed


def main() -> None:
    total = 0
    for path in TARGETS:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        changed = repair_record(payload)
        if changed:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{path.relative_to(ROOT)}: {changed}")
        total += changed
    print(f"total: {total}")


if __name__ == "__main__":
    main()

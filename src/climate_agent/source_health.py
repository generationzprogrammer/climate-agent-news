from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path


QUARANTINE_AFTER = 7
PROBATION_AFTER = 3
REPROBE_DAYS = 7


def load_source_health(path: Path) -> dict:
    if not path.exists():
        return {"updated_at": None, "sources": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"updated_at": None, "sources": {}}
    payload.setdefault("sources", {})
    return payload


def source_is_due(state: dict, source_id: str, *, now: datetime | None = None) -> bool:
    item = state.get("sources", {}).get(source_id, {})
    if item.get("action") != "quarantined":
        return True
    now = now or datetime.now(UTC)
    attempted = item.get("last_attempt_at")
    if not attempted:
        return True
    try:
        last_attempt = datetime.fromisoformat(attempted.replace("Z", "+00:00"))
    except ValueError:
        return True
    return now - last_attempt >= timedelta(days=REPROBE_DAYS)


def update_source_health(state: dict, results: list[dict], *, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    stamp = now.isoformat()
    sources = state.setdefault("sources", {})
    for result in results:
        source_id = result["source_id"]
        item = sources.setdefault(source_id, {"consecutive_failures": 0})
        success = result.get("status") in {"success", "empty"}
        item["last_status"] = result.get("status")
        item["last_attempt_at"] = stamp
        item["error"] = result.get("error")
        if success:
            item["consecutive_failures"] = 0
            item["last_success_at"] = stamp
            item["action"] = "active"
        else:
            failures = int(item.get("consecutive_failures", 0)) + 1
            item["consecutive_failures"] = failures
            item["action"] = "quarantined" if failures >= QUARANTINE_AFTER else (
                "probation" if failures >= PROBATION_AFTER else "active"
            )
    state["updated_at"] = stamp
    return state


def save_source_health(path: Path, state: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path

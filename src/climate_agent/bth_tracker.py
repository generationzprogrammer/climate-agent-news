"""Auditable BTH policy targets and CCPID-inspired document preclassification."""
from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def classify_policies(records: list[dict], taxonomy: dict) -> list[dict]:
    result = []
    for original in records:
        row = deepcopy(original)
        title = str(row.get("title", "")).casefold()
        matches = []
        for category in taxonomy.get("categories", []):
            for group in category["groups"]:
                terms = [term for term in group["terms"] if term.casefold() in title]
                if terms:
                    matches.append({"category": category["id"], "group": group["id"], "terms": terms, "basis": "title_keyword"})
        row["instrument_categories"] = list(dict.fromkeys(m["category"] for m in matches))
        row["instrument_groups"] = list(dict.fromkeys(m["group"] for m in matches))
        row["instrument_evidence"] = matches
        row["classification_status"] = "title_preclassification" if matches else "unclassified"
        result.append(row)
    return result


def build_target_tracker(config: dict, *, today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    sources = {s["id"]: s for s in config.get("sources", [])}
    ids: set[str] = set()
    records = []
    for original in config.get("targets", []):
        row = deepcopy(original)
        if row["id"] in ids:
            raise ValueError("duplicate target ID")
        ids.add(row["id"])
        if row["region"] not in {"北京市", "天津市", "河北省"}:
            raise ValueError("target must be regional")
        if isinstance(row["value"], bool) or not isinstance(row["value"], (int, float)) or not math.isfinite(row["value"]):
            raise ValueError("invalid target value")
        if row["comparator"] not in {"ge", "le", "approx"} or not row["scope"] or not row["excerpt"]:
            raise ValueError("missing target definition")
        source = sources[row["source_id"]]
        if urlsplit(source["url"]).scheme != "https":
            raise ValueError("target requires HTTPS official evidence")
        row["source"] = source
        row["reviewed_at"] = config.get("reviewed_at")
        row["period_status"] = "past_deadline" if row["year"] < today.year else "active"
        candidates = [o for o in config.get("observations", [])
                      if o["region"] == row["region"] and o["metric"] == row["metric"]
                      and o["unit"] == row["unit"] and o["scope"] == row["scope"]
                      and o.get("baseline_year") == row.get("baseline_year") and o["year"] <= row["year"]]
        observation = max(candidates, key=lambda o: (o["year"], sources[o["source_id"]]["date"]), default=None)
        row["observation"] = None
        row["assessment"] = "awaiting_observation"
        if observation:
            observation = deepcopy(observation)
            if isinstance(observation["value"], bool) or not isinstance(observation["value"], (int, float)) or not math.isfinite(observation["value"]):
                raise ValueError("invalid observation")
            observation["source"] = sources[observation["source_id"]]
            row["observation"] = observation
            row["assessment"] = "tracking"
            if observation["year"] == row["year"] and row["comparator"] != "approx":
                met = observation["value"] >= row["value"] if row["comparator"] == "ge" else observation["value"] <= row["value"]
                row["assessment"] = ("preliminary_met" if met else "preliminary_below") if observation.get("status") == "preliminary" else ("met" if met else "below")
            if row["unit"] == "%" and row["comparator"] != "approx":
                row["gap_percentage_points"] = round(observation["value"] - row["value"], 4)
        records.append(row)
    return {"schema_version": 1, "generated_at": today.isoformat(), "reviewed_at": config.get("reviewed_at"),
            "reference": config.get("reference", {}), "records": records,
            "method": "Only identical region, metric, unit, baseline and scope are comparable. No interpolation, missing-as-zero or completion ratio. Past deadline does not establish failure; approximate targets have no invented tolerance."}


def write_target_tracker(root: Path, data_dir: Path) -> dict:
    payload = build_target_tracker(_load(root / "config" / "bth_targets.json"))
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "bth_target_tracker.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

"""Public evidence bundle for the BTH assistant; never includes API credentials."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from urllib.parse import urlsplit
from .bth_tracker import write_target_tracker


def public_url(value: str, *, allow_http: bool = False) -> str:
    url = urlsplit(value)
    if url.scheme not in ({"http", "https"} if allow_http else {"https"}) or not url.hostname or url.username or url.password:
        raise ValueError("assistant evidence requires a public HTTPS URL")
    return value


def build_knowledge(energy: dict, policies: dict, targets: dict | None = None) -> dict:
    sources = {row["id"]: row for row in energy.get("sources", [])}
    records = []
    for row in energy.get("observations", []):
        if row.get("selected") is not True:
            continue
        value = row.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("invalid selected observation")
        source = sources[row["source_id"]]
        records.append({
            "id": "D-" + row["id"], "kind": "observation", "region": row["region"],
            "year": row["year"], "title": row["label"], "metric": row["metric"],
            "value": value, "unit": row["unit"], "category": row["category"],
            "notes": row.get("notes", ""), "status": row.get("status", ""),
            "locator": row.get("locator", ""), "extraction_method": row.get("extraction_method", ""),
            "source": source["publisher"], "source_title": source["title"],
            "url": public_url(source["url"]), "content_scope": "published_numeric_observation",
        })
    for row in policies.get("records", []):
        records.append({
            "id": "P-" + row["policy_id"], "kind": "policy", "title": row["title"],
            "region": row["region"], "province": row["province"],
            "date": row["published_at"], "source": row["source"],
            "keywords": row.get("keywords", []), "url": public_url(row["url"], allow_http=True),
            "content_scope": "title_metadata_only",
        })
    for row in (targets or {}).get("records", []):
        source = row["source"]
        records.append({
            "id": "P-target_" + row["id"], "kind": "target", "title": row["title_zh"],
            "region": row["region"], "year": row["year"], "date": source["date"],
            "value": row["value"], "unit": row["unit"], "metric": row["metric"],
            "wording": row["wording_zh"], "baseline_year": row.get("baseline_year"),
            "scope": row["scope"], "excerpt": row["excerpt"], "locator": row["locator"],
            "source": source["publisher"], "source_title": source["title"],
            "url": public_url(source["url"]), "keywords": [row["theme_zh"]],
            "content_scope": "verified_policy_target_excerpt",
        })
        observation = row.get("observation")
        if observation and not any(r["id"] == "D-target_" + observation["id"] for r in records):
            actual_source = observation["source"]
            records.append({
                "id": "D-target_" + observation["id"], "kind": "observation", "title": row["title_zh"],
                "region": observation["region"], "year": observation["year"],
                "value": observation["value"], "unit": observation["unit"], "metric": observation["metric"],
                "scope": observation["scope"], "notes": "初步测算，非最终统计值", "status": observation["status"],
                "source": actual_source["publisher"], "source_title": actual_source["title"],
                "url": public_url(actual_source["url"]), "date": actual_source["date"],
                "excerpt": observation["excerpt"], "content_scope": "published_numeric_observation",
            })
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate assistant evidence IDs")
    return {"schema_version": 1, "energy_snapshot": energy.get("snapshot_date"),
            "policy_snapshot": policies.get("updated_at"), "records": records,
            "limitations": ["统计数值沿用原始单位和来源口径；2025年缺值不插值。",
                "政策题名与标签不等同于政策全文，不据此推断具体条款。",
                "CIB专家评分尚未核验，不作为观测值或政策效果证据。"]}


def write_assistant_assets(root: Path, data_dir: Path) -> dict:
    energy_path = root / "config" / "bth_energy_evidence.json"
    energy = json.loads(energy_path.read_text(encoding="utf-8")) if energy_path.exists() else {}
    policy_path = root / "data" / "bth_policy_archive.json"
    policies = json.loads(policy_path.read_text(encoding="utf-8")) if policy_path.exists() else {}
    targets = write_target_tracker(root, data_dir)
    bundle = build_knowledge(energy, policies, targets)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "bth_assistant_knowledge.json").write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    endpoint = os.getenv("BTH_ASSISTANT_ENDPOINT", "").strip().rstrip("/")
    if endpoint:
        public_url(endpoint)
    config = {"endpoint": endpoint, "sitekey": os.getenv("BTH_TURNSTILE_SITE_KEY", "").strip()}
    (data_dir / "bth_assistant_config.json").write_text(json.dumps(config), encoding="utf-8")
    return {"evidence_count": len(bundle["records"]), "configured": bool(endpoint and config["sitekey"])}

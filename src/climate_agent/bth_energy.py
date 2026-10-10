"""One structured evidence store drives the BTH database and monitor.

Observation grain: region, metric, period, unit, source. Policy goals remain
separate; missing values and future years are never filled or interpolated.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path

REGIONS = {"北京市": ("CN11", "Beijing"), "天津市": ("CN12", "Tianjin"), "河北省": ("CN13", "Hebei")}
CATEGORIES = [
    {"id": "supply", "zh": "能源供需", "en": "Energy supply and demand"},
    {"id": "structure", "zh": "清洁能源与结构", "en": "Clean energy and mix"},
    {"id": "industry", "zh": "产业活动", "en": "Industrial activity"},
    {"id": "transport", "zh": "交通与建筑", "en": "Transport and buildings"},
    {"id": "society", "zh": "经济社会", "en": "Economy and society"},
    {"id": "resources", "zh": "资源与环境", "en": "Resources and environment"},
]
KEY_METRICS = [
    ("pv_capacity", "光伏累计并网装机", "Solar PV capacity", "structure"),
    ("renewable_energy_consumption_share", "可再生能源消费比重", "Renewable share of energy consumption", "structure"),
    ("power_society", "全社会用电量", "Electricity consumption", "supply"),
    ("energy_total", "能源消费总量", "Total energy consumption", "supply"),
    ("nev_stock", "新能源汽车保有量", "New-energy vehicle stock", "transport"),
    ("population", "年末常住人口", "Resident population", "society"),
    ("gdp_current", "地区生产总值", "GDP at current prices", "society"),
    ("power_residential_society", "居民生活用电量", "Residential electricity use", "society"),
    ("re_capacity_share_local", "本地可再生能源装机占比", "Local renewable capacity share", "structure"),
]


def category(row: dict) -> str:
    metric, label, original = row["metric"], row.get("label", ""), row.get("category", "")
    if metric in {"population", "gdp_current", "va_primary", "va_secondary", "va_tertiary", "power_residential_society"} or original == "宏观":
        return "society"
    if any(term in label for term in ("光伏", "风电", "可再生", "非化石", "能源构成", "能源结构")) or metric.startswith(("pv_", "wind_", "re_", "renewable_")):
        return "structure"
    if "水" in original or any(term in label for term in ("排放", "森林", "PM2.5")):
        return "resources"
    if "交通" in original or any(term in label for term in ("汽车", "轨道", "供热", "建筑", "公路", "铁路")):
        return "transport"
    if "工业" in original or "产量" in label or "行业" in original:
        return "industry"
    return "supply"


def build_energy_database(evidence: dict, targets: dict, updates: dict | None = None, *, today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    sources = {s["id"]: deepcopy(s) for s in evidence.get("sources", [])}
    rows, ids = [], set()
    for original in evidence.get("observations", []):
        if original.get("selected") is not True:
            continue
        row = deepcopy(original)
        value = row.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("non-finite energy observation")
        if row["id"] in ids or row["region"] not in REGIONS or row["source_id"] not in sources:
            raise ValueError("invalid energy identity or provenance")
        ids.add(row["id"])
        if not 1900 <= int(row["year"]) <= today.year:
            raise ValueError("future observation is not an actual")
        source = sources[row["source_id"]]
        if not source["url"].startswith("https://"):
            raise ValueError("energy evidence must have public HTTPS provenance")
        row.update({"region_code": REGIONS[row["region"]][0], "kind": "observation",
                    "period": row.get("period", str(row["year"])), "frequency": row.get("frequency", "annual"),
                    "dimension": category(row), "source": source,
                    "published_at": row.get("published_at") or source.get("published_at"),
                    "scope": row.get("scope") or row.get("notes") or row["label"]})
        rows.append(row)
    # Prefer explicit monitor-series bindings. Reject ambiguous comparisons.
    indicators = []
    for metric, zh, en, dimension in KEY_METRICS:
        histories = [r for r in rows if r["metric"] == metric and r["frequency"] == "annual"]
        if not histories:
            continue
        latest = []
        for region in REGIONS:
            eligible = [r for r in histories if r["region"] == region]
            if eligible:
                newest = max(r["year"] for r in eligible)
                candidates = [r for r in eligible if r["year"] == newest]
                if len({(r["value"], r["unit"]) for r in candidates}) == 1:
                    latest.append(candidates[0]["id"])
        indicators.append({"metric": metric, "zh": zh, "en": en, "dimension": dimension,
                           "latest_ids": latest, "history_ids": [r["id"] for r in histories]})
    goals = deepcopy(targets.get("records", []))
    # Targets link to actual evidence only when scope, baseline and unit match.
    for goal in goals:
        goal["database_observation_ids"] = [r["id"] for r in rows if r["region"] == goal["region"]
            and r["metric"] == goal["metric"] and r["unit"] == goal["unit"]
            and r["scope"] == goal["scope"] and r.get("baseline_year") == goal.get("baseline_year")]
    return {"schema_version": 1, "name": "京津冀能源统计数据库", "generated_at": today.isoformat(),
            "snapshot_date": evidence.get("snapshot_date"), "regions": [{"zh": k, "id": v[0], "en": v[1]} for k, v in REGIONS.items()],
            "categories": CATEGORIES, "records": rows, "indicators": indicators, "targets": goals,
            "recent_records": sorted([r["id"] for r in rows if r["frequency"] != "annual"], key=lambda i: next(r["period"] for r in rows if r["id"]==i), reverse=True)[:12],
            "updates": updates or {}, "counts": {"observations": len(rows), "metrics": len({r["metric"] for r in rows}),
                "sources": len({r["source_id"] for r in rows}), "dimensions": dict(Counter(r["dimension"] for r in rows))},
            "definitions": {"current": "最新已公布实绩，不等于本日或本年实绩", "future": "政策目标，不作为预测或实绩",
                "emissions": "不以用电量或装机量替代碳排放；未取得同口径排放数据时不计算碳中和完成率",
                "gdp": "GDP保留来源现价口径及修订说明；不同版本现价GDP不用于实际增长率推算",
                "publication": "published_at为空表示尚未核定公布日；access_date不是公布日"}}


def write_energy_assets(root: Path, data_dir: Path, targets: dict) -> dict:
    evidence = json.loads((root / "config/bth_energy_evidence.json").read_text(encoding="utf-8")) if (root / "config/bth_energy_evidence.json").exists() else {}
    update_path = root / "data/bth_energy_updates.json"
    updates = json.loads(update_path.read_text(encoding="utf-8")) if update_path.exists() else {}
    # Weekly additions are separate from the curated seed. Revisions are retained.
    evidence.setdefault("sources", []).extend(updates.get("sources", []))
    evidence.setdefault("observations", []).extend(updates.get("observations", []))
    # A verified publication date enriches matching provenance, not numeric values.
    published = {s["url"]:s["published_at"] for s in updates.get("sources",[]) if s.get("published_at")}
    for source in evidence["sources"]:
        if source["url"] in published: source["published_at"]=published[source["url"]]
    # Reuse tracker ACTUALS, never tracker target values, in the same database.
    known_ids={r["id"] for r in evidence["observations"]}
    for target in targets.get("records",[]):
        actual=target.get("observation")
        if not actual or "target_"+actual["id"] in known_ids: continue
        oid="target_"+actual["id"]; sid="target_"+actual["source_id"]
        if not any(s["id"]==sid for s in evidence["sources"]):
            evidence["sources"].append({**actual["source"],"id":sid,"published_at":actual["source"]["date"]})
        evidence["observations"].append({**actual,"id":oid,"source_id":sid,"selected":True,"label":target["title_zh"],
            "category":"能源","notes":"初步测算，非最终统计值" if actual.get("status")=="preliminary" else actual["scope"],
            "access_date":target.get("reviewed_at"),"extraction_method":"reviewed_official_progress_excerpt"})
        known_ids.add(oid)
    result = build_energy_database(evidence, targets, updates={k: v for k, v in updates.items() if k not in {"observations", "sources"}})
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "bth_energy_database.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result

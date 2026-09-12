from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path


DIMENSIONS = {
    "policy": ("政策执行", "Policy", r"政策|规划|目标|监管|法案|policy|plan|target|regulation|auction"),
    "deployment": ("项目落地", "Deployment", r"项目|投产|装机|部署|开工|project|commission|capacity|deploy|construction"),
    "technology": ("技术广度", "Technology", r"光伏|风电|核能|氢能|地热|电动车|solar|wind|nuclear|hydrogen|geothermal|electric vehicle"),
    "grid": ("电网与储能", "Grid and storage", r"电网|储能|电池|输电|灵活性|grid|storage|battery|transmission|flexibility"),
    "finance": ("投资与融资", "Finance", r"投资|融资|资金|贷款|补贴|investment|finance|fund|loan|subsid"),
}
SUPPORT = re.compile(r"加速|增长|新增|批准|发布|投资|目标|accelerat|growth|add|approv|launch|invest|target", re.I)
HEADWIND = re.compile(r"取消|推迟|削减|回撤|暂停|反对|煤炭扩张|油气扩张|cancel|delay|cut|rollback|pause|oppose|coal expansion|oil expansion", re.I)


def _text(row: dict) -> str:
    return " ".join(str(row.get(key) or "") for key in ("title_original", "title_zh", "summary_source", "summary_zh"))


def build_transition_tracker(*archives: dict) -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=365)
    by_country: dict[str, dict] = defaultdict(lambda: {"name_zh": "", "records": [], "counts": defaultdict(int)})
    seen = set()
    for archive in archives:
        for row in archive.get("records", []):
            key = row.get("record_id") or row.get("canonical_url")
            if not key or key in seen:
                continue
            seen.add(key)
            try:
                moment = datetime.fromisoformat(str(row.get("published_at") or "").replace("Z", "+00:00"))
                if moment.tzinfo is None:
                    moment = moment.replace(tzinfo=UTC)
            except ValueError:
                continue
            if moment < cutoff:
                continue
            text = _text(row)
            for country in row.get("country_codes") or []:
                code = str(country.get("alpha2") or "")
                if not code:
                    continue
                item = by_country[code]
                item["name_zh"] = country.get("name_zh") or code
                item["records"].append(row)
                for dimension, (_label_zh, _label_en, pattern) in DIMENSIONS.items():
                    if re.search(pattern, text, re.I):
                        item["counts"][dimension] += 1
    eligible = {code: value for code, value in by_country.items() if len(value["records"]) >= 8}
    maxima = {dimension: max([value["counts"][dimension] for value in eligible.values()] or [1]) for dimension in DIMENSIONS}
    countries = []
    for code, value in eligible.items():
        scores = {dimension: round(100 * math.sqrt(value["counts"][dimension] / max(1, maxima[dimension]))) for dimension in DIMENSIONS}
        recent_text = " ".join(_text(row) for row in value["records"])
        support, headwind = len(SUPPORT.findall(recent_text)), len(HEADWIND.findall(recent_text))
        direction = "承压" if headwind > support * 0.65 and headwind >= 3 else "加速" if support > headwind * 2 and support >= 4 else "分化"
        countries.append({"alpha2": code, "name_zh": value["name_zh"], "evidence_count": len(value["records"]),
                          "scores": scores, "signal": direction,
                          "signal_en": {"承压": "Under pressure", "加速": "Accelerating", "分化": "Diverging"}[direction],
                          "support_signals": support, "headwind_signals": headwind})
    countries.sort(key=lambda item: (sum(item["scores"].values()), item["evidence_count"]), reverse=True)
    return {
        "generated_at": datetime.now(UTC).isoformat(), "window_days": 365,
        "method": "Scores are normalized country-level signals from source-linked corpus records, not forecasts or official performance rankings.",
        "dimensions": [{"id": key, "label_zh": label_zh, "label_en": label_en}
                       for key, (label_zh, label_en, _pattern) in DIMENSIONS.items()],
        "countries": countries[:18],
    }


def write_transition_tracker(output_path: Path, *archives: dict) -> dict:
    payload = build_transition_tracker(*archives)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

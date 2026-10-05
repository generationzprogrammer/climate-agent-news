"""Evidence-coded collaboration structure, never a performance league table."""
from __future__ import annotations

AXES = [
    {"id": "crossborder", "label": {"zh": "跨境联结", "en": "Country breadth"}, "unit": {"zh": "个国家", "en": "countries"},
     "field": "country_count", "thresholds": [1, 2, 5, 9], "bands": ["1", "2", "3–5", "6–9", "≥10"]},
    {"id": "industry", "label": {"zh": "产业参与", "en": "Industry breadth"}, "unit": {"zh": "家企业", "en": "companies"},
     "field": "company_count", "thresholds": [1, 2, 5, 9], "bands": ["1", "2", "3–5", "6–9", "≥10"]},
    {"id": "science", "label": {"zh": "科研支撑", "en": "Research breadth"}, "unit": {"zh": "家高校或研究机构", "en": "research bodies"},
     "field": "research_count", "thresholds": [1, 2, 5, 9], "bands": ["1", "2", "3–5", "6–9", "≥10"]},
    {"id": "diversity", "label": {"zh": "主体多样性", "en": "Actor diversity"}, "unit": {"zh": "种机构类型", "en": "actor types"},
     "field": "actor_type_count", "thresholds": [1, 2, 3, 4], "bands": ["1", "2", "3", "4", "5"]},
    {"id": "funding", "label": {"zh": "联合资助规模", "en": "Grant scale"}, "unit": {"zh": "百万欧元", "en": "EUR million"},
     "field": "eu_grant_million", "thresholds": [1, 3, 6, 10], "bands": ["≤1", "(1, 3]", "(3, 6]", "(6, 10]", ">10"]},
]


def profile_metrics(project: dict | None, source_id: str | None) -> dict:
    """A null observation is not scored. Only complete project register fields."""
    result = {}
    for axis in AXES:
        value = project.get(axis["field"]) if project else None
        if value is not None and (type(value) not in (int, float) or value < 0):
            raise ValueError("Invalid project indicator: " + axis["id"])
        if value == 0:
            # These are eligible collaborative projects; zero grant may be real,
            # but zero partner counts cannot silently become a positive category.
            score = 1 if axis["id"] == "funding" else None
        elif value is None:
            score = None
        else:
            score = 1 + sum(value > threshold for threshold in axis["thresholds"])
        result[axis["id"]] = {"raw": value, "score": score, "source_id": source_id if value is not None else None}
    return result


def validate_profile(case: dict) -> None:
    if "profile" not in case:
        return
    refs = {r["source_id"] for r in case.get("evidence", [])}
    expected = profile_metrics(case.get("project"), next(iter(refs), None))
    for axis in AXES:
        row = case["profile"].get(axis["id"], {})
        if row.get("raw") != expected[axis["id"]]["raw"] or row.get("score") != expected[axis["id"]]["score"]:
            raise ValueError("Profile observation/score mismatch: " + case["id"] + ":" + axis["id"])
        if row.get("raw") is not None and row.get("source_id") not in refs:
            raise ValueError("Profile lacks evidence: " + case["id"])

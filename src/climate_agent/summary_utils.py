from __future__ import annotations

import re


GENERIC_SUMMARY_MARKERS = (
    "来源标题显示",
    "来源摘要显示",
    "适合作为当日气候情报线索",
    "具体数字、责任主体和政策含义仍需回到原文核验",
)

NUMBER_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:million|billion|trillion|percent|%|fold|times|gw|mw|gwh|twh|hectares|acres|tonnes|tons|"
    r"万人|亿元|亿美元|万亿|亿吨|万吨|吉瓦|兆瓦|千瓦时|公顷|英亩)\b",
    re.IGNORECASE,
)


def is_generic_summary(text: str | None) -> bool:
    value = str(text or "")
    return any(marker in value for marker in GENERIC_SUMMARY_MARKERS)


def extract_numbers(text: str, limit: int = 3) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for match in NUMBER_RE.findall(text or ""):
        normalized = re.sub(r"\s+", " ", match.strip())
        key = normalized.lower()
        if key and key not in seen:
            seen.add(key)
            values.append(normalized)
        if len(values) >= limit:
            break
    return values


def infer_focus(text: str, theme_zh: str) -> str:
    haystack = (text or "").lower()
    if any(term in haystack for term in ("renewable", "solar", "wind", "clean energy", "energy transition", "storage", "battery", "grid")):
        return "清洁能源项目、投资或电力系统变化"
    if any(term in haystack for term in ("wildfire", "heat wave", "heatwave", "extreme heat", "smoke")):
        return "极端高温、野火风险及其应急压力"
    if any(term in haystack for term in ("flood", "rainfall", "storm", "hurricane")):
        return "洪水、强降雨或风暴造成的气候风险"
    if any(term in haystack for term in ("drought", "water scarcity", "water stress")):
        return "干旱、水资源压力及适应需求"
    if any(term in haystack for term in ("climate finance", "loss and damage", "fund", "funding", "bond")):
        return "气候资金安排、资金缺口或融资工具"
    if any(term in haystack for term in ("cop30", "cop31", "unfccc", "ndc", "negotiat", "summit")):
        return "国际谈判、国家承诺或大会进程"
    if any(term in haystack for term in ("carbon market", "carbon credit", "carbon price", "emission", "methane")):
        return "排放治理、碳市场或甲烷减排"
    return f"{theme_zh or '气候动态'}相关变化"


def factual_fallback_summary(record: dict) -> str:
    title_zh = str(record.get("title_zh") or "该条情报").strip()
    theme_zh = str(record.get("theme_zh") or record.get("theme") or "气候动态").strip()
    source_text = " ".join(str(record.get(key) or "") for key in ("title_original", "summary_source", "source_name", "source_domain"))
    places = record.get("places") or []
    place_names = []
    for place in places:
        if isinstance(place, dict):
            name = place.get("name_zh") or place.get("name")
        else:
            name = str(place)
        if name and name not in place_names:
            place_names.append(str(name))
    place_part = f"涉及{ '、'.join(place_names[:2]) }，" if place_names else ""
    numbers = extract_numbers(source_text)
    number_part = f"原文出现{ '、'.join(numbers) }等量化信息，" if numbers else ""
    focus = infer_focus(source_text, theme_zh)
    return f"{place_part}这条情报聚焦{focus}。{number_part}需要重点关注其对政策执行、谈判表述或风险研判的影响。".replace("。。", "。")[:220]

"""COP editorial priorities: discovery/selection hints, never factual evidence."""
from __future__ import annotations

import re

DAILY_TARGET = 12
COP_DAILY_TARGET = 4
REGIONAL_SHARE_TARGET = 0.05
PACIFIC_ISLAND_CODES = frozenset({
    "CK", "FM", "FJ", "KI", "MH", "NR", "NU", "PW", "PG", "WS", "SB", "TO", "TV", "VU", "NC", "PF",
})
# Australia/New Zealand belong to PIF, but do not count towards island coverage.
COP_PRIORITIES = {
    "气候谈判与国家承诺": r"\bcop\s*-?\s*\d{1,2}\b|unfccc|climate (?:talks|summit|pledge|target)|nationally determined|\bndcs?\b|气候谈判|国家自主贡献|国家气候承诺",
    "气候资金与损失损害": r"climate finance|climate fund|adaptation fund|loss and damage|\bncqg\b|气候资[金助]|损失[与和]损害",
    "适应与韧性": r"climate adaptation|adaptation plan|climate resilien|early warning|sea.level rise|气候适应|适应气候|气候韧性|海平面上升|早期预警",
    "碳市场与履约": r"article\s*6|carbon market|carbon credit|global stocktake|biennial transparency|巴黎协定第六条|国际碳市场|全球盘点|透明度报告",
    "减排与公正转型": r"fossil.fuel phase|transition away from fossil|just transition|methane emission|deforestation|clean energy transition|green industriali[sz]ation|公正转型|甲烷减排|停止毁林|化石能源转型|清洁能源转型",
}
_PACIFIC = re.compile(
    r"\b(?:pacific island(?:s)?|fiji|fijian|tuvalu|vanuatu|samoa|tonga|kiribati|nauru|palau|"
    r"solomon islands|marshall islands|micronesia|papua new guinea|cook islands|niue|new caledonia|french polynesia)\b"
    r"|太平洋岛国|斐济|图瓦卢|瓦努阿图|萨摩亚|汤加|基里巴斯|所罗门群岛|马绍尔群岛|密克罗尼西亚|巴布亚新几内亚|瑙鲁|帕劳|库克群岛|纽埃", re.I)


def record_text(item: dict) -> str:
    return " ".join(str(item.get(key) or "") for key in (
        "title_original", "title_zh", "summary_source", "summary_zh", "summary_from_source",
    ))


def cop_topics(item: dict) -> list[str]:
    text = record_text(item)
    return [name for name, pattern in COP_PRIORITIES.items() if re.search(pattern, text, re.I)]


def coverage_regions(item: dict) -> set[str]:
    codes = {str(value.get("alpha2", "")).upper() for value in item.get("country_codes", []) if isinstance(value, dict)}
    text = record_text(item)
    result = set()
    if "RU" in codes or re.search(r"\brussia(?:n)?\b|俄罗斯|俄联邦", text, re.I):
        result.add("RU")
    if codes & PACIFIC_ISLAND_CODES or _PACIFIC.search(text):
        result.add("PACIFIC_ISLANDS")
    return result


def regional_deficits(history: list[dict], current_count: int) -> set[str]:
    """Soft 5% rolling target; never forces an unavailable or older story."""
    denominator = len(history) + current_count
    return {region for region in ("RU", "PACIFIC_ISLANDS")
            if sum(region in coverage_regions(item) for item in history) < denominator * REGIONAL_SHARE_TARGET}


def prioritize_translation(rows: list[dict], limit: int, balance) -> list[dict]:
    """Reserve newest-day processing capacity before ordinary source balancing."""
    from datetime import datetime, timedelta, timezone
    def day(row):
        try:
            return datetime.fromisoformat(str(row.get("published_at_utc", "")).replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=8))).date().isoformat()
        except (ValueError, TypeError):
            return ""
    latest = max((day(row) for row in rows), default="")
    fresh = [row for row in rows if day(row) == latest]
    selected = []
    def take(pool, count):
        seen = {row["article_id"] for row in selected}
        selected.extend(balance([row for row in pool if row["article_id"] not in seen], min(count, limit - len(selected))))
    for region in ("RU", "PACIFIC_ISLANDS"):
        take([row for row in fresh if region in coverage_regions(row)], 2)
    take([row for row in fresh if cop_topics(row)], min(8, max(4, limit // 3)))
    take(fresh, limit)
    take(rows, limit)
    return selected

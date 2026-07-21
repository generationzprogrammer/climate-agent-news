from __future__ import annotations

from urllib.parse import urljoin


def _clip(value: str | None, limit: int) -> str:
    text = " ".join((value or "").split())
    return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}…"


def publishable_items(payload: dict) -> list[dict]:
    """Return only Chinese-complete items that are safe for a public push."""
    return [
        item for item in payload.get("intelligence", [])
        if item.get("title_zh") and item.get("summary_zh")
    ]


def build_push_message(payload: dict, public_url: str, *, max_items: int = 3) -> str:
    """Build a compact executive notification; the website remains canonical."""
    items = publishable_items(payload)[: max(1, min(max_items, 5))]
    if not items:
        raise ValueError("没有通过中文标题与概要校验的情报，取消推送")
    date = payload.get("meta", {}).get("date", "今日")
    lines = [f"【国际气候谈判情报｜{date}】", f"今日优先阅读 {len(items)} 条：", ""]
    for index, item in enumerate(items, 1):
        lines.extend([
            f"{index}. [{_clip(item.get('theme_zh') or '气候动态', 12)}] {_clip(item['title_zh'], 52)}",
            f"概要：{_clip(item['summary_zh'], 118)}",
            f"关注：{_clip(item.get('why_zh') or '请结合原文核验。', 78)}",
            "",
        ])
    if public_url:
        lines.append(f"完整地图、来源与原文：{urljoin(public_url.rstrip('/') + '/', './')}" )
    lines.append("说明：中文编译不替代原文核验；未通过质量门禁的内容不会推送。")
    return "\n".join(lines)

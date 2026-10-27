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


def build_weekly_message(report: dict, public_url: str, *, max_items: int = 7, language: str = "zh") -> str:
    meta = report.get("meta", {})
    site = public_url.rstrip('/') + '/' if public_url else "https://generationzprogrammer.github.io/climate-agent-news/"
    if language == "en":
        from .english_brief import english_fields
        lines = [f"GREEN Weekly Climate Briefing | {meta.get('start_date', '')} – {meta.get('end_date', '')}",
                 f"This week's archive covers {meta.get('total', 0)} climate news records.", "", "Selected developments", ""]
        for index, item in enumerate(report.get("highlights", [])[:max(1, min(max_items, 10))], 1):
            title, summary = english_fields(item)
            lines.extend([f"{index}. {title}", summary, f"Source: {item.get('canonical_url', '')}", ""])
        lines.extend([f"Explore the interactive map and news archive: {urljoin(site, './cop31/?lang=en')}",
                      f"Today's English PDF: {urljoin(site, './data/daily_brief_en.pdf')}",
                      "Unsubscribe or change language: open the website, choose Subscribe and use the same email address. You can also reply with 'unsubscribe'."])
        return "\n".join(lines)
    lines = [
        f"【{meta.get('title', '国际气候情报周报')}】",
        f"本周纳入 {meta.get('total', 0)} 条通过质量门禁的公开气候新闻记录。",
        "",
        "一周观察：",
    ]
    for observation in report.get("observations", [])[:3]:
        lines.append(f"- {_clip(observation, 130)}")
    lines.extend(["", "重点阅读："])
    for index, item in enumerate(report.get("highlights", [])[: max(1, min(max_items, 10))], 1):
        lines.extend([
            f"{index}. [{_clip(item.get('theme_zh') or '气候动态', 12)}] {_clip(item.get('title_zh') or item.get('title_original'), 54)}",
            f"概括：{_clip(item.get('summary_zh') or '概要待补充。', 120)}",
            "",
        ])
    lines.append(f"查看全球地图与最新情报：{urljoin(site, './cop31/')}")
    lines.append(f"下载PDF周报：{urljoin(site, './data/weekly_report.pdf')}")
    lines.append("退订或修改邮件语言：打开网站，点击“订阅”，填写同一邮箱操作；也可回复本邮件并注明“退订气候周报”。")
    lines.append("说明：周报为自动生成；重要数字、承诺和立场请回到原文核验。")
    return "\n".join(lines)

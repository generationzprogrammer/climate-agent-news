from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path


THEME_LABELS = {
    "污染碳协同": "减污降碳协同",
    "减污降碳协同": "减污降碳协同",
    "生态环境治理": "生态环境治理",
    "能源转型": "能源转型",
    "工业绿色化": "工业绿色化",
    "绿色交通": "绿色交通",
    "绿色建筑": "绿色建筑",
    "循环经济": "循环经济",
    "碳目标与治理": "碳目标与治理",
    "碳市场与绿色金融": "碳市场与绿色金融",
    "绿色转型": "综合绿色转型",
    "综合绿色转型": "综合绿色转型",
}

PROFILE_EXCLUDE_TERMS = (
    "社会保险", "科普基地", "文化产业", "外国投资者", "视听系统", "内部比选", "结果公示",
    "信息公开指南", "规划专栏", "意见征集", "通知公告",
)


def _profile_eligible(record: dict) -> bool:
    title = str(record.get("title") or "").strip()
    return (
        len(title) >= 8
        and bool(record.get("keywords"))
        and not any(term in title for term in PROFILE_EXCLUDE_TERMS)
    )


def _summary(name: str, records: list[dict], themes: Counter[str], sources: Counter[str], recent: int) -> str:
    if not records:
        return ""
    theme_text = "、".join(f"{value}{count}件" for value, count in themes.most_common(3))
    lead_source, lead_count = sources.most_common(1)[0]
    latest = records[0]
    if len(records) == 1:
        return f"{latest['published_at']}，{lead_source}发布《{latest['title']}》，当前可核验重点为{theme_text}。"
    return (
        f"{name}的政策组合以{theme_text}为主；近12个月发布{recent}件。"
        f"{lead_source}发布{lead_count}件，为主要发布主体；最新动作为{latest['published_at']}发布的《{latest['title']}》。"
    )


def build_city_profiles(archive: dict, config: dict, *, today: date | None = None) -> dict:
    today = today or date.today()
    raw_records = list(archive.get("records") or [])
    records = [item for item in raw_records if _profile_eligible(item)]
    profiles = []
    for jurisdiction in config.get("jurisdictions", []):
        rows = [item for item in records if item.get("region_id") == jurisdiction.get("id")]
        rows.sort(key=lambda item: (str(item.get("published_at") or ""), str(item.get("title") or "")), reverse=True)
        themes = Counter(
            THEME_LABELS.get(keyword, keyword)
            for item in rows for keyword in item.get("keywords", []) if keyword
        )
        sources = Counter(str(item.get("source") or "").strip() for item in rows if item.get("source"))
        domains = {str(item.get("official_domain") or "").strip() for item in rows if item.get("official_domain")}
        recent = sum(
            date.fromisoformat(str(item.get("published_at"))[:10]) >= today - timedelta(days=365)
            for item in rows if item.get("published_at")
        )
        dates = sorted(str(item.get("published_at") or "") for item in rows if item.get("published_at"))
        profiles.append({
            "region_id": jurisdiction.get("id"),
            "admin_code": jurisdiction.get("admin_code"),
            "name": jurisdiction.get("name"),
            "province": jurisdiction.get("province"),
            "administrative_level": jurisdiction.get("level"),
            "official_homepage": jurisdiction.get("homepage"),
            "evidence_count": len(rows),
            "recent_365_days": recent,
            "date_start": dates[0] if dates else "",
            "date_end": dates[-1] if dates else "",
            "source_count": len(sources),
            "official_domain_count": len(domains),
            "themes": [{"name": name, "count": count} for name, count in themes.most_common()],
            "profile": {
                "primary_focus": themes.most_common(1)[0][0] if themes else "",
                "policy_mix": [{"theme": name, "count": count} for name, count in themes.most_common(5)],
                "activity_last_12_months": recent,
                "lead_publisher": sources.most_common(1)[0][0] if sources else "",
                "latest_action": {
                    "date": rows[0].get("published_at"), "title": rows[0].get("title"),
                    "source": rows[0].get("source"), "url": rows[0].get("url"),
                } if rows else {},
                "evidence_strength": "较强" if len(rows) >= 8 else "中等" if len(rows) >= 3 else "初步",
            },
            "summary": _summary(str(jurisdiction.get("name") or "该地区"), rows, themes, sources, recent),
            "latest_policies": [
                {
                    "published_at": item.get("published_at"),
                    "title": item.get("title"),
                    "source": item.get("source"),
                    "url": item.get("url"),
                }
                for item in rows[:5]
            ],
            "evidence_policy_ids": [item.get("policy_id") for item in rows[:10] if item.get("policy_id")],
        })

    covered = [item for item in profiles if item["evidence_count"]]
    province_counts = Counter(str(item.get("province") or "") for item in records)
    theme_counts = Counter(
        THEME_LABELS.get(keyword, keyword)
        for item in records for keyword in item.get("keywords", []) if keyword
    )
    source_count = len({item.get("source") for item in records if item.get("source")})
    domain_count = len({item.get("official_domain") for item in records if item.get("official_domain")})
    findings = [
        f"政策库原始记录{len(raw_records)}份；经标题相关性筛查后，{len(records)}份用于城市画像，覆盖{len(covered)}个行政单元；配置清单共{len(profiles)}个行政单元。",
        f"现有记录来自{source_count}个发布主体和{domain_count}个官方域名。",
        "政策数量较多的地区为" + "、".join(
            f"{item['name']}（{item['evidence_count']}份）"
            for item in sorted(covered, key=lambda value: value["evidence_count"], reverse=True)[:5]
        ) + "。",
        "高频议题为" + "、".join(f"{name}（{count}份）" for name, count in theme_counts.most_common(5)) + "。",
        "地区间记录数量差异主要反映当前公开检索覆盖和网站可访问性，不能直接用于比较地方绿色转型绩效。",
    ]
    return {
        "schema_version": "1.0",
        "dataset_name": "京津冀绿色转型城市画像与短报告",
        "generated_on": today.isoformat(),
        "source_archive_updated_at": archive.get("updated_at", ""),
        "source_policy_total": len(raw_records),
        "profile_evidence_total": len(records),
        "screened_out_total": len(raw_records) - len(records),
        "method": "仅使用标题明确涉及绿色低碳议题的具体政策文件，按标准行政区代码聚合政策组合、近12个月活跃度、主要发布主体和最新动作；所有判断均可回溯到政策原文链接。",
        "scope_note": "本文件用于内部研究，未接入公开网站。画像反映政策文本供给，不代表实际排放或转型绩效。",
        "coverage": {
            "configured_jurisdictions": len(profiles),
            "covered_jurisdictions": len(covered),
            "coverage_rate": round(len(covered) * 100 / len(profiles), 1) if profiles else 0,
            "publishing_bodies": source_count,
            "official_domains": domain_count,
            "province_record_counts": dict(province_counts),
        },
        "brief_report": findings,
        "profiles": profiles,
    }


def write_city_profiles(archive_path: Path, config_path: Path, output_path: Path, report_path: Path) -> dict:
    archive = json.loads(archive_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    payload = build_city_profiles(archive, config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 京津冀绿色转型城市画像简报",
        "",
        f"数据日期：{payload['generated_on']}",
        "",
        *[f"- {item}" for item in payload["brief_report"]],
        "",
        "## 城市与区级画像",
        "",
    ]
    for item in (profile for profile in payload["profiles"] if profile["evidence_count"]):
        dimensions = item["profile"]
        policy_mix = "、".join(f"{entry['theme']}（{entry['count']}件）" for entry in dimensions["policy_mix"][:3])
        latest = dimensions["latest_action"]
        lines.extend([
            f"### {item['name']}",
            "",
            f"- 政策重点：{policy_mix}",
            f"- 近12个月：{dimensions['activity_last_12_months']}件",
            f"- 主要发布主体：{dimensions['lead_publisher']}",
            f"- 最新动作：{latest.get('date', '')}《{latest.get('title', '')}》",
            f"- 画像判断：{item['summary']}",
            "",
        ])
    missing = [item["name"] for item in payload["profiles"] if not item["evidence_count"]]
    if missing:
        lines.extend(["## 待补充证据地区", "", "、".join(missing), ""])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return payload

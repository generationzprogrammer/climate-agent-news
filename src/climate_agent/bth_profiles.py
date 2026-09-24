from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path


THEME_LABELS = {
    "污染碳协同": "减污降碳协同",
    "能源转型": "能源转型",
    "工业绿色化": "工业绿色化",
    "绿色交通": "绿色交通",
    "绿色建筑": "绿色建筑",
    "循环经济": "循环经济",
    "碳目标与治理": "碳目标与治理",
    "碳市场与绿色金融": "碳市场与绿色金融",
    "绿色转型": "综合绿色转型",
}

PROFILE_TITLE_TERMS = (
    "碳达峰", "碳排放", "碳市场", "碳足迹", "碳核算", "低碳", "绿色转型", "绿色低碳",
    "绿色发展", "绿色建筑", "绿色交通", "绿色制造", "节能降碳", "节能", "能源转型",
    "清洁能源", "可再生能源", "能效", "新能源", "循环经济", "动力电池", "废旧电池",
    "气候变化", "温室气体", "污染防治", "大气污染", "空气质量", "减污降碳",
)
PROFILE_EXCLUDE_TERMS = (
    "社会保险", "科普基地", "文化产业", "外国投资者", "视听系统", "内部比选", "结果公示",
    "信息公开指南", "规划专栏", "意见征集", "通知公告",
)


def _profile_eligible(record: dict) -> bool:
    if record.get("curated"):
        return True
    title = str(record.get("title") or "").strip()
    return (
        len(title) >= 8
        and any(term in title for term in PROFILE_TITLE_TERMS)
        and not any(term in title for term in PROFILE_EXCLUDE_TERMS)
    )


def _summary(name: str, records: list[dict], themes: Counter[str], sources: Counter[str]) -> str:
    if not records:
        return f"当前政策库尚未检出{name}近三年的可核验绿色转型政策；该结果表示公开检索覆盖不足，不表示当地没有相关政策。"
    dates = sorted(str(item.get("published_at") or "") for item in records if item.get("published_at"))
    theme_text = "、".join(value for value, _count in themes.most_common(3)) or "综合绿色转型"
    source_text = "、".join(value for value, _count in sources.most_common(2)) or "当地政府部门"
    if len(records) < 5:
        return (
            f"{name}现有{len(records)}份可追溯政策，时间覆盖{dates[0]}至{dates[-1]}，"
            f"主要涉及{theme_text}，发布主体包括{source_text}。样本量较小，目前仅适合用于政策线索核验。"
        )
    return (
        f"{name}现有{len(records)}份可追溯政策，时间覆盖{dates[0]}至{dates[-1]}。"
        f"政策供给主要集中于{theme_text}，主要发布主体为{source_text}；"
        "该画像描述政策发布结构，不直接等同于减排成效或转型绩效。"
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
            "summary": _summary(str(jurisdiction.get("name") or "该地区"), rows, themes, sources),
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
        "method": "先按标题中的绿色低碳实质性术语排除栏目页和明显无关文件，再按标准行政区代码聚合，并统计时间、主题、来源和近一年更新；所有判断均可回溯到政策原文链接。",
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
    for item in payload["profiles"]:
        lines.extend([
            f"### {item['name']}",
            "",
            item["summary"],
            "",
        ])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return payload

from __future__ import annotations

import json
import hashlib
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .summary_utils import is_generic_summary, is_generic_title


DEFAULT_CATALOGUE = Path(__file__).resolve().parents[2] / "config" / "energy_companies.json"
DEFAULT_PROFILES = Path(__file__).resolve().parents[2] / "config" / "energy_company_profiles.json"
COOPERATION_TERMS = (
    "partnership", "partner with", "collaboration", "collaborate", "joint venture", "consortium",
    "memorandum of understanding", "mou", "alliance", "teams up", "agreement with",
    "合作", "合资", "联合", "联盟", "签署协议", "谅解备忘录",
)
PROJECT_TERMS = (
    "project", "plant", "facility", "factory", "gigafactory", "farm", "power station", "refinery",
    "pipeline", "terminal", "grid", "storage", "electrolyser", "electrolyzer", "reactor", "mine",
    "investment", "invests", "launches", "builds", "construction", "capacity", "gw", "mw",
    "项目", "工厂", "电站", "风场", "光伏", "储能", "电网", "产能", "投资", "投产", "开工",
)
BOILERPLATE_TERMS = ("消息显示，涉及", "报道中出现", "主题上属于", "该段为题名与来源摘要")


def load_company_catalogue(path: Path = DEFAULT_CATALOGUE, profiles_path: Path = DEFAULT_PROFILES) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    companies = payload.get("companies") or []
    required = {"id", "name_zh", "name_en", "type", "country", "continent", "lon", "lat", "business_zh", "aliases", "website"}
    seen: set[str] = set()
    for company in companies:
        missing = required - set(company)
        if missing:
            raise ValueError(f"company {company.get('id', '?')} missing fields: {sorted(missing)}")
        if company["id"] in seen:
            raise ValueError(f"duplicate company id: {company['id']}")
        seen.add(company["id"])
    if profiles_path.exists():
        profiles = json.loads(profiles_path.read_text(encoding="utf-8")).get("profiles") or []
        by_id = {str(profile.get("company_id")): profile for profile in profiles if profile.get("company_id")}
        for company in companies:
            profile = by_id.get(company["id"])
            if profile:
                company.update({key: value for key, value in profile.items() if key != "company_id"})
    return payload


def _contains_alias(text: str, alias: str) -> bool:
    alias = str(alias or "").strip().lower()
    if not alias:
        return False
    if re.search(r"[\u4e00-\u9fff]", alias):
        return alias in text
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text, re.IGNORECASE))


def match_companies(record: dict, companies: list[dict]) -> list[dict]:
    text = " ".join(str(record.get(key) or "") for key in (
        "title_original", "title_zh", "summary_source", "summary_zh",
    )).lower()
    return [
        company for company in companies
        if any(_contains_alias(text, alias) for alias in company.get("aliases") or [])
    ]


def _dynamic_companies(records: list[dict], catalogue_companies: list[dict]) -> list[dict]:
    """Admit model entities only when the source record literally names them."""
    known_aliases = {
        str(alias).strip().lower()
        for company in catalogue_companies
        for alias in company.get("aliases") or []
        if str(alias).strip()
    }
    discovered: dict[str, dict] = {}
    for record in records:
        source_text = " ".join(str(record.get(key) or "") for key in (
            "title_original", "summary_source",
        )).lower()
        place = next((item for item in record.get("places") or [] if item.get("name_zh")), {})
        for entity in record.get("company_entities") or []:
            if not isinstance(entity, dict):
                continue
            name_en = str(entity.get("name_en") or "").strip()
            name_zh = str(entity.get("name_zh") or name_en).strip()
            literal_names = [name for name in (name_en, name_zh) if len(name) >= 2]
            if not literal_names or not any(name.lower() in source_text for name in literal_names):
                continue
            if any(name.lower() in known_aliases for name in literal_names):
                continue
            key = name_en.lower() or name_zh.lower()
            if key in discovered:
                continue
            business = entity.get("business_zh") or []
            if isinstance(business, str):
                business = [business]
            business = [str(item).strip() for item in business if str(item).strip()][:4]
            if not business:
                continue
            company_type = str(entity.get("company_type") or "energy_company")
            if company_type not in {"energy_major", "energy_startup", "energy_company"}:
                company_type = "energy_company"
            discovered[key] = {
                "id": "discovered_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12],
                "name_zh": name_zh,
                "name_en": name_en or name_zh,
                "type": company_type,
                "country": str(entity.get("country") or place.get("name_zh") or "未标注"),
                "continent": "动态识别",
                "lon": place.get("lon"),
                "lat": place.get("lat"),
                "business_zh": business,
                "aliases": literal_names,
                "website": "",
                "profile_basis_zh": "由新闻原文与模型结构化抽取，名称已通过原文逐字校验",
            }
    return list(discovered.values())


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)
    except ValueError:
        return None


def _event_location(record: dict, companies: list[dict]) -> dict | None:
    place = next((place for place in record.get("places") or [] if place.get("name_zh") and place.get("lon") is not None and place.get("lat") is not None), None)
    if place:
        return {"name_zh": place["name_zh"], "lon": place["lon"], "lat": place["lat"], "basis_zh": "新闻明确地点"}
    if companies and companies[0].get("lon") is not None and companies[0].get("lat") is not None:
        company = companies[0]
        return {
            "name_zh": company["country"], "lon": company["lon"], "lat": company["lat"],
            "basis_zh": "企业总部（新闻未明确项目地点）",
        }
    return None


def _event_category(record: dict, companies: list[dict]) -> tuple[str, str] | None:
    text = " ".join(str(record.get(key) or "") for key in (
        "title_original", "title_zh", "summary_source", "summary_zh",
    )).lower()
    if len(companies) >= 2 and any(term in text for term in COOPERATION_TERMS):
        return "cooperation", "企业合作"
    if any(company["type"] == "energy_startup" for company in companies):
        return "startup", "能源初创企业"
    if companies and any(term in text for term in PROJECT_TERMS):
        return "major_project", "能源巨头项目"
    return None


def _public_text(record: dict, companies: list[dict]) -> tuple[str, str] | None:
    title = str(record.get("title_zh") or "").strip()
    summary = str(record.get("summary_zh") or "").strip()
    original = str(record.get("title_original") or "").strip()
    # Preserve a useful current project that older fallback translation reduced
    # to boilerplate. The pattern only states facts explicitly present in its
    # source headline; other weak records remain excluded.
    bess = re.search(
        r"reaches\s+RTB\s+stage\s+for\s+([\d.]+)\s*MW\s*/\s*([\d.]+)\s*GWh\s+BESS\s+project\s+in\s+([A-Za-z ]+)",
        original,
        re.IGNORECASE,
    )
    weak = not summary or is_generic_summary(summary) or any(term in summary for term in BOILERPLATE_TERMS)
    if bess and companies:
        capacity_mw, capacity_gwh, country_en = bess.groups()
        country = (record.get("places") or [{}])[0].get("name_zh") or country_en.strip()
        title = f"{companies[0]['name_zh']}在{country}推进{capacity_mw}兆瓦、{capacity_gwh}吉瓦时储能项目"
        summary = f"{companies[0]['name_zh']}在{country}开发的{capacity_mw}兆瓦、{capacity_gwh}吉瓦时电池储能项目已达到开工准备阶段。"
        weak = False
    if not title or is_generic_title(title) or weak:
        return None
    return title, summary


def _intelligence_records(records: list[dict], companies: list[dict]) -> list[dict]:
    output = []
    for record in records:
        matched = match_companies(record, companies)
        category = _event_category(record, matched)
        if not matched or not category:
            continue
        public_text = _public_text(record, matched)
        if not public_text:
            continue
        location = _event_location(record, matched)
        output.append({
            "event_id": f"company_{record.get('record_id') or record.get('article_id')}",
            "record_id": record.get("record_id") or record.get("article_id"),
            "category": category[0],
            "category_zh": category[1],
            "company_ids": [company["id"] for company in matched],
            "companies": [company["name_zh"] for company in matched],
            "title_zh": public_text[0],
            "summary_zh": public_text[1],
            "source_name": record.get("source_name"),
            "published_at": record.get("published_at"),
            "canonical_url": record.get("canonical_url"),
            "location": location,
        })
    return sorted(output, key=lambda item: item.get("published_at") or "", reverse=True)


def _periods(events: list[dict]) -> tuple[list[dict], list[dict], str | None]:
    dated = [(event, _parse_time(event.get("published_at"))) for event in events]
    latest = max((parsed.date() for _, parsed in dated if parsed), default=None)
    if not latest:
        return [], [], None
    first = latest - timedelta(days=6)
    today = [event for event, parsed in dated if parsed and parsed.date() == latest]
    week = [event for event, parsed in dated if parsed and first <= parsed.date() <= latest]
    return today[:30], week[:100], latest.isoformat()


def _map_events(events: list[dict], prefix: str) -> list[dict]:
    output = []
    for event in events:
        location = event.get("location")
        if not location:
            continue
        output.append({
            "marker_id": f"{prefix}_{len(output)}_{event['event_id']}",
            "place": location["name_zh"],
            "lon": location["lon"],
            "lat": location["lat"],
            "location_basis_zh": location["basis_zh"],
            "theme": event["category_zh"],
            "title_zh": event["title_zh"],
            "summary_zh": event["summary_zh"],
            "source_name": event["source_name"],
            "published_at": event["published_at"],
            "url": event["canonical_url"],
            "companies": event["companies"],
        })
    return output


def build_company_intelligence(energy_archive: dict, catalogue: dict) -> dict:
    records = energy_archive.get("records") or []
    companies = [dict(company) for company in catalogue.get("companies") or []]
    discovered = _dynamic_companies(records, companies)
    companies.extend(discovered)
    events = _intelligence_records(records, companies)
    today, week, latest_day = _periods(events)
    by_company: dict[str, list[dict]] = {company["id"]: [] for company in companies}
    for event in events:
        for company_id in event["company_ids"]:
            by_company.setdefault(company_id, []).append(event)
    for company in companies:
        company["latest_intelligence"] = by_company.get(company["id"], [])[:3]
        company["intelligence_count"] = len(by_company.get(company["id"], []))
    categories = Counter(event["category_zh"] for event in events)
    countries = Counter(company["country"] for company in companies)
    return {
        "schema_version": "1.0",
        "meta": {
            "updated_at": energy_archive.get("updated_at") or datetime.now(UTC).isoformat(),
            "latest_news_date": latest_day,
            "scope_note_zh": catalogue.get("scope_note_zh"),
            "location_rule_zh": "优先采用新闻明确地点；缺失时使用企业总部并明确标注，不把总部推断为项目所在地。",
        },
        "statistics": {
            "companies": len(companies),
            "majors": sum(company["type"] == "energy_major" for company in companies),
            "startups": sum(company["type"] == "energy_startup" for company in companies),
            "dynamically_discovered": len(discovered),
            "countries": len(countries),
            "intelligence": len(events),
            "detailed_profiles": sum(bool(company.get("profile_updated_at")) for company in companies),
            "categories": dict(categories),
        },
        "methodology_sources": catalogue.get("methodology_sources") or [],
        "companies": companies,
        "intelligence": events,
        "today": today,
        "week": week,
        "map_events_today": _map_events(today, "company_today"),
        "map_events_week": _map_events(week, "company_week"),
    }


def write_company_intelligence(energy_archive: dict, output_path: Path, catalogue_path: Path = DEFAULT_CATALOGUE) -> dict:
    payload = build_company_intelligence(energy_archive, load_company_catalogue(catalogue_path))
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

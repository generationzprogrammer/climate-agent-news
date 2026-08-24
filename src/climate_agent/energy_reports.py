from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

from .collector import fetch_resource
from .chinese_text import is_readable_chinese_title, to_simplified
from .providers import OpenAICompatibleModel
from .summary_utils import is_generic_summary, is_generic_title


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED = ROOT / "config" / "energy_reports.seed.json"
DEFAULT_BULK = ROOT / "config" / "energy_reports.bulk.json"
DEFAULT_SOURCES = ROOT / "config" / "energy_report_sources.json"
DEFAULT_DATABASES = ROOT / "config" / "energy_databases.seed.json"
WORLD_BANK_API = "https://search.worldbank.org/api/v3/wds"
REPORT_TERMS = (
    "report", "outlook", "review", "statistics", "assessment", "white paper", "roadmap",
    "energy balance", "energy in brief", "technology perspectives", "market report",
    "报告", "展望", "白皮书", "统计", "评估", "路线图", "能源平衡",
)
ENERGY_SCOPE_TERMS = (
    "energy", "electricity", "power system", "power sector", "renewable", "solar", "wind",
    "hydrogen", "battery", "storage", "oil", "petroleum", "natural gas", "lng", "coal",
    "nuclear", "geothermal", "biofuel", "grid", "electrification", "critical mineral",
    "decarbon", "net zero", "clean cooking", "能源", "电力", "可再生", "光伏", "风电",
    "氢能", "储能", "电池", "石油", "天然气", "煤炭", "核能", "电网", "关键矿产",
)
REPORT_TITLE_EXCLUDES = (
    "procurement plan", "resettlement plan", "environmental and social commitment",
    "implementation status", "audit report", "loan agreement", "financing agreement",
    "contract award", "project appraisal document", "project information document",
    "disclosable version of the isr", "audited financial statement", "project introduction",
    "frequently asked questions",
)
OFFICIAL_REPORT_HOSTS = (
    "iea.org", "irena.org", "eia.gov", "energy.gov", "energy.gov.au", "gov.uk",
    "europa.eu", "ec.europa.eu", "meti.go.jp", "nea.gov.cn", "mospi.gov.in",
    "epe.gov.br", "nrcan.gc.ca", "natural-resources.canada.ca", "un.org", "worldbank.org",
)
TOPIC_TERMS = {
    "能源安全": ("energy security", "security of supply", "能源安全"),
    "电力系统": ("electricity", "power system", "grid", "电力", "电网"),
    "可再生能源": ("renewable", "solar", "wind", "可再生", "光伏", "风电"),
    "油气市场": ("oil", "gas", "lng", "petroleum", "石油", "天然气"),
    "储能与电池": ("battery", "storage", "储能", "电池"),
    "氢能": ("hydrogen", "氢"),
    "关键矿产": ("critical mineral", "lithium", "cobalt", "关键矿产", "锂"),
    "能源投资": ("investment", "finance", "投资", "融资"),
    "能源效率": ("efficiency", "energy consumption", "能效", "能源消费"),
    "能源技术": ("technology", "innovation", "ai", "digital", "技术", "创新", "人工智能"),
    "能源转型": ("transition", "net zero", "decarbon", "转型", "净零", "脱碳"),
}


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict] = []
        self._href = ""
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr = {key.lower(): value or "" for key, value in attrs}
        self._href = attr.get("href", "")
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            text = re.sub(r"\s+", " ", unescape(" ".join(self._parts))).strip()
            self.links.append({"href": self._href, "text": text})
            self._href = ""
            self._parts = []


def _load_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def _record_key(record: dict) -> str:
    title = re.sub(r"\W+", "", str(record.get("title_original") or "").lower(), flags=re.UNICODE)
    publisher = re.sub(r"\W+", "", str(record.get("publisher") or "").lower(), flags=re.UNICODE)
    if title:
        return f"title:{publisher}:{title}"
    return str(record.get("report_url") or "").strip()


def _normalise_record(record: dict, *, added_at: str) -> dict | None:
    url = str(record.get("report_url") or record.get("source_url") or "").strip()
    original = str(record.get("title_original") or "").strip()
    chinese = to_simplified(record.get("title_zh"))
    if not url.startswith("https://") or not original or not is_readable_chinese_title(chinese) or is_generic_title(chinese):
        return None
    summary = to_simplified(record.get("summary_zh"))
    if summary and is_generic_summary(summary):
        summary = ""
    year_match = re.search(r"\b(202[3-9])\b", " ".join((original, url, str(record.get("year") or ""))))
    year = int(record.get("year") or (year_match.group(1) if year_match else datetime.now(UTC).year))
    topics = record.get("topics") or _topics_for(f"{original} {chinese} {summary}")
    normalised = {
        "report_id": str(record.get("report_id") or "report_" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]),
        "title_zh": chinese,
        "title_original": original,
        "summary_zh": summary,
        "publisher": to_simplified(record.get("publisher") or "未标注机构"),
        "publisher_type": to_simplified(record.get("publisher_type") or "政府或国际组织"),
        "country_or_region": to_simplified(record.get("country_or_region") or "国际组织"),
        "year": year,
        "published_at": str(record.get("published_at") or f"{year}-01-01"),
        "language": str(record.get("language") or "English"),
        "topics": list(dict.fromkeys(to_simplified(item) for item in topics if str(item).strip()))[:5],
        "report_url": url,
        "source_url": str(record.get("source_url") or url),
        "discovery_method": str(record.get("discovery_method") or "curated_official_source"),
        "added_at": str(record.get("added_at") or added_at),
    }
    for key in ("abstract_original", "translation_method", "source_tier", "access_note_zh"):
        if record.get(key):
            normalised[key] = to_simplified(record[key]) if key != "abstract_original" else record[key]
    return normalised


def _topics_for(text: str) -> list[str]:
    haystack = text.lower()
    topics = [name for name, terms in TOPIC_TERMS.items() if any(term in haystack for term in terms)]
    return topics[:5] or ["能源综合"]


def _merge_records(*groups: list[dict]) -> list[dict]:
    now = datetime.now(UTC).isoformat()
    merged: dict[str, dict] = {}
    for group in groups:
        for raw in group:
            record = _normalise_record(raw, added_at=now)
            if record:
                merged[_record_key(record)] = {**merged.get(_record_key(record), {}), **record}
    return sorted(merged.values(), key=lambda row: (row["year"], row["published_at"], row["title_zh"]), reverse=True)


def _normalise_database_catalogue(payload: dict) -> list[dict]:
    databases = []
    for item in payload.get("databases") or []:
        url = str(item.get("database_url") or "").strip()
        name_zh = to_simplified(item.get("name_zh"))
        if not url.startswith("https://") or not is_readable_chinese_title(name_zh):
            continue
        databases.append({
            "database_id": str(item.get("database_id") or "energy_db_" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]),
            "record_type": "能源数据库",
            "domain": to_simplified(item.get("domain") or "能源综合"),
            "name_zh": name_zh,
            "name_original": str(item.get("name_original") or "").strip(),
            "database_url": url,
            "maintainer": to_simplified(item.get("maintainer") or "未标注机构"),
            "core_data": to_simplified(item.get("core_data") or ""),
            "primary_use": to_simplified(item.get("primary_use") or ""),
            "coverage": to_simplified(item.get("coverage") or ""),
            "update_note": to_simplified(item.get("update_note") or ""),
        })
    return sorted(databases, key=lambda row: (row["domain"], row["name_zh"]))


def _archive_candidates(energy_archive: dict) -> list[dict]:
    candidates = []
    for item in energy_archive.get("records") or []:
        text = " ".join(str(item.get(key) or "") for key in ("title_original", "title_zh", "summary_source", "summary_zh"))
        if not any(term in text.lower() for term in REPORT_TERMS):
            continue
        if int(item.get("authority") or item.get("quality", {}).get("authority") or 0) < 4:
            continue
        host = (urlparse(str(item.get("canonical_url") or "")).hostname or "").lower()
        if not any(host == allowed or host.endswith("." + allowed) for allowed in OFFICIAL_REPORT_HOSTS):
            continue
        if not item.get("title_zh") or is_generic_title(str(item.get("title_zh"))):
            continue
        published = str(item.get("published_at") or "")
        year_match = re.search(r"\b(202[3-9])\b", published)
        candidates.append({
            "title_original": item.get("title_original"),
            "title_zh": item.get("title_zh"),
            "summary_zh": item.get("summary_zh"),
            "publisher": item.get("source_name"),
            "publisher_type": "政府、国际组织或权威研究机构",
            "country_or_region": ((item.get("places") or [{}])[0].get("name_zh") or "国际组织"),
            "year": int(year_match.group(1)) if year_match else datetime.now(UTC).year,
            "published_at": published,
            "language": item.get("language") or "English",
            "topics": _topics_for(text),
            "report_url": item.get("canonical_url"),
            "source_url": item.get("canonical_url"),
            "discovery_method": "daily_quality_archive",
        })
    return candidates


def build_energy_report_database(
    energy_archive: dict,
    persistent_path: Path,
    seed_path: Path = DEFAULT_SEED,
    bulk_path: Path = DEFAULT_BULK,
    databases_path: Path = DEFAULT_DATABASES,
) -> dict:
    seed = _load_json(seed_path, {"reports": []})
    bulk = _load_json(bulk_path, {"reports": []})
    existing = _load_json(persistent_path, {"reports": []})
    database_catalogue = _normalise_database_catalogue(_load_json(databases_path, {"databases": []}))
    seed_titles = {str(row.get("title_original") or "").strip().lower() for row in seed.get("reports") or []}
    retained_existing = [
        row for row in (existing.get("reports") or [])
        if row.get("discovery_method") != "curated_official_source"
        or str(row.get("title_original") or "").strip().lower() in seed_titles
    ]
    retained_existing = [
        row for row in retained_existing
        if row.get("discovery_method") != "daily_quality_archive"
        or any(
            (urlparse(str(row.get("report_url") or "")).hostname or "").lower() == allowed
            or (urlparse(str(row.get("report_url") or "")).hostname or "").lower().endswith("." + allowed)
            for allowed in OFFICIAL_REPORT_HOSTS
        )
    ]
    reports = _merge_records(
        retained_existing,
        _archive_candidates(energy_archive),
        bulk.get("reports") or [],
        seed.get("reports") or [],
    )
    countries = sorted({row["country_or_region"] for row in reports})
    publishers = sorted({row["publisher"] for row in reports})
    years = sorted({row["year"] for row in reports}, reverse=True)
    domains = sorted({row["domain"] for row in database_catalogue})
    return {
        "schema_version": "1.0",
        "meta": {
            "updated_at": datetime.now(UTC).isoformat(),
            "scope_note_zh": "近三年能源技术、产业与转型报告，以及可直接支撑能源研究和产业分析的国际数据库；报告每日增量更新，数据库按来源复核更新。",
            "selection_note_zh": "基础目录与编辑精选分层管理；报告数量反映当前收录范围，不代表各国发布强度，条目均保留原文或正式发布信息入口。",
        },
        "statistics": {
            "reports": len(reports), "databases": len(database_catalogue), "countries_or_regions": len(countries), "publishers": len(publishers), "years": years,
            "with_abstract": sum(bool(row.get("abstract_original") or row.get("summary_zh")) for row in reports),
        },
        "filters": {"countries_or_regions": countries, "publishers": publishers, "years": years, "database_domains": domains},
        "reports": reports,
        "databases": database_catalogue,
    }


def write_energy_report_database(energy_archive: dict, persistent_path: Path, output_path: Path) -> dict:
    payload = build_energy_report_database(energy_archive, persistent_path)
    persistent_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    persistent_path.write_text(text, encoding="utf-8")
    output_path.write_text(text, encoding="utf-8")
    return payload


def _api_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("cdata!") or value.get("value") or "").strip()
    if isinstance(value, list):
        return "; ".join(filter(None, (_api_text(item) for item in value)))
    return ""


def _report_title_in_scope(title: str) -> bool:
    lowered = title.lower()
    return any(term in lowered for term in ENERGY_SCOPE_TERMS) and not any(term in lowered for term in REPORT_TITLE_EXCLUDES)


def _world_bank_daily_candidates(existing: list[dict], max_new: int) -> list[dict]:
    cutoff = (datetime.now(UTC).date() - timedelta(days=21)).isoformat()
    query = urlencode({
        "format": "json", "qterm": "energy", "strdate": cutoff,
        "enddate": datetime.now(UTC).date().isoformat(), "docty_exact": "Report",
        "srt": "docdt", "order": "desc", "rows": 200, "os": 0,
        "fl": "display_title,docdt,docty,count,abstracts,lang,repnme,url,txturl",
    })
    response = fetch_resource(f"{WORLD_BANK_API}?{query}", max_bytes=4_000_000, accept="application/json")
    payload = json.loads(response.payload.decode("utf-8", errors="replace"))
    known_urls = {str(row.get("report_url") or "") for row in existing}
    output = []
    for raw in (payload.get("documents") or {}).values():
        title = _api_text(raw.get("display_title"))
        language = _api_text(raw.get("lang"))
        if len(title) < 12 or not _report_title_in_scope(title) or (language and "english" not in language.lower()):
            continue
        published = _api_text(raw.get("docdt"))[:10]
        year_match = re.match(r"(20\d{2})", published)
        profile_url = _api_text(raw.get("url"))
        if profile_url.startswith("http://"):
            profile_url = "https://" + profile_url[7:]
        report_url = _api_text(raw.get("pdfurl")) or profile_url
        if not year_match or not report_url.startswith("https://") or report_url in known_urls:
            continue
        output.append({
            "title_original": title,
            "publisher": "世界银行",
            "publisher_type": "国际组织",
            "country_or_region": _api_text(raw.get("count")) or "国际组织",
            "year": int(year_match.group(1)),
            "published_at": published,
            "language": "English",
            "topics": _topics_for(title),
            "report_url": report_url,
            "source_url": profile_url or report_url,
            "abstract_original": _api_text(raw.get("abstracts"))[:1600],
            "discovery_method": "world_bank_documents_api_daily",
            "source_tier": "official_metadata",
            "access_note_zh": "世界银行正式报告页面或全文",
        })
        if len(output) >= max_new:
            break
    return output


def discover_official_reports(
    persistent_path: Path,
    *,
    model: OpenAICompatibleModel | None = None,
    sources_path: Path = DEFAULT_SOURCES,
    max_new: int = 12,
) -> dict:
    """Scan official listing pages and add only translated, traceable new reports."""
    current = _load_json(persistent_path, {"reports": []})
    existing_urls = {_record_key(item) for item in current.get("reports") or []}
    sources = _load_json(sources_path, {"sources": []}).get("sources") or []
    found: list[dict] = []
    failures: list[dict] = []
    try:
        found.extend(_world_bank_daily_candidates(current.get("reports") or [], max_new))
    except Exception as exc:
        failures.append({"publisher": "世界银行", "error": type(exc).__name__})
    for source in sources:
        if len(found) >= max_new:
            break
        try:
            response = fetch_resource(str(source["listing_url"]), max_bytes=2_000_000, accept="text/html,application/xhtml+xml")
            parser = _LinkParser()
            parser.feed(response.payload.decode("utf-8", errors="replace"))
            allowed_hosts = tuple(str(host).lower() for host in source.get("allowed_hosts") or [])
            for link in parser.links:
                title = link["text"].strip()
                url = urljoin(str(source["listing_url"]), link["href"])
                host = (urlparse(url).hostname or "").lower()
                if allowed_hosts and not any(host == allowed or host.endswith("." + allowed) for allowed in allowed_hosts):
                    continue
                if not title or len(title) < 8 or not any(term in f"{title} {url}".lower() for term in REPORT_TERMS):
                    continue
                if _record_key({"report_url": url}) in existing_urls or any(item.get("report_url") == url for item in found):
                    continue
                year_match = re.search(r"\b(202[3-9])\b", f"{title} {url}")
                if year_match and int(year_match.group(1)) < datetime.now(UTC).year - 3:
                    continue
                found.append({
                    "title_original": title,
                    "publisher": source["publisher"],
                    "publisher_type": source.get("publisher_type", "政府或国际组织"),
                    "country_or_region": source.get("country_or_region", "国际组织"),
                    "year": int(year_match.group(1)) if year_match else datetime.now(UTC).year,
                    "published_at": f"{year_match.group(1)}-01-01" if year_match else datetime.now(UTC).date().isoformat(),
                    "language": source.get("language", "English"),
                    "topics": _topics_for(title),
                    "report_url": url,
                    "source_url": source["listing_url"],
                    "discovery_method": "official_listing_daily_scan",
                })
                if len(found) >= max_new:
                    break
        except Exception as exc:
            failures.append({"publisher": source.get("publisher"), "error": type(exc).__name__})
        if len(found) >= max_new:
            break

    translated: list[dict] = []
    if found and model:
        result = model.complete_json(
            "你是能源报告目录编辑。逐义忠实翻译英文报告标题；如提供原文摘要，再将摘要压缩为一段60至120字中文概括。不得虚构数字、结论或发布日期；没有摘要时summary_zh留空。只返回JSON对象，键为reports。",
            {"reports": [{
                "index": index, "title": item["title_original"], "publisher": item["publisher"],
                "abstract": str(item.get("abstract_original") or "")[:1200],
            } for index, item in enumerate(found[:max_new])]},
        )
        by_index = {int(item.get("index")): item for item in result.get("reports") or [] if str(item.get("index", "")).isdigit()}
        for index, item in enumerate(found[:max_new]):
            translation = by_index.get(index, {})
            title_zh = str(translation.get("title_zh") or "").strip()
            if not title_zh or is_generic_title(title_zh):
                continue
            translated.append({**item, "title_zh": title_zh, "summary_zh": str(translation.get("summary_zh") or "").strip()})

    merged = _merge_records(current.get("reports") or [], translated)
    current.update({
        "schema_version": "1.0",
        "meta": {**current.get("meta", {}), "updated_at": datetime.now(UTC).isoformat()},
        "reports": merged,
    })
    persistent_path.parent.mkdir(parents=True, exist_ok=True)
    persistent_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "discovered": len(found), "added": len(translated), "failures": failures}

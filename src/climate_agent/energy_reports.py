from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .collector import fetch_resource
from .providers import OpenAICompatibleModel
from .summary_utils import is_generic_summary, is_generic_title


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED = ROOT / "config" / "energy_reports.seed.json"
DEFAULT_SOURCES = ROOT / "config" / "energy_report_sources.json"
REPORT_TERMS = (
    "report", "outlook", "review", "statistics", "assessment", "white paper", "roadmap",
    "energy balance", "energy in brief", "technology perspectives", "market report",
    "报告", "展望", "白皮书", "统计", "评估", "路线图", "能源平衡",
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
    chinese = str(record.get("title_zh") or "").strip()
    if not url.startswith("https://") or not original or not chinese or is_generic_title(chinese):
        return None
    summary = str(record.get("summary_zh") or "").strip()
    if summary and is_generic_summary(summary):
        summary = ""
    year_match = re.search(r"\b(202[3-9])\b", " ".join((original, url, str(record.get("year") or ""))))
    year = int(record.get("year") or (year_match.group(1) if year_match else datetime.now(UTC).year))
    topics = record.get("topics") or _topics_for(f"{original} {chinese} {summary}")
    return {
        "report_id": str(record.get("report_id") or "report_" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]),
        "title_zh": chinese,
        "title_original": original,
        "summary_zh": summary,
        "publisher": str(record.get("publisher") or "未标注机构"),
        "publisher_type": str(record.get("publisher_type") or "政府或国际组织"),
        "country_or_region": str(record.get("country_or_region") or "国际组织"),
        "year": year,
        "published_at": str(record.get("published_at") or f"{year}-01-01"),
        "language": str(record.get("language") or "English"),
        "topics": list(dict.fromkeys(str(item) for item in topics if str(item).strip()))[:5],
        "report_url": url,
        "source_url": str(record.get("source_url") or url),
        "discovery_method": str(record.get("discovery_method") or "curated_official_source"),
        "added_at": str(record.get("added_at") or added_at),
    }


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


def build_energy_report_database(energy_archive: dict, persistent_path: Path, seed_path: Path = DEFAULT_SEED) -> dict:
    seed = _load_json(seed_path, {"reports": []})
    existing = _load_json(persistent_path, {"reports": []})
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
    reports = _merge_records(retained_existing, _archive_candidates(energy_archive), seed.get("reports") or [])
    countries = sorted({row["country_or_region"] for row in reports})
    publishers = sorted({row["publisher"] for row in reports})
    years = sorted({row["year"] for row in reports}, reverse=True)
    return {
        "schema_version": "1.0",
        "meta": {
            "updated_at": datetime.now(UTC).isoformat(),
            "scope_note_zh": "近三年能源重点报告数据库，优先收录政府与国际组织官方英文版；每日扫描官方发布页，有新报告时增量入库。",
            "selection_note_zh": "报告数量反映当前收录范围，不代表各国发布强度；条目均保留官方原文入口。",
        },
        "statistics": {"reports": len(reports), "countries_or_regions": len(countries), "publishers": len(publishers), "years": years},
        "filters": {"countries_or_regions": countries, "publishers": publishers, "years": years},
        "reports": reports,
    }


def write_energy_report_database(energy_archive: dict, persistent_path: Path, output_path: Path) -> dict:
    payload = build_energy_report_database(energy_archive, persistent_path)
    persistent_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    persistent_path.write_text(text, encoding="utf-8")
    output_path.write_text(text, encoding="utf-8")
    return payload


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
    for source in sources:
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
            "你是能源报告目录编辑。逐字忠实翻译英文报告标题，并根据标题写一句40至90字的中文内容说明；不得虚构数字、结论或发布日期。只返回JSON对象，键为reports。",
            {"reports": [{"index": index, "title": item["title_original"], "publisher": item["publisher"]} for index, item in enumerate(found)]},
        )
        by_index = {int(item.get("index")): item for item in result.get("reports") or [] if str(item.get("index", "")).isdigit()}
        for index, item in enumerate(found):
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

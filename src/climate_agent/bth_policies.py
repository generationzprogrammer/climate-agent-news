from __future__ import annotations

import hashlib
import json
import re
import time
from collections import deque
from datetime import UTC, date, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from xml.etree import ElementTree

from .chinese_text import to_simplified
from .collector import fetch_resource


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "bth_policy_sources.json"
DEFAULT_ARCHIVE = ROOT / "data" / "bth_policy_archive.json"
FOLLOW_TERMS = ("政策", "政府信息公开", "政务公开", "规范性文件", "规划计划", "通知公告", "法规", "文件", "zcwj", "zwgk", "gongkai", "policy")
EXCLUDE_TITLE_TERMS = ("政策解读", "图解", "新闻发布", "答记者问", "访谈", "会议召开", "工作动态", "一图读懂")
BASELINE_TERMS = ("碳达峰实施方案", "十四五", "绿色低碳循环发展", "应对气候变化规划")


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.h1: list[str] = []
        self.title: list[str] = []
        self.text: list[str] = []
        self._href = ""
        self._link_text: list[str] = []
        self._tag = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag = tag.lower()
        if self._tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._link_text = []

    def handle_data(self, value: str) -> None:
        value = re.sub(r"\s+", " ", unescape(value)).strip()
        if not value:
            return
        self.text.append(value)
        if self._tag == "h1":
            self.h1.append(value)
        if self._tag == "title":
            self.title.append(value)
        if self._href:
            self._link_text.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, " ".join(self._link_text).strip()))
            self._href = ""
            self._link_text = []
        self._tag = ""


def _decode(payload: bytes) -> str:
    head = payload[:4000].decode("ascii", errors="ignore")
    match = re.search(r"charset\s*=\s*[\"']?([\w-]+)", head, re.I)
    encodings = [match.group(1)] if match else []
    encodings.extend(["utf-8", "gb18030"])
    options = []
    for encoding in dict.fromkeys(encodings):
        try:
            text = payload.decode(encoding, errors="replace")
        except LookupError:
            continue
        options.append((text.count("�"), text))
    return min(options, default=(0, ""), key=lambda item: item[0])[1]


def _canonical(url: str) -> str:
    parts = urlparse(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return ""
    return urlunparse((parts.scheme, parts.netloc.lower(), parts.path or "/", "", parts.query, ""))


def _host_allowed(url: str, domains: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _page(html: str) -> tuple[str, str, list[tuple[str, str]]]:
    parser = _PageParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    title = " ".join(parser.h1).strip() or " ".join(parser.title).strip()
    title = re.split(r"[_|—-]\s*(?:北京市|天津市|河北省|人民政府|政府门户)", title)[0].strip()
    return to_simplified(title), to_simplified(" ".join(parser.text)), parser.links


def _published(text: str) -> str:
    for pattern in (
        r"(20\d{2})[年\-/\.](\d{1,2})[月\-/\.](\d{1,2})日?",
        r"(20\d{2})(\d{2})(\d{2})",
    ):
        match = re.search(pattern, text[:12000])
        if not match:
            continue
        try:
            return date(*(int(value) for value in match.groups())).isoformat()
        except ValueError:
            continue
    return ""


def _source(text: str, fallback: str) -> str:
    match = re.search(r"(?:来源|发布机构|制定机关|发文机关)\s*[:：]\s*([^\s|<>]{2,40})", text[:8000])
    return to_simplified(match.group(1).strip("：:，,。")) if match else fallback


def _policy_type(title: str, policy_terms: list[str]) -> str:
    return next((term for term in policy_terms if term in title), "政策文件")


def _keywords(text: str, taxonomy: dict[str, list[str]]) -> list[str]:
    return [label for label, terms in taxonomy.items() if any(term.lower() in text.lower() for term in terms)]


def _record(url: str, html: str, jurisdiction: dict, config: dict, start: date) -> dict | None:
    title, text, _links = _page(html)
    if not title or any(term in title for term in EXCLUDE_TITLE_TERMS):
        return None
    combined = f"{title} {text[:16000]}"
    topic_terms = config["topic_terms"]
    policy_terms = config["policy_terms"]
    if not any(term.lower() in combined.lower() for term in topic_terms):
        return None
    if not any(term in title for term in policy_terms):
        return None
    published = _published(f"{text[:5000]} {url}")
    if not published:
        return None
    moment = date.fromisoformat(published)
    baseline = moment < start and any(term in title for term in BASELINE_TERMS)
    if moment < start and not baseline:
        return None
    if moment > date.today():
        return None
    labels = _keywords(combined, config["keyword_taxonomy"])
    if not labels:
        return None
    canonical = _canonical(url)
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]
    return {
        "policy_id": f"bth_policy_{digest}",
        "published_at": published,
        "source": _source(text, jurisdiction["name"] + "人民政府"),
        "title": title,
        "province": jurisdiction["province"],
        "region": jurisdiction["name"],
        "region_id": jurisdiction["id"],
        "admin_code": jurisdiction["admin_code"],
        "administrative_level": jurisdiction["level"],
        "keywords": labels,
        "policy_type": _policy_type(title, policy_terms),
        "baseline_policy": baseline,
        "url": canonical,
        "official_domain": urlparse(canonical).hostname or "",
        "collected_at": datetime.now(UTC).isoformat(),
    }


def _sitemap_urls(base: str, domains: list[str], limit: int) -> list[str]:
    candidates = [urljoin(base, "/sitemap.xml"), urljoin(base, "/sitemap_index.xml")]
    found: list[str] = []
    seen: set[str] = set()
    while candidates and len(seen) < 12 and len(found) < limit * 4:
        url = candidates.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            response = fetch_resource(url, timeout=8, max_bytes=4_000_000, retries=0, accept="application/xml,text/xml,*/*")
            root = ElementTree.fromstring(response.payload)
        except Exception:
            continue
        locations = [node.text.strip() for node in root.iter() if node.tag.lower().endswith("loc") and node.text]
        for location in locations:
            if not _host_allowed(location, domains):
                continue
            if location.lower().endswith(".xml"):
                candidates.append(location)
            else:
                found.append(_canonical(location))
    return sorted(set(found), reverse=True)[: limit * 4]


def collect_batch(
    config_path: Path = DEFAULT_CONFIG,
    *,
    batch: int = 0,
    batch_count: int = 10,
    max_pages_per_source: int = 80,
    page_window: int = 0,
) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    start = date.fromisoformat(config["coverage_start"])
    sources = []
    for jurisdiction in config["jurisdictions"]:
        for domain in jurisdiction["domains"]:
            sources.append((jurisdiction, domain))
    selected = [item for index, item in enumerate(sources) if index % batch_count == batch]
    records: dict[str, dict] = {}
    coverage = []
    for jurisdiction, domain in selected:
        base = jurisdiction["homepage"] if _host_allowed(jurisdiction["homepage"], [domain]) else f"https://{domain}/"
        sitemap = _sitemap_urls(base, [domain], max_pages_per_source)
        offset = max(0, page_window) * max_pages_per_source
        queue = deque([base, *sitemap[offset:offset + max_pages_per_source]])
        seen: set[str] = set()
        fetched = accepted = failed = 0
        consecutive_failures = 0
        deadline = time.monotonic() + 150
        while queue and fetched < max_pages_per_source and consecutive_failures < 5 and time.monotonic() < deadline:
            url = _canonical(queue.popleft())
            if not url or url in seen or not _host_allowed(url, [domain]):
                continue
            seen.add(url)
            try:
                response = fetch_resource(url, timeout=10, max_bytes=2_500_000, retries=0, accept="text/html,application/xhtml+xml;q=0.9")
                if "html" not in response.content_type and b"<html" not in response.payload[:2000].lower():
                    continue
                html = _decode(response.payload)
                fetched += 1
                consecutive_failures = 0
            except Exception:
                failed += 1
                consecutive_failures += 1
                continue
            item = _record(response.final_url, html, jurisdiction, config, start)
            if item:
                records[item["policy_id"]] = item
                accepted += 1
            _title, _text, links = _page(html)
            for href, label in links:
                link = _canonical(urljoin(response.final_url, href))
                marker = f"{label} {link}".lower()
                if link and _host_allowed(link, [domain]) and (
                    any(term.lower() in marker for term in FOLLOW_TERMS)
                    or any(term.lower() in marker for term in config["topic_terms"])
                ):
                    if any(term.lower() in marker for term in config["topic_terms"]):
                        queue.appendleft(link)
                    else:
                        queue.append(link)
        coverage.append({
            "jurisdiction_id": jurisdiction["id"], "jurisdiction": jurisdiction["name"],
            "domain": domain, "fetched": fetched, "accepted": accepted, "failed": failed,
            "page_window": page_window,
            "complete": not queue,
            "completed_at": datetime.now(UTC).isoformat(),
        })
    return {
        "schema_version": "1.0", "batch": batch, "batch_count": batch_count, "page_window": page_window,
        "coverage_start": config["coverage_start"], "records": list(records.values()), "source_status": coverage,
    }


def write_batch(path: Path, **kwargs) -> dict:
    payload = collect_batch(**kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _valid(record: dict, config: dict) -> bool:
    required = ("published_at", "source", "title", "province", "region", "admin_code", "keywords", "url")
    domains = {domain for item in config["jurisdictions"] for domain in item["domains"]}
    host = (urlparse(str(record.get("url") or "")).hostname or "").lower()
    return all(record.get(key) for key in required) and any(host == domain or host.endswith("." + domain) for domain in domains)


def _curated_records(config: dict) -> list[dict]:
    topic_path = ROOT / "config" / "topic_desks.json"
    if not topic_path.exists():
        return []
    topic_payload = json.loads(topic_path.read_text(encoding="utf-8"))
    desk = next((item for item in topic_payload.get("desks", []) if item.get("id") == "bth_green_transition"), {})
    jurisdiction_map = {
        "regional": ("京津冀", "京津冀", "bth", "BTH", "region"),
        "beijing": ("北京市", "北京市", "bj", "110000", "province"),
        "tianjin": ("天津市", "天津市", "tj", "120000", "province"),
        "hebei": ("河北省", "河北省", "hb", "130000", "province"),
    }
    source_names = {
        "mee.gov.cn": "生态环境部", "beijing.gov.cn": "北京市人民政府",
        "sthjj.beijing.gov.cn": "北京市生态环境局", "tj.gov.cn": "天津市人民政府",
        "sthj.tj.gov.cn": "天津市生态环境局", "gxt.hebei.gov.cn": "河北省工业和信息化厅",
        "hbepb.hebei.gov.cn": "河北省生态环境厅",
    }
    sector_keywords = {
        "economy": "绿色转型", "energy": "能源转型", "industry": "工业绿色化",
        "transport": "绿色交通", "buildings": "绿色建筑", "carbon_market": "碳市场与绿色金融",
    }
    records = []
    for item in desk.get("policy_tools", []):
        province, region, region_id, code, level = jurisdiction_map.get(item.get("jurisdiction"), jurisdiction_map["regional"])
        host = (urlparse(item.get("url") or "").hostname or "").lower()
        source = next((name for domain, name in source_names.items() if host == domain or host.endswith("." + domain)), region + "人民政府")
        records.append({
            "policy_id": str(item.get("id") or "curated_" + hashlib.sha1(item["url"].encode()).hexdigest()[:16]),
            "published_at": item["published_at"], "source": source,
            "title": item["title_zh"], "province": province, "region": region,
            "region_id": region_id, "admin_code": code, "administrative_level": level,
            "keywords": list(dict.fromkeys(sector_keywords.get(value, value) for value in item.get("sector_ids", []))),
            "policy_type": item.get("instrument") or "政策文件", "baseline_policy": item["published_at"] < config["coverage_start"],
            "url": item["url"], "official_domain": host,
            "collected_at": datetime.now(UTC).isoformat(), "curated": True,
        })
    return records


def merge_batches(input_dir: Path, archive_path: Path = DEFAULT_ARCHIVE, config_path: Path = DEFAULT_CONFIG) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    existing = {item["policy_id"]: item for item in _curated_records(config)}
    statuses: dict[tuple[str, str, int], dict] = {}
    if archive_path.exists():
        prior = json.loads(archive_path.read_text(encoding="utf-8"))
        existing.update({item["policy_id"]: item for item in prior.get("records", []) if item.get("policy_id")})
        statuses = {(item["jurisdiction_id"], item["domain"], int(item.get("page_window", 0))): item for item in prior.get("source_status", [])}
    for path in sorted(input_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for record in payload.get("records", []):
            if _valid(record, config):
                existing[record["policy_id"]] = record
        for item in payload.get("source_status", []):
            statuses[(item["jurisdiction_id"], item["domain"], int(item.get("page_window", 0)))] = item
    records = sorted(existing.values(), key=lambda item: (item["published_at"], item["title"]), reverse=True)
    payload = {
        "schema_version": "1.0",
        "dataset_name": "京津冀绿色转型政策库",
        "updated_at": datetime.now(UTC).isoformat(),
        "coverage_start": config["coverage_start"],
        "jurisdiction_total": len(config["jurisdictions"]),
        "source_total": sum(len(item["domains"]) for item in config["jurisdictions"]),
        "total": len(records),
        "records": records,
        "source_status": sorted(statuses.values(), key=lambda item: (item["jurisdiction"], item["domain"])),
    }
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

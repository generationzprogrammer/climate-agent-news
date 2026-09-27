from __future__ import annotations

import hashlib
import json
import re
import time
from collections import deque
from datetime import UTC, date, datetime, timedelta
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .chinese_text import to_simplified
from .collector import fetch_resource
from .article_content import extract_article_text


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "bth_policy_sources.json"
DEFAULT_ARCHIVE = ROOT / "data" / "bth_policy_archive.json"
FOLLOW_TERMS = ("政策", "政府信息公开", "政务公开", "规范性文件", "规划计划", "通知公告", "法规", "文件", "zcwj", "zwgk", "gongkai", "policy")
EXCLUDE_TITLE_TERMS = (
    "政策解读", "图解", "新闻发布", "答记者问", "访谈", "会议召开", "工作动态", "一图读懂",
    "结果公示", "中标公告", "成交公告", "采购公告", "招标公告", "内部比选", "招聘公告",
    "信息公开指南", "信息公开目录", "基层政务公开标准目录",
    "文字解读", "图片解读", "音频解读", "专家解读", "实施方案解读", "政策问答",
)
GENERIC_TITLES = {
    "通知公告", "规划计划", "政策文件", "规范性文件", "政府信息公开", "政务公开",
    "公告公示", "部门文件", "政府文件", "市政府文件", "区政府文件", "法定主动公开内容",
}
BASELINE_TERMS = ("碳达峰实施方案", "十四五", "绿色低碳循环发展", "应对气候变化规划")
PAGINATION_WINDOW_SIZE = 5
OFFICIAL_SEARCH_TERMS = (
    "绿色低碳", "节能降碳", "碳达峰", "清洁能源", "可再生能源",
    "新能源", "绿色制造", "绿色建筑", "绿色交通", "循环经济",
)
TIANJIN_EXTENDED_SEARCH_TERMS = (
    "碳市场", "绿色金融", "减污降碳", "污染防治", "空气质量",
    "清洁生产", "绿色工厂", "新能源汽车", "无废城市", "资源综合利用",
)
TIANJIN_DETAIL_SEARCH_TERMS = (
    "碳排放", "碳普惠", "碳足迹", "气候变化", "能效", "光伏", "风电", "氢能", "储能", "充电",
    "再生资源", "垃圾分类", "绿色供应链", "绿色采购", "超低能耗", "清洁取暖", "排污许可", "污染治理", "生态保护", "美丽天津",
)
SUMMARY_TITLE_SIGNALS = (
    "绿色", "低碳", "碳", "气候", "生态", "环境", "污染", "美丽", "能源", "节能",
    "光伏", "风电", "氢", "储能", "电力", "供热", "全电", "新能源", "充电", "清洁生产",
    "循环", "再生资源", "废弃物", "垃圾", "绿色工厂", "绿色建筑", "绿色交通", "空气质量", "零碳",
)
EXECUTION_DOCUMENT_TERMS = ("公告", "公示", "征集", "报告", "名录", "名单")
CORE_POLICY_TERMS = (
    "条例", "决定", "意见", "通知", "办法", "规定", "规范", "规划", "计划", "方案",
    "批复", "试点", "细则", "规则", "标准", "指引", "指南", "要点", "措施", "实施",
)
BODY_SIGNAL_TERMS = {
    "碳达峰", "碳中和", "碳排放", "温室气体", "碳核算", "碳足迹", "碳市场", "碳排放权",
    "绿色低碳", "绿色转型", "减污降碳", "低碳", "低碳发展", "气候变化", "气候适应",
    "节能", "节能降碳", "节能改造", "能效提升", "清洁能源", "可再生能源", "新能源", "光伏", "风电",
    "氢能", "储能", "绿电", "绿色制造", "绿色工厂", "绿色供应链", "清洁生产", "工业节能",
    "绿色建筑", "超低能耗", "绿色交通", "新能源汽车", "充电", "充换电", "零碳", "近零碳",
    "循环经济", "资源综合利用", "资源循环利用", "再生资源", "动力电池", "退役动力电池", "无废城市", "绿色金融", "气候投融资",
    "污染防治", "空气质量", "大气污染", "生态环境", "美丽中国",
}


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.h1: list[str] = []
        self.title: list[str] = []
        self.text: list[str] = []
        self._href = ""
        self._link_title = ""
        self._link_text: list[str] = []
        self._tag = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag = tag.lower()
        if self._tag == "a":
            values = dict(attrs)
            self._href = values.get("href") or ""
            self._link_title = values.get("title") or ""
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
            label = self._link_title.strip() or " ".join(self._link_text).strip()
            self.links.append((self._href, label))
            self._href = ""
            self._link_title = ""
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
    title = re.split(r"[_|—-]\s*(?:北京市|天津市|河北省|人民政府|政府门户|通知公告|政策文件|政务公开)", title)[0].strip()
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


def _specific_policy_title(title: str, config: dict, *, require_topic: bool = True) -> bool:
    """Keep concrete policy documents; reject navigation pages and page-wide keyword leakage."""
    compact = re.sub(r"\s+", "", title or "").strip("_-|—– ")
    return (
        len(compact) >= 8
        and compact not in GENERIC_TITLES
        and not any(term in compact for term in EXCLUDE_TITLE_TERMS)
        and (not require_topic or any(term.lower() in compact.lower() for term in config["topic_terms"]))
        and any(term in compact for term in config["policy_terms"])
    )


def _body_topic_evidence(text: str, taxonomy: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """Classify substantive article text while excluding generic sector words."""
    compact = text or ""
    matched = sorted(term for term in BODY_SIGNAL_TERMS if term in compact)
    if not matched:
        return [], []
    labels = []
    for label, terms in taxonomy.items():
        if any(term in BODY_SIGNAL_TERMS and term in compact for term in terms):
            labels.append(label)
    return labels, matched


def _record(
    url: str, html: str, jurisdiction: dict, config: dict, start: date,
    *, source_fallback: str = "",
) -> dict | None:
    title, text, _links = _page(html)
    if not _specific_policy_title(title, config, require_topic=False):
        return None
    policy_terms = config["policy_terms"]
    published = _published(f"{text[:5000]} {url}")
    if not published:
        return None
    moment = date.fromisoformat(published)
    baseline = moment < start and any(term in title for term in BASELINE_TERMS)
    if moment < start and not baseline:
        return None
    if moment > date.today():
        return None
    title_labels = _keywords(title, config["keyword_taxonomy"]) if _specific_policy_title(title, config) else []
    article = extract_article_text(html, limit=16_000)
    body_labels, matched_terms = _body_topic_evidence(article.get("text", ""), config["keyword_taxonomy"])
    labels = title_labels or body_labels
    if not labels:
        return None
    canonical = _canonical(url)
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]
    return {
        "policy_id": f"bth_policy_{digest}",
        "published_at": published,
        "source": _source(text, source_fallback or jurisdiction["name"] + "人民政府"),
        "title": title,
        "province": jurisdiction["province"],
        "region": jurisdiction["name"],
        "region_id": jurisdiction["id"],
        "admin_code": jurisdiction["admin_code"],
        "administrative_level": jurisdiction["level"],
        "keywords": labels,
        "relevance_basis": "title" if title_labels else "article_body",
        "matched_terms": sorted({term for term in config["topic_terms"] if term in title}) if title_labels else matched_terms,
        "policy_type": _policy_type(title, policy_terms),
        "baseline_policy": baseline,
        "within_last_year": moment >= date.today() - timedelta(days=365),
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


def _pager_urls(page_url: str, html: str) -> list[str]:
    """Expand government-list Pager({size,prefix,suffix}) scripts into concrete URLs."""
    match = re.search(r"Pager\s*\(\s*\{(?P<body>.*?)\}\s*\)", html, re.I | re.S)
    size = 0
    prefix = "index"
    suffix = "html"
    if match:
        body = match.group("body")
        size_match = re.search(r"\bsize\s*:\s*(\d+)", body, re.I)
        prefix_match = re.search(r"\bprefix\s*:\s*['\"]([^'\"]+)['\"]", body, re.I)
        suffix_match = re.search(r"\bsuffix\s*:\s*['\"]([^'\"]+)['\"]", body, re.I)
        if size_match and prefix_match and suffix_match:
            size = min(int(size_match.group(1)), 500)
            prefix, suffix = prefix_match.group(1), suffix_match.group(1)
    if not size:
        # Many district-government sites write pagination links with JavaScript
        # instead of placing them in the HTML DOM.
        create = re.search(
            r"createPageHTML\s*\(\s*(\d+)\s*,\s*\d+\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
            html, re.I,
        )
        count = re.search(r"\bcountPage\s*=\s*(\d+)", html, re.I)
        if create:
            size, prefix, suffix = min(int(create.group(1)), 500), create.group(2), create.group(3)
        elif count:
            size = min(int(count.group(1)), 500)
            suffix_match = re.search(r"['\"]index['\"]\s*\+.*?['\"]\.([a-z0-9]+)['\"]", html, re.I | re.S)
            suffix = suffix_match.group(1) if suffix_match else "shtml"
    if not size:
        return []
    return [
        _canonical(urljoin(page_url, f"{prefix}{'' if index == 0 else '_' + str(index)}.{suffix}"))
        for index in range(size)
    ]


def _looks_like_policy_detail(url: str, label: str, config: dict) -> bool:
    marker = f"{label} {url}".lower()
    return (
        any(term.lower() in marker for term in config["policy_terms"])
        or bool(re.search(r"/(?:20\d{2}(?:0[1-9]|1[0-2])|20\d{4})/[^?#]+(?:s?html?|htm)$", url, re.I))
        or bool(re.search(r"/(?:t20\d{6}|content[_-]?\d+|art[_-]?\d+)[^/?#]*\.(?:s?html?|htm)$", url, re.I))
    )


def _search_record(data: dict, jurisdiction: dict, config: dict, start: date, source_fallback: str) -> dict | None:
    """Build a record from the Beijing government unified-search index."""
    title = to_simplified(re.sub(r"<[^>]+>", " ", unescape(str(data.get("titleO") or data.get("title") or ""))))
    title = re.sub(r"\s+", " ", title).strip()
    if not _specific_policy_title(title, config, require_topic=False):
        return None
    canonical = _canonical(str(data.get("url") or ""))
    if not canonical or not _host_allowed(canonical, jurisdiction["domains"]):
        return None
    published = str(data.get("docDate") or "")[:10]
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", published):
        timestamp = data.get("dreDate")
        try:
            published = datetime.fromtimestamp(float(timestamp) / 1000, tz=UTC).date().isoformat()
        except (TypeError, ValueError, OSError):
            return None
    moment = date.fromisoformat(published)
    baseline = moment < start and any(term in title for term in BASELINE_TERMS)
    if (moment < start and not baseline) or moment > date.today():
        return None
    title_labels = _keywords(title, config["keyword_taxonomy"]) if _specific_policy_title(title, config) else []
    values = data.get("myValues") or {}
    summary = " ".join(str(value or "") for value in (
        data.get("summary"), values.get("QUICKDESCRIPTION"), values.get("SUMMARY"),
    ))
    summary = to_simplified(re.sub(r"<[^>]+>", " ", unescape(summary)))
    body_labels, matched_terms = _body_topic_evidence(summary, config["keyword_taxonomy"])
    labels = title_labels or body_labels
    if not labels:
        return None
    if not title_labels and not any(term in title for term in SUMMARY_TITLE_SIGNALS):
        return None
    site_label = data.get("siteLabel") or {}
    source = to_simplified(str(site_label.get("value") or values.get("DOMAINSITENAME") or source_fallback))
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]
    return {
        "policy_id": f"bth_policy_{digest}", "published_at": published,
        "source": source or source_fallback or jurisdiction["name"] + "人民政府",
        "title": title, "province": jurisdiction["province"], "region": jurisdiction["name"],
        "region_id": jurisdiction["id"], "admin_code": jurisdiction["admin_code"],
        "administrative_level": jurisdiction["level"], "keywords": labels,
        "relevance_basis": "official_search_title" if title_labels else "official_search_summary",
        "matched_terms": sorted({term for term in config["topic_terms"] if term in title}) if title_labels else matched_terms,
        "policy_type": _policy_type(title, config["policy_terms"]), "baseline_policy": baseline,
        "within_last_year": moment >= date.today() - timedelta(days=365), "url": canonical,
        "official_domain": urlparse(canonical).hostname or "", "discovery_method": "beijing_government_search",
        "collected_at": datetime.now(UTC).isoformat(),
    }


def _official_search_records(source: dict, jurisdiction: dict, config: dict, start: date, page_window: int) -> tuple[list[dict], int]:
    if source.get("search_provider") == "tianjin_policy_db":
        return _tianjin_policy_records(source, jurisdiction, config, start, page_window)
    if source.get("search_provider") == "bing_official_rss":
        return _official_rss_search_records(source, jurisdiction, config, start, page_window)
    site_code = str(source.get("search_site_code") or "")
    if not site_code:
        return [], 0
    origin = str(source.get("search_origin") or jurisdiction["homepage"]).rstrip("/")
    terms = {OFFICIAL_SEARCH_TERMS[page_window % len(OFFICIAL_SEARCH_TERMS)]}
    records: dict[str, dict] = {}
    hits = 0
    for term in terms:
        # The shared Beijing government search service rate-limits concurrent
        # clients aggressively.  One result page per scheduled term is enough
        # for weekly incremental discovery; direct official listings remain
        # the primary source for historical pagination.
        for page in range(1, 2):
            body = urlencode({
                "qt": term, "siteCode": site_code, "tab": "all", "page": page,
                "pageSize": 20, "sort": "dateDesc", "ie": "climate-policy-index",
            }).encode("utf-8")
            request = Request("https://api.so-gov.cn/query/s", data=body, headers={
                "Origin": origin, "Referer": f"{origin}/so/s?qt=x&siteCode={site_code}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            })
            try:
                with urlopen(request, timeout=15) as response:
                    payload = json.loads(response.read(8_000_000).decode("utf-8-sig"))
            except Exception:
                continue
            if not payload.get("ok"):
                continue
            docs = payload.get("resultDocs") or []
            hits += len(docs)
            for raw in docs:
                item = _search_record(raw.get("data") or {}, jurisdiction, config, start, str(source.get("name") or ""))
                if item:
                    records[item["policy_id"]] = item
    return list(records.values()), hits


def _official_rss_search_records(
    source: dict, jurisdiction: dict, config: dict, start: date, page_window: int,
) -> tuple[list[dict], int]:
    """Discover official local policies via Bing RSS, then verify official pages."""
    domain = str(source.get("domain") or "")
    if not domain:
        return [], 0
    term = OFFICIAL_SEARCH_TERMS[page_window % len(OFFICIAL_SEARCH_TERMS)]
    query = f'site:{domain} "{term}" 通知 方案 规划 办法 意见'
    search_url = "https://www.bing.com/search?format=rss&q=" + urlencode({"q": query})[2:]
    browser_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36"
    try:
        response = fetch_resource(
            search_url, timeout=20, retries=1, max_bytes=1_500_000,
            accept="application/rss+xml,application/xml,text/xml", user_agent=browser_ua,
        )
        root = ElementTree.fromstring(response.payload)
    except Exception:
        return [], 0
    records: dict[str, dict] = {}
    items = root.findall(".//item")
    for item in items:
        link = _canonical(item.findtext("link") or "")
        if not link or not _host_allowed(link, [domain]):
            continue
        title = to_simplified(unescape(re.sub(r"<[^>]+>", "", item.findtext("title") or ""))).strip()
        description = to_simplified(unescape(re.sub(r"<[^>]+>", " ", item.findtext("description") or ""))).strip()
        try:
            page = fetch_resource(
                link, timeout=12, retries=0, max_bytes=2_500_000,
                accept="text/html,application/xhtml+xml;q=0.9", user_agent=browser_ua,
            )
            html = _decode(page.payload)
            record = _record(page.final_url, html, jurisdiction, config, start, source_fallback=str(source.get("name") or jurisdiction["name"]))
        except Exception:
            record = None
        if record:
            record["discovery_method"] = "official_web_search_verified"
            records[record["policy_id"]] = record
            continue
        # A small number of official sites block automated article reads.  A
        # metadata fallback is allowed only when the exact title is itself a
        # concrete green policy and the official URL carries a valid date.
        published = _published(f"{link} {description}")
        if not published or not _specific_policy_title(title, config):
            continue
        try:
            moment = date.fromisoformat(published)
        except ValueError:
            continue
        baseline = moment < start and any(value in title for value in BASELINE_TERMS)
        if moment < start and not baseline:
            continue
        digest = hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]
        labels = _keywords(title, config["keyword_taxonomy"])
        record = {
            "policy_id": f"bth_policy_{digest}", "published_at": published,
            "source": str(source.get("name") or jurisdiction["name"]), "title": title,
            "province": jurisdiction["province"], "region": jurisdiction["name"],
            "region_id": jurisdiction["id"], "admin_code": jurisdiction["admin_code"],
            "administrative_level": jurisdiction["level"], "keywords": labels,
            "relevance_basis": "official_search_title", "matched_terms": [term],
            "policy_type": _policy_type(title, config["policy_terms"]), "baseline_policy": baseline,
            "within_last_year": moment >= date.today() - timedelta(days=365), "url": link,
            "official_domain": urlparse(link).hostname or "", "discovery_method": "official_web_search_metadata",
            "collected_at": datetime.now(UTC).isoformat(),
        }
        records[record["policy_id"]] = record
    return list(records.values()), len(items)


def _tianjin_policy_records(
    source: dict, jurisdiction: dict, config: dict, start: date, page_window: int,
) -> tuple[list[dict], int]:
    """Read Tianjin's public policy-file index and retain policy originals.

    The index covers municipal departments and district issuers.  Search
    results often point to an interpretation page while exposing the related
    policy original; the latter is preferred so the archive never substitutes
    a commentary page for the underlying instrument.
    """
    terms = tuple(source.get("search_terms") or (
        OFFICIAL_SEARCH_TERMS[page_window % len(OFFICIAL_SEARCH_TERMS)],
        TIANJIN_EXTENDED_SEARCH_TERMS[page_window % len(TIANJIN_EXTENDED_SEARCH_TERMS)],
        TIANJIN_DETAIL_SEARCH_TERMS[(page_window * 2) % len(TIANJIN_DETAIL_SEARCH_TERMS)],
        TIANJIN_DETAIL_SEARCH_TERMS[(page_window * 2 + 1) % len(TIANJIN_DETAIL_SEARCH_TERMS)],
    ))
    districts = [
        item for item in config["jurisdictions"]
        if item.get("province") == "\u5929\u6d25\u5e02" and item.get("level") == "district"
    ]
    records: dict[str, dict] = {}
    hits = 0
    endpoint = "https://www.tj.gov.cn/igs/front/search.jhtml"
    page_start = max(1, int(source.get("search_page_start", 1)))
    page_count = max(1, int(source.get("search_pages", 3)))
    for search_term in terms:
        for page in range(page_start, page_start + page_count):
            query = urlencode({
                "code": "856e304b1b034799b51ab10e02afe386", "pageSize": 20,
                "pageNumber": page, "searchWord": search_term, "siteId": 100,
                "orderBy": "time", "timeOrder": "desc",
            })
            request = Request(endpoint + "?" + query, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT; Windows NT 10.0; zh-CN) WindowsPowerShell/5.1.26100.6584",
                "Referer": "https://www.tj.gov.cn/zwgk/zcwjk/index_22280.html",
                "Accept": "application/json",
            })
            try:
                with urlopen(request, timeout=25) as response:
                    payload = json.loads(response.read(12_000_000).decode("utf-8-sig"))
            except Exception:
                continue
            docs = ((payload.get("page") or {}).get("content") or [])
            hits += len(docs)
            for data in docs:
                related_url = _canonical(str(data.get("RELATEDURL") or data.get("ZCJDURL") or ""))
                related_title = to_simplified(re.sub(r"<[^>]+>", "", unescape(str(data.get("RELATEDTITLE") or ""))))
                raw_url = related_url or _canonical(str(data.get("url") or ""))
                raw_title = related_title or to_simplified(re.sub(r"<[^>]+>", "", unescape(str(data.get("TITLE") or ""))))
                if not raw_url or not _specific_policy_title(raw_title, config, require_topic=False):
                    continue
                title_labels = _keywords(raw_title, config["keyword_taxonomy"])
                content = to_simplified(re.sub(r"<[^>]+>", " ", unescape(str(data.get("CONTENT") or ""))))
                body_labels, body_terms = _body_topic_evidence(content, config["keyword_taxonomy"])
                title_relevant = bool(title_labels) and _specific_policy_title(raw_title, config)
                body_relevant = (
                    not any(term in raw_title for term in EXECUTION_DOCUMENT_TERMS)
                    and any(term in raw_title for term in CORE_POLICY_TERMS)
                    and len(body_labels) >= 2
                    and len(body_terms) >= 3
                )
                if not title_relevant and not body_relevant:
                    continue
                try:
                    moment = date.fromisoformat(str(data.get("PUBDATE") or "")[:10])
                except ValueError:
                    continue
                baseline = moment < start and any(value in raw_title for value in BASELINE_TERMS)
                if moment < start and not baseline:
                    continue
                issuer = to_simplified(str(data.get("QJFWJG") or data.get("FWJG") or jurisdiction["name"]))
                local_issuer = issuer.startswith("市") or "天津" in issuer or any(item["name"] in issuer for item in districts)
                if not local_issuer:
                    continue
                region = next((item for item in districts if item["name"] in f"{issuer} {raw_title} {raw_url}"), jurisdiction)
                canonical = _canonical(raw_url)
                digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]
                records[f"bth_policy_{digest}"] = {
                    "policy_id": f"bth_policy_{digest}", "published_at": moment.isoformat(),
                    "source": issuer, "title": raw_title, "province": "天津市",
                    "region": region["name"], "region_id": region["id"],
                    "admin_code": region["admin_code"], "administrative_level": region["level"],
                    "keywords": title_labels if title_relevant else body_labels,
                    "relevance_basis": "tianjin_policy_title" if title_relevant else "tianjin_policy_body",
                    "matched_terms": (
                        sorted(term for term in config["topic_terms"] if term in raw_title)
                        if title_relevant else body_terms
                    ),
                    "policy_type": _policy_type(raw_title, config["policy_terms"]),
                    "baseline_policy": baseline, "within_last_year": moment >= date.today() - timedelta(days=365),
                    "url": canonical, "official_domain": urlparse(canonical).hostname or "",
                    "discovery_method": "tianjin_policy_database", "collected_at": datetime.now(UTC).isoformat(),
                }
    return list(records.values()), hits


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
    priority = {
        (str(item.get("jurisdiction_id") or ""), str(item.get("domain") or "")): item
        for item in config.get("priority_sources", [])
    }
    sources = []
    for jurisdiction in config["jurisdictions"]:
        for domain in jurisdiction["domains"]:
            source = priority.get((jurisdiction["id"], domain), {})
            seed_urls = [
                _canonical(url) for url in source.get("seed_urls", [])
                if _canonical(url) and _host_allowed(url, [domain])
            ]
            sources.append((jurisdiction, domain, source.get("name", ""), seed_urls, source))
    selected = [item for index, item in enumerate(sources) if index % batch_count == batch]
    records: dict[str, dict] = {}
    coverage = []
    for jurisdiction, domain, source_name, seed_urls, source_config in selected:
        base = jurisdiction["homepage"] if _host_allowed(jurisdiction["homepage"], [domain]) else f"https://{domain}/"
        sitemap = _sitemap_urls(base, [domain], max_pages_per_source)
        offset = max(0, page_window) * max_pages_per_source
        queue = deque([base, *seed_urls, *sitemap[offset:offset + max_pages_per_source]])
        seen: set[str] = set()
        fetched = accepted = failed = 0
        search_items, search_hits = _official_search_records(source_config, jurisdiction, config, start, page_window)
        for search_item in search_items:
            records[search_item["policy_id"]] = search_item
        search_accepted = len(search_items)
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
            item = _record(
                response.final_url, html, jurisdiction, config, start,
                source_fallback=source_name,
            )
            if item:
                records[item["policy_id"]] = item
                accepted += 1
            _title, _text, links = _page(html)
            pager_urls = _pager_urls(response.final_url, html)
            if pager_urls:
                window_start = max(0, page_window) * PAGINATION_WINDOW_SIZE
                window_end = window_start + PAGINATION_WINDOW_SIZE
                for page_link in reversed(pager_urls[window_start:window_end]):
                    if page_link and page_link not in seen and _host_allowed(page_link, [domain]):
                        queue.appendleft(page_link)
            for href, label in links:
                link = _canonical(urljoin(response.final_url, href))
                marker = f"{label} {link}".lower()
                listing_context = response.final_url in seed_urls or any(term.lower() in response.final_url.lower() for term in FOLLOW_TERMS)
                if link and _host_allowed(link, [domain]) and (
                    any(term.lower() in marker for term in FOLLOW_TERMS)
                    or any(term.lower() in marker for term in config["topic_terms"])
                    or (listing_context and _looks_like_policy_detail(link, label, config))
                ):
                    if any(term.lower() in marker for term in config["topic_terms"]):
                        queue.appendleft(link)
                    else:
                        queue.append(link)
        coverage.append({
            "jurisdiction_id": jurisdiction["id"], "jurisdiction": jurisdiction["name"],
            "domain": domain, "fetched": fetched, "accepted": accepted, "failed": failed,
            "source_name": source_name, "seed_count": len(seed_urls),
            "search_hits": search_hits, "search_accepted": search_accepted,
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


def _normalise_record(record: dict, config: dict) -> dict | None:
    required = ("published_at", "source", "title", "province", "region", "admin_code", "keywords", "url")
    domains = {domain for item in config["jurisdictions"] for domain in item["domains"]}
    host = (urlparse(str(record.get("url") or "")).hostname or "").lower()
    if not all(record.get(key) for key in required) or not any(host == domain or host.endswith("." + domain) for domain in domains):
        return None
    title = str(record.get("title") or "").strip()
    title_relevant = _specific_policy_title(title, config)
    if not _specific_policy_title(title, config, require_topic=False):
        return None
    if any(term in title for term in EXECUTION_DOCUMENT_TERMS) and not title_relevant:
        return None
    if record.get("relevance_basis") == "official_search_summary" and not any(
        term in title for term in SUMMARY_TITLE_SIGNALS
    ):
        return None
    labels = _keywords(title, config["keyword_taxonomy"]) if title_relevant else []
    if not labels and record.get("relevance_basis") in {"article_body", "official_search_summary", "tianjin_policy_body"} and record.get("matched_terms"):
        allowed = set(config["keyword_taxonomy"])
        labels = [value for value in record.get("keywords", []) if value in allowed]
    if not labels:
        return None
    cleaned = dict(record)
    cleaned["keywords"] = labels
    cleaned["policy_type"] = _policy_type(title, config["policy_terms"])
    cleaned["official_domain"] = host
    try:
        cleaned["within_last_year"] = date.fromisoformat(str(cleaned["published_at"])[:10]) >= date.today() - timedelta(days=365)
    except ValueError:
        return None
    return cleaned


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
    existing = {
        item["policy_id"]: cleaned
        for item in _curated_records(config)
        if (cleaned := _normalise_record(item, config))
    }
    statuses: dict[tuple[str, str, int], dict] = {}
    if archive_path.exists():
        prior = json.loads(archive_path.read_text(encoding="utf-8"))
        existing.update({
            item["policy_id"]: cleaned
            for item in prior.get("records", [])
            if item.get("policy_id") and (cleaned := _normalise_record(item, config))
        })
        statuses = {(item["jurisdiction_id"], item["domain"], int(item.get("page_window", 0))): item for item in prior.get("source_status", [])}
    for path in sorted(input_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for record in payload.get("records", []):
            cleaned = _normalise_record(record, config)
            if cleaned:
                existing[cleaned["policy_id"]] = cleaned
        for item in payload.get("source_status", []):
            statuses[(item["jurisdiction_id"], item["domain"], int(item.get("page_window", 0)))] = item
    by_url: dict[str, dict] = {}
    for item in existing.values():
        key = _canonical(str(item.get("url") or ""))
        current = by_url.get(key)
        score = (len(item.get("keywords", [])), len(str(item.get("title") or "")), bool(item.get("collected_at")))
        current_score = (
            len(current.get("keywords", [])), len(str(current.get("title") or "")), bool(current.get("collected_at"))
        ) if current else (-1, -1, False)
        if current is None or score > current_score:
            by_url[key] = item
    records = sorted(by_url.values(), key=lambda item: (item["published_at"], item["title"]), reverse=True)
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

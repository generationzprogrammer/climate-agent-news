"""Private, resumable 100-target original-language fulltext benchmark.

No production database writes, model calls, authenticated requests or publication.
Run with PYTHONPATH=src and tmp/fulltext_pilot_env/Scripts/python.exe.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import contextlib
import csv
import gzip
import hashlib
import html
import importlib.metadata
import io
import ipaddress
import json
import math
import os
import platform
import random
import re
import socket
import sqlite3
import statistics
import threading
import time
import unicodedata
import urllib.error
import urllib.parse as up
import urllib.request as ur
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
import trafilatura

from climate_agent.article_content import METADATA_ONLY_HOSTS
from climate_agent.research import news_records, title_matches

ROOT = Path(__file__).resolve().parents[1]
DAY = "20261103"
PRIVATE = ROOT / "data" / ("private_fulltext_pilot_" + DAY)
OUT = ROOT / "analysis" / ("fulltext_pilot_" + DAY)
UA = "ClimateText-Lab/1.0 (+https://generationzprogrammer.github.io/climate-agent-news/)"
SEED = "green-fulltext-pilot-20261103-v1"
CAP = 8 * 1024 * 1024
WORKERS = 4
GAP = 2.0
TIMEOUT = 12
ACCEPT_ENCODING = "identity"
TOTAL_RESPONSE_TIMEOUT = 45


def stamp():
    return datetime.now(timezone.utc).isoformat()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def jsonbytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def load_lines(path):
    if not path.exists():
        return []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def host(url):
    return (up.urlsplit(url).hostname or "").lower()


def restricted(url):
    h = host(url)
    return any(h == x or h.endswith("." + x) for x in METADATA_ONLY_HOSTS if x != "news.google.com")


def text_key(title):
    title = unicodedata.normalize("NFKC", html.unescape(title or "")).casefold()
    return re.sub(r"[^\w\u4e00-\u9fff]+", " ", title).strip()


def title_ok(expected, actual):
    if not expected or not actual:
        return False
    # RSS often appends the publisher; do not require that suffix in the page title.
    expected = re.split(r"\s[-–|]\s", expected)[0]
    return title_matches(expected, actual)


def make_frame():
    originals = news_records(ROOT)
    texts = [x for x in load_lines(ROOT / "data/research_texts.jsonl.gz")
             if x.get("text_kind") != "licensed_document_text"]
    by_url = {x["canonical_url"]: dict(x) for x in originals}
    for x in texts:
        u = x["canonical_url"]
        by_url[u] = {**by_url.get(u, {}), **{k: v for k, v in x.items() if k != "source_text"}}
    source_cfg = json.loads((ROOT / "config/sources.master.json").read_text("utf-8"))
    cfg = {s["source_id"]: s for s in source_cfg}
    name_home = {text_key(s["name"]): s.get("homepage_url") for s in source_cfg}
    db = sqlite3.connect((ROOT / "data/climate.db").resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    all_db = []
    for r in db.execute("SELECT a.canonical_url,a.title_original,a.metadata_json,s.homepage_url,s.name FROM articles a JOIN sources s USING(source_id)"):
        r = dict(r)
        m = json.loads(r.pop("metadata_json") or "{}")
        all_db.append((r["title_original"], r["canonical_url"]))
        if r["canonical_url"] in by_url:
            x = by_url[r["canonical_url"]]
            x["publisher_homepage"] = m.get("publisher_homepage") or x.get("publisher_homepage")
            x["source_name"] = m.get("publisher_name") or x.get("source_name") or r["name"]
    db.close()
    archives = json.loads((ROOT / "config/research_archives.json").read_text("utf-8"))["sources"]
    archive_hosts = {h: s for s in archives for h in s["allowed_hosts"]}
    merged = {}
    for x in by_url.values():
        original = x["canonical_url"]
        publisher = x.get("publisher_url")
        u = publisher if publisher and host(publisher) != "news.google.com" else original
        key = u.rstrip("/")
        if key in merged:
            merged[key]["aliases"].append(original)
            continue
        src = cfg.get(x.get("source_id"), {})
        homepage = x.get("publisher_homepage") or name_home.get(text_key(x.get("source_name")))
        if not homepage and host(u) != "news.google.com":
            homepage = src.get("homepage_url") or up.urlunsplit(("https", host(u), "/", "", ""))
        arc = archive_hosts.get(host(u))
        stratum = "google_wrapper" if host(u) == "news.google.com" else "public_wordpress" if arc else "direct_other"
        merged[key] = {"id": "pilot_" + digest(key.encode())[:16], "url": u, "aliases": [original],
                       "title": x.get("title_original", ""), "date": x.get("published_at") or x.get("published_at_utc") or x.get("published_date"),
                       "source": x.get("source_name"), "source_id": x.get("source_id"),
                       "language": x.get("language"), "publisher_homepage": homepage,
                       "stratum": stratum, "api_endpoint": (arc or {}).get("endpoint"),
                       "archive_post_id": x.get("archive_post_id"),
                       "old_excerpt_characters": x.get("text_characters"),
                       "old_text_basis": x.get("text_basis")}
    frame = list(merged.values())
    title_map = {}
    for title, u in all_db + [(r.get("title_original"), r["canonical_url"]) for r in originals] + [(r.get("title_original"), r.get("publisher_url")) for r in texts]:
        if u and host(u) != "news.google.com":
            key = text_key(re.split(r"\s[-–|]\s", title or "")[0])
            if key:
                title_map.setdefault(key, u)
    return frame, title_map, {"metadata_news_records": len(originals), "existing_news_text_records": len(texts),
                              "url_union_before_alias_dedup": len(by_url), "unique_known_url_groups": len(frame),
                              "strata": dict(collections.Counter(r["stratum"] for r in frame)),
                              "publisher_homepage_known": sum(bool(r["publisher_homepage"]) for r in frame),
                              "scope": "Existing climate news metadata corpus/archive plus independent research news excerpts. Excludes policy documents, energy reports and company/case catalogues; unresolved aliases may still denote the same article."}


def select_sample(frame):
    buckets = collections.defaultdict(list)
    for x in frame:
        buckets[x["stratum"]].append(x)
    total = len(frame)
    allocations = {s: int(80 * len(rows) / total) for s, rows in buckets.items()}
    for s in sorted(buckets, key=lambda s: 80 * len(buckets[s]) / total - allocations[s], reverse=True)[:80 - sum(allocations.values())]:
        allocations[s] += 1
    sample = []
    for s, rows in sorted(buckets.items()):
        rows = sorted(rows, key=lambda r: digest((SEED + r["id"]).encode()))
        n = allocations[s]
        sample.extend({**x, "sample_group": "representative", "inclusion_probability": n / len(rows),
                       "design_weight": len(rows) / n} for x in rows[:n])
    selected = {r["id"] for r in sample}
    remaining = [x for x in frame if x["id"] not in selected]
    # Purposeful stress cases, never mixed into population estimates.
    categories = [
        ("old_google_no_homepage", lambda x: x["stratum"] == "google_wrapper" and not x["publisher_homepage"], 5),
        ("google_homepage", lambda x: x["stratum"] == "google_wrapper" and bool(x["publisher_homepage"]), 5),
        ("source_restricted", lambda x: restricted(x["url"]) or any(k in host(x["url"]) for k in ("nytimes", "ft.com", "bloomberg", "wsj.com")), 4),
        ("long_article_candidate", lambda x: x["stratum"] == "public_wordpress" and (x.get("old_excerpt_characters") or 0) >= 750, 4),
        ("non_english", lambda x: x.get("language") not in (None, "en", "und") and x["stratum"] != "google_wrapper", 2),
    ]
    for category, predicate, number in categories:
        candidates = sorted((x for x in remaining if x["id"] not in selected and predicate(x)), key=lambda r: digest((SEED + category + r["id"]).encode()))
        for x in candidates[:number]:
            sample.append({**x, "sample_group": "stress", "stress_category": category, "inclusion_probability": None, "design_weight": None})
            selected.add(x["id"])
    for x in sorted(remaining, key=lambda r: digest((SEED + "reserve" + r["id"]).encode())):
        if len(sample) == 100:
            break
        if x["id"] not in selected:
            sample.append({**x, "sample_group": "stress", "stress_category": "reserve", "inclusion_probability": None, "design_weight": None})
            selected.add(x["id"])
    return sample


class StopFetch(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


class NoRedirect(ur.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Fetcher:
    def __init__(self):
        self.lock = threading.RLock()
        self.host_locks = collections.defaultdict(threading.RLock)
        self.last = {}
        self.robots_cache = {}
        self.dns_cache = {}
        self.stop_hosts = {}
        self.requests = []
        self.publisher_cache = {}
        self.opener = ur.build_opener(NoRedirect)

    def public(self, url, timing):
        t = time.perf_counter()
        if not isinstance(url,str) or re.search(r'[\x00-\x20\x7f]',url):
            raise StopFetch('invalid_url_whitespace_or_control')
        try:
            p = up.urlsplit(url)
            port=p.port
        except ValueError:
            raise StopFetch('invalid_url_structure')
        if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password or (port and port not in (80, 443)):
            raise StopFetch("unsafe_url")
        h = p.hostname.lower()
        if h in ("localhost",) or h.endswith((".local", ".internal", ".localhost")):
            raise StopFetch("unsafe_url")
        with self.lock:
            ips = self.dns_cache.get(h)
        if ips is None:
            try:
                ips = [x[4][0] for x in socket.getaddrinfo(h, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)]
            except OSError:
                raise StopFetch("dns_failed")
            with self.lock:
                self.dns_cache[h] = ips
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise StopFetch("unsafe_dns")
        timing["dns_seconds"] += time.perf_counter() - t

    def raw(self, url, timing, max_bytes=CAP):
        self.public(url, timing)
        h = host(url)
        with self.host_locks[h]:
            if h in self.stop_hosts:
                raise StopFetch("host_circuit_" + self.stop_hosts[h])
            wait = max(0, self.last.get(h, 0) + GAP - time.monotonic())
            time.sleep(wait)
            timing["rate_wait_seconds"] += wait
            t = time.perf_counter()
            code, payload, headers = None, b"", {}
            wire_bytes = 0
            try:
                req = ur.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json,application/xml;q=0.9,*/*;q=0.5", "Accept-Encoding": ACCEPT_ENCODING})
                try:
                    response = self.opener.open(req, timeout=TIMEOUT)
                except urllib.error.HTTPError as e:
                    response = e
                with response:
                    code = response.code
                    headers = dict(response.headers)
                    if code in (401, 403, 429):
                        self.stop_hosts[h] = 'http_' + str(code)
                    chunks = []
                    received = 0
                    reader = getattr(response, 'read1', response.read)
                    while received <= max_bytes:
                        if time.perf_counter() - t > TOTAL_RESPONSE_TIMEOUT:
                            raise StopFetch('response_wall_time_limit')
                        part = reader(min(65536, max_bytes + 1 - received))
                        if not part:
                            break
                        chunks.append(part)
                        received += len(part)
                        wire_bytes = received
                    payload = b''.join(chunks)
                    wire_bytes = len(payload)
                if code in (401, 403, 429):
                    self.stop_hosts[h] = "http_" + str(code)
                if len(payload) > max_bytes:
                    raise StopFetch("response_size_limit")
                if headers.get('Content-Encoding', headers.get('content-encoding', '')).lower() == 'gzip':
                    try:
                        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as compressed:
                            payload = compressed.read(max_bytes + 1)
                    except (OSError, EOFError):
                        raise StopFetch('invalid_gzip_response')
                    if len(payload) > max_bytes:
                        raise StopFetch('decompressed_response_size_limit')
                return code, headers, payload
            except (OSError, urllib.error.URLError, TimeoutError) as e:
                raise StopFetch("network_" + type(e).__name__)
            finally:
                self.last[h] = time.monotonic()
                elapsed = time.perf_counter() - t
                timing["network_seconds"] += elapsed
                timing["request_count"] += 1
                timing["response_bytes"] += len(payload)
                with self.lock:
                    self.requests.append({"url": url, "host": h, "http_status": code, "elapsed_seconds": elapsed, "response_bytes": len(payload), "wire_response_bytes": wire_bytes, "at": stamp()})

    def robots(self, url, timing):
        p = up.urlsplit(url)
        origin = up.urlunsplit((p.scheme, p.netloc, "", "", ""))
        with self.host_locks[host(url)]:
            if origin not in self.robots_cache:
                t = time.perf_counter()
                try:
                    target = origin + "/robots.txt"
                    for _ in range(4):
                        code, heads, body = self.raw(target, timing, 512000)
                        if code in (301, 302, 303, 307, 308):
                            target = up.urljoin(target, heads.get("Location", heads.get("location", "")))
                            continue
                        break
                    if code in (404, 410):
                        decision = ("missing_allows", None)
                    elif code == 200 and b"<html" not in body[:500].lower():
                        parser = urllib.robotparser.RobotFileParser()
                        parser.parse(body.decode("utf-8", "replace").splitlines())
                        decision = ("parsed", parser)
                    else:
                        decision = ("unavailable_" + str(code), None)
                except StopFetch as e:
                    decision = ("unavailable_" + e.reason, None)
                self.robots_cache[origin] = decision
                timing["robots_seconds"] += time.perf_counter() - t
            state, parser = self.robots_cache[origin]
            if state == "parsed":
                if not parser.can_fetch(UA, url):
                    raise StopFetch("robots_disallowed")
            elif state != "missing_allows":
                raise StopFetch("robots_unknown_" + state)

    def get(self, url, timing, *, permit_aggregator=False):
        for _ in range(6):
            if restricted(url):
                raise StopFetch("metadata_only_source_policy")
            self.public(url, timing)
            self.robots(url, timing)
            code, headers, body = self.raw(url, timing)
            if code in (301, 302, 303, 307, 308):
                url = up.urljoin(url, headers.get("Location", headers.get("location", "")))
                continue
            if code != 200:
                raise StopFetch("http_" + str(code))
            charset = re.search(r"charset=([\w-]+)", headers.get("Content-Type", headers.get("content-type", "")), re.I)
            enc = charset.group(1) if charset else "utf-8"
            try:
                content = body.decode(enc)
            except (UnicodeDecodeError, LookupError):
                content = body.decode("utf-8", "replace")
            if host(url) in ("consent.google.com", "accounts.google.com"):
                raise StopFetch("aggregator_consent_or_login")
            if host(url) == "news.google.com" and not permit_aggregator:
                raise StopFetch("publisher_url_unresolved")
            return url, content, body, headers
        raise StopFetch("redirect_limit")

    def resolve(self, row, title_map, timing):
        if row["stratum"] != "google_wrapper":
            return row["url"], "known_publisher_url"
        key = text_key(re.split(r"\s[-–|]\s", row["title"])[0])
        if key in title_map:
            return title_map[key], "existing_title_exact_match"
        # Normal public redirect only. No private RPC, reverse engineering or proxy.
        try:
            final, content, _, _ = self.get(row["url"], timing, permit_aggregator=True)
            if host(final) != "news.google.com":
                return final, "public_http_redirect"
            soup = BeautifulSoup(content, "lxml")
            candidates = []
            for a in soup.find_all("a", href=True):
                u = up.urljoin(final, a["href"])
                if host(u) not in ("news.google.com", "www.google.com", "support.google.com", "policies.google.com") and title_ok(row["title"], a.get_text(" ", strip=True)):
                    candidates.append(u)
            if candidates:
                return candidates[0], "public_aggregator_anchor"
        except StopFetch as e:
            timing["resolution_note"] = e.reason
        homepage = row.get("publisher_homepage")
        if not homepage:
            return None, "publisher_homepage_unknown"
        h = host(homepage)
        with self.host_locks[h]:
            if homepage not in self.publisher_cache:
                links = []
                try:
                    final, content, _, _ = self.get(homepage, timing)
                    soup = BeautifulSoup(content, "lxml")
                    links += [(a.get_text(" ", strip=True), up.urljoin(final, a["href"])) for a in soup.find_all("a", href=True)]
                    feeds = [up.urljoin(final, a.get("href", "")) for a in soup.find_all("link") if a.get("type") in ("application/rss+xml", "application/atom+xml")][:2]
                    for feed in feeds:
                        try:
                            ff, xml, _, _ = self.get(feed, timing)
                            xs = BeautifulSoup(xml, "xml")
                            for item in xs.find_all(["item", "entry"]):
                                title, link = item.find("title"), item.find("link")
                                if title and link:
                                    links.append((title.get_text(), link.get("href") or link.get_text()))
                        except StopFetch:
                            pass
                except StopFetch as e:
                    timing["publisher_resolution_note"] = e.reason
                self.publisher_cache[homepage] = links
            for title, url in self.publisher_cache[homepage]:
                if title_ok(row["title"], title):
                    return url, "advertised_homepage_or_feed"
        return None, "publisher_link_not_found"


def paywall_reason(soup):
    text = soup.get_text(" ", strip=True)
    if soup.select_one("#mepr-paywall-block, .mepr-unauthorized-message, .blurred-fifth-paragraph"):
        return "registration_wall_detected"
    for script in soup.find_all("script", type="application/ld+json"):
        if re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")', script.get_text(), re.I):
            return "declared_paywall"
    main = soup.find("article") or soup.find("main")
    scope = main.get_text(" ", strip=True) if main else text
    if len(scope) < 3000 and re.search(r"subscribe to (?:read|continue)|to continue reading|sign in to read|enable javascript and cookies|verify you are human|checking your browser|access denied|just a moment", scope, re.I):
        return "access_or_subscription_prompt"
    return None


def restricted_syndication(text):
    """Explicit wire attribution, not an incidental reference to another outlet."""
    lead = text[:1800]
    return bool(re.search(r'AP is solely responsible for all content|Associated Press[’\x27] climate and environmental coverage receives',text[-2500:],re.I)
                or re.search(r'\((?:AP|Reuters)\)\s*[—–-]|\bby\s+(?:the\s+)?Associated Press\b|\boriginally published by\s+(?:Reuters|POLITICO|the Associated Press)\b', lead, re.I)
                or re.search(r'(?:copyright|©)\s*.{0,60}(?:Associated Press|Reuters|POLITICO)', text[-1800:], re.I))


def extract(content, expected_title, final_url, *, api=False, compare_alternative=True):
    """No length clipping. Return candidate text plus observable integrity signals."""
    soup = BeautifulSoup(content, "lxml")
    reason = paywall_reason(soup)
    if reason:
        raise StopFetch(reason)
    # A publisher logo/navigation can be the first h1. Compare actual headline
    # candidates instead of rejecting a valid article because of that logo.
    candidates=[]
    og = soup.find('meta',property='og:title')
    if og: candidates.append(og.get('content',''))
    candidates += [x.get_text(' ',strip=True) for x in soup.select('article h1, main h1')]
    if soup.title: candidates.append(soup.title.get_text(' ',strip=True))
    candidates += [x.get_text(' ',strip=True) for x in soup.find_all('h1')[:3]]
    page_title=next((x for x in candidates if title_ok(expected_title,x)), candidates[0] if candidates else '')
    if not title_ok(expected_title, page_title):
        raise StopFetch("page_title_mismatch_or_missing")
    for el in soup.select("script,style,nav,footer,form,aside,noscript,svg,[data-current-post-id],.related-posts,.related-articles,.newsletter,.share-buttons,.social-share,.author-bio,[data-component='links-block'],section.cards,article.g-card,blockquote.wp-embedded-content,.wp-block-query,.icn-donate-block,.icn-newsletter-block"):
        # Some malformed pages leave the navigation element unclosed around the
        # actual main article. Unwrap that ancestor instead of deleting the news.
        if el.find('main') is not None or el.select_one("[itemprop='articleBody'],article[id^='post-']") is not None:
            el.unwrap()
        else:
            el.decompose()
    articles = soup.find_all('article')
    body = max(articles,key=lambda x:len(x.get_text())) if articles else soup.find("main") or soup.body or soup
    explicit_body = bool(soup.find("article")) or api
    # Source-specific deterministic containers, drawn from observed HTML semantics.
    selectors = ("[itemprop='articleBody']", ".article-body-commercial-selector", ".entry-content", ".article-body", ".article-content", ".post-content", ".story-body", ".story__content", "section.gutenberg", ".detail-content")
    if host(final_url).removeprefix('www.') == 'whyy.org':
        selectors = ('.detail-content',) + selectors
    if host(final_url).removeprefix('www.') in ('news.cn','english.news.cn'):
        selectors = ('#detailContent',) + selectors
    if host(final_url).removeprefix('www.') in ('environewsnigeria.com','carboncredits.com'):
        # Observed TagDiv templates wrap related-news cards in <article>.
        selectors = ('.tdb_single_content.td-post-content',) + selectors
    if host(final_url).removeprefix('www.') == 'gov.uk':
        selectors = ('.gem-c-govspeak',) + selectors
    for selector in selectors:
        matches = soup.select(selector)
        match = max(matches, key=lambda el: len(el.get_text(" ", strip=True))) if matches else None
        if match and len(match.get_text(" ", strip=True)) >= 250:
            body = match
            explicit_body = True
            break
    if host(final_url).endswith("canarymedia.com"):
        # Its public story is split into multiple prose blocks by an ad slot.
        # Selecting only the first/longest block would lose half the article.
        prose = [x for x in soup.select(".prose:not(.prose-sans)") if len(x.get_text(" ", strip=True)) >= 200]
        if prose:
            body = BeautifulSoup("<article>" + "".join(str(x) for x in prose) + "</article>", "lxml").article
            explicit_body = True
    for el in body.select("script,style,nav,footer,form,aside,noscript,svg,.related-posts,.related-articles,.newsletter,.share-buttons,.social-share,.author-bio,.icn-donate-block,.icn-newsletter-block"):
        el.decompose()
    if host(final_url).removeprefix('www.') in ('bbc.co.uk','bbc.com'):
        for el in body.select('.visually-hidden'):
            if re.sub(r'\s+',' ',el.get_text()).strip().lower() in (', external','external'):
                el.decompose()
    if host(final_url).removeprefix('www.') == 'phys.org':
        for el in body.select('.author-card'):
            el.decompose()
    if host(final_url).removeprefix('www.') == 'scitechdaily.com':
        for el in body.find_all('p'):
            if el.get_text(' ',strip=True).startswith('Never miss a breakthrough:'):
                el.decompose()
    nodes = body.find_all(["p", "h2", "h3", "h4", "li", "table", "figcaption"])
    blocks = []
    for node in nodes:
        if node.find_parent(["table", "li", "figcaption"]) is not None:
            continue
        # Preserve inline spelling (e.g. a drop-cap E + urope and CO + subscript 2).
        # Table cell boundaries still require a separator.
        value = re.sub(r"\s+", " ", node.get_text(" " if node.name == "table" else "", strip=False)).strip()
        if re.match(r"^(?:This story is funded by readers like you|Explore the world of impactful news with CitiNewsroom on WhatsApp|Sign up to receive our alerts directly in your inbox)",value,re.I):
            # Such calls-to-action can occur MID-ARTICLE. Never use their text
            # as a terminal boundary; remove the component/line and continue.
            continue
        if node.name in ('h2','h3','h4') and value.casefold() in ('related content','related articles','related stories') and len(' '.join(blocks))>400:
            break
        if re.match(r"^(?:As a nonprofit organization, we rely on financial support|WHYY is your source for fact-based)",value,re.I):
            continue
        if value.casefold() in ("related topics", "more on this story") and len(" ".join(blocks)) > 400:
            break
        if value.casefold() in ("back to top", "credits", "topics"):
            continue
        if re.match(r"^(?:FEEDBACK:|See related from this reporter:|Related reading:)", value, re.I):
            continue
        if value:
            blocks.append(value)
    reference = "\n\n".join(blocks)
    extracted = (trafilatura.extract(str(soup), url=final_url, include_comments=False, include_tables=True,
                                    include_formatting=False, include_links=False, favor_recall=True,
                                    deduplicate=False, output_format="txt") or "") if (compare_alternative or not explicit_body or len(reference)<400) else ""
    # Explicit article DOM preserves short paragraphs, tables and captions.
    method = "semantic_article_dom" if explicit_body and len(reference) >= 400 else "trafilatura_recall"
    text = reference if method == "semantic_article_dom" else extracted
    if len(text) < 300:
        raise StopFetch("insufficient_article_text")
    if re.search(r'This website uses the following additional cookies',text[:300],re.I):
        raise StopFetch('non_article_cookie_boilerplate')
    # Diagnostic coverage uses source blocks, not an independent human gold standard.
    expected = [x for x in blocks if len(x) >= 35]
    normalized = re.sub(r"\s+", " ", text)
    present = [re.sub(r"\s+", " ", x) in normalized for x in expected]
    coverage = sum(present) / len(present) if present else None
    pagination = any((a.get("rel") and "next" in a.get("rel")) or re.search(r"next page|下一页", a.get_text(" ", strip=True), re.I) for a in body.find_all("a", href=True))
    flags = []
    if pagination:
        flags.append("possible_article_pagination_not_followed")
    if "\ufffd" in text:
        flags.append("unicode_replacement_character")
    if not explicit_body:
        flags.append("no_explicit_article_container")
    if re.search(r"(?:let|const)\s+\w+\s*=|function\s*\(|=>|scrolledValue|\{\s*\"[a-z_]+\"\s*:", text):
        flags.append("possible_script_or_serialized_data_noise")
    if coverage is not None and coverage < .9:
        flags.append("source_block_coverage_below_90pct")
    if not text.rstrip().endswith((".", "!", "?", '"', "”", "’", ")", "]", "。", "！", "？", ":", "）", "」", "』", "»", "■")):
        flags.append("last_block_needs_review")
    if restricted_syndication(text):
        raise StopFetch("metadata_only_syndicated_source_policy")
    return text, {"extraction_method": method, "page_title": page_title, "title_match": True,
                  "source_blocks": len(expected), "source_block_coverage": coverage,
                  "first_block_present": present[0] if present else None,
                  "last_block_present": present[-1] if present else None,
                  "trafilatura_characters": len(extracted) if compare_alternative else None, "alternative_extractor_run": compare_alternative, "semantic_dom_characters": len(reference),
                  "words": len(re.findall(r"\b\w+\b", text)), "paragraphs": len(text.split("\n\n")),
                  "completeness_flags": flags, "status": "candidate_complete" if not flags else "needs_completeness_review",
                  "completeness_basis": "automatic source-DOM checks, not independent human validation"}


def perform(row, fetcher, title_map):
    started = time.perf_counter()
    timing = {k: 0.0 for k in ("dns_seconds", "robots_seconds", "network_seconds", "rate_wait_seconds", "resolve_seconds", "fetch_seconds", "extract_seconds", "validate_seconds", "store_seconds")}
    timing.update(request_count=0, response_bytes=0)
    result = {**row, "started_at": stamp(), "status": "unattempted", "parser_version": trafilatura.__version__, "timing": timing}
    raw, text = None, None
    active_stage, stage_start = "resolve_seconds", time.perf_counter()
    try:
        t = time.perf_counter()
        url, route = fetcher.resolve(row, title_map, timing)
        result["resolution_method"] = route
        timing["resolve_seconds"] = time.perf_counter() - t
        active_stage, stage_start = "fetch_seconds", time.perf_counter()
        if not url:
            raise StopFetch("publisher_url_unresolved")
        result["publisher_url"] = url
        if restricted(url):
            raise StopFetch("metadata_only_source_policy")
        t = time.perf_counter()
        content, page_url, api_used = None, url, False
        if row.get("api_endpoint"):
            # Endpoint was advertised and recorded by the existing archive importer.
            endpoint = row["api_endpoint"]
            post_id = row.get("archive_post_id")
            request_url = endpoint.rstrip("/") + "/" + str(post_id) if post_id else endpoint + "?" + up.urlencode({"slug": up.urlsplit(url).path.rstrip("/").split("/")[-1], "per_page": 5})
            try:
                _, api_content, api_raw, _ = fetcher.get(request_url, timing)
                data = json.loads(api_content)
                posts = data if isinstance(data, list) else [data]
                selected = next((p for p in posts if title_ok(row["title"], html.unescape(p.get("title", {}).get("rendered", "")))), None)
                if selected:
                    if selected.get("content", {}).get("protected"):
                        raise StopFetch("api_protected_content")
                    rendered = selected.get("content", {}).get("rendered", "")
                    if len(BeautifulSoup(rendered, "lxml").get_text()) >= 300:
                        title = selected.get("title", {}).get("rendered", "")
                        content = "<html><head><title>" + title + "</title></head><body><h1>" + title + "</h1><article>" + rendered + "</article></body></html>"
                        page_url = selected.get("link") or url
                        # API content link must correspond to the requested publisher page.
                        if host(page_url) != host(url) or up.urlsplit(page_url).path.rstrip("/") != up.urlsplit(url).path.rstrip("/"):
                            raise StopFetch("api_identity_mismatch")
                        raw, api_used = api_raw, True
                        result["api_request_url"] = request_url
            except (StopFetch, ValueError, KeyError, TypeError) as e:
                result["api_fallback_note"] = e.reason if isinstance(e, StopFetch) else type(e).__name__
        if content is None:
            page_url, content, raw, _ = fetcher.get(url, timing)
        timing["fetch_seconds"] = time.perf_counter() - t
        active_stage, stage_start = "extract_seconds", time.perf_counter()
        t = time.perf_counter()
        text, details = extract(content, row["title"], page_url, api=api_used)
        timing["extract_seconds"] = time.perf_counter() - t
        active_stage, stage_start = "validate_seconds", time.perf_counter()
        t = time.perf_counter()
        result.update(details)
        result.update(publisher_url=page_url, api_used=api_used,
                      text_sha256=digest(text.encode("utf-8")), text_characters=len(text),
                      text_utf8_bytes=len(text.encode("utf-8")), text_gzip_bytes=len(gzip.compress(text.encode("utf-8"), mtime=0)),
                      raw_response_bytes=len(raw), rights_status="private_research_copy_permission_not_established_for_redistribution",
                      public_redistribution_allowed=False, translated=False, manual_review="not_independently_reviewed")
        timing["validate_seconds"] = time.perf_counter() - t
        active_stage, stage_start = "store_seconds", time.perf_counter()
        t = time.perf_counter()
        PRIVATE.mkdir(parents=True, exist_ok=True)
        (PRIVATE / "articles").mkdir(exist_ok=True)
        doc = {k: v for k, v in result.items() if k != "timing"}
        doc["source_text"] = text
        (PRIVATE / "articles" / (row["id"] + ".json")).write_bytes(jsonbytes(doc))
        (PRIVATE / "raw").mkdir(exist_ok=True)
        (PRIVATE / "raw" / (row["id"] + ".response.gz")).write_bytes(gzip.compress(raw, mtime=0))
        timing["store_seconds"] = time.perf_counter() - t
    except StopFetch as e:
        if not timing[active_stage]:
            timing[active_stage] = time.perf_counter() - stage_start
        result["status"] = e.reason
    except Exception as e:
        result["status"] = "unexpected_" + type(e).__name__
    finally:
        # Ensure failed stage durations are not silently zero when a timeout occurred.
        finished = time.perf_counter()
        timing["total_seconds"] = finished - started
        result["finished_at"] = stamp()
        for k in list(timing):
            if isinstance(timing[k], float):
                timing[k] = round(timing[k], 6)
    return result


def input_hashes():
    paths = [ROOT / "data/climate_text_corpus.jsonl", ROOT / "data/news_archive.json", ROOT / "data/research_texts.jsonl.gz", ROOT / "data/climate.db"]
    return {str(p.relative_to(ROOT)): {"bytes": p.stat().st_size, "sha256": digest(p.read_bytes())} for p in paths if p.exists()}


def run(*, supplement=False):
    OUT.mkdir(parents=True, exist_ok=True)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    before = input_hashes()
    if (OUT / "input_before.json").exists():
        prior = json.loads((OUT / "input_before.json").read_text("utf-8"))
        if before != prior:
            raise RuntimeError("Source inputs changed since frozen sample: do not resume over a different population")
    else:
        dump(OUT / "input_before.json", before)
    frame, title_map, population = make_frame()
    if (OUT / "sample.json").exists():
        sample = json.loads((OUT / "sample.json").read_text("utf-8"))
    else:
        sample = select_sample(frame)
        dump(OUT / "sample.json", sample)
        dump(OUT / "population.json", population)
        dump(OUT / "population_frame.json", frame)
    dump(OUT / "runtime.json", {"python": platform.python_version(), "platform": platform.platform(),
                              "trafilatura": trafilatura.__version__, "beautifulsoup4": importlib.metadata.version("beautifulsoup4"),
                              "lxml": importlib.metadata.version("lxml"), "workers": WORKERS, "same_host_gap_seconds": GAP,
                              "request_timeout_seconds": TIMEOUT, "response_cap_bytes": CAP, "retries": 0,
                              "seed": SEED, "started_at": stamp(), "translation": False, "model_requests": 0,
                              "browser_rendering": "not enabled; blocked/dynamic failures remain explicit, no access-control bypass"})
    old = load_lines(OUT / "attempts.jsonl")
    done = {x["id"] for x in old}
    if supplement:
        # Additional bodies serve the requested 100-document deliverable, NOT the
        # probability-sample success-rate estimate. Keep all failed initial targets.
        available = [x for x in frame if x["id"] not in done and x["stratum"] == "public_wordpress"]
        buckets = collections.defaultdict(list)
        for x in sorted(available, key=lambda r: digest((SEED + "supplement" + r["id"]).encode())):
            buckets[host(x["url"])].append(x)
        queue = []
        while any(buckets.values()):
            for h in sorted(buckets):
                if buckets[h]:
                    x = buckets[h].pop(0)
                    queue.append({**x, "sample_group": "supplementary_collection", "inclusion_probability": None, "design_weight": None})
        needed = max(0, 100 - len(list((PRIVATE / "articles").glob("*.json"))))
        sample = queue[:needed]
        dump(OUT / ("supplement_sample_" + str(len(old)) + ".json"), sample)
    remaining = [x for x in sample if x["id"] not in done]
    fetcher = Fetcher()
    t = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(perform, r, fetcher, title_map): r for r in remaining}
        with (OUT / "attempts.jsonl").open("a", encoding="utf-8") as f:
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()
                old.append(result)
                if len(old) % 10 == 0:
                    print(json.dumps({"completed": len(old), "statuses": dict(collections.Counter(r["status"] for r in old)), "wall_seconds_this_run": round(time.perf_counter() - t, 1)}, ensure_ascii=False), flush=True)
    elapsed = time.perf_counter() - t
    previous_runs = json.loads((OUT / "run_times.json").read_text("utf-8")) if (OUT / "run_times.json").exists() else []
    previous_runs.append({"completed_at": stamp(), "targets_this_run": len(remaining), "wall_seconds": elapsed, "requests": len(fetcher.requests)})
    dump(OUT / "run_times.json", previous_runs)
    existing_requests = json.loads((OUT / "requests.json").read_text("utf-8")) if (OUT / "requests.json").exists() else []
    dump(OUT / "requests.json", existing_requests + fetcher.requests)
    dump(OUT / "robots_audit.json", {origin: {"state": state, "rules": {k: v for k, v in vars(parser).items() if k in ("allow_all", "disallow_all")}} if parser else {"state": state} for origin, (state, parser) in fetcher.robots_cache.items()})
    after = input_hashes()
    dump(OUT / "input_integrity.json", {"unchanged": before == after, "before": before, "after": after})
    summarize()


def reextract():
    """Reprocess saved public responses after fixture-based parser fixes; no network."""
    rows = load_lines(OUT / "attempts.jsonl")
    prior = OUT / "attempts_initial_parser.jsonl"
    if not prior.exists():
        prior.write_bytes((OUT / "attempts.jsonl").read_bytes())
    audit = []
    for row in rows:
        article_path = PRIVATE / "articles" / (row["id"] + ".json")
        raw_path = PRIVATE / "raw" / (row["id"] + ".response.gz")
        if not raw_path.exists():
            continue
        t = time.perf_counter()
        raw = gzip.decompress(raw_path.read_bytes())
        content = raw.decode("utf-8", "replace")
        if row.get("api_used"):
            value = json.loads(content)
            posts = value if isinstance(value, list) else [value]
            p = next(p for p in posts if title_ok(row["title"], html.unescape(p.get("title", {}).get("rendered", ""))))
            title = p["title"]["rendered"]
            content = "<html><head><title>" + title + "</title></head><body><h1>" + title + "</h1><article>" + p["content"]["rendered"] + "</article></body></html>"
        try:
            text, details = extract(content, row["title"], row["publisher_url"], api=row.get("api_used", False))
            row.update(details)
            row.update(text_sha256=digest(text.encode("utf-8")), text_characters=len(text), text_utf8_bytes=len(text.encode("utf-8")), text_gzip_bytes=len(gzip.compress(text.encode("utf-8"), mtime=0)))
            doc = {k: v for k, v in row.items() if k != "timing"}
            doc["source_text"] = text
            article_path.write_bytes(jsonbytes(doc))
        except StopFetch as e:
            row["status"] = e.reason
            for k in ("text_characters", "text_utf8_bytes", "text_gzip_bytes", "text_sha256"):
                row.pop(k, None)
            # These files are newly created pilot outputs only, never source inputs.
            # Do not retain hidden registration-wall text accidentally present in HTML.
            for p in (article_path, raw_path):
                if p.exists() and PRIVATE.resolve() in p.resolve().parents:
                    p.unlink()
            row["discarded_new_private_response"] = True
        audit.append({"id": row["id"], "seconds": time.perf_counter() - t, "final_status": row["status"]})
    (OUT / "attempts.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), "utf-8")
    history_path = OUT / "reextraction_history.json"
    history = json.loads(history_path.read_text("utf-8")) if history_path.exists() else []
    history.append({"at": stamp(), "rows": audit})
    dump(history_path, history)
    dump(OUT / "reextraction_audit.json", audit)
    summarize()


def summarize():
    attempts = load_lines(OUT / "attempts.jsonl")
    population = json.loads((OUT / "population.json").read_text("utf-8"))
    by_id = {x["id"]: x for x in attempts}
    docs = []
    for p in sorted((PRIVATE / "articles").glob("*.json")):
        doc = json.loads(p.read_text("utf-8"))
        doc.update({k: v for k, v in by_id.get(doc["id"], {}).items() if k in ("manual_review", "status", "completeness_flags", "review_notes")})
        docs.append(doc)
    plain = b"".join(jsonbytes(d) + b"\n" for d in docs)
    (PRIVATE / "fulltexts.jsonl").write_bytes(plain)
    (PRIVATE / "fulltexts.jsonl.gz").write_bytes(gzip.compress(plain, mtime=0))
    bodies = b"\n\n".join(d["source_text"].encode("utf-8") for d in docs)
    success = {"candidate_complete", "verified_complete", "needs_completeness_review", "verified_partial"}
    representative = [r for r in attempts if r["sample_group"] == "representative"]
    strata = []
    estimate_seconds = estimate_body = estimate_fulljson = estimate_complete = estimate_gzip = estimate_stored = 0.0
    for s, n in population["strata"].items():
        rows = [r for r in representative if r["stratum"] == s]
        got = [r for r in rows if r["status"] in success]
        complete = [r for r in rows if r["status"] in ("candidate_complete", "verified_complete")]
        mean = lambda key: sum(r["timing"].get(key, 0) for r in rows) / len(rows) if rows else None
        complete_rate = len(complete) / len(rows) if rows else None
        texts_mean = sum(r.get("text_utf8_bytes", 0) for r in rows) / len(rows) if rows else None
        gzip_mean = sum(r.get("text_gzip_bytes", 0) for r in rows) / len(rows) if rows else None
        # Failed requests consume time but contribute no saved text bytes.
        estimate_seconds += n * (mean("total_seconds") or 0)
        estimate_body += n * (texts_mean or 0)
        estimate_gzip += n * (gzip_mean or 0)
        estimate_complete += n * (complete_rate or 0)
        json_mean = sum(len(jsonbytes(d)) + 1 for d in docs if d["id"] in {r["id"] for r in rows}) / len(rows) if rows else None
        estimate_fulljson += n * (json_mean or 0)
        estimate_stored += n * (len(got) / len(rows) if rows else 0)
        strata.append({"stratum": s, "population": n, "sample_n": len(rows), "text_extracted": len(got),
                       "candidate_or_reviewed_complete": len(complete), "complete_rate": complete_rate,
                       "mean_target_seconds": mean("total_seconds"), "mean_network_seconds": mean("network_seconds"),
                       "mean_text_bytes_per_attempt": texts_mean, "mean_individual_gzip_bytes_per_attempt": gzip_mean,
                       "statuses": dict(collections.Counter(r["status"] for r in rows))})
    times = json.loads((OUT / "run_times.json").read_text("utf-8"))
    stage_keys = ["resolve_seconds", "fetch_seconds", "extract_seconds", "validate_seconds", "store_seconds", "robots_seconds", "dns_seconds", "network_seconds", "rate_wait_seconds", "total_seconds"]
    stages = {k: {"sum": sum(r["timing"].get(k, 0) for r in attempts), "mean": statistics.mean(r["timing"].get(k, 0) for r in attempts), "median": statistics.median(r["timing"].get(k, 0) for r in attempts), "p95": sorted(r["timing"].get(k, 0) for r in attempts)[math.ceil(.95 * len(attempts))-1]} for k in stage_keys}
    storage = {"extracted_articles": len(docs), "text_only_utf8_bytes": len(bodies), "text_only_gzip_bytes": len(gzip.compress(bodies, mtime=0)),
               "full_jsonl_bytes": len(plain), "full_jsonl_gzip_bytes": len(gzip.compress(plain, mtime=0)),
               "individual_raw_response_bytes": sum(d.get("raw_response_bytes", 0) for d in docs),
               "raw_responses_gzip_bytes": sum(p.stat().st_size for p in (PRIVATE / "raw").glob("*.gz")),
               "duplicate_text_hashes": len(docs) - len({d["text_sha256"] for d in docs})}
    out = {"generated_at": stamp(), "population": population, "attempted": len(attempts),
           "statuses": dict(collections.Counter(r["status"] for r in attempts)),
           "representative_statuses": dict(collections.Counter(r["status"] for r in representative)),
           "stress_statuses": dict(collections.Counter(r["status"] for r in attempts if r["sample_group"] == "stress")),
           "wall_seconds": sum(r["wall_seconds"] for r in times), "network_requests": sum(r["requests"] for r in times),
           "stages": stages, "storage": storage, "strata": strata,
           "projection": {"one_pass_target_service_seconds": estimate_seconds,
                          "ideal_four_worker_hours": estimate_seconds / WORKERS / 3600,
                          "serial_service_hours": estimate_seconds / 3600,
                          "estimated_candidates_complete": estimate_complete,
                          "estimated_texts_stored": estimate_stored,
                          "estimated_utf8_body_bytes_observed_access": estimate_body,
                          "estimated_individual_gzip_body_bytes_observed_access": estimate_gzip,
                          "estimated_jsonl_bytes_observed_access": estimate_fulljson,
                          "all_accessible_scenario_body_bytes": population["unique_known_url_groups"] * (len(bodies) / len(docs) if docs else 0),
                          "all_accessible_scenario_gzip_body_bytes": population["unique_known_url_groups"] * (len(gzip.compress(bodies, mtime=0)) / len(docs) if docs else 0),
                          "method": "Population-stratum expansion of the 80 probability-sampled attempts, not the 20 stress tests. Four-worker figure is an ideal service-time division, not a wall-time guarantee. All-accessible scenario uses successful sample body size and is not a completeness prediction."},
           "old_data_unchanged": json.loads((OUT / "input_integrity.json").read_text("utf-8"))["unchanged"]}
    dump(OUT / "summary.json", out)
    columns = ["id", "sample_group", "stratum", "source", "date", "title", "status", "manual_review", "text_characters", "text_utf8_bytes", "text_gzip_bytes", "publisher_url", "url", "resolution_method"]
    with (OUT / "attempts.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns + stage_keys)
        writer.writeheader()
        for r in attempts:
            writer.writerow({**{k: r.get(k) for k in columns}, **{k: r["timing"].get(k) for k in stage_keys}})
    print(json.dumps({"attempted": len(attempts), "statuses": out["statuses"], "storage": storage, "wall_seconds": out["wall_seconds"], "old_data_unchanged": out["old_data_unchanged"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--supplement", action="store_true")
    parser.add_argument("--reextract", action="store_true")
    args = parser.parse_args()
    if args.reextract:
        reextract()
    elif args.summarize:
        summarize()
    else:
        run(supplement=args.supplement)

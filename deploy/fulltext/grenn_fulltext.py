#!/usr/bin/env python3
"""GRENN full-text climate news archive: crawl full text and article images (local research copy).

Covers the sources of config/sources.master.json (discovery adapters in sources.json next to this file)
over the last five years, plus a COP1-COP31 history pass (cops.json). Each article page is fetched once,
its main text and article images are extracted, and the original project's quality rules are applied:
  - source scope gates (sync._source_scope_match) and the Google News exclusion terms;
  - climate relevance (research_archives.CORE, sync.CLIMATE_SIGNAL_TERMS, config/keywords.yml topics,
    ambiguous phrases such as "business climate" removed first);
  - substantive text (research.substantive), page title verification (research.title_matches),
    publication date required, no future dates, URL / text-hash de-duplication;
  - METADATA_ONLY_HOSTS are never fetched; robots.txt (and Crawl-delay) for every host; one request
    per host at a time; 401/403/429 back off and stop the host; CAPTCHA / paywalls are never bypassed.
Tags reuse the original taxonomy (topics, numbers, relevance score, ISO countries, organisations) plus COP tags.

Data: $GRENN_FULLTEXT_DIR (default GRENN/.fulltext/data): fulltext.db (SQLite, WAL) and images/<sha[:2]>/.
Full text and images are for internal research only: never publish them in /downloads/.
Network: $GRENN_PROXY (default http://127.0.0.1:7897, "" = none) for foreign hosts, direct for .cn.

Commands: run · test SOURCE · status · export.  Run with -h for options.  Every command is resumable.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html as htmllib
import http.client
import io
import json
import logging
import os
import re
import shutil
import signal
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

import trafilatura  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from lxml import etree  # noqa: E402
from PIL import Image  # noqa: E402

from climate_agent.article_content import METADATA_ONLY_HOSTS  # noqa: E402
from climate_agent.collector import NormalizedArticle, parse_feed  # noqa: E402
from climate_agent.pipeline import normalize_url, stable_id  # noqa: E402
from climate_agent.research import substantive, title_key, title_matches  # noqa: E402
from climate_agent.research_archives import CORE  # noqa: E402
from climate_agent.sync import CLIMATE_SIGNAL_TERMS, GOOGLE_NEWS_EXCLUDE_TERMS, _analyse, _source_scope_match  # noqa: E402
from climate_agent.taxonomy import country_codes_for, organization_tags_for  # noqa: E402

DATA = Path(os.environ.get("GRENN_FULLTEXT_DIR") or REPO.parent / ".fulltext" / "data")
DB_PATH = DATA / "fulltext.db"
IMAGES = DATA / "images"
LOGS = DATA / "logs"
PROXY = os.environ.get("GRENN_PROXY", "http://127.0.0.1:7897")
UA = "GRENN-ClimateNewsArchive/1.0 (+https://zerocarbonx.cn/; climate news research archive)"
TODAY = datetime.now(UTC).date()
START = TODAY.replace(year=TODAY.year - 5)
INTERVAL = {"page": 1.5, "api": 2.0, "image": 0.25, "gdelt": 6.0}
ACCEPT = {"page": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5", "api": "application/json, application/xml, text/xml;q=0.9, */*;q=0.5",
          "image": "image/avif,image/webp,image/jpeg,image/png,image/*;q=0.8", "gdelt": "application/json"}
PAGE_MAX, API_MAX, IMG_MAX = 8_000_000, 60_000_000, 10_000_000
MAX_IMAGES = 8
MIN_FREE_GB = float(os.environ.get("GRENN_FULLTEXT_MIN_FREE_GB", "25"))
MAX_ATTEMPTS = 3
RIGHTS = "full_text_internal_research_only"

log = logging.getLogger("fulltext")

# ---------------------------------------------------------------- configuration


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


MASTER = {s["source_id"]: s for s in load_json(REPO / "config" / "sources.master.json")}
ADAPTERS = load_json(HERE / "sources.json")
COPS = load_json(HERE / "cops.json")["cops"]
for _c in COPS:
    _c["d_start"], _c["d_end"] = date.fromisoformat(_c["start"]), date.fromisoformat(_c["end"])
    _c["win"] = (_c["d_start"] - timedelta(days=45), _c["d_end"] + timedelta(days=30))  # tagging window
    _c["disc"] = (_c["d_start"] - timedelta(days=30), _c["d_end"] + timedelta(days=21))  # discovery window


def keyword_terms() -> tuple[list[str], list[str]]:
    """Topic terms (en/tr/zh) and ambiguous phrases from config/keywords.yml (flat lists; no YAML library needed)."""
    terms, ambiguous, section = [], [], ""
    for line in (REPO / "config" / "keywords.yml").read_text(encoding="utf-8").splitlines():
        if re.match(r"^\S", line):
            section = line.split(":")[0]
        m = re.match(r"^\s+(?:en|tr|zh):\s*\[(.*)\]\s*$", line)
        if m:
            items = [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
            (terms if section == "topics" else ambiguous if section == "exclude_or_downrank" else []).extend(items)
    return terms, ambiguous


_TOPIC_TERMS, _AMBIGUOUS = keyword_terms()


def _term_regex(terms) -> re.Pattern:
    parts = []
    for t in sorted({t.lower() for t in terms if len(t) > 1}, key=len, reverse=True):
        e = re.escape(t)
        parts.append(rf"(?<![a-z0-9]){e}" if re.match(r"[a-z0-9]", t) else e)
    return re.compile("|".join(parts), re.I)


BROAD = _term_regex([*CLIMATE_SIGNAL_TERMS, *_TOPIC_TERMS])
STRONG = re.compile(CORE.pattern + r"|\bcop\s?-?\d{1,2}\b|unfccc|ipcc\b|iklim|karbon|emisyon|sera gaz|küresel ısınma|fosil|kömür|termik"
                    r"|yenilenebilir|güneş enerjisi|rüzgar enerjisi|kuraklık|气候|碳排放|碳中和|碳达峰|减排|温室气体|可再生能源|新能源|低碳|净零"
                    r"|全球变暖", re.I)
AMBIGUOUS = _term_regex(_AMBIGUOUS + ["climate of fear", "climate of uncertainty", "economic climate", "current climate"])
EXCLUDE_TITLE = _term_regex(GOOGLE_NEWS_EXCLUDE_TERMS)


def relevant(text: str, scope: str) -> bool:
    """dedicated outlets: one climate/topic term; general outlets: a core climate term or two distinct topic terms."""
    t = AMBIGUOUS.sub(" ", text or "")
    if STRONG.search(t):
        return True
    hits = {m.group(0).lower() for m in BROAD.finditer(t)}
    return len(hits) >= (1 if scope == "dedicated" else 2)


# ---------------------------------------------------------------- COP tags

_CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_number(s: str) -> int:
    if s.isdigit():
        return int(s)
    total = 0
    if "十" in s:
        head, _, tail = s.partition("十")
        total = (_CN_DIGITS.get(head, 1) if head else 1) * 10 + (_CN_DIGITS.get(tail, 0) if tail else 0)
    else:
        total = _CN_DIGITS.get(s, 0)
    return total


COP_EXPLICIT = re.compile(r"\bCOP\s?-?(\d{1,2})\b|\b(\d{1,2})(?:st|nd|rd|th)\s+(?:session\s+of\s+the\s+)?Conference\s+of\s+the\s+Parties"
                          r"|第\s*([0-9一二三四五六七八九十]{1,3})\s*届(?:联合国)?气候(?:变化)?(?:大会|缔约方大会)", re.I)
NOT_CLIMATE_COP = re.compile(r"biodivers|\bCBD\b|biological diversity|Kunming|desertif|UNCCD|\bCITES\b|wetland|Ramsar|Montreal Protocol"
                             r"|Basel Convention|Stockholm Convention|Minamata|tobacco|FCTC|Yerevan|Erivan|Armenia|\bCali\b|Riyadh|Ulaanbaatar"
                             r"|30 ?x ?30|30 ?by ?30|NBSAP|Global Biodiversity Framework|nature (?:summit|target|pledges?|deal|finance|conference)"
                             r"|生物多样性|荒漠化|湿地|biyoçeşitlilik|biyolojik çeşitlilik|çölleşme|doğa koruma", re.I)
COP_BY_N = {c["n"]: c for c in COPS}


def climate_cop_mention(n: int, text: str, start: int, end: int, published: date | None) -> bool:
    """Other conventions reuse the numbers (CBD COP15-17 in 2022-26, UNCCD COP15-17 in 2022-26): three years after a climate
    COP, its bare number counts only with its host city, its year or climate wording nearby."""
    near = text[max(0, start - 60): end + 60]
    if NOT_CLIMATE_COP.search(near):
        return False
    c = COP_BY_N[n]
    if published and published.year >= c["year"] + 3:
        wide = text[max(0, start - 120): end + 120]
        city = re.escape(c["city"]).replace("ó", "[oó]").replace("é", "[eé]").replace("ú", "[uú]").replace("ń", "[nń]")
        return bool(re.search(rf"{city}|{c['year']}|climate|UNFCCC|气候|iklim|klima", wide, re.I))
    return True
COP_GENERIC = re.compile(r"U\.?N\.? climate (?:summit|talks|conference|negotiations)|climate (?:summit|talks|conference|negotiations)"
                         r"|UNFCCC|Conference of the Parties|联合国气候变化大会|气候大会|气候谈判|iklim zirvesi|taraflar konferansı|iklim müzakere", re.I)
COP_OUTCOMES = [(c["n"], re.compile("|".join(re.escape(x) for x in c["outcomes"]), re.I)) for c in COPS if c["outcomes"]]
COP_ALIASES = [(c, re.compile("|".join(re.escape(x) for x in c["aliases"]), re.I)) for c in COPS if c["aliases"]]


def cop_tags(text: str, published: date | None) -> list[str]:
    """COPn mentions anywhere (not biodiversity/desertification COPs); outcome names anywhere; host-city phrases and
    generic 'climate summit' wording only inside that COP's news window."""
    found: set[int] = set()
    text = text or ""
    # an article about a biodiversity / desertification COP: its bare COPn mentions need climate wording next to them
    other_cop = bool(NOT_CLIMATE_COP.search(text[:600]))
    for m in COP_EXPLICIT.finditer(text):
        n = int(m.group(1) or m.group(2) or 0) if (m.group(1) or m.group(2)) else _cn_number(m.group(3))
        if not 1 <= n <= 31 or not climate_cop_mention(n, text, m.start(), m.end(), published):
            continue
        if other_cop and not re.search(r"climate|UNFCCC|气候|iklim", text[max(0, m.start() - 60): m.end() + 60], re.I):
            continue
        found.add(n)
    for n, rx in COP_OUTCOMES:
        if rx.search(text or ""):
            found.add(n)
    if published:
        generic = [m for m in COP_GENERIC.finditer(text)
                   if not other_cop or re.search(r"climate|UNFCCC|气候|iklim", text[max(0, m.start() - 80): m.end() + 80], re.I)]
        for c in (c for c in COPS if c["win"][0] <= published <= c["win"][1]):
            if any(rx.search(text) for cc, rx in COP_ALIASES if cc is c) or generic:
                found.add(c["n"])
    return [f"COP{n}" for n in sorted(found)]


def discovery_ranges(cop: bool, around: tuple[int, int] | None = None) -> list[tuple[date, date, str]]:
    """Newest first: the five-year range in yearly slices, then COP windows that lie before it."""
    ranges, hi = [], TODAY
    while hi >= START:
        lo = max(START, hi.replace(year=hi.year - 1) + timedelta(days=1))
        ranges.append((lo, hi, "5y"))
        hi = lo - timedelta(days=1)
    if cop:
        for c in sorted(COPS, key=lambda c: -c["n"]):
            lo, hi = c["disc"]
            if around:
                lo, hi = c["d_start"] + timedelta(days=around[0]), c["d_end"] + timedelta(days=around[1])
            hi = min(hi, START - timedelta(days=1))
            if lo <= hi:
                ranges.append((lo, hi, f"cop{c['n']}"))
    return ranges


def in_ranges(d: date, ranges) -> str | None:
    for lo, hi, scope in ranges:
        if lo <= d <= hi:
            return scope
    return None


# ---------------------------------------------------------------- small helpers

EMAIL = re.compile(r"[A-Za-z0-9.!#$%&*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
CREDENTIAL = re.compile(r"\b(?:AIza[\w-]{30,}|sk-[\w-]{24,})\b")
PAYWALL = re.compile(r"subscribe (?:now )?to (?:continue|read)|(?:only )?available (?:only )?to (?:paying )?subscribers|already a subscriber"
                     r"|sign in to (?:continue|read)|to continue reading,? (?:please )?(?:log ?in|subscribe)|this content is for (?:paid )?members", re.I)
BLOCKED_PAGE = re.compile(r"access denied|enable javascript|verify you are human|just a moment|attention required|are you a robot", re.I)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def squash(s) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(str(s or ""))).strip()


def redact(s: str) -> str:
    return CREDENTIAL.sub("[credential redacted]", EMAIL.sub("[email redacted]", s))


def html_text(fragment) -> str:
    return squash(BeautifulSoup(str(fragment or ""), "lxml").get_text(" ")) if fragment else ""


def parse_dt(value) -> datetime | None:
    if not value:
        return None
    s = str(value).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(s)
        except (TypeError, ValueError, IndexError):
            m = re.match(r"(\d{4})-?(\d{2})-?(\d{2})", s)
            if not m:
                return None
            try:
                dt = datetime(int(m[1]), int(m[2]), int(m[3]))
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def title_verified(listed: str, page_title: str) -> bool:
    """research.title_matches, or the shorter title's words (>= 80%) contained in the longer one:
    listing anchors often carry the headline plus a kicker or standfirst."""
    if title_matches(listed, page_title):
        return True
    a, b = (set(re.findall(r"\w{3,}", s.lower())) for s in (listed, page_title))
    short = min(a, b, key=len)
    return len(short) >= 2 and len(a & b) >= 0.8 * len(short)


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def same_site(a: str, b: str) -> bool:
    a, b = a.removeprefix("www."), b.removeprefix("www.")
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def metadata_only(host: str) -> bool:
    return any(host == h or host.endswith("." + h) for h in METADATA_ONLY_HOSTS)


def disk_free_gb() -> float:
    return shutil.disk_usage(DATA).free / 1e9


# ---------------------------------------------------------------- network


class FetchError(Exception):
    def __init__(self, reason: str, status: int | None = None):
        super().__init__(reason)
        self.reason, self.status = reason, status


class Resp:
    def __init__(self, status, url, headers, body):
        self.status, self.url, self.headers, self.body = status, url, headers, body

    def text(self) -> str:
        charset = None
        m = re.search(r"charset=([\w-]+)", self.headers.get("content-type", ""), re.I)
        if m:
            charset = m.group(1)
        else:
            m = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", self.body[:4000], re.I)
            charset = m.group(1).decode() if m else "utf-8"
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


CHALLENGE = re.compile(rb"Just a moment\.\.\.|cf-browser-verification|challenge-platform|Attention Required! \| Cloudflare|captcha-delivery"
                       rb"|_Incapsula_Resource|Request unsuccessful\. Incapsula", re.I)


class Net:
    """One request per host at a time, spaced by INTERVAL / robots Crawl-delay; proxy or direct route per host."""

    def __init__(self, proxy: str):
        self.ops = {"direct": urllib.request.build_opener(urllib.request.ProxyHandler({}))}
        if proxy:
            self.ops["proxy"] = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        self.route_of: dict[str, str] = {}
        self.robots: dict[str, tuple[float, object]] = {}
        self.locks: dict[str, threading.Lock] = {}
        self.next_at: dict[str, float] = {}
        self.cooldown: dict[str, float] = {}
        self.strikes: Counter = Counter()
        self.netfail: Counter = Counter()
        self.meta_lock = threading.Lock()
        self.requests = Counter()

    def _lock(self, key: str) -> threading.Lock:
        with self.meta_lock:
            return self.locks.setdefault(key, threading.Lock())

    def routes(self, host: str) -> list[str]:
        first = self.route_of.get(host) or ("direct" if host.endswith(".cn") or "proxy" not in self.ops else "proxy")
        return [first] + [r for r in self.ops if r != first]

    def pace(self, host: str, interval: float):
        with self._lock("pace:" + host):
            wait = self.next_at.get(host, 0) - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.next_at[host] = time.monotonic() + interval

    def _open(self, route, url, headers, timeout, max_bytes) -> Resp:
        req = urllib.request.Request(url, headers=headers)
        try:
            with self.ops[route].open(req, timeout=timeout) as r:
                return Resp(r.status, r.geturl(), {k.lower(): v for k, v in r.headers.items()}, r.read(max_bytes + 1))
        except urllib.error.HTTPError as e:
            try:
                body = e.read(300_000)
            except Exception:
                body = b""
            return Resp(e.code, url, {k.lower(): v for k, v in (e.headers or {}).items()}, body)

    def robot(self, url: str):
        p = urlsplit(url)
        key = f"{p.scheme}://{p.netloc}"
        with self._lock("robots:" + key):
            cached = self.robots.get(key)
            if cached and (cached[1] != "unknown" or time.monotonic() - cached[0] < 600):
                return cached[1]
            try:
                resp = self.get(key + "/robots.txt", kind="api", robots=False, max_bytes=800_000, retries=1, timeout=25)
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(resp.text().splitlines())
                value = parser
            except FetchError as e:
                # RFC 9309: 4xx = no restrictions; 5xx / unreachable = try again later
                value = "allow" if e.status and 400 <= e.status < 500 and e.status != 429 else "unknown"
            self.robots[key] = (time.monotonic(), value)
            return value

    def check_robots(self, url: str) -> float:
        value = self.robot(url)
        if value == "unknown":
            raise FetchError("robots_unavailable")
        if value == "allow":
            return 0.0
        if not value.can_fetch(UA, url):
            raise FetchError("robots_disallowed")
        delay = value.crawl_delay(UA)
        return min(float(delay or 0), 30.0)

    def get(self, url: str, *, kind="page", accept=None, max_bytes=PAGE_MAX, robots=True, retries=2, timeout=45) -> Resp:
        host = host_of(url)
        if self.cooldown.get(host, 0) > time.monotonic():
            raise FetchError("host_cooldown")
        delay = self.check_robots(url) if robots else 0.0
        interval = max(INTERVAL[kind], delay)
        headers = {"User-Agent": UA, "Accept": accept or ACCEPT[kind], "Accept-Language": "en,zh-CN;q=0.8,tr;q=0.6"}
        routes, ri, attempt = self.routes(host), 0, 0
        while True:
            route = routes[ri]
            self.pace(host, interval)
            self.requests[kind] += 1
            try:
                resp = self._open(route, url, headers, timeout, max_bytes)
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, http.client.HTTPException, ValueError) as exc:
                if ri + 1 < len(routes):
                    ri += 1
                    continue
                attempt += 1
                if attempt > retries:
                    with self.meta_lock:
                        self.netfail[host] += 1
                        if self.netfail[host] >= 6:  # unreachable on every route: stop hammering it for an hour
                            self.cooldown[host] = time.monotonic() + 3600
                            self.netfail[host] = 0
                            log.warning("host %s unreachable, paused for 1 h", host)
                    raise FetchError("network_" + type(exc).__name__)
                ri = 0
                time.sleep(5 * attempt)
                continue
            if len(resp.body) > max_bytes:
                raise FetchError("too_large", resp.status)
            if resp.status == 200 and len(resp.body) < 6000 and CHALLENGE.search(resp.body):
                resp.status = 403  # interstitial anti-bot page served with 200
            if resp.status == 200:
                with self.meta_lock:
                    self.route_of.setdefault(host, route)
                    self.strikes[host] = self.netfail[host] = 0
                if resp.body[:2] == b"\x1f\x8b":
                    try:
                        resp.body = gzip.decompress(resp.body)
                    except OSError:
                        pass
                return resp
            challenge = resp.status in (403, 429, 503) and (CHALLENGE.search(resp.body[:30000]) or resp.headers.get("cf-mitigated"))
            if challenge:
                if ri + 1 < len(routes):  # the other network path is not a bypass: same identity, same request
                    ri += 1
                    continue
                self._strike(host)
                raise FetchError("anti_bot_challenge", resp.status)
            if resp.status == 429:
                attempt += 1
                if attempt > 3:
                    self.cooldown[host] = time.monotonic() + 1800
                    raise FetchError("http_429", 429)
                wait = resp.headers.get("retry-after", "")
                time.sleep(min(600, int(wait) if wait.isdigit() else 30 * 2 ** attempt))
                continue
            if resp.status >= 500:
                attempt += 1
                if attempt > retries:
                    raise FetchError(f"http_{resp.status}", resp.status)
                time.sleep(10 * attempt)
                continue
            if resp.status in (401, 403):
                self._strike(host)
            raise FetchError(f"http_{resp.status}", resp.status)

    def _strike(self, host: str):
        with self.meta_lock:
            self.strikes[host] += 1
            if self.strikes[host] >= 8:
                self.cooldown[host] = time.monotonic() + 7200
                log.warning("host %s: repeated 401/403/challenge, paused for 2 h", host)


# ---------------------------------------------------------------- storage

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE, source_id TEXT NOT NULL, host TEXT NOT NULL, via TEXT,
    scope TEXT, listing_title TEXT, listing_date TEXT, listing_summary TEXT,
    status TEXT NOT NULL, reason TEXT, attempts INTEGER NOT NULL DEFAULT 0, next_try REAL, http_status INTEGER,
    final_url TEXT, title TEXT, subtitle TEXT, authors TEXT, published_at TEXT, modified_at TEXT, language TEXT,
    section TEXT, keywords TEXT, text TEXT, text_chars INTEGER, text_sha256 TEXT, extraction TEXT,
    title_verified INTEGER, duplicate_of TEXT, relevance_score INTEGER, topics TEXT, cop_tags TEXT,
    country_codes TEXT, organization_tags TEXT, numbers TEXT, lead_image TEXT, image_count INTEGER NOT NULL DEFAULT 0,
    rights_status TEXT, discovered_at TEXT, fetched_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_articles_queue ON articles(status, host);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_id, status);
CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(text_sha256);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY, article_id TEXT NOT NULL, position INTEGER NOT NULL, role TEXT NOT NULL, url TEXT NOT NULL,
    host TEXT NOT NULL, alt TEXT, caption TEXT, credit TEXT, status TEXT NOT NULL, reason TEXT,
    attempts INTEGER NOT NULL DEFAULT 0, path TEXT, sha256 TEXT, bytes INTEGER, width INTEGER, height INTEGER,
    mime TEXT, fetched_at TEXT, UNIQUE(article_id, url)
);
CREATE INDEX IF NOT EXISTS idx_images_queue ON images(status, host);
CREATE TABLE IF NOT EXISTS cursors (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT, args TEXT, stats TEXT);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.local, self.wlock = path, threading.local(), threading.RLock()
        c = self.conn()
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)

    def conn(self) -> sqlite3.Connection:
        c = getattr(self.local, "c", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=120, isolation_level=None, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA busy_timeout=120000")
            c.execute("PRAGMA synchronous=NORMAL")
            self.local.c = c
        return c

    def q(self, sql, args=()):
        return self.conn().execute(sql, args).fetchall()

    def one(self, sql, args=()):
        return self.conn().execute(sql, args).fetchone()

    def w(self, sql, args=()):
        with self.wlock:
            return self.conn().execute(sql, args)

    def cursor(self, key):
        row = self.one("SELECT value FROM cursors WHERE key=?", (key,))
        return json.loads(row["value"]) if row else None

    def set_cursor(self, key, value):
        self.w("INSERT INTO cursors(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
               "updated_at=excluded.updated_at", (key, json.dumps(value, ensure_ascii=False), now_iso()))

    def add_candidate(self, c: dict) -> bool:
        cur = self.w("INSERT OR IGNORE INTO articles(id,url,source_id,host,via,scope,listing_title,listing_date,listing_summary,"
                     "status,reason,discovered_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                     (c["id"], c["url"], c["source_id"], c["host"], c.get("via"), c.get("scope"), c.get("listing_title"),
                      c.get("listing_date"), c.get("listing_summary"), c.get("status", "pending"), c.get("reason"), now_iso()))
        return cur.rowcount > 0

    def known(self, url: str) -> bool:
        return self.one("SELECT 1 FROM articles WHERE url=?", (url,)) is not None

    def settle(self, aid: str, status: str, reason: str | None, fields: dict | None = None, images: list | None = None):
        fields = dict(fields or {})
        fields.update(status=status, reason=reason, fetched_at=now_iso())
        cols = ",".join(f"{k}=?" for k in fields)
        with self.wlock:
            c = self.conn()
            c.execute("BEGIN")
            try:
                c.execute(f"UPDATE articles SET {cols} WHERE id=?", (*fields.values(), aid))
                for i, img in enumerate(images or []):
                    c.execute("INSERT OR IGNORE INTO images(article_id,position,role,url,host,alt,caption,credit,status) "
                              "VALUES(?,?,?,?,?,?,?,?,'pending')",
                              (aid, i, img["role"], img["url"], host_of(img["url"]), img.get("alt"), img.get("caption"), img.get("credit")))
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise

    def retry_later(self, aid: str, reason: str, status_code=None):
        row = self.one("SELECT attempts FROM articles WHERE id=?", (aid,))
        attempts = (row["attempts"] if row else 0) + 1
        status = "failed" if attempts >= MAX_ATTEMPTS else "pending"
        self.w("UPDATE articles SET status=?, reason=?, attempts=?, next_try=?, http_status=?, fetched_at=? WHERE id=?",
               (status, reason, attempts, time.time() + 1800 * attempts, status_code, now_iso(), aid))


# ---------------------------------------------------------------- extraction

JUNK_CLASS = re.compile(r"newsletter|subscribe|signup|sign-up|related-(?:post|articles|stories|content|links)|share-?(?:buttons|bar|links|tools)"
                        r"|social-?share|donat|advert|\bads?\b|ad-slot|sponsor|promo|paywall|author-bio|post-tags|breadcrumb", re.I)
BAD_IMAGE = re.compile(r"logo|icon|avatar|sprite|pixel|tracking|1x1|spacer|placeholder|blank\.gif|gravatar|feedburner|doubleclick"
                       r"|\.svg(?:$|\?)|emoji|badge|button|banner-ad|data:|overlay-base64", re.I)
BODY_SELECTORS = ("[itemprop=articleBody]", "article .entry-content", ".entry-content", ".article-body", ".article__body",
                  ".story-body", ".post-content", ".content-body", "#maincontent article", "main article", "article", "main")
META_DATE = re.compile(r"<meta[^>]+(?:property|name|itemprop)=[\"'](?:article:published_time|og:published_time|datePublished|pubdate|publishdate"
                       r"|publish[-_]date|dc\.date\.issued|dc\.date|dcterms\.created|parsely-pub-date|sailthru\.date)[\"'][^>]*?content=[\"']([^\"']+)", re.I)
META_DATE_REV = re.compile(r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]*(?:property|name|itemprop)=[\"'](?:article:published_time|datePublished"
                           r"|pubdate|publishdate|dc\.date)[\"']", re.I)
META_MODIFIED = re.compile(r"<meta[^>]+(?:property|name)=[\"'](?:article:modified_time|og:updated_time|dateModified)[\"'][^>]*?content=[\"']([^\"']+)", re.I)
JSONLD_DATE = re.compile(r"\"datePublished\"\s*:\s*\"([^\"]+)\"")
JSONLD_MOD = re.compile(r"\"dateModified\"\s*:\s*\"([^\"]+)\"")
OG_IMAGE = re.compile(r"<meta[^>]+(?:property|name)=[\"'](?:og:image(?::secure_url|:url)?|twitter:image)[\"'][^>]*?content=[\"']([^\"']+)", re.I)
OG_IMAGE_ALT = re.compile(r"<meta[^>]+property=[\"']og:image:alt[\"'][^>]*?content=[\"']([^\"']*)", re.I)
HTML_LANG = re.compile(r"<html[^>]*\blang=[\"']?([A-Za-z]{2,3}(?:-[A-Za-z]+)?)", re.I)


def best_src(el, base: str) -> str | None:
    """Largest srcset candidate up to 1600 px wide, else the plain / lazy-load src."""
    cands = []
    for attr in ("srcset", "data-srcset", "data-lazy-srcset"):
        for part in (el.get(attr) or "").split(","):
            bits = part.strip().split()
            if bits and not bits[0].startswith("data:"):
                w = int(bits[1][:-1]) if len(bits) > 1 and bits[1].endswith("w") and bits[1][:-1].isdigit() else 0
                cands.append((w, bits[0]))
    if cands:
        fit = [c for c in cands if c[0] <= 1600] or cands
        return urljoin(base, max(fit)[1])
    for attr in ("data-src", "data-lazy-src", "data-original", "data-full-url", "src"):
        v = (el.get(attr) or "").strip()
        if v and not v.startswith("data:"):
            return urljoin(base, v)
    return None


def image_key(url: str) -> str:
    p = urlsplit(url)
    return p.netloc.lower() + re.sub(r"-\d{2,4}x\d{2,4}(?=\.\w+$)", "", p.path.lower())


def images_from(container, base: str, lead: dict | None) -> list[dict]:
    out, seen = [], set()
    if lead and lead.get("url") and not BAD_IMAGE.search(lead["url"]):
        out.append({**lead, "role": "lead"})
        seen.add(image_key(lead["url"]))
    for img in container.find_all("img") if container is not None else []:
        if len(out) >= MAX_IMAGES:
            break
        parent_picture = img.find_parent("picture")
        url = best_src(parent_picture.find("source") or img, base) if parent_picture and parent_picture.find("source") else best_src(img, base)
        if not url or not url.startswith("http") or BAD_IMAGE.search(url):
            continue
        try:
            w, h = int(img.get("width") or 0), int(img.get("height") or 0)
        except ValueError:
            w = h = 0
        if (w and w < 160) or (h and h < 100) or (url.lower().split("?")[0].endswith(".gif") and w < 300):
            continue
        key = image_key(url)
        if key in seen:
            continue
        seen.add(key)
        fig = img.find_parent("figure")
        cap_el = fig.find("figcaption") if fig else None
        caption = squash(cap_el.get_text(" ")) if cap_el else ""
        credit_el = cap_el.find(class_=re.compile(r"credit|copyright|attribution|source", re.I)) if cap_el else None
        out.append({"role": "body", "url": url, "alt": squash(img.get("alt"))[:500], "caption": redact(caption)[:1500],
                    "credit": squash(credit_el.get_text(" "))[:300] if credit_el else ""})
    if out and lead and out[0]["role"] == "lead" and not out[0].get("caption"):
        for other in out[1:]:  # the lead photo usually reappears in the body with its caption
            if image_key(other["url"]).rsplit("/", 1)[-1] == image_key(out[0]["url"]).rsplit("/", 1)[-1]:
                out[0].update(caption=other["caption"], credit=other["credit"])
    return out


RELATED_HEAD = re.compile(r"^(?:related(?: content| articles| stories| posts)?|read more|more on this(?: topic)?|sharelines from this story"
                          r"|you (?:may|might) also like|recommended|further reading|相关阅读|相关新闻|延伸阅读|ilgili haberler)\s*:?$", re.I)


def blocks_to_text(blocks: list[tuple[str, str]]) -> str:
    """Paragraphs separated by blank lines; 'related' link boxes (a heading plus a few headline-like lines) dropped."""
    lines, skip = [], 0
    for kind, txt in blocks:
        txt = redact(squash(txt))
        if not txt:
            continue
        if RELATED_HEAD.match(txt):
            skip = 6
            continue
        if skip and len(txt) < 160 and not txt.endswith((".", "。", "!", "?", "”", "\"")):
            skip -= 1
            continue
        skip = 0
        lines.append(("- " + txt) if kind == "li" else txt)
    return "\n\n".join(dict.fromkeys(lines))


def extract_html(html: str, url: str) -> dict | None:
    xml = trafilatura.extract(html, url=url, output_format="xml", include_images=False, include_tables=True, include_comments=False,
                              with_metadata=True, favor_precision=True, deduplicate=False)
    if not xml:
        return None
    try:
        root = etree.fromstring(xml.encode("utf-8"))
    except etree.XMLSyntaxError:
        return None
    blocks = []
    main = root.find("main")

    def walk(el):
        for child in el:
            tag = child.tag
            if tag in ("p", "head", "quote", "code"):
                blocks.append(("h" if tag == "head" else "p", "".join(child.itertext())))
            elif tag == "list":
                for item in child.iter("item"):
                    blocks.append(("li", "".join(item.itertext())))
            elif tag == "table":
                for row in child.iter("row"):
                    cells = [squash("".join(c.itertext())) for c in row.iter("cell")]
                    if any(cells):
                        blocks.append(("p", " | ".join(cells)))
            else:
                walk(child)

    if main is not None:
        walk(main)
    meta = root.attrib
    published = (parse_dt((META_DATE.search(html) or META_DATE_REV.search(html) or JSONLD_DATE.search(html) or [None, None])[1])
                 or parse_dt(meta.get("date")))
    modified = parse_dt((META_MODIFIED.search(html) or JSONLD_MOD.search(html) or [None, None])[1])
    soup = BeautifulSoup(html, "lxml")
    container = None
    for sel in BODY_SELECTORS:
        container = soup.select_one(sel)
        if container is not None and len(container.get_text(" ", strip=True)) > 400:
            break
        container = None
    og = OG_IMAGE.search(html)
    lead = {"url": urljoin(url, htmllib.unescape(og.group(1))), "alt": squash((OG_IMAGE_ALT.search(html) or [None, ""])[1])} if og else None
    lang = HTML_LANG.search(html[:5000])
    return {
        "title": squash(meta.get("title")), "subtitle": squash(meta.get("description")),
        "authors": [a.strip() for a in (meta.get("author") or "").split(";") if a.strip()],
        "published": published, "modified": modified, "language": lang.group(1).lower() if lang else None,
        "section": squash(meta.get("categories")), "keywords": [t.strip() for t in (meta.get("tags") or "").split(",") if t.strip()],
        "text": blocks_to_text(blocks), "images": images_from(container, url, lead), "extraction": "trafilatura_xml",
    }


def extract_wp(item: dict, link: str) -> dict:
    soup = BeautifulSoup((item.get("content") or {}).get("rendered") or "", "lxml")
    for n in soup.select("script,style,noscript,iframe,form,button,svg,input,select,ins"):
        n.decompose()
    for n in soup.find_all(class_=JUNK_CLASS):
        if n.parent is not None:
            n.decompose()
    block_tags = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre", "table"]
    blocks = []
    for el in soup.find_all(block_tags):
        if el.find_parent(block_tags) or el.find_parent("figure"):
            continue
        if el.name == "table":
            for tr in el.find_all("tr"):
                cells = [squash(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
                if any(cells):
                    blocks.append(("p", " | ".join(cells)))
        else:
            blocks.append(("li" if el.name == "li" else "h" if el.name[0] == "h" and len(el.name) == 2 else "p", el.get_text(" ")))
    text = blocks_to_text(blocks)
    if len(text) < 0.5 * len(soup.get_text(" ", strip=True)):  # body text outside block elements
        text = blocks_to_text([("p", t) for t in soup.get_text("\n").split("\n")])
    emb = item.get("_embedded") or {}
    lead = None
    media = (emb.get("wp:featuredmedia") or [None])[0]
    if isinstance(media, dict) and media.get("source_url"):
        sizes = (media.get("media_details") or {}).get("sizes") or {}
        fit = [s for s in sizes.values() if isinstance(s, dict) and s.get("source_url") and 0 < int(s.get("width") or 0) <= 1600]
        src = max(fit, key=lambda s: int(s["width"]))["source_url"] if fit else media["source_url"]
        lead = {"url": src, "alt": squash(media.get("alt_text"))[:500], "caption": redact(html_text((media.get("caption") or {}).get("rendered")))[:1500],
                "credit": ""}
    elif (item.get("yoast_head_json") or {}).get("og_image"):
        og = item["yoast_head_json"]["og_image"][0]
        lead = {"url": og.get("url"), "alt": "", "caption": "", "credit": ""}
    terms = [t for group in emb.get("wp:term") or [] for t in (group or []) if isinstance(t, dict)]
    yoast = item.get("yoast_head_json") or {}
    authors = [a["name"] for a in emb.get("author") or [] if isinstance(a, dict) and a.get("name")] or ([yoast["author"]] if yoast.get("author") else [])
    return {
        "title": html_text((item.get("title") or {}).get("rendered")),
        "subtitle": html_text((item.get("excerpt") or {}).get("rendered"))[:2000],
        "authors": authors,
        "published": parse_dt(item.get("date_gmt")),
        "modified": parse_dt(item.get("modified_gmt")),
        "language": (yoast.get("og_locale") or "").split("_")[0].lower() or None,
        "section": "; ".join(t["name"] for t in terms if t.get("taxonomy") == "category"),
        "keywords": [htmllib.unescape(t["name"]) for t in terms if t.get("taxonomy") in ("post_tag", "topic", "location")],
        "text": text, "images": images_from(soup, link, lead), "extraction": "wordpress_rest_content",
    }


# ---------------------------------------------------------------- crawler


class Crawler:
    def __init__(self, *, proxy=PROXY, cop=True, images=True, limit=None):
        DATA.mkdir(parents=True, exist_ok=True)
        IMAGES.mkdir(parents=True, exist_ok=True)
        self.store, self.net = Store(DB_PATH), Net(proxy)
        self.cop, self.images, self.limit = cop, images, limit
        self.stop = threading.Event()
        self.stats = Counter()
        self.cfg = {s["source_id"]: s for s in ADAPTERS["sources"]}

    # ---- quality gates + tags (shared by every adapter)

    def settle_page(self, cand: dict, page: dict | None, *, final_url=None) -> tuple[str, str | None]:
        cfg = self.cfg.get(cand["source_id"], {})
        aid = cand["id"]
        if not page:
            return self._reject(aid, "extraction_failed")
        title = page["title"] or cand.get("listing_title") or ""
        text = page["text"] or ""
        first, _, rest = text.partition("\n\n")
        if title and title_key(first) == title_key(title):  # extractors often repeat the headline as the first block
            text = rest
        published = page["published"] or parse_dt(cand.get("listing_date"))
        listed = parse_dt(cand.get("listing_date"))
        if listed and published and abs((published - listed).days) > 3 and cand.get("via") in ("sitemap", "guardian:tag", "guardian:section"):
            published = listed  # a dated URL / archive day beats a template meta date
        fields = {"final_url": final_url, "title": title, "subtitle": page["subtitle"], "authors": json.dumps(page["authors"], ensure_ascii=False),
                  "published_at": published.isoformat() if published else None, "modified_at": page["modified"].isoformat() if page["modified"] else None,
                  "language": page["language"] or (MASTER.get(cand["source_id"], {}).get("languages") or [None])[0],
                  "section": page["section"], "keywords": json.dumps(page["keywords"], ensure_ascii=False), "extraction": page["extraction"]}
        if BLOCKED_PAGE.search(text[:400]) and len(text) < 2000:
            return self._reject(aid, "blocked_page", fields)
        if not substantive(text, title):
            return self._reject(aid, "no_substantive_text", fields)
        if len(text) < 3000 and PAYWALL.search(text[-1500:]):
            return self._reject(aid, "paywalled", fields)
        verified = None
        if cand.get("listing_title") and page["title"]:
            verified = int(title_verified(cand["listing_title"], page["title"]))
            if not verified:
                return self._reject(aid, "page_title_mismatch", fields)
        if not published:
            return self._reject(aid, "missing_date", fields)
        if published > datetime.now(UTC) + timedelta(days=1):
            return self._reject(aid, "future_date", fields)
        pub_day = published.date()
        cops = cop_tags(f"{title}\n{page['subtitle']}\n{text}", pub_day)
        scope = cfg.get("scope", "general")
        if (cand.get("via") or "").endswith(":tag"):
            scope = "dedicated"
        lead = f"{title} {page['subtitle']} {text[:2000 if scope == 'dedicated' else 1000]}"
        is_relevant = relevant(lead, scope)
        if pub_day < START and not (cops and cfg.get("cop")):
            return self._reject(aid, "outside_time_range", fields)
        if not is_relevant and not cops:
            return self._reject(aid, "outside_climate_scope", fields)
        article = NormalizedArticle(article_id=aid, source_id=cfg.get("gate") or cand["source_id"], source_url=cand["url"],
                                    canonical_url=cand["url"], title=title, published_at_raw=None, published_at_utc=published.isoformat(),
                                    summary_from_source=page["subtitle"] or text[:600], language=fields["language"], content_hash="")
        if cfg.get("gate") and not _source_scope_match(article, cfg["gate"]):
            return self._reject(aid, "outside_source_scope", fields)
        if scope == "general" and EXCLUDE_TITLE.search(title):
            return self._reject(aid, "excluded_content_type", fields)
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        dup = self.store.one("SELECT id FROM articles WHERE text_sha256=? AND status='done' AND id<>?", (sha, aid))
        analysis = _analyse(article, int(MASTER.get(cand["source_id"], {}).get("authority", 3)))
        head = f"{title}\n{page['subtitle']}\n{text[:5000]}"
        fields.update(text=text, text_chars=len(text), text_sha256=sha, title_verified=verified, relevance_score=analysis["score"],
                      topics=json.dumps(analysis["topics"], ensure_ascii=False), numbers=json.dumps(analysis["numbers"], ensure_ascii=False),
                      cop_tags=json.dumps(cops), country_codes=json.dumps([c["alpha2"] for c in country_codes_for(head)]),
                      organization_tags=json.dumps(organization_tags_for(head)), rights_status=RIGHTS,
                      scope="cop" if pub_day < START else "5y")
        if dup:
            fields["duplicate_of"] = dup["id"]
            return self._reject(aid, "duplicate_text", fields)
        images = page["images"] if self.images else []
        fields.update(lead_image=images[0]["url"] if images and images[0]["role"] == "lead" else None, image_count=len(images))
        self.store.settle(aid, "done", None, fields, images)
        self.stats["done"] += 1
        return "done", None

    def _reject(self, aid, reason, fields=None):
        self.store.settle(aid, "rejected", reason, fields)
        self.stats["rejected:" + reason] += 1
        return "rejected", reason

    def candidate(self, source_id: str, url: str, *, via: str, scope: str, title=None, when=None, summary=None, hold=False) -> dict | None:
        """Register a discovered URL; returns the candidate (with id) when it is new."""
        try:
            url = normalize_url(url)
        except ValueError:
            return None
        if urlsplit(url).scheme not in ("http", "https"):
            return None
        host = host_of(url)
        cand = {"id": stable_id("article", url), "url": url, "source_id": source_id, "host": host, "via": via, "scope": scope,
                "listing_title": squash(title)[:500] or None, "listing_date": when.isoformat() if isinstance(when, (date, datetime)) else when,
                "listing_summary": squash(summary)[:2000] or None}
        if metadata_only(host):
            cand.update(status="skipped", reason="metadata_only_source")
        elif self.cfg.get(source_id, {}).get("fetch_pages") is False and summary:
            cand.update(status="summary")
        elif hold:  # fetched right away by the discovering adapter, not by a host lane
            cand.update(status="hold")
        if not self.store.add_candidate(cand):
            return None
        self.stats["discovered"] += 1
        if cand.get("status") == "summary":
            self.settle_summary(cand)
            return None
        return cand

    def settle_summary(self, cand: dict):
        """Feeds whose pages are not fetched (paywalled journals): keep the publisher's own abstract."""
        page = {"title": cand["listing_title"], "subtitle": "", "authors": [], "published": parse_dt(cand["listing_date"]), "modified": None,
                "language": None, "section": "", "keywords": [], "text": cand["listing_summary"] or "", "images": [], "extraction": "feed_summary"}
        cand = {**cand, "listing_title": None}
        self.settle_page(cand, page)
        self.store.w("UPDATE articles SET rights_status='publisher_abstract' WHERE id=?", (cand["id"],))

    def fetch_article(self, row) -> tuple[str, str | None]:
        cand = dict(row)
        try:
            resp = self.net.get(cand["url"], kind="page")
        except FetchError as e:
            if e.reason == "host_cooldown":
                self.store.w("UPDATE articles SET status='pending' WHERE id=?", (cand["id"],))
                return "retry", e.reason
            if e.reason in ("robots_disallowed", "too_large", "anti_bot_challenge") or (e.status and e.status in (404, 410, 451)):
                return self._reject(cand["id"], e.reason, {"http_status": e.status})
            self.store.retry_later(cand["id"], e.reason, e.status)
            self.stats["retry:" + e.reason] += 1
            return "retry", e.reason
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype and "xml" not in ctype:
            return self._reject(cand["id"], "not_html", {"http_status": resp.status})
        final = normalize_url(resp.url)
        if not same_site(host_of(final), cand["host"]) and not cand["via"].startswith("gdelt"):
            return self._reject(cand["id"], "redirected_off_site", {"final_url": final})
        try:
            html = resp.text()
            page = extract_html(html, resp.url)
        except Exception as exc:  # one malformed page must not stop the lane
            log.warning("extract %s: %s", cand["url"], exc)
            page = None
        if page and self.cfg.get(cand["source_id"], {}).get("fetch_pages") == "abstract":
            # journals: bibliographic record + the publisher's public abstract only, never the (paywalled) article body
            metas = re.findall(r"<meta[^>]+name=[\"'](?:dc\.description|description|citation_abstract)[\"'][^>]*content=[\"']([^\"']{80,})", html, re.I)
            page.update(text=redact(squash(max(metas, key=len))) if metas else "", images=[], extraction="publisher_abstract")
        status = self.settle_page(cand, page, final_url=final if final != cand["url"] else None)
        if page and page["extraction"] == "publisher_abstract":
            self.store.w("UPDATE articles SET rights_status='publisher_abstract' WHERE id=?", (cand["id"],))
        return status

    def fetch_image(self, row) -> str:
        url = row["url"]
        try:
            resp = self.net.get(url, kind="image", max_bytes=IMG_MAX)
        except FetchError as e:
            final = e.status in (404, 410) or e.reason in ("robots_disallowed", "too_large")
            self.store.w("UPDATE images SET status=?, reason=?, attempts=attempts+1 WHERE id=?",
                         ("failed" if final or row["attempts"] + 1 >= MAX_ATTEMPTS else "pending", e.reason, row["id"]))
            return "failed"
        mime = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        try:
            im = Image.open(io.BytesIO(resp.body))
            width, height = im.size
            fmt = (im.format or "").lower()
        except Exception:
            self.store.w("UPDATE images SET status='failed', reason='not_an_image', attempts=attempts+1 WHERE id=?", (row["id"],))
            return "failed"
        if width < 160 or height < 100:
            self.store.w("UPDATE images SET status='rejected', reason='too_small', width=?, height=? WHERE id=?", (width, height, row["id"]))
            return "rejected"
        sha = hashlib.sha256(resp.body).hexdigest()
        ext = {"jpeg": "jpg", "png": "png", "webp": "webp", "gif": "gif", "avif": "avif", "mpo": "jpg", "bmp": "bmp", "tiff": "tif"}.get(fmt, "bin")
        rel = f"{sha[:2]}/{sha}.{ext}"
        path = IMAGES / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".part")
            tmp.write_bytes(resp.body)
            tmp.replace(path)
        self.store.w("UPDATE images SET status='done', reason=NULL, path=?, sha256=?, bytes=?, width=?, height=?, mime=?, fetched_at=? WHERE id=?",
                     (rel, sha, len(resp.body), width, height, mime or f"image/{fmt}", now_iso(), row["id"]))
        self.stats["images"] += 1
        return "done"

    # ---- scheduling

    def lane(self, host: str, table: str):
        fn = self.fetch_article if table == "articles" else self.fetch_image
        while not self.stop.is_set():
            if table == "articles":
                rows = self.store.q("SELECT * FROM articles WHERE host=? AND status='pending' AND (next_try IS NULL OR next_try<=?) "
                                    "ORDER BY discovered_at LIMIT 25", (host, time.time()))
            else:
                if disk_free_gb() < MIN_FREE_GB:
                    log.warning("free disk below %.0f GB: image downloads paused", MIN_FREE_GB)
                    return
                rows = self.store.q("SELECT * FROM images WHERE host=? AND status='pending' LIMIT 50", (host,))
            if not rows:
                return
            for row in rows:
                if self.stop.is_set() or self.net.cooldown.get(host, 0) > time.monotonic():
                    return
                try:
                    fn(row)
                except Exception:
                    log.exception("%s %s", table, row["url"])
                    if table == "articles":
                        self.store.retry_later(row["id"], "crawler_error")
                    else:
                        self.store.w("UPDATE images SET status='failed', reason='crawler_error' WHERE id=?", (row["id"],))

    def run(self, source_ids: list[str], *, discover=True, fetch=True, max_lanes=24, max_image_lanes=10):
        started = now_iso()
        threads = []
        if discover:
            for sid in source_ids:
                cfg = self.cfg[sid]
                for i, a in enumerate(cfg["adapters"]):
                    t = threading.Thread(target=self.run_adapter, args=(sid, a), name=f"disc-{sid}-{i}", daemon=True)
                    t.start()
                    threads.append(t)
        lanes: dict[tuple[str, str], threading.Thread] = {}
        last_report = 0.0
        while not self.stop.is_set():
            for key in [k for k, t in lanes.items() if not t.is_alive()]:
                del lanes[key]
            if fetch:
                now = time.time()
                for table, cap in (("articles", max_lanes), ("images", max_image_lanes if self.images else 0)):
                    active = sum(1 for k in lanes if k[0] == table)
                    if active >= cap:
                        continue
                    if table == "articles":
                        hosts = self.store.q("SELECT host, COUNT(*) n FROM articles WHERE status='pending' AND (next_try IS NULL OR next_try<=?) "
                                             "AND source_id IN (%s) GROUP BY host ORDER BY n DESC" % ",".join("?" * len(source_ids)), (now, *source_ids))
                    else:
                        hosts = self.store.q("SELECT host, COUNT(*) n FROM images WHERE status='pending' GROUP BY host ORDER BY n DESC")
                    for h in hosts:
                        if active >= cap:
                            break
                        if (table, h["host"]) in lanes or self.net.cooldown.get(h["host"], 0) > time.monotonic():
                            continue
                        t = threading.Thread(target=self.lane, args=(h["host"], table), name=f"{table}-{h['host']}", daemon=True)
                        t.start()
                        lanes[(table, h["host"])] = t
                        active += 1
            discovering = any(t.is_alive() for t in threads)
            if time.monotonic() - last_report > 60:
                last_report = time.monotonic()
                log.info("discovering=%d lanes=%d | %s", sum(t.is_alive() for t in threads), len(lanes),
                         " ".join(f"{k}={v}" for k, v in sorted(self.stats.items()) if not k.startswith("rejected:")))
            if not discovering and not lanes:
                pending = self.store.one("SELECT COUNT(*) n FROM articles WHERE status='pending' AND (next_try IS NULL OR next_try<=?)", (time.time(),))["n"]
                pending_img = self.store.one("SELECT COUNT(*) n FROM images WHERE status='pending'")["n"] if self.images else 0
                if not fetch or (pending == 0 and (pending_img == 0 or disk_free_gb() < MIN_FREE_GB)):
                    break
            time.sleep(3)
        self.store.w("INSERT INTO runs(started_at,finished_at,args,stats) VALUES(?,?,?,?)",
                     (started, now_iso(), json.dumps(source_ids), json.dumps(dict(self.stats))))
        log.info("run finished: %s", dict(self.stats))

    def run_adapter(self, sid: str, a: dict):
        cls = {"wordpress": WordPress, "guardian": Guardian, "sitemap": Sitemap, "listing": Listing, "rss": Rss, "gdelt": Gdelt}[a["type"]]
        try:
            cls(self, sid, a).run()
            log.info("discovery %s/%s finished", sid, a["type"])
        except Exception:
            log.exception("discovery %s/%s crashed", sid, a["type"])


# ---------------------------------------------------------------- discovery adapters


class Adapter:
    def __init__(self, crawler: Crawler, sid: str, a: dict):
        self.c, self.sid, self.a = crawler, sid, a
        self.cfg = crawler.cfg[sid]
        self.cop = crawler.cop and self.cfg.get("cop", False)
        self.ranges = discovery_ranges(self.cop, tuple(a["cop_window_days"]) if a.get("cop_window_days") else None)
        self.found = 0

    @property
    def done(self) -> bool:
        return self.c.stop.is_set() or (self.c.limit is not None and self.found >= self.c.limit)

    def add(self, url, *, scope, title=None, when=None, summary=None, via=None, hold=False) -> dict | None:
        cand = self.c.candidate(self.sid, url, via=via or self.a["type"], scope=scope, title=title, when=when, summary=summary, hold=hold)
        if cand:
            self.found += 1
        return cand

    def get(self, url, **kw) -> Resp | None:
        try:
            return self.c.net.get(url, **kw)
        except FetchError as e:
            log.warning("%s %s: %s %s", self.sid, url[:160], e.reason, e.status or "")
            return e if isinstance(e, FetchError) else None


class WordPress(Adapter):
    FIELDS = "id,link,date_gmt,modified_gmt,title,excerpt,content,type,yoast_head_json,_links,_embedded"

    def run(self):
        host = host_of(self.a["endpoint"])
        jobs = [(lo, hi, scope, None) for lo, hi, scope in self.ranges]
        if self.cop:  # COP coverage published after its news window (retrospectives, analyses) before the 5-year range
            for c in COPS:
                if c["d_start"] < START:
                    term = f"COP{c['n']}" if c["n"] >= 10 else (c["outcomes"] or c["aliases"])[0]
                    jobs.append((date(1995, 1, 1), START - timedelta(days=1), f"cop{c['n']}", term))
        include = re.compile(self.a["link_include"]) if self.a.get("link_include") else None
        for lo, hi, scope, search in jobs:
            key = f"wp|{self.sid}|{lo}|{hi}|{search or ''}"
            cur = self.c.store.cursor(key) or {"page": 1}
            if cur.get("done"):
                continue
            page = cur["page"]
            per_page = 10 if self.c.limit else 50
            while not self.done:
                params = {"per_page": per_page, "page": page, "after": f"{lo}T00:00:00", "before": f"{hi}T23:59:59", "orderby": "date",
                          "order": "desc", "_embed": "wp:featuredmedia,wp:term,author", "_fields": self.FIELDS}
                if search:
                    params.update(search=search, orderby="date")
                resp = self.get(self.a["endpoint"] + "?" + urlencode(params), kind="api", accept="application/json", max_bytes=API_MAX)
                if isinstance(resp, FetchError):
                    if resp.status == 400:
                        self.c.store.set_cursor(key, {"page": page, "done": True})
                    break
                try:
                    items = json.loads(resp.body)
                except ValueError:
                    log.warning("%s: WordPress page %d is not JSON", self.sid, page)
                    break
                if not isinstance(items, list) or not items:
                    self.c.store.set_cursor(key, {"page": page, "done": True})
                    break
                for item in items:
                    self.handle(item, host, include, "cop" if scope.startswith("cop") else "5y")
                    if self.done:
                        break
                total_pages = int(resp.headers.get("x-wp-totalpages") or page)
                if len(items) < per_page or page >= total_pages or (search and page >= 20):
                    self.c.store.set_cursor(key, {"page": page, "done": True})
                    break
                page += 1
                self.c.store.set_cursor(key, {"page": page})

    def handle(self, item: dict, host: str, include, scope: str):
        link = item.get("link") or ""
        if not link.startswith("http") or not same_site(host_of(link), host) or (include and not include.search(link)):
            return
        if (item.get("content") or {}).get("protected"):
            return
        cand = self.add(link, scope=scope, via="wordpress")
        if not cand:
            return
        try:
            page = extract_wp(item, cand["url"])
        except Exception as exc:
            log.warning("%s wp item %s: %s", self.sid, link, exc)
            page = None
        self.c.settle_page(cand, page)


class Guardian(Adapter):
    MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
    SKIP = re.compile(r"/(?:live|video|audio|gallery|picture|ng-interactive|crosswords|football|sport|info|help|tone/obituaries)/")

    def run(self):
        paths = [(p, "guardian:tag") for p in self.a.get("tag_paths", [])] + [(p, "guardian:section") for p in self.a.get("section_paths", [])]
        for lo, hi, scope in self.ranges:
            day = hi
            while day >= lo and not self.done:
                for path, via in paths:
                    key = f"gu|{path}|{day}"
                    if self.c.store.cursor(key):
                        continue
                    stamp = f"{day.year}/{self.MONTHS[day.month - 1]}/{day.day:02d}"
                    resp = self.get(f"https://www.theguardian.com/{path}/{stamp}/all", kind="page")
                    if isinstance(resp, FetchError):
                        if resp.status == 404:
                            self.c.store.set_cursor(key, 1)
                        continue
                    for url, title in self.links(resp.text(), stamp):
                        if via == "guardian:section" and not (relevant(title, "general") or cop_tags(title, day)):
                            continue
                        self.add(url, scope="cop" if scope.startswith("cop") else "5y", title=title, when=day, via=via)
                    self.c.store.set_cursor(key, 1)
                day -= timedelta(days=1)

    def links(self, page: str, stamp: str):
        found: dict[str, str] = {}
        for m in re.finditer(r"<a\b[^>]*?href=\"((?:https://www\.theguardian\.com)?/[^\"#?]+)\"[^>]*>(.*?)</a>", page, re.S):
            url, inner = urljoin("https://www.theguardian.com/", m.group(1)), m.group(2)
            if f"/{stamp}/" not in url or self.SKIP.search(url) or url.endswith("/all"):
                continue
            title = squash(re.sub(r"<[^>]+>", " ", inner))
            label = re.search(r"aria-label=\"([^\"]+)\"", m.group(0))
            title = title or (squash(label.group(1)) if label else "")
            if len(title) > len(found.get(url, "")):
                found[url] = title
        return found.items()


class Sitemap(Adapter):
    def run(self):
        self.include = re.compile(self.a["url_include"])
        self.sm_include = re.compile(self.a["sitemap_include"]) if self.a.get("sitemap_include") else None
        self.date_rx = re.compile(self.a["date_from_url"]) if self.a.get("date_from_url") else None
        self.oldest = min(lo for lo, _, _ in self.ranges)
        for sm in self.a["sitemaps"]:
            self.walk(sm, 0, "")

    def walk(self, url: str, depth: int, lastmod: str):
        if self.done or depth > 4:
            return
        key = f"sm|{self.sid}|{url}"
        resp = self.get(url, kind="api", accept="application/xml, text/xml, */*", max_bytes=API_MAX)
        if isinstance(resp, FetchError):
            return
        try:
            root = ET.fromstring(resp.body)
        except ET.ParseError:
            log.warning("%s: sitemap %s is not XML", self.sid, url)
            return

        def field(el, name):
            for child in el:
                if child.tag.rsplit("}", 1)[-1] == name:
                    return (child.text or "").strip()
            return ""

        kind = root.tag.rsplit("}", 1)[-1]
        if kind == "sitemapindex":
            children = [(field(el, "loc"), field(el, "lastmod")) for el in root if el.tag.rsplit("}", 1)[-1] == "sitemap"]
            for i, (loc, child_lastmod) in enumerate(children):
                if not loc or (self.sm_include and not self.sm_include.search(loc)):
                    continue
                m = re.search(r"(\d{4})-(\d{2})(?:\D|$)", loc) if self.sm_include and self.sm_include.groups else None
                if m and date(int(m[1]), int(m[2]), 28) < self.oldest:
                    continue
                lm = parse_dt(child_lastmod)
                if lm and lm.date() < self.oldest:
                    continue
                child_state = self.c.store.cursor(f"sm|{self.sid}|{loc}") or {}
                # unchanged since the last crawl (children without lastmod: only the first two are re-read)
                if child_state.get("done") and (child_state.get("lastmod") == child_lastmod if child_lastmod else i >= 2):
                    continue
                self.walk(loc, depth + 1, child_lastmod)
                if self.done:
                    return
            return
        for el in root:
            if self.done:
                return
            loc = field(el, "loc")
            if not loc or not self.include.search(loc):
                continue
            when, approx = None, False
            if self.date_rx and (m := self.date_rx.search(loc)):
                parts = [int(x) for x in m.groups()]
                when = date(parts[0], parts[1], parts[2] if len(parts) > 2 else 15)
                approx = len(parts) < 3  # month-only URL dates filter ranges but never override the page date
            else:
                news = next((c for c in el if c.tag.rsplit("}", 1)[-1] == "news"), None)
                pub = parse_dt(field(news, "publication_date")) if news is not None else None
                if pub:
                    when = pub.date()
                elif (lm := parse_dt(field(el, "lastmod"))):
                    when, approx = lm.date(), True
            if when:
                scope = in_ranges(when, self.ranges) or (in_ranges(when.replace(day=1), self.ranges) if approx else None)
                if not scope and not (approx and when >= START.replace(day=1)):
                    continue
            else:
                scope = None
            title = None
            news = next((c for c in el if c.tag.rsplit("}", 1)[-1] == "news"), None)
            if news is not None:
                title = field(news, "title") or None
            if self.a.get("slug_filter"):
                slug = " ".join(re.split(r"[/_-]+", urlsplit(loc).path))
                if not (relevant(f"{slug} {title or ''}", "general") or cop_tags(slug, when)):
                    continue
            self.add(loc, scope="cop" if scope and scope.startswith("cop") else "5y", title=title, when=None if approx else when, via="sitemap")
        if not self.done:
            self.c.store.set_cursor(key, {"lastmod": lastmod, "done": True})


class Listing(Adapter):
    def run(self):
        include = re.compile(self.a["link_include"])
        key = f"ls|{self.sid}|{self.a['url']}"
        state = self.c.store.cursor(key) or {"page": self.a.get("first_page", 1)}
        page = self.a.get("first_page", 1) if state.get("done") else state["page"]
        previous: set[str] = set()
        old_pages = 0
        while not self.done and page < self.a.get("first_page", 1) + self.a.get("max_pages", 100):
            resp = self.get(self.a["url"].format(page=page), kind="page")
            if isinstance(resp, FetchError):
                break
            links: dict[str, str] = {}
            for m in re.finditer(r"<a\b[^>]*?href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", resp.text(), re.S):
                url = urljoin(resp.url, htmllib.unescape(m.group(1)))
                if include.search(url):
                    t = squash(re.sub(r"<[^>]+>", " ", m.group(2)))
                    if len(t) >= len(links.get(url, "")):
                        links[url] = t
            if not links or set(links) == previous:
                self.c.store.set_cursor(key, {"page": page, "done": True})
                break
            previous = set(links)
            fresh, older = 0, 0
            for url, title in links.items():
                cand = self.add(url, scope="5y", title=title or None, via="listing", hold=True)
                if not cand:
                    continue
                fresh += 1
                try:
                    self.c.fetch_article(self.c.store.one("SELECT * FROM articles WHERE id=?", (cand["id"],)))
                except Exception:
                    log.exception("%s listing item %s", self.sid, url)
                    self.c.store.retry_later(cand["id"], "crawler_error")
                row = self.c.store.one("SELECT published_at FROM articles WHERE id=?", (cand["id"],))
                if row and row["published_at"] and parse_dt(row["published_at"]).date() < START:
                    older += 1
            if state.get("done") and fresh == 0:
                break  # incremental run caught up with the previous crawl
            old_pages = old_pages + 1 if fresh and older == fresh else 0
            if old_pages >= 2:
                self.c.store.set_cursor(key, {"page": page, "done": True})
                break
            page += 1
            if not state.get("done"):
                self.c.store.set_cursor(key, {"page": page})


class Rss(Adapter):
    def run(self):
        lang = (MASTER.get(self.sid, {}).get("languages") or [None])[0]
        for feed in self.a["feeds"]:
            resp = self.get(feed, kind="api", accept="application/rss+xml, application/atom+xml, application/xml, text/xml")
            if isinstance(resp, FetchError):
                continue
            try:
                items = [(it.canonical_url, it.title, it.published_at_utc, it.summary_from_source) for it in parse_feed(resp.body, self.sid, lang)]
                if not items:  # RSS 1.0 (RDF) feeds keep their items in a namespace parse_feed does not look at
                    ns = {"r": "http://purl.org/rss/1.0/", "dc": "http://purl.org/dc/elements/1.1/"}
                    items = [(el.findtext("r:link", "", ns), el.findtext("r:title", "", ns), el.findtext("dc:date", "", ns),
                              html_text(el.findtext("r:description", "", ns))) for el in ET.fromstring(resp.body).iterfind(".//r:item", ns)]
            except ET.ParseError:
                log.warning("%s: feed %s is not XML", self.sid, feed)
                continue
            for link, title, published, summary in items:
                when = parse_dt(published)
                if not link or (when and when.date() < START):
                    continue
                self.add(link, scope="5y", title=title, when=when, summary=summary, via="rss")
                if self.done:
                    return


class Gdelt(Adapter):
    ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

    def run(self):
        ranges = [r for r in self.ranges if r[1] >= date(2017, 1, 1)]  # the DOC API full-text index starts in 2017
        failures = 0
        for lo, hi, scope in ranges:
            day = hi
            while day >= max(lo, date(2017, 1, 1)) and not self.done:
                key = f"gd|{self.sid}|{day}"
                if not self.c.store.cursor(key):
                    params = {"query": self.a["query"], "mode": "ArtList", "format": "json", "maxrecords": self.a.get("per_day", 25),
                              "sort": "HybridRel", "startdatetime": f"{day:%Y%m%d}000000", "enddatetime": f"{day:%Y%m%d}235959"}
                    resp = self.get(self.ENDPOINT + "?" + urlencode(params), kind="gdelt", robots=False, retries=1)
                    if isinstance(resp, FetchError):
                        failures += 1
                        if failures >= 3:
                            log.warning("%s: GDELT unavailable (%s); will resume from %s next run", self.sid, resp.reason, day)
                            return
                        time.sleep(120)
                        continue
                    failures = 0
                    try:
                        arts = json.loads(resp.body or b"{}").get("articles") or []
                    except ValueError:
                        arts = []
                    for art in arts:
                        when = parse_dt(art.get("seendate"))
                        self.add(art.get("url", ""), scope="cop" if scope.startswith("cop") else "5y", title=art.get("title"), when=when, via="gdelt")
                    self.c.store.set_cursor(key, 1)
                day -= timedelta(days=1)


# ---------------------------------------------------------------- commands


def setup_logging(name: str):
    LOGS.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(message)s", "%Y-%m-%d %H:%M:%S")
    log.setLevel(logging.INFO)
    for h in (logging.FileHandler(LOGS / f"{name}-{datetime.now():%Y%m%d}.log", encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        h.setFormatter(fmt)
        log.addHandler(h)
    logging.getLogger("trafilatura").setLevel(logging.ERROR)
    logging.getLogger("htmldate").setLevel(logging.ERROR)


def pick_sources(spec: str | None) -> list[str]:
    known = [s["source_id"] for s in ADAPTERS["sources"]]
    if not spec:
        return known
    wanted = [s.strip() for s in spec.split(",") if s.strip()]
    unknown = [s for s in wanted if s not in known]
    if unknown:
        sys.exit(f"no adapter for: {', '.join(unknown)} (skipped sources: see sources.json 'skip')")
    return wanted


def single_instance():
    """Hold an OS lock on data/run.lock for the life of the process (a second `run` exits at once)."""
    handle = open(DATA / "run.lock", "a+")
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(f"another run is active ({DATA / 'run.lock'})")
    return handle


def cmd_run(args):
    DATA.mkdir(parents=True, exist_ok=True)
    lock = single_instance()  # noqa: F841 (kept open until exit)
    setup_logging("run")
    crawler = Crawler(cop=not args.no_cop, images=not args.no_images)
    signal.signal(signal.SIGINT, lambda *_: crawler.stop.set())
    sources = [s for s in pick_sources(args.sources) if s not in set((args.skip_sources or "").split(","))]
    log.info("run: %d sources, range %s..%s, cop=%s, images=%s, data=%s", len(sources), START, TODAY, crawler.cop, crawler.images, DATA)
    crawler.run(sources, discover=not args.fetch_only, fetch=not args.discover_only, max_lanes=args.lanes)


def cmd_test(args):
    setup_logging("test")
    crawler = Crawler(cop=not args.no_cop, images=args.images, limit=args.n)
    sid = pick_sources(args.source)[0]
    for a in crawler.cfg[sid]["adapters"]:
        crawler.run_adapter(sid, a)
    rows = crawler.store.q("SELECT * FROM articles WHERE source_id=? AND status='pending' LIMIT ?", (sid, args.n))
    for row in rows:
        crawler.fetch_article(row)
    if args.images:
        for img in crawler.store.q("SELECT i.* FROM images i JOIN articles a ON a.id=i.article_id WHERE a.source_id=? AND i.status='pending' LIMIT 12", (sid,)):
            crawler.fetch_image(img)
    for r in crawler.store.q("SELECT status,reason,published_at,text_chars,image_count,cop_tags,title,url FROM articles WHERE source_id=? "
                             "ORDER BY fetched_at DESC LIMIT ?", (sid, max(args.n * 2, 10))):
        print(f"{r['status']:8} {str(r['reason'] or ''):22} {str(r['published_at'] or '')[:10]:10} {r['text_chars'] or 0:6} img={r['image_count']} "
              f"{r['cop_tags'] or ''} {str(r['title'] or '')[:70]} | {r['url'][:90]}")
    print(dict(crawler.stats))


def cmd_status(args):
    store = Store(DB_PATH)
    print(f"data: {DATA}  range {START}..{TODAY}  free disk {disk_free_gb():.1f} GB")
    rows = store.q("SELECT source_id, status, COUNT(*) n FROM articles GROUP BY 1,2")
    table: dict[str, Counter] = {}
    for r in rows:
        table.setdefault(r["source_id"], Counter())[r["status"]] = r["n"]
    print(f"{'source':8} {'done':>7} {'pending':>7} {'rejected':>8} {'failed':>6} {'skipped':>7}  name")
    for sid in sorted(table):
        c = table[sid]
        print(f"{sid:8} {c['done']:7} {c['pending']:7} {c['rejected']:8} {c['failed']:6} {c['skipped']:7}  {MASTER.get(sid, {}).get('name', '')[:40]}")
    tot = store.one("SELECT COUNT(*) n, SUM(status='done') d, SUM(CASE WHEN status='done' THEN text_chars END) chars, "
                    "SUM(status='done' AND scope='cop') cop FROM articles")
    print(f"total {tot['n']} discovered, {tot['d'] or 0} with full text ({(tot['chars'] or 0) / 1e6:.1f} M chars), {tot['cop'] or 0} pre-range COP articles")
    cops = Counter()
    for r in store.q("SELECT cop_tags FROM articles WHERE status='done' AND cop_tags NOT IN ('[]','')"):
        cops.update(json.loads(r["cop_tags"]))
    if cops:
        print("COP tags:", " ".join(f"{k}={v}" for k, v in sorted(cops.items(), key=lambda kv: int(kv[0][3:]))))
    print("reasons:", ", ".join(f"{r['reason']}={r['n']}" for r in store.q(
        "SELECT reason, COUNT(*) n FROM articles WHERE status IN ('rejected','failed','skipped') OR (status='pending' AND reason IS NOT NULL) "
        "GROUP BY reason ORDER BY n DESC LIMIT 14")))
    img = store.one("SELECT COUNT(*) n, SUM(status='done') d, SUM(status='pending') p, SUM(bytes) b FROM images")
    print(f"images: {img['d'] or 0} saved ({(img['b'] or 0) / 1e9:.2f} GB), {img['p'] or 0} pending, {img['n'] or 0} listed")
    last = store.one("SELECT * FROM runs ORDER BY id DESC LIMIT 1")
    if last:
        print(f"last run: {last['started_at']} .. {last['finished_at']}")


def cmd_retag(args):
    """Recompute COP tags of stored articles with the current rules (pre-range articles left without a COP are rejected)."""
    store = Store(DB_PATH)
    changed = dropped = 0
    for r in store.q("SELECT id, source_id, title, subtitle, text, published_at, cop_tags FROM articles WHERE status='done'"):
        pub = parse_dt(r["published_at"])
        cops = json.dumps(cop_tags(f"{r['title']}\n{r['subtitle'] or ''}\n{r['text']}", pub.date() if pub else None))
        if pub and pub.date() < START and cops == "[]":
            store.w("UPDATE articles SET status='rejected', reason='outside_time_range', cop_tags='[]' WHERE id=?", (r["id"],))
            dropped += 1
        elif cops != r["cop_tags"]:
            store.w("UPDATE articles SET cop_tags=? WHERE id=?", (cops, r["id"]))
            changed += 1
    print(f"retag: {changed} articles changed, {dropped} pre-range articles without a COP rejected")


def cmd_package(args):
    """A snapshot for the server's news database (`grenn-newsdb ingest-fulltext`): fulltext.db with the saved articles and
    images only, package.json (counts + SHA-256) and images.list (paths of the image files to ship next to it)."""
    store = Store(DB_PATH)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = DATA / "package" / stamp
    out.mkdir(parents=True)
    db = out / "fulltext.db"
    store.conn().execute("VACUUM INTO ?", (str(db),))
    snap = sqlite3.connect(db, isolation_level=None)
    try:
        snap.execute("PRAGMA journal_mode=DELETE")  # a single self-contained file
        snap.execute("DELETE FROM articles WHERE status<>'done'")
        snap.execute("DELETE FROM images WHERE status<>'done' OR article_id NOT IN (SELECT id FROM articles)")
        snap.execute("UPDATE articles SET listing_summary=NULL, next_try=NULL")
        snap.execute("DROP TABLE cursors")
        snap.execute("VACUUM")
        counts = snap.execute("SELECT (SELECT COUNT(*) FROM articles), (SELECT SUM(text_chars) FROM articles), "
                              "(SELECT COUNT(*) FROM images), (SELECT COUNT(DISTINCT path) FROM images), "
                              "(SELECT SUM(bytes) FROM (SELECT DISTINCT path, bytes FROM images)), "
                              "(SELECT MIN(published_at) FROM articles), (SELECT MAX(published_at) FROM articles)").fetchone()
        paths = [r[0] for r in snap.execute("SELECT DISTINCT path FROM images ORDER BY path")]
    finally:
        snap.close()
    missing = [p for p in paths if not (IMAGES / p).is_file()]
    if missing:
        sys.exit(f"{len(missing)} saved images are missing from {IMAGES} (e.g. {missing[0]})")
    (out / "images.list").write_text("".join(f"images/{p}\n" for p in paths), encoding="utf-8", newline="\n")
    digest = hashlib.sha256()
    with db.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    package = {"schema": "grenn-fulltext-package/1", "created_at": now_iso(), "range": [START.isoformat(), TODAY.isoformat()],
               "articles": counts[0], "text_chars": counts[1], "image_rows": counts[2], "image_files": counts[3],
               "image_bytes": counts[4], "published_min": counts[5], "published_max": counts[6],
               "db": "fulltext.db", "db_bytes": db.stat().st_size, "db_sha256": digest.hexdigest(), "rights": RIGHTS}
    (out / "package.json").write_text(json.dumps(package, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({**package, "folder": str(out)}, ensure_ascii=False, indent=1))


EXPORT_FIELDS = ("id", "source_id", "url", "final_url", "title", "subtitle", "authors", "published_at", "modified_at", "language", "section",
                 "keywords", "text", "text_chars", "text_sha256", "extraction", "title_verified", "relevance_score", "topics", "cop_tags",
                 "country_codes", "organization_tags", "numbers", "scope", "via", "rights_status", "fetched_at")
JSON_COLS = {"authors", "keywords", "topics", "cop_tags", "country_codes", "organization_tags", "numbers"}


def cmd_export(args):
    store = Store(DB_PATH)
    out = DATA / "export"
    out.mkdir(parents=True, exist_ok=True)
    images: dict[str, list] = {}
    for r in store.q("SELECT article_id, position, role, url, alt, caption, credit, path, width, height, sha256 FROM images WHERE status='done' "
                     "ORDER BY article_id, position"):
        images.setdefault(r["article_id"], []).append({k: r[k] for k in r.keys() if k != "article_id"})
    counts = Counter()
    handles = {}
    try:
        for r in store.conn().execute(f"SELECT {','.join(EXPORT_FIELDS)} FROM articles WHERE status='done' ORDER BY published_at"):
            rec = {k: (json.loads(r[k]) if k in JSON_COLS and r[k] else r[k]) for k in EXPORT_FIELDS}
            rec["source_name"] = MASTER.get(r["source_id"], {}).get("name")
            rec["images"] = images.get(r["id"], [])
            year = (r["published_at"] or "unknown")[:4]
            if year not in handles:
                handles[year] = open(out / f"articles-{year}.jsonl", "w", encoding="utf-8")
            handles[year].write(json.dumps(rec, ensure_ascii=False) + "\n")
            counts[year] += 1
    finally:
        for h in handles.values():
            h.close()
    manifest = {"generated_at": now_iso(), "range": [START.isoformat(), TODAY.isoformat()], "articles": sum(counts.values()),
                "by_year": dict(sorted(counts.items())), "images_dir": str(IMAGES), "rights": RIGHTS,
                "note": "Full text and images: internal research only; do not redistribute (see each source's storage_policy in config/sources.master.json)."}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="discover + fetch + images for all (or --sources) sources; resumable")
    r.add_argument("--sources")
    r.add_argument("--skip-sources")
    r.add_argument("--no-images", action="store_true")
    r.add_argument("--no-cop", action="store_true")
    r.add_argument("--discover-only", action="store_true")
    r.add_argument("--fetch-only", action="store_true")
    r.add_argument("--lanes", type=int, default=24)
    t = sub.add_parser("test", help="discover a few items of one source and fetch them")
    t.add_argument("source")
    t.add_argument("--n", type=int, default=5)
    t.add_argument("--images", action="store_true")
    t.add_argument("--no-cop", action="store_true")
    sub.add_parser("status", help="counts per source, reasons, images, disk")
    sub.add_parser("export", help="write data/export/articles-<year>.jsonl + manifest.json")
    sub.add_parser("retag", help="recompute COP tags of stored articles with the current rules")
    sub.add_parser("package", help="snapshot for the server news database (grenn-newsdb ingest-fulltext)")
    args = p.parse_args()
    {"run": cmd_run, "test": cmd_test, "status": cmd_status, "export": cmd_export, "retag": cmd_retag,
     "package": cmd_package}[args.cmd](args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""GRENN climate news database (zerocarbonx.cn): merge, crawl, export, back up.

The master store is $GRENN_NEWSDB_HOME/news.db (SQLite, WAL): one row per article URL, never pruned.
Three feeds write into it, each through the same upsert (see `Store.upsert`):
  handover      the 2026-10-30 handover package (one-off `import-handover`)
  upstream      the original project's data (data/climate.db, corpus JSONL, news archive), pulled from
                codeload.github.com whenever its main branch moves; falls back to the GitHub Pages copy
                that /srv/grenn/bin/sync-data.sh mirrors into /srv/grenn/data/current
  server-crawl  this server's own crawl of the sources it can reach, using the upstream crawler code
                (climate_agent.sync) on a separate crawler database
  fulltext-archive  packages from the full-text crawler (deploy/fulltext, `grenn_fulltext.py package`), uploaded to
                /srv/grenn/import/ and merged with `ingest-fulltext DIR`: their metadata and a short excerpt join `news`;
                the full text and images are kept privately in $HOME/fulltext/ (fulltext.db + images/<sha[:2]>/),
                which nginx does not serve and the public downloads never include
Public downloads are rebuilt into $HOME/exports/<stamp>/ and published by switching the $HOME/public link,
which nginx serves at /downloads/. Every mutating command takes $HOME/.lock and is logged in the `runs` table.

The research group's own full-text deliveries (历史新闻正文/, 新增历史气候能源全文库/, 高相关全文研究索引与样本/) are not
merged into `news`: `ingest-group DIR` archives one read-only copy in $HOME/group/raw/<label>/ and builds datasets
into $HOME/group/builds/<stamp>/ (switched through the $HOME/group/current link): protected/ holds the full text and
is served at /datasets/ behind the group account (nginx basic auth, /etc/nginx/grenn-datasets.htpasswd);
public/ holds metadata only (catalogue, labels, target ledger) and is linked into every export as /downloads/datasets/.

The full-text archive is zipped once per version into $HOME/fulltext/downloads/ and linked into the same /datasets/
build (account only). The public manifest describes every dataset (`datasets`, with `access` public / account), so the
site lists them all while account files are fetched from /datasets/.

Since 2026-11-05 the history is the governance handover (`ingest-governance DIR`): what came before was archived once
into $HOME/archive/ and removed; news.db holds its articles (metadata, labels, an excerpt) and the feeds above add
only news published after it, labelled with the same rules (grenn_governance/). Its files are published in datasets/
and its full texts in texts/ (public, the user's decision), with search-index.json for the site's list.
2026-11-06: the history is the release governance-handover-20261106 (climate_governance.sqlite: the 106,577 eligible
articles, 14 categories / 83 subcategories, 249 country codes); the 2026-11-05 history and its news.db were archived.
2026-11-09: the history is the delivery of 240,064 eligible articles (data/corpus.sqlite, same labels); its package files
are never published (its notes rule out open download sites), its texts stay readable one article at a time in texts/.
2026-11-14: `ingest-governance-batch` adds a later delivery to the history without replacing it — the second batch's
195,007 eligible articles (new_fulltexts_*.jsonl.gz; same labels, same rights). Its 126,082 records awaiting review are a
separate package and are never imported.

Commands: init · import-handover DIR · ingest-fulltext DIR · ingest-group DIR · ingest-governance DIR · ingest-governance-batch DIR ·
build-datasets · update ·
ingest-upstream · crawl · export · backup · verify · status · restore FILE · vacuum.  Run `grenn-newsdb <command> -h`.
"""
from __future__ import annotations

import argparse
import ast
import csv
import contextlib
import gzip
import hashlib
import html
import io
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

HOME = Path(os.environ.get("GRENN_NEWSDB_HOME", "/srv/grenn/newsdb"))
APP = Path(os.environ.get("GRENN_APP", "/srv/grenn/app/current"))
SITE_DATA = Path(os.environ.get("GRENN_SITE_DATA", "/srv/grenn/data/current"))
REPO = os.environ.get("GRENN_UPSTREAM_REPO", "generationzprogrammer/climate-agent-news")
# P0 sources minus those the mainland network cannot reach (Google News, The Guardian, BBC time out from the server).
CRAWL_SOURCES = tuple(filter(None, os.environ.get(
    "GRENN_CRAWL_SOURCES",
    "INT001,INT002,INT007,INT008,INT009,INT010,INT019,INT020,OFF001,OFF006,OFF013,OFF014,API001,API005",
).split(",")))
STALE_HOURS = int(os.environ.get("GRENN_STALE_HOURS", "48"))
KEEP = {"daily": 14, "weekly": 8, "monthly": 12}
KEEP_EXPORTS = 2
MONTH_MIN_RECORDS = 20  # months before the first one with this many records are stray old articles, not coverage
USER_AGENT = "GRENN-newsdb/1.0 (+https://zerocarbonx.cn)"
SCHEMA_VERSION = "1"

DB_PATH = HOME / "news.db"
CRAWLER_DIR = HOME / "crawler"
EXPORTS = HOME / "exports"
PUBLIC = HOME / "public"
BACKUPS = HOME / "backups"
FULLTEXT = HOME / "fulltext"  # private: full text + images, never under public/
FULLTEXT_DB = FULLTEXT / "fulltext.db"
FULLTEXT_IMAGES = FULLTEXT / "images"
KEEP_FULLTEXT = 3  # fulltext.db changes only on ingest: one compressed copy per version, last three kept
GROUP = HOME / "group"  # the research group's deliveries: raw/<label>/ (read-only archive) + builds/<stamp>/
GROUP_RAW = GROUP / "raw"
GROUP_BUILDS = GROUP / "builds"
GROUP_CURRENT = GROUP / "current"  # → builds/<stamp>: protected/ (nginx /datasets/, group account) + public/
KEEP_GROUP_BUILDS = 2
ARCHIVE_DOWNLOADS = FULLTEXT / "downloads"  # the full-text archive zipped for /datasets/ (linked into each group build)
# 2026-11-05: the governance handover is the text database's history (`ingest-governance`); everything before it was
# archived once into ARCHIVE_DIR and removed. Its files and full-text chunks are public (the user's decision).
GOVERNANCE = HOME / "governance"  # <version>/raw (the package, read-only) + release/ (download files) + texts/
GOV_CURRENT = GOVERNANCE / "current"
ARCHIVE_DIR = HOME / "archive"  # one compressed copy of what each governance history replaced; never served
GOVERNANCE_ORIGIN = "governance-20261109"  # origin of the history rows (earlier histories: governance-20261105, -20261106)
TEXT_CHUNK = 150  # articles per full-text chunk (texts/tNNNN.json, read by the site when an article is opened)
# 2026-11-05, user: every download is limited to 100 records at a time — the site exports from its list instead, so the
# bulk files (range / month / all, SQLite, the history's package files) are no longer published unless this is 1
PUBLIC_BULK = os.environ.get("GRENN_PUBLIC_BULK", "0") == "1"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY,
    record_id TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL UNIQUE,
    published_at TEXT NOT NULL,
    published_date TEXT NOT NULL,
    source_id TEXT,
    source_name TEXT,
    source_domain TEXT,
    language TEXT,
    title_original TEXT NOT NULL,
    summary_source TEXT,
    title_zh TEXT,
    summary_zh TEXT,
    title_en TEXT,
    summary_en TEXT,
    topics TEXT NOT NULL DEFAULT '[]',
    numbers TEXT NOT NULL DEFAULT '[]',
    places TEXT NOT NULL DEFAULT '[]',
    country_tags TEXT NOT NULL DEFAULT '[]',
    country_codes TEXT NOT NULL DEFAULT '[]',
    continent_tags TEXT NOT NULL DEFAULT '[]',
    organization_tags TEXT NOT NULL DEFAULT '[]',
    event_tags TEXT NOT NULL DEFAULT '[]',
    relevance_score INTEGER,
    translation_status TEXT,
    fact_status TEXT,
    rights_status TEXT NOT NULL DEFAULT 'metadata_only',
    content_hash TEXT,
    fetched_at TEXT,
    origin TEXT NOT NULL,
    origins TEXT NOT NULL DEFAULT '[]',
    rank INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    cohort TEXT,
    document_key TEXT,
    primary_topic TEXT,
    policy_tools TEXT NOT NULL DEFAULT '[]',
    policy_stages TEXT NOT NULL DEFAULT '[]',
    research_eligible INTEGER,
    complete_candidate INTEGER,
    label_version TEXT,
    text_ref TEXT
);
CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at);
CREATE INDEX IF NOT EXISTS idx_news_date ON news(published_date);
CREATE INDEX IF NOT EXISTS idx_news_source ON news(source_id);
CREATE INDEX IF NOT EXISTS idx_news_first_seen ON news(first_seen_at);
-- one signature per (feed, url): unchanged input rows are skipped without re-tagging
CREATE TABLE IF NOT EXISTS ingest_state (feed TEXT NOT NULL, url TEXT NOT NULL, sig TEXT NOT NULL, PRIMARY KEY (feed, url)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY, name TEXT, homepage_url TEXT, storage_policy TEXT, compliance_note TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
    status TEXT NOT NULL, stats TEXT NOT NULL DEFAULT '{}', error TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_kind ON runs(kind, started_at);
"""

JSON_FIELDS = ("topics", "numbers", "places", "country_tags", "country_codes", "continent_tags",
               "organization_tags", "event_tags", "policy_tools", "policy_stages")
TEXT_FIELDS = ("source_id", "source_name", "source_domain", "language", "title_original", "summary_source",
               "title_zh", "summary_zh", "title_en", "summary_en", "translation_status", "fact_status",
               "rights_status", "content_hash", "fetched_at", "cohort", "document_key", "primary_topic",
               "label_version", "text_ref")
INT_FIELDS = ("relevance_score", "research_eligible", "complete_candidate")
MERGE_FIELDS = ("published_at", "published_date", *TEXT_FIELDS, *JSON_FIELDS, *INT_FIELDS)
# columns added with the 2026-11-05 governance history (an older news.db gets them on connect)
ADDED_COLUMNS = {"cohort": "TEXT", "document_key": "TEXT", "primary_topic": "TEXT",
                 "policy_tools": "TEXT NOT NULL DEFAULT '[]'", "policy_stages": "TEXT NOT NULL DEFAULT '[]'",
                 "research_eligible": "INTEGER", "complete_candidate": "INTEGER", "label_version": "TEXT", "text_ref": "TEXT"}
FILL_ONLY = {"fetched_at", "content_hash"}
# later, more curated inputs win field conflicts: raw crawl rows < backfill/corpus/full-text rows < bilingual archive rows
RANK = {"articles": 1, "historical": 2, "corpus": 2, "fulltext": 2, "archive": 3, "governance": 4}
AGGREGATORS = {"news.google.com"}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# public columns, in download order (CSV header and JSONL key order)
PUBLIC_FIELDS = (
    "record_id", "published_at", "published_date", "source_name", "source_domain", "source_id", "language",
    "title_original", "summary_source", "title_zh", "summary_zh", "title_en", "summary_en", "url",
    "primary_topic", "topics", "country_tags", "country_codes", "continent_tags", "organization_tags", "policy_tools",
    "policy_stages", "event_tags", "numbers", "places", "relevance_score", "cohort", "document_key", "research_eligible",
    "complete_candidate", "label_version", "translation_status", "fact_status", "rights_status", "origin",
    "first_seen_at", "updated_at",
)
README = """GRENN 全球气候治理新闻数据库 · Global climate governance news database
https://zerocarbonx.cn/cop31/#database

历史数据为全球气候治理新闻全文数据库（标签 governance-14x83-20261106-v2）：2026-11-09 交付的第一批 240,064 篇，
加上 2026-11-12 交付、2026-11-14 并入的第二批 195,007 篇，均为通过自动完整性与相关性筛选的全文
（1992 年起，早期年份稀少，1993—1995 年无数据，2017、2021、2023 年有明显的归档采集集中，
不代表连续、均衡覆盖；两批另有待复核记录 77,196 条与 126,082 条不计入；筛选为程序自动完成，未逐篇人工核验），
按 14 个大类、83 个小类议题、国家与地区（ISO 代码，原文提及）、组织、政策工具与阶段打了可回查原文位置的规则标签。
此后每天自动追加新采集的新闻（原项目每日两次采集 + 本服务器采集，只收历史数据最后一天之后发布的），用同一套规则打标签。
此前的旧数据（2026-11-06 版历史数据）已整体替换。
每条记录对应一篇新闻（按正文与链接去重）；本组文件含元数据、标签与摘录（不超过约 600 字符），全文见 texts/。

文件
  climate-news-last7d / last30d.*   最近 7 / 30 天（按发布日期）
  monthly/climate-news-YYYY-MM.*    按月份（只含持续覆盖以来的月份）
  climate-news-all.*.zip            全部记录
  climate-news-all.sqlite.zip       全部记录的 SQLite 数据库（表 news、sources、dataset_info）
  texts/tNNNN.json、search-index.json  网站「文本数据库」检索与阅读全文用的数据
  manifest.json                     本次导出的条数、日期范围、文件大小与 SHA-256
  CSV 为 UTF-8（带 BOM，可直接用 Excel 打开），列表字段以“; ”分隔；JSONL 每行一个 JSON 对象，列表字段保持为数组。

字段
  record_id            记录编号（历史数据为 article_id）
  published_at         发布时间（ISO 8601；历史数据只有时区有依据时才是真实 UTC）；published_date 为发布者日期（只知年月的为 YYYY-MM）
  source_name          媒体 / 机构名称；source_domain 为其域名；source_id 为原项目来源编号（每日新增的记录）
  language             原文语言（und = 未声明）
  title_original       原文标题；summary_source 为摘录（历史数据取正文开头，每日新增取来源摘要，不超过约 600 字符）
  title_zh, summary_zh 中文标题、摘要；title_en, summary_en 英文标题、摘要（每日新增记录的模型生成内容，并非每条都有）
  url                  原文链接
  primary_topic        主议题候选（小类编号；按标签证据的标题 / 导语 / 正文位置加权，用于互斥展示；不代表人工确认的唯一主题；
                       空 = 无证据）；其前三位（G01–G14）为大类
  topics               议题小类（多标签；CSV 中为中文名，JSONL / SQLite 中为小类编号 G01.01–G14.06，前三位为大类）
  country_tags         原文提及的国家（中文名）；country_codes ISO 3166-1；continent_tags 大洲（部分国家有）
  organization_tags    原文提及的组织；policy_tools 政策工具措辞（regulation / economic / planning / information / cooperation）；
                       policy_stages 政策阶段措辞（proposed / adopted / effective / implemented / target）——只是措辞提及，不等于政策已实施
  event_tags, numbers, places  原项目的事件标签、关键数字与地点（每日新增记录有）
  relevance_score      原项目气候相关度评分（每日新增记录有）
  cohort               original_recovery 原库补齐 / new_library 独立新增库 / new_expansion_20261106 全球扩展采集 /
                       historical_* · targeted_* 历史与定向补充 / daily 每日新增；document_key 历史数据的文档键
  research_eligible    1 = 研究集合（历史数据均为通过完整性与相关性筛选的全文）；complete_candidate 1 = 通过自动完整性检查
  label_version        标签规则版本（governance-14x83-20261106-v2；均为机器候选，未经人工确认）
  translation_status   中文内容状态（model_generated_needs_review = 模型生成、待人工复核）
  fact_status          事实状态（source_claim_unverified = 来源说法，未经核验）
  rights_status        权利状态（历史数据为交付包标注的权利状态，版权归原发布者；metadata_only = 仅元数据与短摘录）
  origin               最早收录渠道：governance-20261106 历史数据 / upstream 原项目采集 / server-crawl 本站服务器采集
  first_seen_at        首次收录本库的时间（UTC）；updated_at 最近一次内容更新时间（UTC）

使用须知
  - 标签是双语词表规则的机器候选：国家只表示原文提及，不代表事件地点、发言主体或立场；共现不代表合作或因果。
  - 来源结构不均（少数行业与气候媒体占大多数），不是全球新闻的随机样本；不声称连续覆盖。研究请报告分母、来源、语言、年份与筛选版本。
  - 摘要与译文由模型生成，重要数字、政策状态与承诺请打开原文并以官方文件核验。
  - 第三方新闻的权利归原作者与媒体所有；引用请保留来源与链接。
  - 文本中的电子邮箱已替换为 [REDACTED_EMAIL]。
"""


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def log(message: str) -> None:
    print(message, flush=True)


# ---------------------------------------------------------------- storage

class Locked(RuntimeError):
    pass


@contextlib.contextmanager
def lock():
    """Exclusive, non-blocking: a second job exits instead of queueing behind a long crawl."""
    HOME.mkdir(parents=True, exist_ok=True)
    handle = open(HOME / ".lock", "a+")
    try:
        try:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:  # Windows (local testing): no locking
            pass
        except BlockingIOError as exc:
            raise Locked("another newsdb job is running") from exc
        yield
    finally:
        handle.close()


def connect(path: Path = DB_PATH, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30, isolation_level=None)
        have = {r[1] for r in conn.execute("PRAGMA table_info(news)")}
        for column, kind in ADDED_COLUMNS.items():
            if have and column not in have:
                conn.execute(f"ALTER TABLE news ADD COLUMN {column} {kind}")
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA synchronous=NORMAL")
        if not conn.execute("SELECT 1 FROM meta WHERE key='schema_version'").fetchone():
            conn.execute("INSERT INTO meta VALUES ('schema_version', ?), ('created_at', ?)", (SCHEMA_VERSION, now_iso()))
    conn.row_factory = sqlite3.Row
    return conn


def meta_get(conn, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def meta_set(conn, key: str, value: str) -> None:
    conn.execute("INSERT INTO meta VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


class Run:
    """One row in `runs`; status/stats are filled in by the command."""

    def __init__(self, conn, kind: str):
        self.conn, self.kind, self.stats, self.status = conn, kind, {}, "ok"
        self.id = conn.execute("INSERT INTO runs (kind, started_at, status) VALUES (?, ?, 'running')",
                               (kind, now_iso())).lastrowid

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        error = None
        if exc is not None:
            self.status, error = "failed", f"{exc_type.__name__}: {exc}"[:2000]
        self.conn.execute("UPDATE runs SET finished_at=?, status=?, stats=?, error=? WHERE id=?",
                          (now_iso(), self.status, json.dumps(self.stats, ensure_ascii=False), error, self.id))
        log(json.dumps({"run": self.kind, "status": self.status, **({"error": error} if error else {}),
                        "stats": self.stats}, ensure_ascii=False))
        return False


def _empty(value) -> bool:
    return value is None or value == "" or value == "[]"


class Store:
    def __init__(self, conn):
        self.conn = conn
        # once the governance history is in, the other feeds only add news published after it, labelled the same way
        self.since = meta_get(conn, "daily_since")

    def seen(self, feed: str, url: str, sig: str) -> bool:
        row = self.conn.execute("SELECT sig FROM ingest_state WHERE feed=? AND url=?", (feed, url)).fetchone()
        return bool(row and row[0] == sig)

    def mark(self, feed: str, url: str, sig: str) -> None:
        self.conn.execute("INSERT INTO ingest_state VALUES (?, ?, ?) ON CONFLICT(feed, url) DO UPDATE SET sig=excluded.sig",
                          (feed, url, sig))

    def upsert(self, rec: dict, *, origin: str, rank: int, stamp: str) -> str:
        url = rec["url"]
        if self.since and not origin.startswith("governance-"):
            if rec["published_date"] < self.since:
                return "rejected"  # the history ends before `daily_since`: older items stay out
            rec = label_daily(rec)
        row = self.conn.execute("SELECT * FROM news WHERE url=?", (url,)).fetchone()
        if row is None:
            record_id = rec.get("record_id") or ""
            if not record_id or self.conn.execute("SELECT 1 FROM news WHERE record_id=?", (record_id,)).fetchone():
                record_id = "news_" + hashlib.sha1(url.encode()).hexdigest()[:16]
            values = {f: rec.get(f) for f in MERGE_FIELDS}
            values.update(record_id=record_id, url=url, origin=origin, origins=json.dumps([origin]), rank=rank,
                          first_seen_at=stamp, updated_at=stamp)
            for f in JSON_FIELDS:
                values[f] = values[f] or "[]"
            values["rights_status"] = values["rights_status"] or "metadata_only"
            cols = ",".join(values)
            self.conn.execute(f"INSERT INTO news ({cols}) VALUES ({','.join('?' * len(values))})", tuple(values.values()))
            return "added"
        changes = {}
        for f in MERGE_FIELDS:
            new, old = rec.get(f), row[f]
            if _empty(new) or new == old:
                continue
            if _empty(old) or (f not in FILL_ONLY and rank >= row["rank"]):
                changes[f] = new
        origins = json.loads(row["origins"] or "[]")
        content_changed = bool(changes)
        if origin not in origins:
            changes["origins"] = json.dumps([*origins, origin])
        if rank > row["rank"]:
            changes["rank"] = rank
        if content_changed:
            changes["updated_at"] = stamp
        if changes:
            sets = ",".join(f"{k}=?" for k in changes)
            self.conn.execute(f"UPDATE news SET {sets} WHERE id=?", (*changes.values(), row["id"]))
        return "updated" if content_changed else "same"


# ---------------------------------------------------------------- record conversion

_climate = None


def climate():
    """The upstream package (taxonomy, place detection, crawler), imported from $GRENN_APP/src."""
    global _climate
    if _climate is None:
        # the taxonomy builds one regex per place / country term (thousands); the default 512-entry cache
        # makes every record recompile them (~100 ms/record instead of ~9)
        re._MAXCACHE = max(getattr(re, "_MAXCACHE", 512), 50000)
        sys.path.insert(0, str(APP / "src"))
        from climate_agent import historical_backfill, translation  # noqa: E402
        _climate = {"to_record": historical_backfill.archive_item_to_historical_record,
                    "detect_places": translation.detect_places,
                    "continents": historical_backfill.COUNTRY_CONTINENT}
    return _climate


_governance = None


def governance():
    """The history's labelling rules (grenn_governance/, copied from the handover package): the 14 categories
    (`parents`: code, zh, en), the 83 subcategories (`topics`: code, parent, zh, en), countries and organisation names."""
    global _governance
    if _governance is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from grenn_governance import governance_labels, governance_taxonomy_v2 as v2, taxonomy  # noqa: E402
        codes = json.loads((Path(governance_labels.__file__).with_name("country_codes.json")).read_text(encoding="utf-8"))
        cjk = re.compile(r"[一-鿿]")
        orgs = {code: name for group in taxonomy.ORGANIZATION_GROUPS for code, name, _ in group["items"]}
        for code, terms in governance_labels.GOVERNANCE_ORGANIZATIONS.items():
            orgs.setdefault(code, next((t for t in terms if cjk.search(t)), code))
        _governance = {"label": v2.label, "version": v2.VERSION, "parents": v2.PARENTS,
                       "topics": [(t["code"], t["parent"], t["name_zh"], t["name_en"]) for t in v2.TOPICS],
                       "countries": {c["alpha2"]: c for c in codes["countries"]}, "organizations": orgs}
    return _governance


def country_fields(alpha2s) -> dict:
    """country_codes / country_tags / continent_tags of a list of ISO alpha-2 codes (the history's own country list)."""
    known = governance()["countries"]
    codes = [{k: known[a][k] for k in ("alpha2", "alpha3", "name_zh", "name_en")} for a in alpha2s if a in known]
    continents = []
    try:
        table = climate()["continents"]
    except Exception:  # the upstream code is not there (local tests): continents stay empty
        table = {}
    for c in codes:
        continent = table.get(c["name_en"])
        if continent and continent not in continents:
            continents.append(continent)
    return {"country_codes": json.dumps(codes, ensure_ascii=False),
            "country_tags": json.dumps([c["name_zh"] for c in codes], ensure_ascii=False),
            "continent_tags": json.dumps(continents, ensure_ascii=False)}


def topic_order(primary: str | None, topics) -> list:
    order = [t[0] for t in governance()["topics"]]
    rest = sorted({t for t in topics if t != primary}, key=lambda t: order.index(t) if t in order else len(order))
    return ([primary] if primary and primary != "unclassified" and primary in topics else []) + rest


def label_daily(rec: dict) -> dict:
    """A newly collected item gets the history's labels from its title and source excerpt (no full text)."""
    g = governance()
    labels = g["label"](rec.get("title_original") or rec.get("title_en") or "", rec.get("summary_source") or rec.get("summary_en") or "")
    return {**rec, **country_fields(labels["country_mentions"]),
            "topics": json.dumps(topic_order(labels["primary_subcategory"], labels["subcategory_mentions"])),
            "primary_topic": labels["primary_subcategory"], "organization_tags": json.dumps(labels["organization_mentions"]),
            "policy_tools": json.dumps(labels["policy_tool_mentions"]), "policy_stages": json.dumps(labels["policy_stage_mentions"]),
            "label_version": labels["version"], "cohort": "daily"}


def _loads(value, default):
    if isinstance(value, (list, dict)):
        return value
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        try:
            return ast.literal_eval(value)  # upstream stores some lists as Python literals
        except (ValueError, SyntaxError):
            return default


def _text(value) -> str | None:
    if value is None:
        return None
    value = EMAIL.sub("[REDACTED_EMAIL]", str(value)).strip()
    return value or None


def _host(url: str | None) -> str | None:
    host = (urlparse(url or "").hostname or "").lower()
    return host.removeprefix("www.") or None


def _utc(value) -> tuple[str, str] | None:
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    moment = moment.astimezone(UTC)
    return moment.isoformat(), moment.date().isoformat()


def finish(rec: dict) -> dict | None:
    """Validate and normalise a record into `news` columns (JSON text for lists)."""
    url = str(rec.get("url") or "").strip()
    if not url.startswith(("http://", "https://")) or not _text(rec.get("title_original")):
        return None
    when = _utc(rec.get("published_at"))
    if not when:
        return None
    out = {"url": url, "record_id": rec.get("record_id"), "published_at": when[0], "published_date": when[1]}
    for f in TEXT_FIELDS:
        out[f] = _text(rec.get(f))
    domain = (out["source_domain"] or "").removeprefix("www.")
    if not domain or domain.startswith("google:") or domain in AGGREGATORS:
        host = _host(url)  # an aggregator's host says nothing about the publisher: leave it empty so it never overwrites one
        out["source_domain"] = None if host in AGGREGATORS else host
    for f in JSON_FIELDS:
        value = _loads(rec.get(f), [])
        out[f] = json.dumps(value if isinstance(value, list) else [], ensure_ascii=False)
    for f in INT_FIELDS:
        value = rec.get(f)
        out[f] = int(value) if str(value if value is not None else "").lstrip("-").isdigit() else None
    return out


def from_corpus(rec: dict) -> dict | None:
    """A corpus / historical_articles record (upstream ClimateText format)."""
    meta = _loads(rec.get("metadata"), {}) or {}
    flags = _loads(rec.get("quality_flags"), {}) or {}
    return finish({
        **{k: rec.get(k) for k in ("record_id", "source_id", "source_name", "source_domain", "language", "title_original",
                                    "summary_source", "relevance_score", "fetched_at", *JSON_FIELDS)},
        "url": rec.get("canonical_url"),
        "published_at": rec.get("published_at_utc"),
        "title_zh": meta.get("title_zh"), "summary_zh": meta.get("summary_zh"),
        "title_en": meta.get("title_en"), "summary_en": meta.get("summary_en"),
        "translation_status": meta.get("translation_status"),
        "fact_status": "source_claim_unverified" if flags.get("source_claim_unverified") else None,
        "rights_status": meta.get("rights_status") or "metadata_only",
    })


def from_archive(item: dict) -> dict | None:
    """A news_archive.json record: bilingual, quality-gated."""
    base = climate()["to_record"](item, fetched_at=item.get("fetched_at") or now_iso())
    if not base:
        return None
    rec = from_corpus(base)
    if not rec:
        return None
    for f in ("title_zh", "summary_zh", "title_en", "summary_en", "translation_status", "fact_status", "source_name",
              "content_hash", "fetched_at"):
        value = _text(item.get(f))
        if value:
            rec[f] = value
    for f in ("topics", "numbers"):
        if item.get(f):
            rec[f] = json.dumps(list(item[f]), ensure_ascii=False)
    return rec


def from_article(row: dict, source_names: dict) -> dict | None:
    """An upstream-schema `articles` row (upstream DB, handover DB or the server's crawler DB)."""
    meta = _loads(row.get("metadata_json"), {}) or {}
    places = _loads(meta.get("places"), [])
    places = [p for p in places if isinstance(p, dict)] if isinstance(places, list) else []
    if not places:
        places = climate()["detect_places"](f"{row.get('title_original') or ''} {row.get('summary_source') or ''}")
    item = {
        "article_id": row.get("article_id"), "canonical_url": row.get("canonical_url"),
        "published_at": row.get("published_at_utc") or row.get("fetched_at"),
        "title_original": row.get("title_original"), "summary_source": row.get("summary_source"),
        "summary_zh": meta.get("summary_zh"), "places": places,
        "topics": _loads(row.get("topics_json"), []), "numbers": _loads(row.get("numbers_json"), []),
        "source_id": row.get("source_id"),
        "source_name": meta.get("publisher_name") or source_names.get(row.get("source_id")),
        "relevance_score": row.get("relevance_score"), "language": row.get("language"),
        "fact_status": meta.get("fact_status"),
    }
    base = climate()["to_record"](item, fetched_at=row.get("fetched_at") or now_iso())
    rec = from_corpus(base) if base else None
    if not rec:
        return None
    rec.update({
        "title_zh": _text(row.get("title_zh")), "summary_zh": _text(meta.get("summary_zh")),
        "title_en": _text(meta.get("title_en")), "summary_en": _text(meta.get("summary_en")),
        "translation_status": _text(meta.get("translation_status")), "fact_status": _text(meta.get("fact_status")),
        "rights_status": _text(row.get("rights_status")) or "metadata_only",
        "content_hash": _text(row.get("content_hash")), "fetched_at": _text(row.get("fetched_at")),
    })
    homepage = _host(meta.get("publisher_homepage"))
    if homepage:
        rec["source_domain"] = homepage
    return rec


def excerpt(subtitle: str | None, text: str | None, limit: int = 600) -> str | None:
    """The public excerpt of a full-text article: the publisher's standfirst, else its opening paragraphs, cut at a sentence."""
    base = re.sub(r"\s+", " ", subtitle or "").strip()
    if len(base) < 80:
        paragraphs = [p for p in (text or "").split("\n\n") if len(p) >= 60 and not p.startswith("- ")]
        base = re.sub(r"\s+", " ", " ".join(paragraphs[:3])).strip()
    if len(base) <= limit:
        return base or None
    cut = max(base.rfind(mark, 0, limit) for mark in (". ", "。", "! ", "? ", "！", "？"))
    return base[:cut + 1] if cut > limit // 2 else base[:limit].rsplit(" ", 1)[0] + "…"


def fulltext_rows(path: Path):
    """Saved articles of a full-text store as ingest rows: everything except the text itself (only its hash and excerpt)."""
    src = sqlite3.connect(f"file:{path}?immutable=1", uri=True)
    src.row_factory = sqlite3.Row
    try:
        for row in src.execute("SELECT * FROM articles WHERE status='done' ORDER BY published_at"):
            raw = {k: row[k] for k in row.keys() if k not in ("text", "listing_summary", "next_try", "attempts")}
            raw["canonical_url"] = row["url"]
            raw["excerpt"] = excerpt(row["subtitle"], row["text"])
            yield raw
    finally:
        src.close()


def from_fulltext(row: dict, source_names: dict) -> dict | None:
    """A full-text archive article: same tagging path as the other feeds (title + excerpt), COP tags from the full text."""
    host = _host(row.get("url")) or ""
    name = host if row.get("source_id") in ("API001", "API005") else source_names.get(row.get("source_id")) or host
    summary = row.get("excerpt")
    item = {
        "article_id": row.get("id"), "canonical_url": row.get("url"), "published_at": row.get("published_at"),
        "title_original": row.get("title"), "summary_source": summary,
        "places": climate()["detect_places"](f"{row.get('title') or ''} {summary or ''}"),
        "topics": _loads(row.get("topics"), []), "numbers": _loads(row.get("numbers"), []),
        "source_id": row.get("source_id"), "source_name": name, "relevance_score": row.get("relevance_score"),
        "language": (row.get("language") or "").split("-")[0].lower() or None,
    }
    base = climate()["to_record"](item, fetched_at=row.get("fetched_at") or now_iso())
    rec = from_corpus(base) if base else None
    if not rec:
        return None
    rec.update(event_tags=json.dumps(_loads(row.get("cop_tags"), [])), rights_status="metadata_only",
               fact_status="source_claim_unverified", content_hash=row.get("text_sha256"), fetched_at=_text(row.get("fetched_at")))
    return rec


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _sig(raw) -> str:
    return hashlib.sha1(json.dumps(raw, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def ingest_rows(store: Store, rows, *, feed: str, kind: str, origin: str, convert, stamp: str) -> dict:
    """Upsert an iterable of raw rows; rows whose raw content is unchanged since the last run are skipped."""
    counts = {"seen": 0, "added": 0, "updated": 0, "same": 0, "skipped": 0, "rejected": 0}
    conn = store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        for raw in rows:
            counts["seen"] += 1
            url = str(raw.get("canonical_url") or "").strip()
            if not url:
                counts["rejected"] += 1
                continue
            sig = _sig(raw)
            if store.seen(feed, url, sig):
                counts["skipped"] += 1
                continue
            rec = convert(raw)
            if rec is None:
                counts["rejected"] += 1
            else:
                counts[store.upsert(rec, origin=origin, rank=RANK[kind], stamp=stamp)] += 1
            store.mark(feed, url, sig)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return counts


def ingest_sqlite(store: Store, path: Path, *, prefix: str, origin: str, stamp: str, snapshot: bool = True) -> dict:
    """articles + historical_articles + sources from an upstream-schema climate.db.

    A snapshot (downloaded / handed-over file) is opened immutable, so no -wal/-shm files are needed;
    the live crawler DB is opened normally so un-checkpointed WAL pages are read too."""
    src = sqlite3.connect(f"file:{path}?immutable=1", uri=True) if snapshot else sqlite3.connect(path)
    src.row_factory = sqlite3.Row
    try:
        if src.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError(f"{path} failed quick_check")
        tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        source_rows = [dict(r) for r in src.execute("SELECT * FROM sources")] if "sources" in tables else []
        names = {r["source_id"]: r.get("name") for r in source_rows}
        if source_rows:
            store.conn.executemany(
                "INSERT INTO sources VALUES (?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET name=excluded.name, "
                "homepage_url=excluded.homepage_url, storage_policy=excluded.storage_policy, "
                "compliance_note=excluded.compliance_note, updated_at=excluded.updated_at",
                [(r["source_id"], r.get("name"), r.get("homepage_url"), r.get("storage_policy"), r.get("compliance_note"), stamp)
                 for r in source_rows])
        result = {}
        if "articles" in tables:
            rows = (dict(r) for r in src.execute("SELECT * FROM articles ORDER BY fetched_at"))
            result["articles"] = ingest_rows(store, rows, feed=f"{prefix}:articles", kind="articles", origin=origin,
                                             convert=lambda r: from_article(r, names), stamp=stamp)
        if "historical_articles" in tables:
            def hist(r):
                r = dict(r)
                for key in ("topics", "numbers", "places", "country_tags", "continent_tags", "quality_flags", "metadata"):
                    r[key] = _loads(r.pop(f"{key}_json", None), [] if key not in ("quality_flags", "metadata") else {})
                return r
            rows = (hist(r) for r in src.execute("SELECT * FROM historical_articles ORDER BY published_at_utc"))
            result["historical"] = ingest_rows(store, rows, feed=f"{prefix}:historical", kind="historical", origin=origin,
                                               convert=from_corpus, stamp=stamp)
        return result
    finally:
        src.close()


def _jsonl(path: Path):
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def ingest_files(store: Store, folder: Path, *, prefix: str, origin: str, stamp: str) -> dict:
    result = {}
    corpus = folder / "climate_text_corpus.jsonl"
    if corpus.exists():
        result["corpus"] = ingest_rows(store, _jsonl(corpus), feed=f"{prefix}:corpus", kind="corpus", origin=origin,
                                       convert=from_corpus, stamp=stamp)
    archive = folder / "news_archive.json"
    if archive.exists():
        records = json.loads(archive.read_text(encoding="utf-8-sig")).get("records") or []
        result["archive"] = ingest_rows(store, records, feed=f"{prefix}:archive", kind="archive", origin=origin,
                                        convert=from_archive, stamp=stamp)
    return result


# ---------------------------------------------------------------- commands: ingest

def verify_handover_checksums(folder: Path) -> dict:
    """文件说明.txt lists `name` lines each followed by its SHA-256; refuse a package that does not match."""
    note = folder / "文件说明.txt"
    if not note.exists():
        return {"checked": 0}
    lines = [line.strip() for line in note.read_text(encoding="utf-8-sig").splitlines()]
    checked = 0
    for name, digest in zip(lines, lines[1:]):
        if re.fullmatch(r"[0-9a-f]{64}", digest) and (folder / name).is_file():
            actual = hashlib.sha256((folder / name).read_bytes()).hexdigest()
            if actual != digest:
                raise RuntimeError(f"{name}: SHA-256 mismatch (package damaged in transfer?)")
            checked += 1
    return {"checked": checked}


def cmd_import_handover(args) -> int:
    folder = Path(args.folder)
    origin = args.origin
    with lock():
        conn = connect()
        with Run(conn, "import-handover") as run:
            run.stats["checksums"] = verify_handover_checksums(folder)
            stamp = now_iso()
            store = Store(conn)
            if (folder / "climate.db").exists():
                run.stats.update(ingest_sqlite(store, folder / "climate.db", prefix="handover", origin=origin, stamp=stamp))
            run.stats.update(ingest_files(store, folder, prefix="handover", origin=origin, stamp=stamp))
            meta_set(conn, "handover_imported_at", stamp)
        if not args.no_export:
            export(conn, force=True)
    return 0


def cmd_ingest_fulltext(args) -> int:
    """A full-text package: verify everything first, then install text + images privately and merge the metadata."""
    folder = Path(args.folder)
    with lock():
        conn = connect()
        with Run(conn, "ingest-fulltext") as run:
            package = json.loads((folder / "package.json").read_text(encoding="utf-8"))
            if package.get("schema") != "grenn-fulltext-package/1":
                raise RuntimeError(f"{folder}: not a full-text package")
            db = folder / package["db"]
            if _sha256(db) != package["db_sha256"]:
                raise RuntimeError(f"{db}: SHA-256 mismatch (package damaged in transfer?)")
            src = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
            src.row_factory = sqlite3.Row
            try:
                if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError(f"{db} failed integrity_check")
                images = src.execute("SELECT DISTINCT path, sha256, bytes FROM images WHERE status='done'").fetchall()
                articles = src.execute("SELECT count(*) FROM articles WHERE status='done'").fetchone()[0]
            finally:
                src.close()
            if articles != package["articles"]:
                raise RuntimeError(f"package.json says {package['articles']} articles, fulltext.db has {articles}")
            todo = []
            for img in images:  # content-addressed: an image already in the store is never copied twice
                target = FULLTEXT_IMAGES / img["path"]
                if target.is_file() and target.stat().st_size == img["bytes"]:
                    continue
                source = folder / "images" / img["path"]
                if not source.is_file() or _sha256(source) != img["sha256"]:
                    raise RuntimeError(f"image {img['path']} missing or damaged in the package")
                todo.append((source, target))
            for source, target in todo:
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_name(target.name + ".tmp")
                shutil.copyfile(source, tmp)
                os.replace(tmp, target)
            FULLTEXT.mkdir(parents=True, exist_ok=True)
            if FULLTEXT_DB.exists():
                run.stats["previous_backup"] = backup_fulltext(conn)  # the snapshot being replaced is kept
            tmp = FULLTEXT / ".fulltext.db.tmp"
            shutil.copyfile(db, tmp)
            os.replace(tmp, FULLTEXT_DB)
            names = {r[0]: r[1] for r in conn.execute("SELECT source_id, name FROM sources")}
            run.stats["merge"] = ingest_rows(Store(conn), fulltext_rows(FULLTEXT_DB), feed="fulltext:articles", kind="fulltext",
                                             origin="fulltext-archive", convert=lambda r: from_fulltext(r, names), stamp=now_iso())
            run.stats.update(articles=articles, images=len(images), images_copied=len(todo), package=package["created_at"])
            meta_set(conn, "fulltext_package", package["created_at"])
            meta_set(conn, "fulltext_ingested_at", now_iso())
            run.stats["backup"] = backup_fulltext(conn)
            run.stats["datasets"] = rebuild_datasets(conn)  # the account-only downloads of the archive
        if not args.no_export:
            export(conn, force=True)
    return 0


# since 2026-11-05 the upstream repo is private: a read-only token in this file (root:grenn 640, also read by
# sync-data.sh) lets the API and codeload answer; without it both fail and the Pages-mirror fallback below is used
GITHUB_TOKEN_FILE = Path(os.environ.get("GRENN_GITHUB_TOKEN_FILE", "/srv/grenn/conf/github-token"))


def _http(url: str, *, accept: str = "*/*", timeout: int = 30):
    headers = {"User-Agent": USER_AGENT, "Accept": accept}
    if urlparse(url).hostname in ("api.github.com", "codeload.github.com"):
        with contextlib.suppress(OSError):
            token = GITHUB_TOKEN_FILE.read_text(encoding="utf-8").strip()
            if token:
                headers["Authorization"] = f"token {token}"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


def upstream_head() -> str | None:
    try:
        with _http(f"https://api.github.com/repos/{REPO}/commits/main", accept="application/vnd.github.sha") as resp:
            sha = resp.read(100).decode().strip()
        return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None
    except Exception as exc:  # the API is a shortcut only; without it we download and compare content
        log(f"upstream head check failed: {type(exc).__name__}: {exc}")
        return None


WANTED = {"data/climate.db", "data/climate_text_corpus.jsonl", "data/news_archive.json"}


def download_upstream(dest: Path) -> dict:
    """Stream the main-branch tarball and keep only the data files (by fixed names, never member paths)."""
    url = f"https://codeload.github.com/{REPO}/tar.gz/refs/heads/main"
    tmp = dest / "main.tar.gz"
    limit = 1_500_000_000
    with _http(url, timeout=60) as resp, tmp.open("wb") as handle:
        size = 0
        while chunk := resp.read(1 << 20):
            size += len(chunk)
            if size > limit:
                raise RuntimeError("upstream tarball larger than expected")
            handle.write(chunk)
    found = {}
    with tarfile.open(tmp, "r:gz") as tar:
        for member in tar:
            parts = member.name.split("/", 1)
            if len(parts) == 2 and parts[1] in WANTED and member.isreg():
                target = dest / Path(parts[1]).name
                with tar.extractfile(member) as src, target.open("wb") as out:
                    shutil.copyfileobj(src, out)
                found[parts[1]] = member.size
    tmp.unlink()
    if "data/climate.db" not in found:
        raise RuntimeError("upstream tarball has no data/climate.db")
    return {"bytes": size, "files": found}


def ingest_upstream(conn, *, force: bool = False) -> dict:
    stats: dict = {}
    head = upstream_head()
    stats["head"] = head
    if head and head == meta_get(conn, "upstream_sha") and not force:
        stats["status"] = "unchanged"
        meta_set(conn, "upstream_checked_at", now_iso())
        return stats
    stamp = now_iso()
    store = Store(conn)
    work = Path(tempfile.mkdtemp(prefix="upstream-", dir=HOME))
    try:
        try:
            stats["download"] = download_upstream(work)
            stats.update(ingest_sqlite(store, work / "climate.db", prefix="upstream", origin="upstream", stamp=stamp))
            stats.update(ingest_files(store, work, prefix="upstream", origin="upstream", stamp=stamp))
            stats["via"] = "codeload"
            if head:
                meta_set(conn, "upstream_sha", head)
        except Exception as exc:
            # GitHub unreachable or the repo changed shape: take what the Pages mirror has (bilingual corpus + archive)
            stats["codeload_error"] = f"{type(exc).__name__}: {exc}"[:300]
            if not (SITE_DATA / "news_archive.json").exists():
                raise
            stats.update(ingest_files(store, SITE_DATA, prefix="upstream", origin="upstream", stamp=stamp))
            stats["via"] = "pages-mirror"
    finally:
        shutil.rmtree(work, ignore_errors=True)
    meta_set(conn, "upstream_checked_at", now_iso())
    meta_set(conn, "upstream_ingested_at", stamp)
    stats["status"] = "ingested"
    return stats


def crawl(conn, sources: tuple[str, ...]) -> dict:
    """Run the upstream P0 crawler on the crawler DB, then merge its articles."""
    climate()
    from climate_agent.db import Database
    from climate_agent.source_health import load_source_health, save_source_health, source_is_due, update_source_health
    from climate_agent.sync import sync_p0
    CRAWLER_DIR.mkdir(parents=True, exist_ok=True)
    db = Database(CRAWLER_DIR / "climate.db")
    db.initialize()
    db.import_sources(APP / "config" / "sources.master.json")
    health_path = CRAWLER_DIR / "source_health.json"
    health = load_source_health(health_path)
    due = tuple(s for s in sources if source_is_due(health, s))
    result = sync_p0(db, due) if due else {"status": "ok", "results": []}
    update_source_health(health, result["results"])
    save_source_health(health_path, health)
    stats = {
        "sources_due": len(due), "sources_ok": result.get("sources_ok", 0),
        "quarantined": [s for s in sources if s not in due],
        "failed": {r["source_id"]: (r.get("error") or "")[:120] for r in result["results"] if r["status"] == "failed"},
        "new_in_crawler": sum(r.get("items_new", 0) for r in result["results"]),
    }
    stats["merge"] = ingest_sqlite(Store(conn), CRAWLER_DIR / "climate.db", prefix="crawl", origin="server-crawl",
                                   stamp=now_iso(), snapshot=False).get("articles")
    return stats


def cmd_ingest_upstream(args) -> int:
    with lock():
        conn = connect()
        with Run(conn, "ingest-upstream") as run:
            run.stats.update(ingest_upstream(conn, force=args.force))
        export(conn)
    return 0


def cmd_crawl(args) -> int:
    sources = tuple(args.sources.split(",")) if args.sources else CRAWL_SOURCES
    with lock():
        conn = connect()
        with Run(conn, "crawl") as run:
            run.stats.update(crawl(conn, sources))
        export(conn)
    return 0


def cmd_update(args) -> int:
    """The scheduled job: upstream → own crawl → downloads. One failing step does not stop the others."""
    with lock():
        conn = connect()
        failed = False
        if not args.no_upstream:
            try:
                with Run(conn, "ingest-upstream") as run:
                    run.stats.update(ingest_upstream(conn, force=args.force))
            except Exception:
                failed = True
        if not args.no_crawl:
            try:
                with Run(conn, "crawl") as run:
                    run.stats.update(crawl(conn, CRAWL_SOURCES))
            except Exception:
                failed = True
        export(conn, force=args.force)
        conn.execute("PRAGMA optimize")
        stale = staleness(conn)
        if stale:
            log(f"WARNING: {stale}")
    return 1 if failed else 0


def staleness(conn) -> str | None:
    latest = conn.execute("SELECT max(first_seen_at) FROM news").fetchone()[0]
    if latest and datetime.fromisoformat(latest) < datetime.now(UTC) - timedelta(hours=STALE_HOURS):
        return f"no new records since {latest} (> {STALE_HOURS} h)"
    return None


# ---------------------------------------------------------------- export

def _csv_value(field: str, value):
    if field in JSON_FIELDS:
        items = json.loads(value or "[]")
        if field == "topics":
            names = {t[0]: t[2] for t in governance()["topics"]}
            items = [names.get(i, i) for i in items]
        elif field == "country_codes":
            items = [i.get("alpha3") or i.get("alpha2") for i in items if isinstance(i, dict)]
        elif field == "places":
            items = [i.get("name_zh") for i in items if isinstance(i, dict)]
        return "; ".join(str(i) for i in items if i)
    return "" if value is None else value


class Sink:
    """A CSV + JSONL pair being written; counts its rows."""

    def __init__(self, base: Path, fields):
        base.parent.mkdir(parents=True, exist_ok=True)
        self.csv_path, self.jsonl_path = base.with_suffix(".csv"), base.with_suffix(".jsonl")
        self.csv_handle = self.csv_path.open("w", encoding="utf-8-sig", newline="")
        self.jsonl_handle = self.jsonl_path.open("w", encoding="utf-8", newline="\n")
        self.writer = csv.writer(self.csv_handle)
        self.writer.writerow(fields)
        self.fields, self.count = fields, 0

    def write(self, row) -> None:
        self.writer.writerow([_csv_value(f, row[f]) for f in self.fields])
        item = {f: (json.loads(row[f] or "[]") if f in JSON_FIELDS else row[f]) for f in self.fields}
        self.jsonl_handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        self.count += 1

    def close(self) -> None:
        self.csv_handle.close()
        self.jsonl_handle.close()


def _file_entry(root: Path, path: Path, **extra) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return {**extra, "path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def _precompress(path: Path) -> None:
    """A .br (where the brotli command is installed) and a .gz beside a file the site fetches, sent as they are by nginx's
    brotli_static / gzip_static (2026-11-07: the index parts are a third smaller in brotli than in on-the-fly gzip)."""
    brotli = shutil.which("brotli")
    if brotli and subprocess.run([brotli, "-q", "9", "-f", "-o", f"{path}.br", str(path)], check=False).returncode:
        Path(f"{path}.br").unlink(missing_ok=True)
    with path.open("rb") as src, gzip.open(f"{path}.gz", "wb", compresslevel=9) as dst:
        shutil.copyfileobj(src, dst)


def _zip(source: Path, target: Path, arcname: str) -> None:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(source, arcname)


def _switch(link: Path, final: Path) -> None:
    """Point `link` at the finished folder `final` in one atomic rename (nginx serves through the link)."""
    tmp = link.with_name(f".{link.name}.tmp")
    with contextlib.suppress(FileNotFoundError):
        tmp.unlink()
    try:
        tmp.symlink_to(final.relative_to(link.parent), target_is_directory=True)
        os.replace(tmp, link)
    except OSError:  # Windows without symlink rights (local testing): plain copy
        shutil.rmtree(link, ignore_errors=True)
        shutil.copytree(final, link)


def _place(source: Path, target: Path) -> None:
    """An unchanged file in a second place: hard link (no extra space), copy where links are not possible."""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copyfile(source, target)


def export(conn, *, force: bool = False) -> dict | None:
    """Rebuild the download set when the data changed since the last export (or the public link is missing)."""
    with Run(conn, "export") as run:
        state = conn.execute("SELECT count(*), max(updated_at), max(first_seen_at) FROM news").fetchone()
        fingerprint = f"{state[0]}|{state[1]}|{state[2]}"
        if not force and PUBLIC.exists() and meta_get(conn, "export_fingerprint") == fingerprint:
            run.status, run.stats["reason"] = "skipped", "unchanged"
            return None
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        EXPORTS.mkdir(parents=True, exist_ok=True)
        work = EXPORTS / f".{stamp}.tmp"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir()
        try:
            manifest = write_export(conn, work, fields=PUBLIC_FIELDS)
            run.stats.update(records=manifest["records"], files=len(manifest["files"]))
            final = EXPORTS / stamp
            work.rename(final)
        except BaseException:
            shutil.rmtree(work, ignore_errors=True)
            raise
        _switch(PUBLIC, final)
        for old in sorted(p for p in EXPORTS.iterdir() if p.is_dir() and not p.name.startswith("."))[:-KEEP_EXPORTS]:
            shutil.rmtree(old, ignore_errors=True)
        meta_set(conn, "export_fingerprint", fingerprint)
        meta_set(conn, "exported_at", now_iso())
        return manifest


def coverage_start(conn) -> str:
    """First month of the unbroken run of months, ending last month, that each hold >= MONTH_MIN_RECORDS records
    (the current month is still filling up and does not break the run)."""
    counts = dict(conn.execute("SELECT substr(published_date, 1, 7), count(*) FROM news GROUP BY 1").fetchall())
    year, month = datetime.now(UTC).year, datetime.now(UTC).month
    start = f"{year:04d}-{month:02d}"
    while True:
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
        key = f"{year:04d}-{month:02d}"
        if counts.get(key, 0) < MONTH_MIN_RECORDS:
            return start
        start = key


def write_export(conn, root: Path, *, fields) -> dict:
    first_month = coverage_start(conn)
    files = write_bulk(conn, root, fields, first_month) if PUBLIC_BULK else []
    link_texts(root)
    datasets = link_group_public(root) if PUBLIC_BULK else []
    (root / "README.txt").write_text(README + (group_public_readme(datasets) if datasets else ""), encoding="utf-8")
    search = write_search_index(conn, root)
    analytics = write_analytics(conn, root)
    for entry in filter(None, [search, *(search or {}).get("parts", []), analytics]):
        _precompress(root / entry["path"])

    stats = conn.execute("SELECT count(*), min(published_date), max(published_date), max(updated_at) FROM news").fetchone()
    cutoff = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
    origins = {r[0]: r[1] for r in conn.execute("SELECT origin, count(*) FROM news GROUP BY origin")}
    manifest = {
        "schema": "grenn-climate-news/1",
        "generated_at": now_iso(),
        "data_updated_at": stats[3],
        "records": stats[0],
        "date_min": stats[1],
        "date_max": stats[2],
        "coverage_from": conn.execute("SELECT min(published_date) FROM news WHERE published_date >= ?",
                                      (f"{first_month}-01",)).fetchone()[0],
        "added_24h": conn.execute("SELECT count(*) FROM news WHERE first_seen_at >= ?", (cutoff,)).fetchone()[0],
        "origins": origins,
        "fields": list(fields),
        "readme": "README.txt",
        "files": files,
        "download_limit": None if PUBLIC_BULK else 100,
        "summary": summary_figures(conn),
    }
    if search:  # the site's text-database list
        manifest["search"] = search
    if analytics:  # the site's research charts
        manifest["analytics"] = analytics
    if datasets:  # keys of their own: the site's range / format bar reads only `files`
        sections = {**GROUP_SECTIONS, "governance": ("全球气候治理全文数据库", "Global climate governance full-text database")}
        manifest["dataset_sections"] = [{"id": k, "title": zh, "title_en": en} for k, (zh, en) in sections.items()
                                        if any(d["section"] == k for d in datasets)]
        manifest["datasets_account"] = "datasets/"  # where `access: account` paths live (nginx basic auth)
        manifest["datasets"] = datasets
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def summary_figures(conn) -> dict:
    """The home page's key figures: topics, domains, countries mentioned, publishers, the research set."""
    countries = set()
    for (value,) in conn.execute("SELECT country_codes FROM news WHERE country_codes != '[]'"):
        countries.update(c.get("alpha2") for c in _loads(value, []) if isinstance(c, dict) and c.get("alpha2"))
    figures = {"countries": len(countries),
               "publishers": conn.execute("SELECT count(DISTINCT coalesce(source_domain, source_name)) FROM news").fetchone()[0],
               "research": conn.execute("SELECT count(*) FROM news WHERE research_eligible=1").fetchone()[0]}
    if meta_get(conn, "history_version"):
        figures.update(topics=len(governance()["topics"]), domains=len(governance()["parents"]))
    return figures


def write_bulk(conn, root: Path, fields, first_month: str) -> list:
    """The range / month / all files (CSV, JSONL, SQLite): published only while PUBLIC_BULK is on."""
    today = datetime.now(UTC).date()
    windows = {"last7d": (today - timedelta(days=6)).isoformat(), "last30d": (today - timedelta(days=29)).isoformat()}
    full = Sink(root / "climate-news-all", fields)
    recent = {key: Sink(root / f"climate-news-{key}", fields) for key in windows}
    months: dict[str, Sink] = {}
    # feeds occasionally surface a years-old article and the full-text archive adds past COP coverage: those stay in
    # the full files, but the month files and the advertised coverage start where regular data does
    for row in conn.execute(f"SELECT {','.join(fields)} FROM news ORDER BY published_at DESC, record_id"):
        full.write(row)
        for key, since in windows.items():
            if row["published_date"] >= since:
                recent[key].write(row)
        month = row["published_date"][:7]
        if month < first_month:
            continue
        if month not in months:
            if months:  # rows arrive newest first, so a month never reopens
                months[next(reversed(months))].close()
            months[month] = Sink(root / "monthly" / f"climate-news-{month}", fields)
        months[month].write(row)
    for sink in (full, *recent.values(), *months.values()):
        sink.close()

    files = []
    for key, sink in recent.items():
        for fmt, path in (("csv", sink.csv_path), ("jsonl", sink.jsonl_path)):
            files.append(_file_entry(root, path, id=key, scope="recent", days=int(key[4:-1]), format=fmt, records=sink.count))
    for month, sink in months.items():
        for fmt, path in (("csv", sink.csv_path), ("jsonl", sink.jsonl_path)):
            files.append(_file_entry(root, path, id=month, scope="month", format=fmt, records=sink.count))
    for fmt, path in (("csv", full.csv_path), ("jsonl", full.jsonl_path)):
        target = root / f"{path.name}.zip"
        _zip(path, target, path.name)
        path.unlink()
        files.append(_file_entry(root, target, id="all", scope="all", format=fmt, records=full.count, compression="zip"))
    sqlite_path = root / "climate-news.sqlite"
    write_sqlite(conn, sqlite_path, fields)
    target = root / "climate-news-all.sqlite.zip"
    _zip(sqlite_path, target, sqlite_path.name)
    sqlite_path.unlink()
    files.append(_file_entry(root, target, id="all", scope="all", format="sqlite", records=full.count, compression="zip"))
    return files


def write_sqlite(conn, path: Path, fields) -> None:
    out = sqlite3.connect(path)
    try:
        cols = ", ".join(f"{f} {'INTEGER' if f in INT_FIELDS else 'TEXT'}" for f in fields)
        out.executescript(f"""
            CREATE TABLE news ({cols});
            CREATE TABLE sources (source_id TEXT PRIMARY KEY, name TEXT, homepage_url TEXT, storage_policy TEXT, compliance_note TEXT);
            CREATE TABLE dataset_info (key TEXT PRIMARY KEY, value TEXT);
        """)
        out.executemany(f"INSERT INTO news VALUES ({','.join('?' * len(fields))})",
                        (tuple(r) for r in conn.execute(f"SELECT {','.join(fields)} FROM news ORDER BY published_at DESC")))
        out.executemany("INSERT INTO sources VALUES (?,?,?,?,?)",
                        (tuple(r) for r in conn.execute(
                            "SELECT source_id, name, homepage_url, storage_policy, compliance_note FROM sources")))
        out.executemany("INSERT INTO dataset_info VALUES (?, ?)", [
            ("name", "GRENN climate news text database"), ("generated_at", now_iso()),
            ("url", "https://zerocarbonx.cn/cop31/#database"), ("readme", README)])
        out.executescript("""
            CREATE INDEX idx_news_date ON news(published_date);
            CREATE INDEX idx_news_source ON news(source_name);
        """)
        out.commit()
        out.execute("VACUUM")
    finally:
        out.close()


def cmd_export(args) -> int:
    with lock():
        conn = connect()
        export(conn, force=args.force)
    return 0


# ---------------------------------------------------------------- group datasets

# Every full-text record in a group delivery carries public_redistribution_allowed=false: the text only ever goes to
# protected/ (/datasets/, group account). public/ gets what holds no article text: the catalogue (metadata, quality,
# labels), the research labels (matched words + character offsets) and the original-record ledger.
ORIGINAL, LIBRARY, RESEARCH = "历史新闻正文", "新增历史气候能源全文库", "高相关全文研究索引与样本"
GROUP_PARTS = {  # what a delivery must contain
    ORIGINAL: ("fulltexts.jsonl.gz", "candidate_full_articles.jsonl.gz", "primary_candidates.jsonl.gz", "records.csv",
               "original_to_document.json"),
    LIBRARY: ("new_fulltexts.jsonl.gz", "primary_candidates.jsonl.gz"),
    RESEARCH: ("labels_with_evidence.jsonl.gz", "source_capped_fulltexts.jsonl.gz"),
}
COHORTS = {"original_recovery": (ORIGINAL, "fulltexts.jsonl.gz"), "new_library": (LIBRARY, "new_fulltexts.jsonl.gz")}
TOPICS = {"climate_governance": "气候治理", "emissions_carbon": "碳排放", "clean_energy": "清洁能源",
          "fossil_energy": "化石能源", "climate_impacts": "气候影响", "land_climate": "土地利用"}
TOPICS_EN = {"climate_governance": "Climate governance", "emissions_carbon": "Emissions & carbon",
             "clean_energy": "Clean energy", "fossil_energy": "Fossil energy", "climate_impacts": "Climate impacts",
             "land_climate": "Land use"}
# section id → (title, English title), in display order; the site's download area and /datasets/ both use them
GROUP_SECTIONS = {
    "collections": ("按收录队列与质量分级", "By collection and quality tier"),
    "topics": ("按主题（优先研究子集，两库合并）", "By topic (priority research subset, both collections)"),
    "database": ("合并数据库", "Combined database"),
    "archive": ("全文归档采集", "Full-text crawl archive"),
    "materials": ("复现材料与说明", "Reproduction materials and notes"),
    "metadata": ("公开元数据（不含正文）", "Public metadata (no article text)"),
}
# delivered full-text files, published unchanged: (id, folder, file, title, description, English title, English description)
GROUP_COLLECTIONS = (
    ("original-all", ORIGINAL, "fulltexts.jsonl.gz", "历史新闻正文 · 全部正文",
     "为原数据库冻结的新闻记录找回的原语言正文，按正文 SHA-256 去重（多条原记录可能指向同一篇）；"
     "含待复核正文、视频说明与直播导语，见 delivery_class、document_genre、quality_flags。",
     "Historical news texts · all texts",
     "Original-language texts recovered for the original database's frozen news records, de-duplicated by text SHA-256 "
     "(several records may point to one text); includes texts awaiting review, video descriptions and live-blog leads."),
    ("original-complete", ORIGINAL, "candidate_full_articles.jsonl.gz", "历史新闻正文 · 候选完整新闻",
     "其中通过严格机器完整性检查的新闻与评论正文（自动检查，不是逐篇人工核验）。",
     "Historical news texts · candidate complete articles",
     "News and commentary texts that pass the strict automatic completeness checks (not article-by-article human review)."),
    ("original-primary", ORIGINAL, "primary_candidates.jsonl.gz", "历史新闻正文 · 优先研究子集",
     "候选完整、领域相关且正文不少于 800 字符。",
     "Historical news texts · priority research subset", "Candidate complete, on topic and at least 800 characters."),
    ("library-all", LIBRARY, "new_fulltexts.jsonl.gz", "新增历史气候能源全文库 · 全部正文",
     "已登记媒体公开接口中 2015 年以来的气候与能源文章，与原库分开统计（与原库相同的正文已排除）。",
     "Historical climate & energy library · all texts",
     "Climate and energy articles since 2015 from registered publishers' public APIs, counted separately from the "
     "original database (texts identical to it are excluded)."),
    ("library-primary", LIBRARY, "primary_candidates.jsonl.gz", "新增历史气候能源全文库 · 优先研究子集",
     "候选完整、领域相关且正文不少于 800 字符。",
     "Historical climate & energy library · priority research subset",
     "Candidate complete, on topic and at least 800 characters."),
    ("research-sample", RESEARCH, "source_capped_fulltexts.jsonl.gz", "高相关全文 · 来源限额样本",
     "按标题国别、主题、年份、发布者分层轮转选取（单个发布者最多 300 篇）的探索性样本，不是全球新闻的概率样本。",
     "High-relevance texts · source-capped sample",
     "Exploratory sample rotated across headline country, topic, year and publisher (at most 300 per publisher); "
     "not a probability sample of global news."),
)
GROUP_CATALOG_FIELDS = (
    "key", "cohort", "document_id", "title", "url", "source", "source_id", "publisher_domain", "language",
    "published_at", "year", "text_characters", "words", "paragraphs", "text_sha256", "status", "delivery_class",
    "document_genre", "quality_flags", "in_complete", "in_primary", "in_sample", "topic_tags", "screening_topic_tags",
    "country_mentions", "extraction_method", "acquired_at", "rights_status",
)
GROUP_LIST_FIELDS = {"quality_flags", "topic_tags", "screening_topic_tags", "country_mentions"}
GROUP_INT_FIELDS = {"text_characters", "words", "paragraphs", "in_complete", "in_primary", "in_sample"}
LABEL_FIELDS = ("topic_tags", "relevance_evidence", "relevance_match_count", "relevance_rule", "country_mentions",
                "country_mention_evidence", "country_tag_meaning", "normalized_text_sha256")
GROUP_README = """GRENN 组内全文数据集 · Group full-text datasets
https://zerocarbonx.cn/datasets/（需组内账号）

研究组自行采集整理的新闻原文数据，交付批次 {label}，生成于 {generated}。
正文为原语言原文，未翻译、未用模型补写。权利状态 private_research_copy_permission_not_established_for_redistribution：
尚未取得全文再分发许可，请勿上传到公开网站、GitHub 或转给组外人员；引用时保留来源与原文链接。
不含正文的目录、标签与补齐台账另在公开下载 https://zerocarbonx.cn/downloads/datasets/。

两个队列分别统计，不要混算：
  original_recovery  历史新闻正文：为原数据库冻结的新闻记录找回原文（{original} 篇去重正文）
  new_library        新增历史气候能源全文库：已登记媒体 2015 年以来的公开文章（{library} 篇，与原库相同的正文已排除）
质量分级（自动检查，不是逐篇人工核验）：全部正文 ⊇ 候选完整新闻（delivery_class = candidate_full_article）⊇
优先研究子集（另需领域相关且不少于 800 字符）。主题与国别标签由确定性词表规则得出；国别只表示文中提及，
不代表事件地点、国家立场或政策辖区。

文件
{files}
  manifest.json  各数据集的条数、文件大小与 SHA-256

格式
  *.jsonl.gz     每行一个 JSON 对象（gzip 压缩）；字段说明见 docs/ 下各批次的「数据说明与复现方法」
  按主题文件      在原记录上附加 cohort 与 research_labels（主题、匹配词、国别提及及其原文字符位置）；一篇文章可属于多个主题
  合并数据库      SQLite：documents（每篇一行，含正文 source_text 与所属子集标记 in_complete / in_primary / in_sample）、
                 topics、country_mentions、original_records（原库目标逐条补齐状态）、original_to_document、dataset_info
  复现材料        各批次除上列正文文件外的全部文件：采集日志、质量复核、段落证据索引、审计记录与代码快照
  archive/       服务器全文归档采集：正文 SQLite（表 articles、images）与配图 zip（按内容 SHA-256 命名，对应 images.path）
"""
GROUP_PUBLIC_README = """
组内全文数据集 · 公开部分（datasets/）
研究组自行采集的新闻原文数据的目录、标签与台账，不含正文（交付批次 {label}）。正文尚未取得再分发许可，
只供组内研究：https://zerocarbonx.cn/datasets/（需组内账号）。
{lines}
"""
GROUP_CSS = """
:root{--gb-900:#1b2634;--gb-700:#2f4156;--gb-500:#587088;--gb-300:#a9b8c7;--gb-150:#dce3ea;--gb-50:#f3f6f9;
--white:#fff;--red:#c8372d;--serif:"Songti SC","Noto Serif CJK SC","Source Han Serif SC",Georgia,serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--gb-50);color:var(--gb-900);
font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
main{max-width:920px;margin:0 auto;padding:48px 16px 72px}
a{color:inherit}
.eyebrow{font:12px/1.4 var(--mono);letter-spacing:.08em;color:var(--gb-500);margin:0 0 10px}
h1{font:600 34px/1.2 var(--serif);margin:0 0 14px}
h2{font:600 20px/1.3 var(--serif);margin:44px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--gb-150)}
h3{font-size:16px;line-height:1.4;margin:0}
.lede{color:var(--gb-700);margin:0}
.note{border-left:3px solid var(--red);background:var(--white);padding:10px 14px;margin:18px 0}
.links{font:13px/1.6 var(--mono);color:var(--gb-500)}
.sets{list-style:none;margin:32px 0 0;padding:0;display:grid;gap:12px}
.sets li{background:var(--white);border-radius:10px;padding:16px 18px;
box-shadow:0 1px 2px rgba(27,38,52,.06),0 6px 18px rgba(27,38,52,.05)}
.head{display:flex;gap:4px 12px;justify-content:space-between;align-items:baseline;flex-wrap:wrap}
.count{font:13px/1.4 var(--mono);color:var(--gb-500)}
.sets p{margin:6px 0 0;color:var(--gb-700)}
.files a{display:inline-block;margin:10px 8px 0 0;padding:3px 10px;border:1px solid var(--gb-300);border-radius:999px;
text-decoration:none;font:13px/1.6 var(--mono)}
.files a:hover{border-color:var(--red);color:var(--red)}
"""


def _gz_rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _gz_lines(path: Path) -> int:
    with gzip.open(path, "rb") as handle:
        return sum(1 for line in handle if line.strip())


def _size(n: int) -> str:
    return f"{n / 1e6:.1f} MB" if n >= 1e5 else f"{n / 1e3:.0f} KB"


def _group_sums(folder: Path) -> dict:
    """SHA-256 and size of every file under the three delivery folders (anything else in `folder` is ignored)."""
    sums = {}
    for part in GROUP_PARTS:
        for path in sorted((folder / part).rglob("*")):
            if path.is_file():
                sums[path.relative_to(folder).as_posix()] = {"sha256": _sha256(path), "bytes": path.stat().st_size}
    return sums


def _catalog_row(r: dict, cohort: str, key: str, labels: dict | None, primary: set, sample: set) -> dict:
    url = r.get("url") or r.get("original_url")
    published = r.get("source_published_at_utc") or r.get("date") or r.get("source_published_at")
    return {
        "key": key, "cohort": cohort, "document_id": r["id"], "title": r.get("title"), "url": url,
        "source": r.get("source"), "source_id": r.get("source_id"), "publisher_domain": _host(url),
        "language": r.get("language"), "published_at": published, "year": (published or "")[:4] or None,
        "text_characters": r.get("text_characters"), "words": r.get("words"), "paragraphs": r.get("paragraphs"),
        "text_sha256": r.get("text_sha256"), "status": r.get("status"), "delivery_class": r.get("delivery_class"),
        "document_genre": r.get("document_genre"), "quality_flags": r.get("quality_flags") or [],
        "in_complete": int(r.get("delivery_class") == "candidate_full_article"), "in_primary": int(r["id"] in primary),
        "in_sample": int(key in sample),
        "topic_tags": (labels or {}).get("topic_tags") or [],  # research index (dictionary v2): primary subset only
        "screening_topic_tags": r.get("topic_tags") or [],  # the new library's intake screen (dictionary v1)
        "country_mentions": (labels or {}).get("country_mentions") or [],
        "extraction_method": r.get("extraction_method"), "acquired_at": r.get("acquired_at") or r.get("fetched_at"),
        "rights_status": r.get("rights_status"),
    }


def write_group(raw: Path, root: Path, label: str) -> dict:
    """Build every dataset of one delivery into root/protected (full text) and root/public (no article text)."""
    prot, pub, work = root / "protected", root / "public", root / "work"
    for folder in (prot, pub, work):
        folder.mkdir(parents=True)
    labels = {r["key"]: r for r in _gz_rows(raw / RESEARCH / "labels_with_evidence.jsonl.gz")}
    primary = {c: {r["id"] for r in _gz_rows(raw / part / "primary_candidates.jsonl.gz")} for c, (part, _) in COHORTS.items()}
    sample = {f"{r['cohort']}:{r['id']}" for r in _gz_rows(raw / RESEARCH / "source_capped_fulltexts.jsonl.gz")}
    datasets, public = [], []

    def add(into, section, ident, title, description, records, base, paths, en):
        files = [_file_entry(base, p, format=fmt, compression=comp) for p, fmt, comp in paths]
        into.append({"id": ident, "section": section, "title": title, "description": description,
                     "title_en": en[0], "description_en": en[1], "records": records, "files": files})

    for ident, part, name, title, description, *en in GROUP_COLLECTIONS:
        target = prot / "collections" / f"{ident}.jsonl.gz"
        _place(raw / part / name, target)
        add(datasets, "collections", ident, title, description, _gz_lines(target), prot, [(target, "jsonl", "gzip")], en)

    # one pass over both cohorts: catalogue, merged database, topic files
    db_path = work / "grenn-group-fulltext.sqlite"
    db = sqlite3.connect(db_path)
    cols = ", ".join(f"{f} {'INTEGER' if f in GROUP_INT_FIELDS else 'TEXT'}" for f in GROUP_CATALOG_FIELDS)
    db.executescript(f"""
        CREATE TABLE documents ({cols}, source_text TEXT);
        CREATE TABLE topics (key TEXT, topic TEXT, topic_zh TEXT);
        CREATE TABLE country_mentions (key TEXT, alpha2 TEXT, alpha3 TEXT, name_zh TEXT, name_en TEXT,
                                       start INTEGER, "end" INTEGER, matched_text TEXT, field TEXT);
        CREATE TABLE original_to_document (target_id TEXT, document_id TEXT, original_url TEXT, publisher_url TEXT, sha256 TEXT);
        CREATE TABLE dataset_info (key TEXT PRIMARY KEY, value TEXT);
    """)
    insert = f"INSERT INTO documents VALUES ({','.join('?' * (len(GROUP_CATALOG_FIELDS) + 1))})"
    cat_csv = (work / "group-catalog.csv").open("w", encoding="utf-8-sig", newline="")
    cat_jsonl = (work / "group-catalog.jsonl").open("w", encoding="utf-8", newline="\n")
    writer = csv.writer(cat_csv)
    writer.writerow(GROUP_CATALOG_FIELDS)
    topic_files, topic_counts, documents = {}, {}, {}
    try:
        for cohort, (part, name) in COHORTS.items():
            documents[cohort] = 0
            for r in _gz_rows(raw / part / name):
                key = f"{cohort}:{r['id']}"
                lab = labels.get(key)
                row = _catalog_row(r, cohort, key, lab, primary[cohort], sample)
                writer.writerow(["; ".join(map(str, row[f])) if f in GROUP_LIST_FIELDS else row[f] for f in GROUP_CATALOG_FIELDS])
                cat_jsonl.write(json.dumps(row, ensure_ascii=False) + "\n")
                db.execute(insert, [json.dumps(row[f], ensure_ascii=False) if f in GROUP_LIST_FIELDS else row[f]
                                    for f in GROUP_CATALOG_FIELDS] + [r.get("source_text")])
                documents[cohort] += 1
                if not lab:
                    continue
                db.executemany("INSERT INTO topics VALUES (?, ?, ?)", [(key, t, TOPICS.get(t)) for t in lab["topic_tags"]])
                db.executemany("INSERT INTO country_mentions VALUES (?,?,?,?,?,?,?,?,?)", [
                    (key, m.get("alpha2"), m.get("alpha3"), m.get("name_zh"), m.get("name_en"), m.get("start"),
                     m.get("end"), m.get("matched_text"), m.get("field"))
                    for m in lab.get("country_mention_evidence") or []])
                item = json.dumps({**r, "cohort": cohort, "research_labels": {f: lab.get(f) for f in LABEL_FIELDS}},
                                  ensure_ascii=False) + "\n"
                for topic in lab["topic_tags"]:
                    if topic not in topic_files:
                        path = prot / "topics" / f"topic-{topic}.jsonl.gz"
                        path.parent.mkdir(exist_ok=True)
                        topic_files[topic] = (path, gzip.open(path, "wt", encoding="utf-8", compresslevel=6))
                        topic_counts[topic] = 0
                    topic_files[topic][1].write(item)
                    topic_counts[topic] += 1
    finally:
        cat_csv.close()
        cat_jsonl.close()
        for _, handle in topic_files.values():
            handle.close()
    for topic in sorted(topic_files, key=lambda t: (t not in TOPICS, list(TOPICS).index(t) if t in TOPICS else 0, t)):
        path, name_en = topic_files[topic][0], TOPICS_EN.get(topic, topic)
        add(datasets, "topics", f"topic-{topic}", f"主题 · {TOPICS.get(topic, topic)}（{topic}）",
            f"优先研究子集中带「{TOPICS.get(topic, topic)}」标签的正文，附研究标签。", topic_counts[topic], prot,
            [(path, "jsonl", "gzip")],
            (f"Topic · {name_en} ({topic})", f"Priority-subset texts tagged “{name_en}”, with their research labels."))

    with (raw / ORIGINAL / "records.csv").open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = [re.sub(r"\W", "_", h) for h in next(reader)]
        db.execute(f"CREATE TABLE original_records ({', '.join(f'{h} TEXT' for h in header)})")
        db.executemany(f"INSERT INTO original_records VALUES ({','.join('?' * len(header))})", reader)
    targets = db.execute("SELECT count(*) FROM original_records").fetchone()[0]
    mapping = json.loads((raw / ORIGINAL / "original_to_document.json").read_text(encoding="utf-8"))
    db.executemany("INSERT INTO original_to_document VALUES (?,?,?,?,?)", [
        (m.get("target_id"), m.get("document_id"), m.get("original_url"), m.get("publisher_url"), m.get("sha256"))
        for m in mapping])
    total = sum(documents.values())
    readme = GROUP_README.format(label=label, generated=now_iso(), original=f"{documents['original_recovery']:,}",
                                 library=f"{documents['new_library']:,}", files="{files}")
    db.executemany("INSERT INTO dataset_info VALUES (?, ?)", [
        ("name", "GRENN group full-text datasets"), ("label", label), ("generated_at", now_iso()),
        ("url", "https://zerocarbonx.cn/datasets/"), ("rights_status", "private_research_copy_permission_not_established_for_redistribution")])
    db.executescript("""
        CREATE INDEX idx_documents_cohort ON documents(cohort);
        CREATE INDEX idx_documents_published ON documents(published_at);
        CREATE INDEX idx_documents_publisher ON documents(publisher_domain);
        CREATE INDEX idx_topics ON topics(topic, key);
        CREATE INDEX idx_country_mentions ON country_mentions(alpha3, key);
    """)
    db.commit()
    db.close()
    target = prot / "database" / "grenn-group-fulltext.sqlite.zip"
    target.parent.mkdir()
    _zip(db_path, target, db_path.name)
    db_path.unlink()
    add(datasets, "database", "database", "两库合并 SQLite 数据库",
        "两个队列的全部正文与标签；表 documents、topics、country_mentions、original_records、original_to_document、dataset_info。",
        total, prot, [(target, "sqlite", "zip")],
        ("Both collections in one SQLite database", "Every text and label of both collections; tables documents, "
         "topics, country_mentions, original_records, original_to_document, dataset_info."))

    collected = {(c[1], c[2]) for c in GROUP_COLLECTIONS} | {(RESEARCH, "labels_with_evidence.jsonl.gz")}
    bundle = ("采集日志、质量复核、证据索引、审计记录、代码快照与说明文档（不含上列正文文件）。",
              "Acquisition logs, quality reviews, evidence index, audits, code snapshot and notes (without the texts above).")
    for ident, part, title, description, en in (
            ("materials-original", ORIGINAL, "历史新闻正文 · 复现材料", bundle[0],
             ("Historical news texts · reproduction materials", bundle[1])),
            ("materials-library", LIBRARY, "新增历史气候能源全文库 · 复现材料", bundle[0],
             ("Historical climate & energy library · reproduction materials", bundle[1])),
            ("materials-research", RESEARCH, "高相关全文研究索引 · 代码与分布", "选样与标注代码快照、样本分布与选取统计、使用说明。",
             ("High-relevance research index · code and distribution",
              "Selection and labelling code snapshot, sample distribution and selection statistics, usage notes."))):
        target = prot / "materials" / f"{ident}.zip"
        target.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted((raw / part).rglob("*")):
                rel = path.relative_to(raw / part).as_posix()
                if path.is_file() and (part, rel) not in collected:  # .gz members are stored, not recompressed
                    archive.write(path, f"{part}/{rel}", zipfile.ZIP_STORED if path.suffix == ".gz" else zipfile.ZIP_DEFLATED)
        add(datasets, "materials", ident, title, description, None, prot, [(target, "zip", None)], en)
    docs =[p for part in GROUP_PARTS for p in sorted((raw / part).glob("*.txt"))]
    docs += sorted((raw / ORIGINAL / "followup").glob("*.txt"))
    placed = []
    for path in docs:
        target = prot / "docs" / f"{path.relative_to(raw).parts[0]}-{path.name}"
        if not target.exists():
            _place(path, target)
            placed.append((target, "txt", None))
    add(datasets, "materials", "docs", "说明文档", "各批次的交付说明、数据说明与复现方法、文件说明与使用说明（纯文本）。",
        None, prot, placed, ("Notes", "Each delivery's handover notes, data description and reproduction method, "
                                      "file notes and usage notes (plain text, Chinese)."))

    # the private full-text crawl archive (ingest-fulltext), zipped once per version by build_archive_downloads()
    index = ARCHIVE_DOWNLOADS / "datasets.json"
    if index.exists():
        for d in json.loads(index.read_text(encoding="utf-8")):
            for f in d["files"]:
                _place(ARCHIVE_DOWNLOADS / f["path"], prot / "archive" / f["path"])
                f["path"] = f"archive/{f['path']}"
            datasets.append(d)

    for fmt in ("csv", "jsonl"):
        source = work / f"group-catalog.{fmt}"
        target = pub / f"group-catalog.{fmt}.zip"
        _zip(source, target, source.name)
        source.unlink()
    add(public, "metadata", "group-catalog", "全文库目录",
        "两个队列每篇正文的元数据（不含正文）：标题、链接、来源、日期、字数、质量分级、主题与国别标签、所属子集。",
        total, pub, [(pub / "group-catalog.csv.zip", "csv", "zip"), (pub / "group-catalog.jsonl.zip", "jsonl", "zip")],
        ("Full-text library catalogue", "Metadata of every text in both collections (no article text): title, link, "
         "source, date, length, quality tier, topic and country labels, subset membership."))
    target = pub / "group-original-records.csv.zip"
    _zip(raw / ORIGINAL / "records.csv", target, "group-original-records.csv")
    add(public, "metadata", "group-original-records", "原库补齐台账",
        "原数据库冻结目标记录逐条的补齐状态（not_attempted = 尚未排到队列，不代表无法获取）。", targets, pub,
        [(target, "csv", "zip")], ("Original-record recovery ledger", "Recovery status of each frozen target record "
                                   "of the original database (not_attempted = not queued yet, not unobtainable)."))
    target = pub / "group-research-labels.jsonl.gz"
    _place(raw / RESEARCH / "labels_with_evidence.jsonl.gz", target)
    add(public, "metadata", "group-research-labels", "研究标签",
        "优先研究子集的主题标签与国别提及（匹配词与原文字符位置，不含正文）。", _gz_lines(target), pub,
        [(target, "jsonl", "gzip")], ("Research labels", "Topic labels and country mentions of the priority subset "
                                      "(matched words and character offsets, no article text)."))
    shutil.rmtree(work)

    lines = [f"  {f['path']:<44} {d['title']}" + (f"（{d['records']:,}）" if d["records"] else "")
             for d in datasets for f in d["files"]]
    (prot / "README.txt").write_text(readme.replace("{files}", "\n".join(lines)), encoding="utf-8")
    (pub / "datasets.json").write_text(json.dumps(public, ensure_ascii=False, indent=1), encoding="utf-8")
    manifest = {"schema": "grenn-group-datasets/1", "label": label, "generated_at": now_iso(), "documents": documents,
                "readme": "README.txt", "datasets": datasets, "public": public}
    (prot / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (prot / "index.html").write_text(group_page(manifest), encoding="utf-8")
    return manifest


def group_page(manifest: dict) -> str:
    """The /datasets/ index: one card per dataset in a single list (in section order); public files link into /downloads/."""
    esc = html.escape
    order = list(GROUP_SECTIONS)
    items = [(d, "") for d in manifest["datasets"]] + [(d, "/downloads/datasets/") for d in manifest["public"]]
    items.sort(key=lambda item: order.index(item[0]["section"]) if item[0]["section"] in order else len(order))
    cards = []
    for d, base in items:
        unit = "张" if d.get("unit") == "images" else "条"
        count = f'<span class="count">{d["records"]:,} {unit}</span>' if d["records"] else ""
        links = "".join(
            f'<a href="{esc(base + f["path"])}" download title="SHA-256 {f["sha256"]}">'
            f'{esc(f["path"].rsplit("/", 1)[-1] if f["format"] == "txt" else f["format"].upper() + (" · " + f["compression"].upper() if f.get("compression") else ""))}'
            f' · {_size(f["bytes"])}</a>' for f in d["files"])
        cards.append(f'<li><div class="head"><h3>{esc(d["title"])}</h3>{count}</div><p>{esc(d["description"])}</p>'
                     f'<p class="files">{links}</p></li>')
    listing = f'<ul class="sets">{"".join(cards)}</ul>'
    docs = manifest["documents"]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>GRENN 组内数据集</title>
<style>{GROUP_CSS}</style>
</head>
<body>
<main>
<header>
<p class="eyebrow">GRENN · 格润气候治理 · 组内</p>
<h1>全文数据集</h1>
<p class="lede">研究组自行采集整理的新闻原文（交付批次 {esc(manifest["label"])}）：历史新闻正文 {docs.get("original_recovery", 0):,} 篇，
新增历史气候能源全文库 {docs.get("new_library", 0):,} 篇。两个队列分别统计，质量分级为自动检查，不是逐篇人工核验。</p>
<p class="note">正文尚未取得再分发许可，仅供组内研究：请勿上传到公开网站、GitHub 或转给组外人员；引用请保留来源与原文链接。</p>
<p class="links"><a href="README.txt">README.txt</a> · <a href="manifest.json">manifest.json</a> · 生成于 {esc(manifest["generated_at"])}</p>
</header>
{listing}
</main>
</body>
</html>
"""


def build_archive_downloads(conn) -> dict | None:
    """Zip the private full-text archive (text database + images) for the account-only /datasets/ area — once per
    fulltext.db version; group builds hard-link the result."""
    if not FULLTEXT_DB.exists():
        return None
    digest = _sha256(FULLTEXT_DB)
    if (ARCHIVE_DOWNLOADS / "datasets.json").exists() and meta_get(conn, "fulltext_downloads_sha256") == digest:
        return {"status": "unchanged"}
    ft = sqlite3.connect(f"file:{FULLTEXT_DB}?immutable=1", uri=True)
    try:
        articles = ft.execute("SELECT count(*) FROM articles WHERE status='done'").fetchone()[0]
        images = [r[0] for r in ft.execute("SELECT DISTINCT path FROM images WHERE status='done' ORDER BY path")]
    finally:
        ft.close()
    work = FULLTEXT / ".downloads.tmp"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    try:
        text = work / "grenn-fulltext-archive.sqlite.zip"
        _zip(FULLTEXT_DB, text, "grenn-fulltext-archive.sqlite")
        pictures = work / "grenn-fulltext-images.zip"
        with zipfile.ZipFile(pictures, "w", zipfile.ZIP_STORED) as archive:  # JPEG / WebP: nothing to gain from deflate
            for path in images:
                archive.write(FULLTEXT_IMAGES / path, f"images/{path}")
        datasets = [
            {"id": "archive-text", "section": "archive", "title": "全文归档 · 正文数据库",
             "description": "服务器全文归档采集（各来源近五年，另含 COP1–COP31 历届报道）的 SQLite 数据库：每篇文章的全文、作者、"
                            "日期、栏目、标签、COP 届次、国家与组织，以及配图的图注、署名与原始链接（表 articles、images）。",
             "title_en": "Full-text archive · text database",
             "description_en": "SQLite database of the server's full-text crawl (each source's last five years plus "
                               "COP1–COP31 coverage): full text, authors, dates, sections, tags, COP sessions, countries "
                               "and organisations, and image captions, credits and source links (tables articles, images).",
             "records": articles, "files": [_file_entry(work, text, format="sqlite", compression="zip")]},
            {"id": "archive-images", "section": "archive", "title": "全文归档 · 配图",
             "description": "上述文章的配图文件，按内容 SHA-256 命名，与数据库 images 表的 path 一一对应。",
             "title_en": "Full-text archive · images",
             "description_en": "The articles' images, named by content SHA-256, matching `path` in the images table.",
             "records": len(images), "unit": "images",
             "files": [_file_entry(work, pictures, format="images", compression="zip")]},
        ]
        (work / "datasets.json").write_text(json.dumps(datasets, ensure_ascii=False, indent=1), encoding="utf-8")
        old = FULLTEXT / ".downloads.old"
        shutil.rmtree(old, ignore_errors=True)
        if ARCHIVE_DOWNLOADS.exists():
            ARCHIVE_DOWNLOADS.rename(old)  # files the current group build links to stay valid (hard links)
        work.rename(ARCHIVE_DOWNLOADS)
        shutil.rmtree(old, ignore_errors=True)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    meta_set(conn, "fulltext_downloads_sha256", digest)
    return {"articles": articles, "images": len(images), "bytes": sum(f["bytes"] for d in datasets for f in d["files"])}


def rebuild_datasets(conn) -> dict:
    """Archive zips (if the archive changed) + a fresh /datasets/ build from the latest group delivery."""
    stats = {"archive": build_archive_downloads(conn)}
    label = meta_get(conn, "group_label")
    if label and (GROUP_RAW / label / "SHA256SUMS.json").exists():
        stats["build"] = group_build(GROUP_RAW / label, label)
    return stats


def group_build(raw: Path, label: str) -> dict:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    GROUP_BUILDS.mkdir(parents=True, exist_ok=True)
    work = GROUP_BUILDS / f".{stamp}.tmp"
    shutil.rmtree(work, ignore_errors=True)
    try:
        manifest = write_group(raw, work, label)
        final = GROUP_BUILDS / stamp
        work.rename(final)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    _switch(GROUP_CURRENT, final)
    for old in sorted(p for p in GROUP_BUILDS.iterdir() if p.is_dir() and not p.name.startswith("."))[:-KEEP_GROUP_BUILDS]:
        shutil.rmtree(old, ignore_errors=True)
    sizes = {k: sum(f["bytes"] for d in manifest[k] for f in d["files"]) for k in ("datasets", "public")}
    return {"build": stamp, "documents": manifest["documents"], "datasets": len(manifest["datasets"]),
            "public_datasets": len(manifest["public"]), "protected_bytes": sizes["datasets"], "public_bytes": sizes["public"]}


def link_group_public(root: Path) -> list:
    """Every dataset of the current group build, for the export manifest: public ones are hard-linked into
    root/datasets/ (`path` relative to /downloads/); account ones only describe their files (`path` relative to
    /datasets/, which asks for the group login). [] when there is no build."""
    manifest_path = GROUP_CURRENT / "protected" / "manifest.json"
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for d in manifest["public"]:
        d["access"] = "public"
        for f in d["files"]:
            _place(GROUP_CURRENT / "public" / f["path"], root / "datasets" / f["path"])
            f["path"] = f"datasets/{f['path']}"
    for d in manifest["datasets"]:
        d["access"] = "account"
    order = list(GROUP_SECTIONS)
    datasets = manifest["datasets"] + manifest["public"]
    return sorted(datasets, key=lambda d: order.index(d["section"]) if d["section"] in order else len(order))


def group_public_readme(datasets: list) -> str:
    public = [d for d in datasets if d.get("access") == "public"]
    if not public:
        return ""
    label = json.loads((GROUP_CURRENT / "protected" / "manifest.json").read_text(encoding="utf-8"))["label"]
    lines = [f"  {' / '.join(f['path'] for f in d['files'])}\n      {d['title']}"
             + (f"（{d['records']:,} 条）" if d["records"] else "") + f"：{d['description']}" for d in public]
    return GROUP_PUBLIC_README.format(label=label, lines="\n".join(lines))


def group_report(*, deep: bool = False) -> dict | None:
    """The current group build and its raw archive: counts, sizes, and any file that is missing / changed."""
    manifest_path = GROUP_CURRENT / "protected" / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad = []
    for base, key in ((GROUP_CURRENT / "protected", "datasets"), (GROUP_CURRENT / "public", "public")):
        for d in manifest[key]:
            for f in d["files"]:
                path = base / f["path"]
                if not path.is_file() or path.stat().st_size != f["bytes"] or (deep and _sha256(path) != f["sha256"]):
                    bad.append(f"{key}/{f['path']}")
    raw = GROUP_RAW / manifest["label"]
    sums = json.loads((raw / "SHA256SUMS.json").read_text(encoding="utf-8")) if (raw / "SHA256SUMS.json").exists() else {}
    if not sums:
        bad.append(f"raw/{manifest['label']}/SHA256SUMS.json")
    for rel, info in sums.items():
        path = raw / rel
        if not path.is_file() or path.stat().st_size != info["bytes"] or (deep and _sha256(path) != info["sha256"]):
            bad.append(f"raw/{manifest['label']}/{rel}")
    return {"label": manifest["label"], "built_at": manifest["generated_at"], "documents": manifest["documents"],
            "datasets": len(manifest["datasets"]), "public_datasets": len(manifest["public"]),
            "protected_bytes": sum(f["bytes"] for d in manifest["datasets"] for f in d["files"]),
            "raw_files": len(sums), "raw_bytes": sum(i["bytes"] for i in sums.values()), "bad_files": bad}


def cmd_build_datasets(args) -> int:
    with lock():
        conn = connect()
        with Run(conn, "build-datasets") as run:
            run.stats.update(rebuild_datasets(conn))
        export(conn, force=True)
    return 0


def cmd_ingest_group(args) -> int:
    """A delivery of the group's own full-text data: check it, archive it read-only, rebuild the datasets, re-export."""
    folder = Path(args.folder)
    missing = [f"{part}/{name}" for part, names in GROUP_PARTS.items() for name in names if not (folder / part / name).is_file()]
    if missing:
        raise SystemExit(f"{folder}: not a group delivery — missing {', '.join(missing)}")
    with lock():
        conn = connect()
        with Run(conn, "ingest-group") as run:
            label = args.label or datetime.now(UTC).strftime("%Y%m%d")
            sums = _group_sums(folder)
            raw = GROUP_RAW / label
            if raw.exists():
                if json.loads((raw / "SHA256SUMS.json").read_text(encoding="utf-8")) != sums:
                    raise RuntimeError(f"{raw} already holds a different delivery — give this one another --label")
                run.stats["raw"] = "unchanged"
            else:
                tmp = GROUP_RAW / f".{label}.tmp"
                shutil.rmtree(tmp, ignore_errors=True)
                for rel, info in sums.items():
                    target = tmp / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(folder / rel, target)
                    if _sha256(target) != info["sha256"]:
                        raise RuntimeError(f"{rel}: copy does not match the delivered file")
                (tmp / "SHA256SUMS.json").write_text(json.dumps(sums, ensure_ascii=False, indent=1), encoding="utf-8")
                if os.name == "posix":  # the archive is never modified: builds hard-link into it
                    for path in tmp.rglob("*"):
                        path.chmod(0o555 if path.is_dir() else 0o444)
                tmp.rename(raw)
                GROUP_RAW.chmod(0o750)
                run.stats["raw"] = "archived"
            run.stats.update(label=label, files=len(sums), bytes=sum(i["bytes"] for i in sums.values()))
            run.stats["archive"] = build_archive_downloads(conn)
            run.stats["build"] = group_build(raw, label)
            meta_set(conn, "group_label", label)
            meta_set(conn, "group_ingested_at", now_iso())
        if not args.no_export:
            export(conn, force=True)
    return 0


# ---------------------------------------------------------------- governance history (2026-11-05, 2026-11-06)

GOV_LANGUAGES = {"english": "en", "eng": "en", "spanish": "es", "spa": "es", "chinese": "zh", "cmn": "zh", "zho": "zh", "french": "fr",
                 "fra": "fr", "portuguese": "pt", "por": "pt", "german": "de", "deu": "de", "italian": "it", "ita": "it", "albanian": "sq",
                 "greek": "el", "ell": "el", "turkish": "tr", "tur": "tr", "ind": "id", "rus": "ru", "jpn": "ja", "kor": "ko", "ron": "ro",
                 "glg": "gl", "vie": "vi", "lvs": "lv"}
# in the package but not kept under raw/: the same rows as data/corpus.sqlite in another format, and that file's split parts
HISTORY_DUPLICATES = ("data/eligible_fulltexts.jsonl.gz", "data/review_required.jsonl.gz")
TIMELINE_FILES = ("policy_timeline.json", "policy_timeline_ready.json")  # not in the 2026-11-09 package: carried over from the history before
TREND_MIN = 100  # the topic trend starts at the first year of the unbroken run of years holding this many research articles


def history_order(db_path: Path) -> list:
    """The eligible articles' rowids, newest first (the date is inside each compressed document)."""
    src = sqlite3.connect(f"file:{db_path}?immutable=1", uri=True)
    try:
        found = [(json.loads(zlib.decompress(blob)).get("published_date") or "", key, rowid)
                 for rowid, key, blob in src.execute("SELECT rowid, id, document FROM articles WHERE eligible=1")]
    finally:
        src.close()
    found.sort(key=lambda row: row[1])
    found.sort(key=lambda row: row[0], reverse=True)
    return [row[2] for row in found]


def history_docs(db_path: Path, order: list):
    """Each article's document, with its article_id and the database's normalised url (the key articles are de-duplicated on)."""
    src = sqlite3.connect(f"file:{db_path}?immutable=1", uri=True)
    try:
        for rowid in order:
            key, url, blob = src.execute("SELECT id, url, document FROM articles WHERE rowid=?", (rowid,)).fetchone()
            doc = json.loads(zlib.decompress(blob))
            doc["article_id"], doc["canonical_url"] = key, url
            yield doc
    finally:
        src.close()


def history_rows(db_path: Path, order: list):
    """The documents as `ingest-governance` merges them: the opening text only, no evidence spans."""
    for doc in history_docs(db_path, order):
        doc["lead"] = (doc.pop("source_text", None) or "")[:4000]
        doc["labels"] = {k: v for k, v in (doc.get("labels") or {}).items() if k not in ("evidence", "scores")}
        yield doc


def from_governance(doc: dict, text_refs: dict) -> dict | None:
    lab = doc["labels"]
    language = (doc.get("language") or "").strip().lower()
    language = GOV_LANGUAGES.get(language, language).split("-")[0] or None
    date = doc.get("published_date") or ""
    published = doc.get("published_utc") or doc.get("published_raw") or date
    if doc.get("date_precision") != "day" or not _utc(published):
        published = date if len(date) == 10 else f"{date[:7]}-01"  # a month-precision date: no day is made up in published_date
    key = doc["article_id"]
    primary = lab.get("primary_subcategory")
    rec = finish({
        "url": doc["canonical_url"], "record_id": key, "published_at": published,
        "source_name": doc.get("publisher_name_original") or doc.get("publisher_name_as_published") or doc.get("publisher"),
        "source_domain": doc.get("publisher"), "language": language, "title_original": doc.get("title"),
        "summary_source": excerpt(None, doc.get("lead")), "fact_status": "source_claim_unverified",
        "rights_status": doc.get("rights_status"), "content_hash": doc.get("text_sha256"), "cohort": doc.get("cohort"),
        "document_key": key, "primary_topic": primary, "label_version": lab.get("version"),
        "research_eligible": 1, "complete_candidate": 1, "text_ref": text_refs.get(key),
        "topics": topic_order(primary, lab.get("subcategory_mentions", [])),
        "organization_tags": lab.get("organization_mentions", []), "policy_tools": lab.get("policy_tool_mentions", []),
        "policy_stages": lab.get("policy_stage_mentions", []),
    })
    if not rec:
        return None
    rec["published_date"] = date or rec["published_date"]  # the publisher's date, whatever the zone (YYYY-MM when only the month is known)
    # focal (headline / lead) countries first
    rec.update(country_fields(list(dict.fromkeys([*lab.get("country_focal_candidates", []), *lab.get("country_mentions", [])]))))
    return rec


def write_texts(db_path: Path, order: list, folder: Path) -> dict:
    """Full texts of the eligible articles in chunks of TEXT_CHUNK (newest first): {article_id: {t, u, p, d, x}};
    returns article_id → chunk name."""
    folder.mkdir(parents=True)
    refs, chunk, n = {}, {}, 0

    def flush():
        nonlocal chunk, n
        if chunk:
            (folder / f"t{n:04d}.json").write_text(json.dumps(chunk, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            chunk, n = {}, n + 1
    for doc in history_docs(db_path, order):
        key, text = doc["article_id"], doc.get("source_text") or ""
        chunk[key] = {"t": doc.get("title"), "u": doc.get("url"), "p": doc.get("publisher"), "d": doc.get("published_date"),
                      "x": EMAIL.sub("[REDACTED_EMAIL]", text) if "@" in text else text}
        refs[key] = f"t{n:04d}"
        if len(chunk) >= TEXT_CHUNK:
            flush()
    flush()
    return refs


def _writable(path: Path) -> None:
    """The package copies were made read-only: open them up again so they can be removed."""
    if os.name == "posix":
        for p in [path, *path.rglob("*")]:
            if p.is_dir() and not p.is_symlink():
                p.chmod(0o755)


def archive_previous(stamp: str, keep: Path) -> dict:
    """One compressed copy of everything a new governance history replaces (news.db, the earlier history folders, and the
    pre-2026-11-05 stores where they are still there); then those are removed, with the backups of the old news.db.
    The crawler's own database stays (it is collection state, not data). The copy stays in ARCHIVE_DIR, never served."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    target = ARCHIVE_DIR / f"pre-governance-{stamp}.tar.gz"
    tmp = target.with_name(target.name + ".tmp")
    snapshot = HOME / f".news-{stamp}.db"
    members = []
    if DB_PATH.exists():
        src = sqlite3.connect(DB_PATH)
        try:
            dst = sqlite3.connect(snapshot)
            src.backup(dst)
            dst.close()
        finally:
            src.close()
        members.append((snapshot, "news.db"))
    histories = [p for p in GOVERNANCE.iterdir() if p.is_dir() and not p.is_symlink() and not p.name.startswith(".")
                 and p != keep and p != GOV_CURRENT]
    members += [(p, f"governance/{p.name}") for p in histories]
    for folder, name in ((FULLTEXT, "fulltext"), (GROUP_RAW, "group-raw")):
        if folder.exists():
            members.append((folder, name))
    derived = {"fulltext/downloads", "fulltext/.downloads.tmp", "fulltext/.downloads.old"}  # rebuilt from the rest
    with tarfile.open(tmp, "w:gz", compresslevel=1) as archive:
        for path, name in members:
            archive.add(path, name, filter=lambda info: None if any(info.name == d or info.name.startswith(d + "/") for d in derived) else info)
    tmp.rename(target)
    snapshot.unlink(missing_ok=True)
    removed = []
    for path in (*histories, FULLTEXT, GROUP, BACKUPS):
        if path.exists():
            _writable(path)
            shutil.rmtree(path)
            removed.append(path.name)
    return {"archive": str(target), "bytes": target.stat().st_size, "removed": removed}


def cmd_ingest_governance(args) -> int:
    """The text-database history: verify the package (handover_manifest.json), archive and remove what it replaces, build
    news.db from its eligible articles, write its full texts, re-export. Later updates add only news published after it."""
    folder = Path(args.folder)
    files = {name: f for name, f in json.loads((folder / "handover_manifest.json").read_text(encoding="utf-8")).items()
             if name not in HISTORY_DUPLICATES}

    def changed(root: Path) -> list:
        return [name for name, f in files.items() if not (root / name).is_file() or (root / name).stat().st_size != f["bytes"]
                or _sha256(root / name) != f["sha256"]]
    bad = changed(folder)
    if bad:
        raise SystemExit(f"{folder}: files missing or changed against handover_manifest.json: {', '.join(bad[:5])}")
    version = json.loads((folder / "method/config/taxonomy_14_83.json").read_text(encoding="utf-8"))["version"]
    if version != governance()["version"]:
        raise SystemExit(f"the package is labelled with {version}, grenn_governance/ has {governance()['version']}")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    release = args.label or f"{version}-{stamp[:8]}"
    with lock():
        # the package (read-only), its text chunks and the new news.db — all before anything goes
        base = GOVERNANCE / release
        if base.exists():
            raise SystemExit(f"{base} exists already")
        work = GOVERNANCE / f".{release}.tmp"
        if work.exists():
            _writable(work)
            shutil.rmtree(work)
        shutil.copytree(folder, work / "raw", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.jsonl.gz", "corpus.sqlite.part-*", "*.zip"))
        if changed(work / "raw"):
            raise RuntimeError("the copy does not match the package")
        for name in TIMELINE_FILES:
            for old in (GOV_CURRENT / name, GOV_CURRENT / "raw" / name):
                if old.is_file():
                    shutil.copy(old, work / name)
                    break
        raw_db = work / "raw" / "data" / "corpus.sqlite"
        order = history_order(raw_db)
        log(f"{len(order)} eligible articles")
        refs = write_texts(raw_db, order, work / "texts")
        previous_since = None
        if DB_PATH.exists():
            old = connect(DB_PATH, readonly=True)
            previous_since = meta_get(old, "daily_since")
            old.close()
        new_path = HOME / f".news-{stamp}.new.db"
        new = connect(new_path)
        merged = ingest_rows(Store(new), history_rows(raw_db, order), feed="governance:articles", kind="governance",
                             origin=GOVERNANCE_ORIGIN, convert=lambda d: from_governance(d, refs), stamp=now_iso())
        last = new.execute("SELECT max(published_date) FROM news").fetchone()[0]
        since = (datetime.fromisoformat(last[:10]).date() + timedelta(days=1)).isoformat()
        # the delivery thins out in its last days: the daily items since the previous history ended stay in (same url = one row)
        since = min(filter(None, (since, previous_since)))
        for key, value in (("history_version", version), ("history_imported_at", now_iso()), ("daily_since", since)):
            meta_set(new, key, value)
        with Run(new, "ingest-governance") as run:
            run.stats.update(version=version, release=release, merge=merged, daily_since=since, text_chunks=len(set(refs.values())))
        new.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        new.close()
        (work / "history.json").write_text(json.dumps({"version": version, "release": release, "imported_at": now_iso(),
                                                       "daily_since": since, "merge": merged}, ensure_ascii=False, indent=1), encoding="utf-8")
        if os.name == "posix":
            for path in (work / "raw").rglob("*"):
                path.chmod(0o555 if path.is_dir() else 0o444)
        work.rename(base)
        _switch(GOV_CURRENT, base)
        # now the old stores go (one archive copy is kept) and the new database takes their place
        archived = archive_previous(stamp, keep=base)
        for suffix in ("", "-wal", "-shm"):
            with contextlib.suppress(FileNotFoundError):
                Path(f"{DB_PATH}{suffix}").unlink()
        new_path.rename(DB_PATH)
        conn = connect()
        with Run(conn, "archive-previous") as run:
            run.stats.update(archived)
        export(conn, force=True)
    log(json.dumps({"governance": release, "daily_since": since, "merge": merged, **archived}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- governance history: a later batch (2026-11-14)
# The second delivery (功能更新1113/GREEN_batch2_01_fulltexts: 195,007 articles that passed the same automatic screening) adds
# to the history instead of replacing it. Its sister package of records awaiting review (…_02_review, research_eligible
# false) is never imported: review files are refused by name and, again, record by record.

BATCH_DATA = re.compile(r"new_fulltexts_\d+\.jsonl\.gz")
BATCH_NOTES = ("manifest.json", "README.txt", "validation.json", "coverage.json")


def batch_docs(files: list, known: dict, folder: Path, start: int, counts: dict, written: list):
    """The batch's eligible articles as `ingest_rows` takes them (the opening text, no evidence spans). An article's full
    text goes into a new chunk under `folder` as it passes, unless the database has that article's text already
    (`known`: article_id → chunk), so a second run of the same batch writes nothing."""
    version = governance()["version"]
    chunk, n, placed = {}, start, {}

    def flush():
        nonlocal chunk, n
        if chunk:
            path = folder / f"t{n:04d}.json"
            path.write_text(json.dumps(chunk, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            written.append(path)
            chunk, n = {}, n + 1
    for path in files:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                doc = json.loads(line)
                counts["read"] += 1
                key, text = doc.get("article_id"), doc.get("source_text") or ""
                if doc.get("research_eligible") is not True:
                    counts["not_eligible"] += 1
                    continue
                if not key or hashlib.sha256(text.encode()).hexdigest() != doc.get("text_sha256"):
                    counts["bad_checksum"] += 1
                    continue
                labels = doc.get("labels") or {}
                if labels.get("version") != version:
                    counts["other_labels"] += 1
                    continue
                if key in known or key in placed:
                    counts["text_known"] += 1
                else:
                    chunk[key] = {"t": doc.get("title"), "u": doc.get("url"), "p": doc.get("publisher"), "d": doc.get("published_date"),
                                  "x": EMAIL.sub("[REDACTED_EMAIL]", text) if "@" in text else text}
                    placed[key] = f"t{n:04d}"
                    counts["texts"] += 1
                    if len(chunk) >= TEXT_CHUNK:
                        flush()
                doc["text_ref"] = known.get(key) or placed[key]
                doc["canonical_url"] = doc.get("url")
                doc["lead"] = text[:4000]
                del doc["source_text"]
                doc["labels"] = {k: v for k, v in labels.items() if k not in ("evidence", "scores")}
                doc.pop("relevance_evidence", None)
                yield doc
    flush()


def cmd_ingest_governance_batch(args) -> int:
    """Add a later delivery of eligible full texts to the history: check the files against the package's manifest.json,
    merge the articles (same url or same normalised text = one row), write their texts as further chunks, keep the package
    beside the history (never served), re-export. Running it again adds nothing."""
    folder = Path(args.folder)
    listed = {f["name"]: f for f in json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["files"]}
    files = sorted((folder / "data").glob("*.jsonl.gz"))
    wrong = [p.name for p in files if not BATCH_DATA.fullmatch(p.name)]
    if wrong or not files:
        raise SystemExit(f"{folder}/data: only new_fulltexts_NNN.jsonl.gz is taken in (review records stay out): {', '.join(wrong[:5]) or 'no files'}")
    missing = sorted(name for name in listed if BATCH_DATA.fullmatch(name) and not (folder / "data" / name).is_file())
    bad = [p.name for p in files if p.name not in listed or p.stat().st_size != listed[p.name]["bytes"] or _sha256(p) != listed[p.name]["sha256"]]
    if missing or bad:
        raise SystemExit(f"{folder}: against manifest.json — missing {missing[:5]}, changed or unlisted {bad[:5]}")
    if not (GOV_CURRENT / "history.json").exists():
        raise SystemExit("no governance history yet: ingest-governance comes first")
    label = args.label or folder.name
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,60}", label):
        raise SystemExit("--label: letters, digits, . _ - only")
    origin = "governance-" + re.sub(r"\D", "", str(json.loads((folder / "manifest.json").read_text(encoding="utf-8")).get("at", ""))[:10])
    texts = GOV_CURRENT / "texts"
    counts = {"read": 0, "not_eligible": 0, "bad_checksum": 0, "other_labels": 0, "text_known": 0, "texts": 0}
    written = []
    with lock():
        conn = connect()
        before = conn.execute("SELECT count(*), sum(research_eligible=1) FROM news").fetchone()
        known = dict(conn.execute("SELECT coalesce(document_key, record_id), text_ref FROM news WHERE text_ref IS NOT NULL"))
        start = max((int(p.stem[1:]) for p in texts.glob("t*.json")), default=-1) + 1
        try:
            with Run(conn, "ingest-governance-batch") as run:
                merged = ingest_rows(Store(conn), batch_docs(files, known, texts, start, counts, written), feed=f"governance-batch:{label}",
                                     kind="governance", origin=origin, stamp=now_iso(),
                                     convert=lambda d: from_governance(d, {d["article_id"]: d["text_ref"]}))
                run.stats.update(batch=label, origin=origin, merge=merged, **counts, text_chunks=len(written))
        except BaseException:
            for path in written:  # the rows were rolled back: their chunks go too
                path.unlink(missing_ok=True)
            raise
        after = conn.execute("SELECT count(*), sum(research_eligible=1) FROM news").fetchone()
        report = {"batch": label, "origin": origin, "imported_at": now_iso(), "files": len(files), "merge": merged, **counts,
                  "text_chunks": len(written), "records": [before[0], after[0]], "eligible": [before[1], after[1]]}
        # the package beside the history: private, read-only, checked by `verify`
        keep = GOV_CURRENT / "batches" / label
        if not keep.exists():
            work = GOV_CURRENT / "batches" / f".{label}.tmp"
            shutil.rmtree(work, ignore_errors=True)
            (work / "data").mkdir(parents=True)
            for name in BATCH_NOTES:
                if (folder / name).is_file():
                    shutil.copy(folder / name, work / name)
            for path in files:
                shutil.copy(path, work / "data" / path.name)
            if os.name == "posix":
                for path in work.rglob("*"):
                    path.chmod(0o555 if path.is_dir() else 0o444)
            work.rename(keep)
        batches = json.loads(meta_get(conn, "history_batches") or "[]")
        if merged["added"] or not any(b.get("batch") == label for b in batches):  # a repeat that adds nothing keeps the first report
            batches = [b for b in batches if b.get("batch") != label] + [report]
        meta_set(conn, "history_batches", json.dumps(batches, ensure_ascii=False))
        conn.commit()
        export(conn, force=True)
    log(json.dumps(report, ensure_ascii=False))
    return 0


def batch_report(conn=None, *, deep: bool = False) -> list:
    """The later batches kept beside the history: name, files, and whether they still match their manifest."""
    out = []
    root = GOV_CURRENT / "batches"
    for folder in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")) if root.is_dir() else []:
        listed = {f["name"]: f for f in json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["files"] if BATCH_DATA.fullmatch(f["name"])}
        bad = [n for n, f in listed.items() if not (folder / "data" / n).is_file() or (folder / "data" / n).stat().st_size != f["bytes"]
               or (deep and _sha256(folder / "data" / n) != f["sha256"])]
        out.append({"batch": folder.name, "files": len(listed), "bad_files": bad})
    return out


def link_texts(root: Path) -> None:
    """The history's text chunks hard-linked into an export as texts/ (the site reads them to show an article)."""
    for chunk in (GOV_CURRENT / "texts").glob("t*.json"):
        _place(chunk, root / "texts" / chunk.name)


NETWORK_NODES = 45  # the most frequent countries and organisations in the co-occurrence network
NETWORK_PARTNERS = 14  # strongest partners listed per node (the network's focused view)
COUNTRY_ROWS = 30  # most mentioned countries in the countries × categories matrix
# policy-timeline proposition prefix → category (the package has no such table; fossil_* is the energy transition,
# science_* the assessment category)
TIMELINE_CATEGORY = {"negotiations": "G01", "mitigation": "G03", "energy": "G03", "fossil": "G03", "adaptation": "G04",
                     "loss": "G05", "finance": "G06", "market": "G07", "technology": "G08", "transparency": "G09",
                     "science": "G09", "justice": "G10", "nature": "G12"}


CONTINENTS = {"Asia": "亚洲", "Europe": "欧洲", "North America": "北美洲", "South America": "南美洲", "Africa": "非洲",
              "Oceania": "大洋洲", "Antarctica": "南极洲"}
AGGREGATOR_NAMES = re.compile(r"^(gdelt|google news)", re.I)  # feed names, not publishers: the domain names those rows
# UNFCCC COP sessions (number, host city, first and last day; deploy/fulltext/cops.json): the event window of the
# statistics page's COP chart. COP26 was held in 2021 (none in 2020).
COP_SESSIONS = {
    2007: (13, "Bali", "2007-12-03", "2007-12-15"), 2008: (14, "Poznan", "2008-12-01", "2008-12-12"),
    2009: (15, "Copenhagen", "2009-12-07", "2009-12-19"), 2010: (16, "Cancun", "2010-11-29", "2010-12-11"),
    2011: (17, "Durban", "2011-11-28", "2011-12-11"), 2012: (18, "Doha", "2012-11-26", "2012-12-08"),
    2013: (19, "Warsaw", "2013-11-11", "2013-11-23"), 2014: (20, "Lima", "2014-12-01", "2014-12-14"),
    2015: (21, "Paris", "2015-11-30", "2015-12-12"), 2016: (22, "Marrakech", "2016-11-07", "2016-11-18"),
    2017: (23, "Bonn", "2017-11-06", "2017-11-17"), 2018: (24, "Katowice", "2018-12-02", "2018-12-15"),
    2019: (25, "Madrid", "2019-12-02", "2019-12-15"), 2021: (26, "Glasgow", "2021-10-31", "2021-11-13"),
    2022: (27, "Sharm el-Sheikh", "2022-11-06", "2022-11-20"), 2023: (28, "Dubai", "2023-11-30", "2023-12-13"),
    2024: (29, "Baku", "2024-11-11", "2024-11-24"), 2025: (30, "Belem", "2025-11-10", "2025-11-22"),
    2026: (31, "Antalya", "2026-11-09", "2026-11-20"),
}
COP_WINDOW = 45  # days before and after a session's first day


def write_analytics(conn, root: Path) -> dict | None:
    """The four research charts (2026-11-05, user: 科研分析功能，优先开发四类图表), from news.db, by the 14 categories (a
    subcategory code's first three characters): categories by year (multi-label and exclusive primary category, with
    each year's denominator and active publishers, so collection growth is not read as topic growth; `trend_from` is
    where the years stop being sparse), the category co-occurrence matrix, the country / organisation co-occurrence
    network, and the history's policy timeline (complete records).
    2026-11-09: also each year's primary subcategories and months, countries × categories, each network node's strongest
    partners, and categories → policy tools → policy stages (user: 增加数据可视化图表).
    2026-11-10 (user: 把数据统计页面的数据和整个数据库的数据统一起来): every record of the database, not only the research
    set (research_eligible = 1, the history), and `corpus`: the statistics page's key figures and summary charts (the
    shape of the original project's corpus_analytics.json, which the page showed until then) counted as the manifest
    counts them — records, coverage_from, summary_figures' countries / publishers / topics.
    2026-11-11 (user: 增加更多有科研意义的数据可视化): every country's mentions by category (`countries_all`, the world
    map), the continents' (`continents`, the regional profiles), each year's effective number of countries (the
    exponential of the Shannon entropy of its country mentions: the agenda-diversity chart) and the days around each
    COP session (`cop_window`: all articles and those whose primary category is G01, with the year's daily mean)."""
    if not meta_get(conn, "history_version"):
        return None
    g = governance()
    order = [p[0] for p in g["parents"]]
    years: dict[str, dict] = {}
    pair = [[0] * len(order) for _ in order]
    totals = [0] * len(order)
    entities: dict[str, int] = {}
    entity_topics: dict[str, dict] = {}
    edges: dict[tuple, int] = {}
    subcategories = {t[0] for t in g["topics"]}
    topic_tool: dict[tuple, int] = {}
    tool_stage: dict[tuple, int] = {}
    months: dict[str, int] = {}
    days: set = set()
    sub_counts: dict[str, int] = {}
    country_counts: dict[str, int] = {}
    continent_counts: dict[str, int] = {}
    publisher_counts: dict[str, int] = {}
    publisher_names: dict[str, dict] = {}
    records = tagged = 0
    daily: dict[str, int] = {}
    daily_talks: dict[str, int] = {}
    continent_topics: dict[str, dict] = {}

    def mentioned(codes, orgs) -> set:
        return {f"country:{c['alpha2']}" for c in _loads(codes, []) if isinstance(c, dict) and c.get("alpha2")} | {f"org:{o}" for o in _loads(orgs, []) if o}
    for date, primary, topics, codes, orgs, publisher, tools, stages, continents, name in conn.execute(
            """SELECT published_date, primary_topic, topics, country_codes, organization_tags, coalesce(source_domain, source_name),
                      policy_tools, policy_stages, continent_tags, source_name FROM news"""):
        records += 1
        months[date[:7]] = months.get(date[:7], 0) + 1
        if len(date) == 10:
            days.add(date)
        if publisher is not None:  # as summary_figures' count(DISTINCT …), which leaves NULL out
            publisher_counts[publisher] = publisher_counts.get(publisher, 0) + 1
        if name and not AGGREGATOR_NAMES.match(name):
            names = publisher_names.setdefault(publisher, {})
            names[name] = names.get(name, 0) + 1
        for code in dict.fromkeys(t for t in _loads(topics, []) if t in subcategories):
            sub_counts[code] = sub_counts.get(code, 0) + 1
        for place in _loads(continents, []) or ["unassigned"]:
            continent_counts[place] = continent_counts.get(place, 0) + 1
        y = years.setdefault(date[:4], {"articles": 0, "publishers": set(), "topics": dict.fromkeys(order, 0),
                                        "primary": dict.fromkeys([*order, "unclassified"], 0), "sub": {}, "months": [0] * 12})
        y["articles"] += 1
        y["publishers"].add(publisher)
        cats = list(dict.fromkeys(t[:3] for t in _loads(topics, []) if t[:3] in y["topics"]))
        for t in cats:
            y["topics"][t] += 1
            totals[order.index(t)] += 1
        main = (primary or "")[:3]
        y["primary"][main if main in y["topics"] else "unclassified"] += 1
        if primary in subcategories:
            y["sub"][primary] = y["sub"].get(primary, 0) + 1
        if len(date) == 10:
            daily[date] = daily.get(date, 0) + 1
            if main == "G01":
                daily_talks[date] = daily_talks.get(date, 0) + 1
        for place in _loads(continents, []):
            bucket = continent_topics.setdefault(place, {})
            for t in cats:
                bucket[t] = bucket.get(t, 0) + 1
        if date[5:7].isdigit() and 1 <= int(date[5:7]) <= 12:
            y["months"][int(date[5:7]) - 1] += 1
        tools, stages = _loads(tools, []), _loads(stages, [])
        for tool in tools:
            if main in y["topics"]:
                topic_tool[(main, tool)] = topic_tool.get((main, tool), 0) + 1
            for stage in stages:
                tool_stage[(tool, stage)] = tool_stage.get((tool, stage), 0) + 1
        idx = sorted(order.index(t) for t in cats)
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                pair[idx[a]][idx[b]] += 1
        named = mentioned(codes, orgs)
        countries = [e[8:] for e in named if e.startswith("country:")]
        if countries:
            tagged += 1
            mentions = y.setdefault("countries", {})
            for code in countries:
                country_counts[code] = country_counts.get(code, 0) + 1
                mentions[code] = mentions.get(code, 0) + 1
        for e in named:
            entities[e] = entities.get(e, 0) + 1
            bucket = entity_topics.setdefault(e, {})
            for t in cats:
                bucket[t] = bucket.get(t, 0) + 1
    top = [e for e, _ in sorted(entities.items(), key=lambda kv: -kv[1])[:NETWORK_NODES]]
    keep = set(top)
    for codes, orgs in conn.execute("SELECT country_codes, organization_tags FROM news"):
        mine = sorted(mentioned(codes, orgs) & keep)
        for a in range(len(mine)):
            for b in range(a + 1, len(mine)):
                edges[(mine[a], mine[b])] = edges.get((mine[a], mine[b]), 0) + 1
    org_names = g["organizations"]
    def label(e):
        kind, code = e.split(":", 1)
        if kind == "country":
            c = g["countries"].get(code, {})
            return {"zh": c.get("name_zh", code), "en": c.get("name_en", code)}
        return {"zh": org_names.get(code, code), "en": code.replace("_", " ")}
    nodes = [{"id": e, "kind": e.split(":")[0], **label(e), "articles": entities[e],
              "topic": max(entity_topics.get(e, {"": 0}).items(), key=lambda kv: kv[1])[0] or None} for e in top]
    links = [{"a": a, "b": b, "articles": n, "jaccard": round(n / (entities[a] + entities[b] - n), 4)}
             for (a, b), n in edges.items() if n >= 3]
    links.sort(key=lambda link: -link["jaccard"])
    partners: dict[str, list] = {}
    for link in links:  # strongest first: each node's closest partners, for the network's focused view
        for me, other in ((link["a"], link["b"]), (link["b"], link["a"])):
            mine = partners.setdefault(me, [])
            if len(mine) < NETWORK_PARTNERS:
                mine.append([other, link["articles"], link["jaccard"]])
    country_rows = [e for e, _ in sorted(entities.items(), key=lambda kv: -kv[1]) if e.startswith("country:")][:COUNTRY_ROWS]
    try:
        events = json.loads((GOV_CURRENT / "policy_timeline_ready.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        events = []
    def actor(code):
        c = g["countries"].get(code)
        return {"zh": c["name_zh"], "en": c["name_en"]} if c else {"zh": org_names.get(code, code), "en": code}
    # one row per document: several claims of the same statement (same date, actor, link) are merged
    merged = {}
    for e in events:
        if not e.get("date"):
            continue
        prop = str(e.get("topic_proposition") or "")
        topic = TIMELINE_CATEGORY.get(prop.split("_")[0])
        key = (e.get("date"), e.get("actor"), e.get("source_url") or e.get("title"))
        row = merged.setdefault(key, {"date": e.get("date"), "actor": e.get("actor"), "actor_name": actor(e.get("actor")),
                                      "topics": [], "propositions": [], "title": e.get("title"), "summary": e.get("summary_zh"),
                                      "quotes": [], "url": e.get("source_url"), "review": e.get("review_status")})
        if topic and topic not in row["topics"]:
            row["topics"].append(topic)
        if prop:
            row["propositions"].append(prop)
        if e.get("evidence_quote") and e["evidence_quote"] not in row["quotes"]:
            row["quotes"].append(e["evidence_quote"])
    timeline = sorted(merged.values(), key=lambda e: e["date"])
    def effective(counts: dict) -> float:  # exp(Shannon entropy): how many equally mentioned items the spread equals
        total = sum(counts.values())
        return round(math.exp(-sum(n / total * math.log(n / total) for n in counts.values() if n)), 2) if total else 0
    rows = [{"year": k, "articles": v["articles"], "publishers": len(v["publishers"]), "topics": v["topics"],
             "primary": v["primary"], "sub": v["sub"], "months": v["months"],
             "countries": len(v.get("countries", {})), "country_effective": effective(v.get("countries", {}))}
            for k, v in sorted(years.items())]
    # the days around each COP session whose whole window lies inside the data
    last_day, sessions = max(daily, default=""), []
    for year, (number, city, start, end) in COP_SESSIONS.items():
        first = datetime.strptime(start, "%Y-%m-%d").date()
        span = [(first + timedelta(days=offset)).isoformat() for offset in range(-COP_WINDOW, COP_WINDOW + 1)]
        info = years.get(str(year))
        if not info or span[-1] > last_day or info["articles"] < TREND_MIN:
            continue
        length = 366 if year % 4 == 0 else 365
        sessions.append({"n": number, "year": year, "city": city, "start": start,
                         "length": (datetime.strptime(end, "%Y-%m-%d").date() - first).days + 1,
                         "base": round(info["articles"] / length, 3), "base_talks": round(info["primary"].get("G01", 0) / length, 3),
                         "days": [daily.get(day, 0) for day in span], "talks": [daily_talks.get(day, 0) for day in span]})
    trend_from = None
    for r in reversed(rows):  # back from the latest year while every year is well filled and the years are consecutive
        if r["articles"] < TREND_MIN or (trend_from and int(r["year"]) != int(trend_from) - 1):
            break
        trend_from = r["year"]

    # the statistics page: months from the coverage start (the manifest's coverage_from; the stray older records and any
    # undated month are in the cumulative series' first value, so it ends at the record count)
    first_month = coverage_start(conn)
    valid = [m for m in months if re.fullmatch(r"\d{4}-\d{2}", m)]
    series, cumulative = [], sum(n for m, n in months.items() if m not in valid or m < first_month)
    year, month = int(first_month[:4]), int(first_month[5:7])
    while valid and f"{year:04d}-{month:02d}" <= max(valid):
        key = f"{year:04d}-{month:02d}"
        cumulative += months.get(key, 0)
        series.append((key, months.get(key, 0), cumulative))
        year, month = (year, month + 1) if month < 12 else (year + 1, 1)
    known, sub_names = g["countries"], {t[0]: (t[2], t[3]) for t in g["topics"]}
    def most(counts: dict, n: int) -> list:
        return sorted(counts.items(), key=lambda kv: -kv[1])[:n]
    def publisher_name(key: str) -> str:
        names = publisher_names.get(key)
        return max(names.items(), key=lambda kv: kv[1])[0] if names else re.sub(r"^www\.", "", key)
    span = conn.execute("SELECT min(published_date) FILTER (WHERE published_date >= ?), max(published_date) FROM news",
                        (f"{first_month}-01",)).fetchone()
    corpus = {
        "records": records, "date_start": span[0], "date_end": span[1],
        "days_covered": len(days), "avg_per_day": round(records / max(1, len(days)), 1),
        "country_tagged_records": tagged, "country_tagged_rate": round(tagged / max(1, records), 4),
        "topic_count": len(g["topics"]), "country_count": len(country_counts), "source_count": len(publisher_counts),
        "monthly_records": [{"month": k, "count": n} for k, n, _ in series],
        "archive_cumulative": [{"date": k, "value": c} for k, _, c in series],
        "top_topics": [{"id": k, "zh": sub_names[k][0], "en": sub_names[k][1], "count": n} for k, n in most(sub_counts, 10)],
        "top_countries": [{"id": k, "zh": known.get(k, {}).get("name_zh", k), "en": known.get(k, {}).get("name_en", k), "count": n}
                          for k, n in most(country_counts, 12)],
        "continents": [{"id": k, "zh": "全球/未标注" if k == "unassigned" else CONTINENTS.get(k, k),
                        "en": "Global / unassigned" if k == "unassigned" else k, "count": n} for k, n in most(continent_counts, 10)],
        "top_sources": [{"id": k, "name": publisher_name(k), "count": n} for k, n in most(publisher_counts, 10)],
    }
    body = {"schema": "grenn-analytics/6", "generated_at": now_iso(), "history": meta_get(conn, "history_version"),
            "scope": "all records", "corpus": corpus,
            "topics": [{"id": p[0], "zh": p[1], "en": p[2]} for p in g["parents"]],
            "subtopics": len(g["topics"]),
            "subcategories": [{"id": t[0], "parent": t[1], "zh": t[2], "en": t[3]} for t in g["topics"]],
            "years": rows, "trend_from": trend_from,
            "matrix": {"totals": totals, "pairs": pair},
            "network": {"nodes": nodes, "links": links[:220], "partners": partners},
            "country_topics": [{"id": e.split(":", 1)[1], **label(e), "articles": entities[e], "topics": entity_topics.get(e, {})} for e in country_rows],
            "countries_all": [{"id": e.split(":", 1)[1], **label(e), "n": n, "t": [entity_topics.get(e, {}).get(k, 0) for k in order]}
                              for e, n in sorted(entities.items(), key=lambda kv: -kv[1]) if e.startswith("country:")],
            "continents": [{"id": k, "zh": CONTINENTS.get(k, k), "en": k, "n": continent_counts.get(k, 0), "t": [v.get(c, 0) for c in order]}
                           for k, v in sorted(continent_topics.items(), key=lambda kv: -continent_counts.get(kv[0], 0))],
            "cop_window": {"before": COP_WINDOW, "after": COP_WINDOW, "sessions": sessions},
            "flows": {"topic_tool": [[a, b, n] for (a, b), n in topic_tool.items()], "tool_stage": [[a, b, n] for (a, b), n in tool_stage.items()]},
            "timeline": timeline}
    path = root / "analytics.json"
    path.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return _file_entry(root, path)


INDEX_EXCERPT = 140  # characters of excerpt per row in search-index.json
INDEX_FIRST = 2000  # rows (newest first) in search-index.json (≈ 0.3 MB compressed: the list is up within seconds even
                    # over a slow link); the rest in search-index-N.json of INDEX_PART rows, which the site appends in turn
INDEX_PART = 20000  # (240,000 rows: about 80 MB; the site fetches these parts only when someone searches or filters)
COHORT_CODES = {"original_recovery": "o", "new_library": "n", "new_expansion_20261106": "x", "new_cloud_20261107": "x",
                "green-incremental-8h-v1": "x", "green-incremental-48h-v1": "x", "daily": "d"}  # others: "s" (supplements)


def write_search_index(conn, root: Path) -> dict | None:
    """Every record for the site's text-database list (title, date, publisher, labels, excerpt), newest first, written part
    by part; the full text of a history article is in texts/<text_ref>.json. Topics are the 83 subcategories, grouped
    (`domain`) by the 14 categories (`domains`). `facets` (the country and year filters' values) and `records` let the
    list open from the first part alone."""
    if not meta_get(conn, "history_version"):
        return None
    g = governance()
    first, rows, parts = [], [], []
    total = 0
    country_counts: dict[str, int] = {}
    years: set[str] = set()

    def write_part() -> None:
        part = root / f"search-index-{len(parts) + 1}.json"
        part.write_text(json.dumps({"rows": rows}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        parts.append(_file_entry(root, part, records=len(rows)))
        rows.clear()
    for r in conn.execute("""SELECT record_id, document_key, published_date, source_domain, source_name, title_original, title_zh,
                                    primary_topic, topics, country_codes, summary_zh, summary_source, url, text_ref, cohort,
                                    research_eligible FROM news ORDER BY published_date DESC, record_id"""):
        codes = [c.get("alpha2") for c in _loads(r["country_codes"], []) if isinstance(c, dict)]
        blurb = re.sub(r"\s+", " ", r["summary_zh"] or r["summary_source"] or "").strip()
        row = [r["document_key"] or r["record_id"], r["published_date"], r["source_domain"] or r["source_name"] or "",
               r["title_original"] or "", r["title_zh"] or "", r["primary_topic"] or "", ",".join(_loads(r["topics"], [])),
               ",".join(filter(None, codes)), blurb[:INDEX_EXCERPT] + ("…" if len(blurb) > INDEX_EXCERPT else ""),
               r["text_ref"] or "", "" if r["text_ref"] else r["url"],
               COHORT_CODES.get(r["cohort"] or "daily", "s"), r["research_eligible"] or 0]
        total += 1
        years.add(r["published_date"][:4])
        for code in filter(None, codes):
            country_counts[code] = country_counts.get(code, 0) + 1
        if len(first) < INDEX_FIRST:
            first.append(row)
            continue
        rows.append(row)
        if len(rows) >= INDEX_PART:
            write_part()
    if rows:
        write_part()
    countries = {a: [c["name_zh"], c["name_en"], c["alpha3"]] for a, c in g["countries"].items()}
    body = {"schema": "grenn-text-index/3", "generated_at": now_iso(), "history": meta_get(conn, "history_version"),
            "fields": ["key", "date", "publisher", "title", "title_zh", "primary_topic", "topics", "countries", "excerpt",
                       "text", "url", "cohort", "research"],
            "topics": [{"id": t[0], "domain": t[1], "zh": t[2], "en": t[3]} for t in g["topics"]],
            "domains": [{"id": p[0], "zh": p[1], "en": p[2]} for p in g["parents"]],
            "countries": countries, "records": total,
            "facets": {"countries": sorted(country_counts, key=lambda code: -country_counts[code]), "years": sorted(years, reverse=True)},
            "rows": first}
    path = root / "search-index.json"
    path.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return _file_entry(root, path, records=total, parts=parts)


def governance_report(*, deep: bool = False) -> dict | None:
    if not (GOV_CURRENT / "history.json").exists():
        return None
    raw = GOV_CURRENT / "raw"
    files = {n: f for n, f in json.loads((raw / "handover_manifest.json").read_text(encoding="utf-8")).items() if n not in HISTORY_DUPLICATES}
    bad = [n for n, f in files.items() if not (raw / n).is_file() or (raw / n).stat().st_size != f["bytes"] or (deep and _sha256(raw / n) != f["sha256"])]
    history = json.loads((GOV_CURRENT / "history.json").read_text(encoding="utf-8"))
    batches = batch_report(deep=deep)
    return {"version": history["version"], "release": history.get("release"), "text_chunks": len(list((GOV_CURRENT / "texts").glob("t*.json"))),
            "archives": sorted(p.name for p in ARCHIVE_DIR.glob("pre-governance-*.tar.gz")) if ARCHIVE_DIR.exists() else [],
            "batches": [b["batch"] for b in batches],
            "bad_files": bad + [f"batches/{b['batch']}/{name}" for b in batches for name in b["bad_files"]]}


# ---------------------------------------------------------------- backup / restore / verify

def _sqlite_ok(path: Path, table: str = "news") -> tuple[bool, int]:
    probe = sqlite3.connect(f"file:{path}?immutable=1", uri=True)
    try:
        ok = probe.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        count = probe.execute(f"SELECT count(*) FROM {table}").fetchone()[0] if ok else 0
        return ok, count
    finally:
        probe.close()


def _rotate(folder: Path, keep: int, pattern: str = "news-*.db.gz") -> None:
    for old in sorted(folder.glob(pattern))[:-keep]:
        old.unlink()


def backup_fulltext(conn) -> dict | None:
    """One verified, compressed copy per fulltext.db version (it changes only on ingest). The images are
    content-addressed and immutable: `verify` checks them, the crawler machine keeps the second copy."""
    if not FULLTEXT_DB.exists():
        return None
    digest = _sha256(FULLTEXT_DB)
    if meta_get(conn, "fulltext_backup_sha256") == digest:
        return {"status": "unchanged"}
    ok, _ = _sqlite_ok(FULLTEXT_DB, table="articles")
    if not ok:
        raise RuntimeError("fulltext.db failed integrity_check — not backing up a damaged database")
    folder = BACKUPS / "fulltext"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"fulltext-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db.gz"
    with FULLTEXT_DB.open("rb") as src, gzip.open(target.with_suffix(".gz.tmp"), "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst)
    target.with_suffix(".gz.tmp").rename(target)
    _rotate(folder, KEEP_FULLTEXT, "fulltext-*.db.gz")
    meta_set(conn, "fulltext_backup_sha256", digest)
    return {"file": str(target), "bytes": target.stat().st_size}


def fulltext_report(*, deep: bool = False) -> dict | None:
    """Counts of the private full-text store and any image file that is missing / changed."""
    if not FULLTEXT_DB.exists():
        return None
    ft = sqlite3.connect(f"file:{FULLTEXT_DB}?immutable=1", uri=True)
    try:
        integrity = ft.execute("PRAGMA integrity_check").fetchone()[0]
        articles, chars = ft.execute("SELECT count(*), sum(text_chars) FROM articles WHERE status='done'").fetchone()
        images = ft.execute("SELECT DISTINCT path, bytes, sha256 FROM images WHERE status='done'").fetchall()
    finally:
        ft.close()
    bad = []
    for path, size, digest in images:
        file = FULLTEXT_IMAGES / path
        if not file.is_file() or file.stat().st_size != size or (deep and _sha256(file) != digest):
            bad.append(path)
    return {"integrity": integrity, "articles": articles, "text_chars": chars, "image_files": len(images),
            "image_bytes": sum(r[1] or 0 for r in images), "bad_images": bad}


def cmd_backup(args) -> int:
    with lock():
        conn = connect()
        with Run(conn, "backup") as run:
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("news.db failed quick_check — not backing up a damaged database; see `verify`")
            stamp = datetime.now().strftime("%Y%m%d-%H%M")
            for kind in KEEP:
                (BACKUPS / kind).mkdir(parents=True, exist_ok=True)
            tmp = BACKUPS / f".news-{stamp}.db"
            target = sqlite3.connect(tmp)
            try:
                conn.backup(target)
            finally:
                target.close()
            ok, count = _sqlite_ok(tmp)
            expected = conn.execute("SELECT count(*) FROM news").fetchone()[0]
            if not ok or count != expected:
                tmp.unlink()
                raise RuntimeError(f"backup copy failed verification (ok={ok}, rows {count} != {expected})")
            daily = BACKUPS / "daily" / f"news-{stamp}.db.gz"
            with tmp.open("rb") as src, gzip.open(daily.with_suffix(".gz.tmp"), "wb", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst)
            daily.with_suffix(".gz.tmp").rename(daily)
            tmp.unlink()
            today = datetime.now()
            if today.weekday() == 6:
                shutil.copy2(daily, BACKUPS / "weekly" / daily.name)
            if today.day == 1:
                shutil.copy2(daily, BACKUPS / "monthly" / daily.name)
            for kind, keep in KEEP.items():
                _rotate(BACKUPS / kind, keep)
            run.stats.update(file=str(daily), rows=count, bytes=daily.stat().st_size)
            run.stats["fulltext"] = backup_fulltext(conn)
            if today.day == 1:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                run.stats["vacuumed"] = True
    return 0


def restore_fulltext(source: Path) -> int:
    """Put a fulltext-*.db.gz backup back in place (the current file is kept aside); images are not touched."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tmp = FULLTEXT / f".restore-{stamp}.db"
    FULLTEXT.mkdir(parents=True, exist_ok=True)
    with gzip.open(source, "rb") as src, tmp.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    ok, count = _sqlite_ok(tmp, table="articles")
    if not ok:
        tmp.unlink()
        raise RuntimeError(f"{source} is not an intact full-text database")
    if FULLTEXT_DB.exists():
        keep = FULLTEXT / f"fulltext.db.before-restore-{stamp}"
        FULLTEXT_DB.rename(keep)
        log(f"previous full-text database kept as {keep}")
    os.replace(tmp, FULLTEXT_DB)
    conn = connect()
    with Run(conn, "restore") as run:
        run.stats.update(source=str(source), articles=count, store="fulltext")
    return 0


def cmd_restore(args) -> int:
    source = Path(args.file)
    if source.name.startswith("fulltext-"):
        with lock():
            return restore_fulltext(source)
    with lock():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        tmp = HOME / f".restore-{stamp}.db"
        opener = gzip.open if source.suffix == ".gz" else open
        with opener(source, "rb") as src, tmp.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        ok, count = _sqlite_ok(tmp)
        if not ok:
            tmp.unlink()
            raise RuntimeError(f"{source} is not an intact news database")
        if DB_PATH.exists():
            current = connect()
            current.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            current.close()
            keep = HOME / f"news.db.before-restore-{stamp}"
            DB_PATH.rename(keep)
            for suffix in ("-wal", "-shm"):
                with contextlib.suppress(FileNotFoundError):
                    Path(f"{DB_PATH}{suffix}").unlink()
            log(f"previous database kept as {keep}")
        tmp.rename(DB_PATH)
        conn = connect()
        with Run(conn, "restore") as run:
            run.stats.update(source=str(source), rows=count)
        export(conn, force=True)
    return 0


def cmd_verify(args) -> int:
    problems, notes = [], {}
    if not DB_PATH.exists():
        print("news.db does not exist — run `init` / `import-handover` first")
        return 1
    conn = connect(readonly=True)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        problems.append(f"integrity_check: {integrity}")
    notes["records"] = conn.execute("SELECT count(*) FROM news").fetchone()[0]
    future = (datetime.now(UTC).date() + timedelta(days=2)).isoformat()
    bad = conn.execute("""SELECT
        sum(title_original IS NULL OR title_original=''), sum(url NOT LIKE 'http%'),
        sum(published_date > ?), sum(json_valid(topics)=0 OR json_valid(country_codes)=0 OR json_valid(places)=0)
        FROM news""", (future,)).fetchone()
    for label, value in zip(("empty titles", "non-http urls", "future-dated", "invalid json"), bad):
        if value:
            problems.append(f"{value} rows with {label}")
    stale = staleness(conn)
    if stale:
        problems.append(stale)
    failed = conn.execute("""SELECT kind, max(started_at) FROM runs WHERE status='failed'
        AND started_at > coalesce((SELECT max(started_at) FROM runs r2 WHERE r2.kind=runs.kind AND r2.status='ok'), '')
        GROUP BY kind""").fetchall()
    for kind, when in failed:
        problems.append(f"last `{kind}` run failed ({when})")
    manifest_path = PUBLIC / "manifest.json"
    if not manifest_path.exists():
        problems.append("no published download set (public/manifest.json)")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        notes["exported_records"] = manifest["records"]
        public = [f for d in manifest.get("datasets", []) if d.get("access") != "account" for f in d["files"]]
        for entry in [*manifest["files"], *public, *(manifest[k] for k in ("search", "analytics") if manifest.get(k))]:
            path = PUBLIC / entry["path"]
            if not path.exists() or path.stat().st_size != entry["bytes"]:
                problems.append(f"download file missing or changed: {entry['path']}")
            elif args.deep and _file_entry(PUBLIC, path)["sha256"] != entry["sha256"]:
                problems.append(f"download file checksum mismatch: {entry['path']}")
    latest_backup = max((BACKUPS / "daily").glob("news-*.db.gz"), default=None)
    notes["latest_backup"] = latest_backup.name if latest_backup else None
    if not latest_backup or time.time() - latest_backup.stat().st_mtime > 2 * 86400:
        problems.append("no backup in the last 48 h")
    fulltext = fulltext_report(deep=args.deep)
    if fulltext:
        notes["fulltext"] = {k: v for k, v in fulltext.items() if k != "bad_images"}
        if fulltext["integrity"] != "ok":
            problems.append(f"fulltext.db integrity_check: {fulltext['integrity']}")
        if fulltext["bad_images"]:
            problems.append(f"{len(fulltext['bad_images'])} full-text images missing or changed (e.g. {fulltext['bad_images'][0]})")
        if meta_get(conn, "fulltext_backup_sha256") != _sha256(FULLTEXT_DB):
            problems.append("fulltext.db has no backup of its current version")
    history = governance_report(deep=args.deep)
    if history:
        notes["governance"] = {k: v for k, v in history.items() if k != "bad_files"}
        if history["bad_files"]:
            problems.append(f"{len(history['bad_files'])} governance files missing or changed (e.g. {history['bad_files'][0]})")
    group = group_report(deep=args.deep)
    if group:  # the raw archive is the delivery itself (the group keeps the originals); builds are rebuilt from it
        notes["group"] = {k: v for k, v in group.items() if k != "bad_files"}
        if group["bad_files"]:
            problems.append(f"{len(group['bad_files'])} group dataset files missing or changed (e.g. {group['bad_files'][0]})")
        if manifest_path.exists() and "datasets" not in manifest:
            problems.append("the downloads lack the group's public datasets — run `export --force`")
    if FULLTEXT_DB.exists() and meta_get(conn, "fulltext_downloads_sha256") != _sha256(FULLTEXT_DB):
        problems.append("the account downloads of the full-text archive are out of date — run `build-datasets`")
    print(json.dumps({"ok": not problems, "problems": problems, **notes}, ensure_ascii=False, indent=1))
    return 1 if problems else 0


def cmd_vacuum(args) -> int:
    with lock():
        conn = connect()
        with Run(conn, "vacuum") as run:
            before = DB_PATH.stat().st_size
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
            run.stats.update(bytes_before=before, bytes_after=DB_PATH.stat().st_size)
    return 0


def cmd_status(args) -> int:
    if not DB_PATH.exists():
        print("news.db does not exist yet")
        return 1
    conn = connect(readonly=True)
    total, first, last = conn.execute("SELECT count(*), min(published_date), max(published_date) FROM news").fetchone()
    report = {
        "database": str(DB_PATH),
        "bytes": DB_PATH.stat().st_size,
        "records": total,
        "published": [first, last],
        "by_origin": dict(conn.execute("SELECT origin, count(*) FROM news GROUP BY origin ORDER BY 2 DESC").fetchall()),
        "with_chinese": conn.execute("SELECT count(*) FROM news WHERE title_zh IS NOT NULL").fetchone()[0],
        "added": {
            label: conn.execute("SELECT count(*) FROM news WHERE first_seen_at >= ?",
                                ((datetime.now(UTC) - delta).isoformat(),)).fetchone()[0]
            for label, delta in (("24h", timedelta(hours=24)), ("7d", timedelta(days=7)))
        },
        "upstream": {k: meta_get(conn, f"upstream_{k}") for k in ("sha", "checked_at", "ingested_at")},
        "exported_at": meta_get(conn, "exported_at"),
        "last_runs": {
            r["kind"]: {"at": r["started_at"], "status": r["status"], "stats": json.loads(r["stats"]), "error": r["error"]}
            for r in conn.execute("""SELECT * FROM runs WHERE id IN (SELECT max(id) FROM runs GROUP BY kind) ORDER BY kind""")
        },
        "backups": {kind: len(list((BACKUPS / kind).glob("news-*.db.gz"))) for kind in KEEP},
        "disk_free_gb": round(shutil.disk_usage(HOME).free / 1e9, 1),
    }
    fulltext = fulltext_report()
    if fulltext:
        report["fulltext"] = {**{k: v for k, v in fulltext.items() if k != "bad_images"}, "bad_images": len(fulltext["bad_images"]),
                              "package": meta_get(conn, "fulltext_package"), "ingested_at": meta_get(conn, "fulltext_ingested_at"),
                              "public_records": conn.execute("SELECT count(*) FROM news WHERE origins LIKE '%fulltext-archive%'").fetchone()[0],
                              "backups": len(list((BACKUPS / "fulltext").glob("fulltext-*.db.gz")))}
    history = governance_report()
    if history:
        report["governance"] = {**history, "bad_files": len(history["bad_files"]),
                                "daily_since": meta_get(conn, "daily_since"), "imported_at": meta_get(conn, "history_imported_at")}
    group = group_report()
    if group:
        report["group"] = {**group, "bad_files": len(group["bad_files"]), "ingested_at": meta_get(conn, "group_ingested_at"),
                           "raw_labels": sorted(p.name for p in GROUP_RAW.iterdir() if p.is_dir() and not p.name.startswith("."))}
    if not args.json:
        for run in report["last_runs"].values():  # keep the human view short
            run["stats"] = {k: v for k, v in run["stats"].items() if not isinstance(v, (dict, list))}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


def cmd_init(args) -> int:
    with lock():
        conn = connect()
        log(f"initialised {DB_PATH} (schema {meta_get(conn, 'schema_version')})")
    return 0


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(prog="grenn-newsdb", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = cli.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="create news.db (schema only)").set_defaults(func=cmd_init)
    p = sub.add_parser("import-handover", help="import a handover package folder (climate.db / corpus / archive)")
    p.add_argument("folder")
    p.add_argument("--origin", default="handover-20261030")
    p.add_argument("--no-export", action="store_true")
    p.set_defaults(func=cmd_import_handover)
    p = sub.add_parser("ingest-fulltext", help="merge a full-text package (deploy/fulltext `package`): text + images kept privately")
    p.add_argument("folder")
    p.add_argument("--no-export", action="store_true")
    p.set_defaults(func=cmd_ingest_fulltext)
    p = sub.add_parser("ingest-governance", help="the text-database history (governance handover): archive and "
                                                 "remove the previous data, rebuild news.db from it, write its full texts")
    p.add_argument("folder", help="the unzipped handover package with data/corpus.sqlite merged (handover_manifest.json, "
                                  "method/config/taxonomy_14_83.json, …)")
    p.add_argument("--label", help="folder name under governance/ (default: <label version>-<date>)")
    p.set_defaults(func=cmd_ingest_governance)
    p = sub.add_parser("ingest-group", help="the research group's own full-text delivery: archive it, build the "
                                            "/datasets/ (group account) and public metadata datasets")
    p.add_argument("folder", help=f"folder holding {ORIGINAL}/, {LIBRARY}/ and {RESEARCH}/")
    p.add_argument("--label", help="delivery label (default: today's UTC date, YYYYMMDD); a different delivery needs a new one")
    p.add_argument("--no-export", action="store_true")
    p.set_defaults(func=cmd_ingest_group)
    sub.add_parser("build-datasets", help="rebuild /datasets/ (latest group delivery + full-text archive zips) and the downloads"
                   ).set_defaults(func=cmd_build_datasets)
    p = sub.add_parser("ingest-governance-batch", help="add a later delivery of eligible full texts (data/new_fulltexts_*.jsonl.gz + "
                       "manifest.json) to the history; review records are refused; running it again adds nothing")
    p.add_argument("folder")
    p.add_argument("--label", help="name the batch is kept under (default: the folder's name)")
    p.set_defaults(func=cmd_ingest_governance_batch)
    p = sub.add_parser("update", help="scheduled job: upstream + own crawl + downloads")
    p.add_argument("--force", action="store_true", help="re-ingest upstream and rebuild downloads even if unchanged")
    p.add_argument("--no-upstream", action="store_true")
    p.add_argument("--no-crawl", action="store_true")
    p.set_defaults(func=cmd_update)
    p = sub.add_parser("ingest-upstream", help="merge the original project's data")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_ingest_upstream)
    p = sub.add_parser("crawl", help="crawl the reachable sources and merge them")
    p.add_argument("--sources", help="comma-separated source ids (default: GRENN_CRAWL_SOURCES)")
    p.set_defaults(func=cmd_crawl)
    p = sub.add_parser("export", help="rebuild the public download set")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_export)
    sub.add_parser("backup", help="verified, compressed backup with daily/weekly/monthly rotation").set_defaults(func=cmd_backup)
    p = sub.add_parser("restore", help="replace news.db with a backup (the current file is kept aside)")
    p.add_argument("file")
    p.set_defaults(func=cmd_restore)
    p = sub.add_parser("verify", help="integrity, freshness, downloads and backups; exit 1 on problems")
    p.add_argument("--deep", action="store_true", help="also re-hash every download file")
    p.set_defaults(func=cmd_verify)
    sub.add_parser("vacuum", help="VACUUM + ANALYZE").set_defaults(func=cmd_vacuum)
    p = sub.add_parser("status", help="counts, last runs, backups")
    p.add_argument("--json", action="store_true", help="full run statistics")
    p.set_defaults(func=cmd_status)
    args = cli.parse_args(argv)
    try:
        return args.func(args)
    except Locked as exc:
        log(str(exc))
        return 0


if __name__ == "__main__":
    sys.exit(main())

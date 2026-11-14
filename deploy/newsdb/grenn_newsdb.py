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
Public downloads are rebuilt into $HOME/exports/<stamp>/ and published by switching the $HOME/public link,
which nginx serves at /downloads/. Every mutating command takes $HOME/.lock and is logged in the `runs` table.

Commands: init · import-handover DIR · update · ingest-upstream · crawl · export · backup · verify · status ·
restore FILE · vacuum.  Run `grenn-newsdb <command> -h` for options.
"""
from __future__ import annotations

import argparse
import ast
import csv
import contextlib
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
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
    updated_at TEXT NOT NULL
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
               "organization_tags", "event_tags")
TEXT_FIELDS = ("source_id", "source_name", "source_domain", "language", "title_original", "summary_source",
               "title_zh", "summary_zh", "title_en", "summary_en", "translation_status", "fact_status",
               "rights_status", "content_hash", "fetched_at")
MERGE_FIELDS = ("published_at", "published_date", *TEXT_FIELDS, *JSON_FIELDS, "relevance_score")
FILL_ONLY = {"fetched_at", "content_hash"}
# later, more curated inputs win field conflicts: raw crawl rows < backfill/corpus rows < bilingual archive rows
RANK = {"articles": 1, "historical": 2, "corpus": 2, "archive": 3}
AGGREGATORS = {"news.google.com"}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# public columns, in download order (CSV header and JSONL key order)
PUBLIC_FIELDS = (
    "record_id", "published_at", "published_date", "source_name", "source_domain", "source_id", "language",
    "title_original", "summary_source", "title_zh", "summary_zh", "title_en", "summary_en", "url",
    "topics", "country_tags", "country_codes", "continent_tags", "organization_tags", "event_tags", "numbers",
    "places", "relevance_score", "translation_status", "fact_status", "rights_status", "origin",
    "first_seen_at", "updated_at",
)
README = """GRENN 气候新闻文本数据库 · Climate news text database
https://zerocarbonx.cn/cop31/#database

本数据集由格润气候治理（GREEN）整理，每天自动更新：合并原项目每日两次的采集结果、本服务器自行采集的公开来源，以及 2026-10-30 交接的历史数据。
每条记录对应一篇新闻（按链接去重），只含元数据、来源摘录、模型生成的中英文标题与摘要和原文链接，不含原文全文。

文件
  climate-news-last7d / last30d.*   最近 7 / 30 天（按发布日期，UTC）
  monthly/climate-news-YYYY-MM.*    按月份（来源偶尔带出的多年前旧文章只收在“全部记录”里）
  climate-news-all.*.zip            全部记录
  climate-news-all.sqlite.zip       全部记录的 SQLite 数据库（表 news、sources、dataset_info）
  manifest.json                     本次导出的条数、日期范围、文件大小与 SHA-256
  CSV 为 UTF-8（带 BOM，可直接用 Excel 打开），列表字段以“; ”分隔；JSONL 每行一个 JSON 对象，列表字段保持为数组。

字段
  record_id            记录编号（沿用原项目 article_id）
  published_at         发布时间（UTC，ISO 8601）；published_date 为其 UTC 日期，换算北京时间请加 8 小时
  source_name          媒体 / 机构名称；source_domain 为其域名（聚合条目查不到时留空）；source_id 为原项目来源编号（API004 = 经 Google News 聚合）
  language             原文语言（multilingual = 聚合源未标明）
  title_original       原文标题；summary_source 为来源提供的摘录（RSS / API 摘要，非全文）
  title_zh, summary_zh 中文标题、摘要；title_en, summary_en 英文标题、摘要（模型生成，并非每条都有）
  url                  原文链接（Google News 聚合条目为其跳转链接）
  topics               议题；country_tags 国家/地区（“未标注”表示无信息）；country_codes ISO 3166-1（alpha-3）
  continent_tags       大洲；organization_tags 国际组织；event_tags 事件标签；numbers 文中关键数字
  places               地点（CSV 中只有地名，JSONL / SQLite 含经纬度）
  relevance_score      气候相关度评分（原项目规则，0–100）
  translation_status   中文内容状态（model_generated_needs_review = 模型生成、待人工复核）
  fact_status          事实状态（source_claim_unverified = 来源说法，未经核验）
  rights_status        权利状态（metadata_only = 仅元数据与短摘录）
  origin               最早收录渠道：handover-20261030 历史交接数据 / upstream 原项目采集 / server-crawl 本站服务器采集
  first_seen_at        首次收录本库的时间（UTC）；updated_at 最近一次内容更新时间（UTC）

使用须知
  - 摘要与译文由模型生成，重要数字、政策状态与承诺请打开原文并以官方文件核验。
  - 同一事件可能有多篇报道；条数不等于独立事件数，也不代表全球新闻总量。
  - 第三方新闻的权利归原作者与媒体所有；引用请保留来源与链接。本数据仅供研究与学习。
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

    def seen(self, feed: str, url: str, sig: str) -> bool:
        row = self.conn.execute("SELECT sig FROM ingest_state WHERE feed=? AND url=?", (feed, url)).fetchone()
        return bool(row and row[0] == sig)

    def mark(self, feed: str, url: str, sig: str) -> None:
        self.conn.execute("INSERT INTO ingest_state VALUES (?, ?, ?) ON CONFLICT(feed, url) DO UPDATE SET sig=excluded.sig",
                          (feed, url, sig))

    def upsert(self, rec: dict, *, origin: str, rank: int, stamp: str) -> str:
        url = rec["url"]
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
                    "detect_places": translation.detect_places}
    return _climate


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
    score = rec.get("relevance_score")
    out["relevance_score"] = int(score) if str(score or "").lstrip("-").isdigit() else None
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


def _http(url: str, *, accept: str = "*/*", timeout: int = 30):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    return urllib.request.urlopen(request, timeout=timeout)


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
        if field == "country_codes":
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


def _zip(source: Path, target: Path, arcname: str) -> None:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(source, arcname)


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
        link = HOME / ".public.tmp"
        with contextlib.suppress(FileNotFoundError):
            link.unlink()
        try:
            link.symlink_to(final.relative_to(HOME), target_is_directory=True)
            os.replace(link, PUBLIC)  # atomic switch for nginx
        except OSError:  # Windows without symlink rights (local testing): plain copy
            shutil.rmtree(PUBLIC, ignore_errors=True)
            shutil.copytree(final, PUBLIC)
        for old in sorted(p for p in EXPORTS.iterdir() if p.is_dir() and not p.name.startswith("."))[:-KEEP_EXPORTS]:
            shutil.rmtree(old, ignore_errors=True)
        meta_set(conn, "export_fingerprint", fingerprint)
        meta_set(conn, "exported_at", now_iso())
        return manifest


def write_export(conn, root: Path, *, fields) -> dict:
    today = datetime.now(UTC).date()
    windows = {"last7d": (today - timedelta(days=6)).isoformat(), "last30d": (today - timedelta(days=29)).isoformat()}
    full = Sink(root / "climate-news-all", fields)
    recent = {key: Sink(root / f"climate-news-{key}", fields) for key in windows}
    months: dict[str, Sink] = {}
    # feeds occasionally surface a years-old article: those stay in the full files, but the month files and the
    # advertised coverage start at the first month with regular data
    first_month = conn.execute("SELECT min(m) FROM (SELECT substr(published_date, 1, 7) m FROM news GROUP BY m HAVING count(*) >= ?)",
                               (MONTH_MIN_RECORDS,)).fetchone()[0] or "0000-00"
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
    (root / "README.txt").write_text(README, encoding="utf-8")

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
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def write_sqlite(conn, path: Path, fields) -> None:
    out = sqlite3.connect(path)
    try:
        cols = ", ".join(f"{f} {'INTEGER' if f == 'relevance_score' else 'TEXT'}" for f in fields)
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


# ---------------------------------------------------------------- backup / restore / verify

def _sqlite_ok(path: Path) -> tuple[bool, int]:
    probe = sqlite3.connect(f"file:{path}?immutable=1", uri=True)
    try:
        ok = probe.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        count = probe.execute("SELECT count(*) FROM news").fetchone()[0] if ok else 0
        return ok, count
    finally:
        probe.close()


def _rotate(folder: Path, keep: int) -> None:
    for old in sorted(folder.glob("news-*.db.gz"))[:-keep]:
        old.unlink()


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
            if today.day == 1:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                run.stats["vacuumed"] = True
    return 0


def cmd_restore(args) -> int:
    source = Path(args.file)
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
        for entry in manifest["files"]:
            path = PUBLIC / entry["path"]
            if not path.exists() or path.stat().st_size != entry["bytes"]:
                problems.append(f"download file missing or changed: {entry['path']}")
            elif args.deep and _file_entry(PUBLIC, path)["sha256"] != entry["sha256"]:
                problems.append(f"download file checksum mismatch: {entry['path']}")
    latest_backup = max((BACKUPS / "daily").glob("news-*.db.gz"), default=None)
    notes["latest_backup"] = latest_backup.name if latest_backup else None
    if not latest_backup or time.time() - latest_backup.stat().st_mtime > 2 * 86400:
        problems.append("no backup in the last 48 h")
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

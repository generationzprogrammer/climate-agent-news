from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    region TEXT,
    languages_json TEXT NOT NULL,
    focus TEXT,
    homepage_url TEXT NOT NULL,
    machine_url TEXT,
    access_method TEXT NOT NULL,
    storage_policy TEXT NOT NULL,
    compliance_note TEXT,
    phase TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    authority INTEGER NOT NULL,
    climate_relevance INTEGER NOT NULL,
    machine_readability INTEGER NOT NULL,
    poll_interval_minutes INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    title_zh TEXT NOT NULL,
    kicker TEXT NOT NULL,
    topic TEXT NOT NULL,
    status TEXT NOT NULL,
    data_status TEXT NOT NULL,
    key_value TEXT NOT NULL,
    key_label TEXT NOT NULL,
    summary TEXT NOT NULL,
    fact TEXT NOT NULL,
    assessment TEXT NOT NULL,
    action TEXT NOT NULL,
    published_at TEXT NOT NULL,
    urgency INTEGER NOT NULL,
    china_relevance INTEGER NOT NULL,
    negotiation_relevance INTEGER NOT NULL,
    independent_sources INTEGER NOT NULL,
    official_sources INTEGER NOT NULL,
    confidence REAL NOT NULL,
    source_refs_json TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    demo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS briefs (
    brief_id TEXT PRIMARY KEY,
    brief_date TEXT NOT NULL,
    version INTEGER NOT NULL,
    title TEXT NOT NULL,
    markdown TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(brief_date, version)
);

CREATE TABLE IF NOT EXISTS delivery_log (
    delivery_key TEXT PRIMARY KEY,
    brief_id TEXT NOT NULL REFERENCES briefs(brief_id),
    channel TEXT NOT NULL,
    recipient_ref TEXT NOT NULL,
    status TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS fetch_runs (
    run_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    endpoint TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    status TEXT NOT NULL,
    http_status INTEGER,
    content_type TEXT,
    response_bytes INTEGER NOT NULL DEFAULT 0,
    items_seen INTEGER NOT NULL DEFAULT 0,
    items_new INTEGER NOT NULL DEFAULT 0,
    items_updated INTEGER NOT NULL DEFAULT 0,
    error_class TEXT,
    error_message TEXT,
    quality_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_fetch_runs_source_time
ON fetch_runs(source_id, finished_at DESC);

CREATE TABLE IF NOT EXISTS articles (
    article_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    source_url TEXT NOT NULL,
    canonical_url TEXT NOT NULL UNIQUE,
    title_original TEXT NOT NULL,
    title_zh TEXT,
    summary_source TEXT,
    published_at_utc TEXT,
    language TEXT,
    rights_status TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    relevance_score INTEGER NOT NULL DEFAULT 0,
    topics_json TEXT NOT NULL DEFAULT '[]',
    numbers_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_articles_published
ON articles(published_at_utc DESC);

CREATE INDEX IF NOT EXISTS idx_articles_source
ON articles(source_id, published_at_utc DESC);

CREATE TABLE IF NOT EXISTS official_documents (
    document_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    party TEXT,
    title TEXT NOT NULL,
    symbol TEXT,
    body TEXT,
    session TEXT,
    cop_number INTEGER,
    version TEXT,
    status TEXT,
    publication_date TEXT,
    language TEXT,
    detail_url TEXT,
    file_url TEXT,
    source_dataset TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(kind, source_hash)
);

CREATE INDEX IF NOT EXISTS idx_documents_kind_date
ON official_documents(kind, publication_date DESC);

CREATE TABLE IF NOT EXISTS official_metrics (
    metric_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES official_documents(document_id),
    label_zh TEXT NOT NULL,
    value_text TEXT NOT NULL,
    scope_text TEXT NOT NULL,
    source_url TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def import_sources(self, source_file: Path) -> int:
        rows = json.loads(source_file.read_text(encoding="utf-8"))
        now = datetime.now(UTC).isoformat()
        sql = """
        INSERT INTO sources (
          source_id,name,source_type,region,languages_json,focus,homepage_url,
          machine_url,access_method,storage_policy,compliance_note,phase,enabled,
          authority,climate_relevance,machine_readability,poll_interval_minutes,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(source_id) DO UPDATE SET
          name=excluded.name, source_type=excluded.source_type, region=excluded.region,
          languages_json=excluded.languages_json, focus=excluded.focus,
          homepage_url=excluded.homepage_url, machine_url=excluded.machine_url,
          access_method=excluded.access_method, storage_policy=excluded.storage_policy,
          compliance_note=excluded.compliance_note, phase=excluded.phase,
          enabled=excluded.enabled, authority=excluded.authority,
          climate_relevance=excluded.climate_relevance,
          machine_readability=excluded.machine_readability,
          poll_interval_minutes=excluded.poll_interval_minutes, updated_at=excluded.updated_at
        """
        values = [
            (
                item["source_id"], item["name"], item["source_type"], item.get("region"),
                json.dumps(item.get("languages", []), ensure_ascii=False), item.get("focus"),
                item["homepage_url"], item.get("machine_url") or None, item["access_method"],
                item["storage_policy"], item.get("compliance_note"), item.get("phase", "P2"),
                int(bool(item.get("enable_recommended"))), item.get("authority", 3),
                item.get("climate_relevance", 3), item.get("machine_readability", 2),
                item.get("poll_interval_minutes", 360), now,
            )
            for item in rows
        ]
        with self.connect() as conn:
            conn.executemany(sql, values)
        return len(values)

    def seed_events(self, event_file: Path) -> int:
        rows = json.loads(event_file.read_text(encoding="utf-8"))
        columns = [
            "event_id", "title_zh", "kicker", "topic", "status", "data_status",
            "key_value", "key_label", "summary", "fact", "assessment", "action",
            "published_at", "urgency", "china_relevance", "negotiation_relevance",
            "independent_sources", "official_sources", "confidence", "source_refs_json",
            "tags_json", "demo",
        ]
        placeholders = ",".join("?" for _ in columns)
        updates = ",".join(f"{c}=excluded.{c}" for c in columns[1:])
        sql = f"INSERT INTO events ({','.join(columns)}) VALUES ({placeholders}) ON CONFLICT(event_id) DO UPDATE SET {updates}"
        values = []
        for item in rows:
            item = dict(item)
            item["source_refs_json"] = json.dumps(item.pop("source_refs", []), ensure_ascii=False)
            item["tags_json"] = json.dumps(item.pop("tags", []), ensure_ascii=False)
            item["demo"] = int(bool(item.get("demo", True)))
            values.append(tuple(item[c] for c in columns))
        with self.connect() as conn:
            conn.executemany(sql, values)
        return len(values)

    def rows(self, query: str, params: tuple = ()) -> list[dict]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def execute(self, query: str, params: tuple = ()) -> None:
        with self.connect() as conn:
            conn.execute(query, params)

    def upsert_articles(self, rows: list[dict]) -> dict[str, int]:
        if not rows:
            return {"seen": 0, "new": 0, "updated": 0}
        urls = [row["canonical_url"] for row in rows]
        existing: dict[str, str] = {}
        with self.connect() as conn:
            for start in range(0, len(urls), 500):
                batch = urls[start:start + 500]
                placeholders = ",".join("?" for _ in batch)
                for item in conn.execute(
                    f"SELECT canonical_url, content_hash FROM articles WHERE canonical_url IN ({placeholders})",
                    tuple(batch),
                ):
                    existing[item["canonical_url"]] = item["content_hash"]
            sql = """
            INSERT INTO articles (
              article_id,source_id,source_url,canonical_url,title_original,title_zh,
              summary_source,published_at_utc,language,rights_status,content_hash,
              fetched_at,relevance_score,topics_json,numbers_json,metadata_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(canonical_url) DO UPDATE SET
              source_id=excluded.source_id, source_url=excluded.source_url,
              title_original=excluded.title_original,
              summary_source=excluded.summary_source,
              published_at_utc=COALESCE(excluded.published_at_utc, articles.published_at_utc),
              language=excluded.language, rights_status=excluded.rights_status,
              content_hash=excluded.content_hash, fetched_at=excluded.fetched_at,
              relevance_score=excluded.relevance_score, topics_json=excluded.topics_json,
              numbers_json=excluded.numbers_json, metadata_json=excluded.metadata_json
            """
            conn.executemany(sql, [(
                row["article_id"], row["source_id"], row["source_url"], row["canonical_url"],
                row["title_original"], row.get("title_zh"), row.get("summary_source"),
                row.get("published_at_utc"), row.get("language"), row["rights_status"],
                row["content_hash"], row["fetched_at"], row.get("relevance_score", 0),
                json.dumps(row.get("topics", []), ensure_ascii=False),
                json.dumps(row.get("numbers", []), ensure_ascii=False),
                json.dumps(row.get("metadata", {}), ensure_ascii=False),
            ) for row in rows])
        new = sum(row["canonical_url"] not in existing for row in rows)
        updated = sum(
            row["canonical_url"] in existing and existing[row["canonical_url"]] != row["content_hash"]
            for row in rows
        )
        return {"seen": len(rows), "new": new, "updated": updated}

    def record_fetch_run(self, row: dict) -> None:
        self.execute(
            """INSERT INTO fetch_runs (
              run_id,source_id,endpoint,started_at,finished_at,status,http_status,
              content_type,response_bytes,items_seen,items_new,items_updated,
              error_class,error_message,quality_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["run_id"], row["source_id"], row["endpoint"], row["started_at"],
                row["finished_at"], row["status"], row.get("http_status"),
                row.get("content_type"), row.get("response_bytes", 0),
                row.get("items_seen", 0), row.get("items_new", 0), row.get("items_updated", 0),
                row.get("error_class"), row.get("error_message"),
                json.dumps(row.get("quality", {}), ensure_ascii=False),
            ),
        )

    def upsert_official_documents(self, rows: list[dict]) -> dict[str, int]:
        if not rows:
            return {"seen": 0, "new": 0, "updated": 0}
        keys = [(row["kind"], row["source_hash"]) for row in rows]
        existing: dict[tuple[str, str], str] = {}
        with self.connect() as conn:
            for kind, source_hash in keys:
                found = conn.execute(
                    "SELECT document_id, imported_at FROM official_documents WHERE kind=? AND source_hash=?",
                    (kind, source_hash),
                ).fetchone()
                if found:
                    existing[(kind, source_hash)] = found["document_id"]
            sql = """
            INSERT INTO official_documents (
              document_id,kind,party,title,symbol,body,session,cop_number,version,status,
              publication_date,language,detail_url,file_url,source_dataset,source_hash,
              imported_at,metadata_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(kind, source_hash) DO UPDATE SET
              party=excluded.party,title=excluded.title,symbol=excluded.symbol,
              body=excluded.body,session=excluded.session,cop_number=excluded.cop_number,
              version=excluded.version,status=excluded.status,
              publication_date=excluded.publication_date,language=excluded.language,
              detail_url=excluded.detail_url,file_url=excluded.file_url,
              source_dataset=excluded.source_dataset,imported_at=excluded.imported_at,
              metadata_json=excluded.metadata_json
            """
            conn.executemany(sql, [(
                row["document_id"], row["kind"], row.get("party"), row["title"],
                row.get("symbol"), row.get("body"), row.get("session"), row.get("cop_number"),
                row.get("version"), row.get("status"), row.get("publication_date"),
                row.get("language"), row.get("detail_url"), row.get("file_url"),
                row["source_dataset"], row["source_hash"], row["imported_at"],
                json.dumps(row.get("metadata", {}), ensure_ascii=False),
            ) for row in rows])
        new = sum(key not in existing for key in keys)
        return {"seen": len(rows), "new": new, "updated": len(rows) - new}

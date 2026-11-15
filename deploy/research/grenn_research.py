#!/usr/bin/env python3
"""GRENN research index and evidence API (2026-11-13) — the 功能更新1113 handover (COP31_research_handover:
research_store.py) fitted to this server. Standard library only.

What the handover asks for, and where it lives here
  index      one article_id / topic_code / country_code / date index for 国家立场 and 事件追踪. The handover's store
             imports JSONL packages into its own SQLite; this server already holds the corpus in the news database
             (/srv/grenn/newsdb/news.db: record_id, url, published_date, the 83 subcategory codes, country codes,
             organisation tags) with the full texts kept privately beside it (governance/current/texts/tNNNN.json).
             `sync` derives the index from it: metadata and labels only, no bodies.
  claims     reviewed positions (grenn_research_claim_schema.json). `claims --input reviewed.jsonl` accepts a line only when it names
             its reviewer and review date, its quote is exactly the article's text at [start, end) (Unicode character
             offsets, half-open) and the article carries the claim's topic. The check is mechanical: the reviewer
             still answers for speaker, actor, stance and reason. Kept in its own file, never rebuilt by `sync`.
  search     2026-11-14: with the second batch the history holds 435,071 articles and the site's text database could no
             longer hand its whole list to the browser (22 index parts, 42 MB compressed, on the first search). GET
             /api/research/search?q=&topic=&country=&year= answers twenty rows at a time in that list's own row
             format: every word of q must occur in title / Chinese title / excerpt / publisher (lower-cased substring
             match over a narrow table, a scan of well under a second), filters as for events.
  API        GET /api/research/topics | events | positions | search on 127.0.0.1 (nginx proxies /api/research/ with a rate
             limit, deploy/server/grenn-site.conf). Thirty items a page by default (100 at most), keyset cursor on
             (date, id) so same-day records are never skipped. There is no full-text endpoint: an item is title,
             date, publisher, link and labels; a position adds the reviewed quote.
  not done   nothing here extracts positions with a model, clusters reports into events, or imports the 待复核
             (review) batch: 事件追踪 is a report timeline, and positions exist only once a reviewer has filed them.

Commands
  sync [--force]         rebuild the index from news.db (atomic swap; unchanged database → nothing to do)
  claims --input FILE…   file reviewed claims (JSON lines); prints what was added, already there, or rejected
  serve [--port 8797]    the read-only API (grenn-research.service)
  status                 counts and paths

Paths (GRENN_NEWSDB, default /srv/grenn/newsdb): news.db, governance/current/texts/, research/index.sqlite,
research/claims.sqlite. grenn_research_taxonomy.json (the handover's taxonomy.json, 14 × 83) sits beside this file.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sqlite3
import sys
import threading
import time
from contextlib import closing
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HOME = Path(os.environ.get("GRENN_NEWSDB", "/srv/grenn/newsdb"))
NEWS_DB = HOME / "news.db"
TEXTS = HOME / "governance" / "current" / "texts"
STORE = HOME / "research"
INDEX = STORE / "index.sqlite"
CLAIMS = STORE / "claims.sqlite"
TAXONOMY = Path(__file__).resolve().parent / "grenn_research_taxonomy.json"

DEFAULT_LIMIT, MAX_LIMIT = 30, 100
NOTE = "事件页为报道时间线，不将共同议题自动合并为同一事件"
NOTE_EN = "The events view is a timeline of reports; reports on a shared topic are not merged into one event."
EMPTY = "证据不足：尚无已核验立场"
EMPTY_EN = "Insufficient evidence: no reviewed position yet"

# Negotiating groups and blocs among the database's organisation tags: an actor table of their own (a group's
# statement is never passed on to its members; the EU is one actor, not 27).
GROUPS = {
    "EU": ("欧盟", "European Union"), "G77": ("77国集团和中国", "G77 and China"), "AOSIS": ("小岛屿国家联盟", "AOSIS"),
    "BRICS": ("金砖国家", "BRICS"), "G20": ("二十国集团", "G20"), "G7": ("七国集团", "G7"),
    "AU": ("非洲联盟", "African Union"), "ASEAN": ("东盟", "ASEAN"), "PIF": ("太平洋岛国论坛", "Pacific Islands Forum"),
    "APEC": ("亚太经合组织", "APEC"), "SCO": ("上海合作组织", "SCO"),
}

# everyday Chinese names where the database carries the formal one (labels on chips and in the country list)
SHORT_ZH = {"CN": "中国", "PK": "巴基斯坦", "AE": "阿联酋", "VE": "委内瑞拉", "LA": "老挝", "KP": "朝鲜", "HK": "中国香港", "MO": "中国澳门",
            "CD": "刚果（金）", "BN": "文莱", "PS": "巴勒斯坦", "VA": "梵蒂冈", "DO": "多米尼加", "FM": "密克罗尼西亚联邦"}

RE_TOPIC = re.compile(r"G\d{2}(?:\.\d{2})?")
RE_COUNTRY = re.compile(r"[A-Z]{2}")
RE_GROUP = re.compile(r"[A-Z][A-Z0-9_]{1,15}")
RE_YEAR = re.compile(r"(?:19|20)\d{2}")
RE_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
CLAIM_FIELDS = ["id", "article_id", "actor", "topic", "stance", "reason", "quote", "start", "end", "speaker",
                "reviewer", "reviewed_at"]


# ---------------------------------------------------------------- taxonomy
@lru_cache(maxsize=1)
def taxonomy() -> dict:
    data = json.loads(TAXONOMY.read_text("utf-8"))
    parents = [{k: p[k] for k in ("code", "name_zh", "name_en")} for p in data["parents"]]
    subs = [{k: s[k] for k in ("code", "parent", "name_zh", "name_en")} for s in data["subcategories"]]
    return {"version": data.get("version"), "parents": parents, "subcategories": subs,
            "codes": {s["code"] for s in subs}, "parent_codes": {p["code"] for p in parents}}


# ---------------------------------------------------------------- index (sync)
SCHEMA = 2  # 2: the text database's search (articles' excerpt / primary topic / cohort / label lists, the hay table)
EXCERPT = 140  # characters of excerpt per row, as in the news database's search index
COHORTS = {"original_recovery": "o", "new_library": "n", "new_expansion_20261106": "x", "new_cloud_20261107": "x",
           "green-incremental-8h-v1": "x", "green-incremental-48h-v1": "x", "daily": "d"}  # others: "s", as grenn_newsdb.py
SEARCH_FIELDS = ["key", "date", "publisher", "title", "title_zh", "primary_topic", "topics", "countries", "excerpt",
                 "text", "url", "cohort", "research"]  # the rows of downloads/search-index.json, field for field
INDEX_SCHEMA = """
CREATE TABLE articles(id TEXT PRIMARY KEY, url TEXT, title TEXT, title_zh TEXT, title_en TEXT, date TEXT,
                      publisher TEXT, lang TEXT, fulltext INTEGER, text_ref TEXT,
                      excerpt TEXT, primary_topic TEXT, cohort TEXT, topics TEXT, countries TEXT) WITHOUT ROWID;
CREATE TABLE hay(date TEXT, id TEXT, text TEXT, PRIMARY KEY(date DESC, id)) WITHOUT ROWID;
CREATE TABLE labels(dimension TEXT, code TEXT, date TEXT, id TEXT,
                    PRIMARY KEY(dimension, code, date DESC, id)) WITHOUT ROWID;
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
"""
INDEX_AFTER = """
CREATE INDEX articles_date ON articles(date DESC, id);
CREATE INDEX labels_article ON labels(id, dimension, code);
"""


def _loads(text) -> list:
    try:
        value = json.loads(text) if text else []
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def _publisher(name, domain) -> str:
    domain = re.sub(r"^www\.", "", (domain or "").strip())
    name = (name or "").strip()
    if name and "API" not in name and re.sub(r"^www\.", "", name) != domain:
        return name
    return domain or name


def article_rows(news: sqlite3.Connection):
    """One (article, labels) pair for every dated record of the news database. Labels are the record's own:
    83-code topics (+ their parents), countries mentioned (alpha-2), organisation tags."""
    codes = taxonomy()["codes"]
    # an article's id is the key its text is stored under (document_key; a daily item that later arrived with its
    # full text keeps its own record_id in news.db) — the same key the site's text database uses
    query = """SELECT coalesce(document_key, record_id), url, published_date, title_original, title_zh, title_en, source_name, source_domain,
                      language, topics, country_codes, organization_tags, research_eligible, text_ref,
                      summary_zh, summary_source, primary_topic, cohort
               FROM news ORDER BY id"""
    for r in news.execute(query):
        ident, url, date = r[0], r[1] or "", r[2] or ""
        if not ident or not RE_DATE.fullmatch(date) or not re.match(r"https?://", url):
            continue
        listed = list(dict.fromkeys(t for t in _loads(r[9]) if isinstance(t, str) and t in codes))  # the primary topic first
        topics = sorted(listed)
        countries, names = [], {}
        for c in _loads(r[10]):
            code = c.get("alpha2") if isinstance(c, dict) else c if isinstance(c, str) else None
            if code and RE_COUNTRY.fullmatch(code) and code not in countries:
                countries.append(code)
                if isinstance(c, dict):
                    names[code] = (c.get("name_zh") or code, c.get("name_en") or code)
        orgs = sorted({o for o in _loads(r[11]) if isinstance(o, str) and RE_GROUP.fullmatch(o)})
        fulltext = 1 if (r[12] and r[13]) else 0
        blurb = re.sub(r"\s+", " ", r[14] or r[15] or "").strip()
        blurb = blurb[:EXCERPT] + ("…" if len(blurb) > EXCERPT else "")
        article = (ident, url, (r[3] or "").strip(), r[4], r[5], date, _publisher(r[6], r[7]), r[8], fulltext,
                   r[13] if fulltext else None, blurb, r[16] if r[16] in codes else "", COHORTS.get(r[17] or "daily", "s"),
                   ",".join(listed), ",".join(countries))
        labels = ([("topic", t) for t in topics] + [("parent", p) for p in sorted({t[:3] for t in topics})]
                  + [("country", c) for c in countries] + [("org", o) for o in orgs])
        yield article, labels, names


def fingerprint(news: sqlite3.Connection) -> str:
    row = news.execute("SELECT count(*), max(id), max(updated_at), sum(length(topics)), sum(length(country_codes)), "
                       "sum(length(organization_tags)) FROM news").fetchone()
    return json.dumps(list(row))


def read_meta(path: Path = None) -> dict:
    path = path or INDEX
    if not path.exists():
        return {}
    with closing(open_ro(path)) as conn:
        return {k: json.loads(v) for k, v in conn.execute("SELECT key, value FROM meta")}


def sync(force: bool = False) -> dict:
    """Rebuild index.sqlite from news.db and swap it in. Running it again on an unchanged database adds nothing."""
    STORE.mkdir(parents=True, exist_ok=True)
    news = sqlite3.connect(_uri(NEWS_DB), uri=True)
    try:
        mark = fingerprint(news)
        old = read_meta()
        if not force and old.get("fingerprint") == mark and old.get("taxonomy") == taxonomy()["version"] and old.get("schema") == SCHEMA:
            return {"changed": False, "articles": old.get("total", 0), "added": 0, "removed": 0}
        before = set()
        if INDEX.exists():
            with closing(open_ro(INDEX)) as conn:
                before = {r[0] for r in conn.execute("SELECT id FROM articles")}
        tmp = STORE / f".index-{os.getpid()}.sqlite"
        tmp.unlink(missing_ok=True)
        out = sqlite3.connect(tmp)
        try:
            out.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + INDEX_SCHEMA)
            names, ids, n_labels, batch_a, batch_l = {}, set(), 0, [], []

            def flush():
                out.executemany("INSERT OR IGNORE INTO articles VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch_a)
                out.executemany("INSERT OR IGNORE INTO labels VALUES(?,?,?,?)", batch_l)
                # what a search reads: title, Chinese title, excerpt and publisher, lower-cased, in date order
                out.executemany("INSERT OR IGNORE INTO hay VALUES(?,?,?)",
                                [(a[5], a[0], " ".join(filter(None, (a[2], a[3], a[10], a[6]))).lower()) for a in batch_a])
                batch_a.clear(); batch_l.clear()
            for article, labels, seen in article_rows(news):
                if article[0] in ids:
                    continue
                ids.add(article[0])
                names.update(seen)
                batch_a.append(article)
                batch_l.extend((dim, code, article[5], article[0]) for dim, code in labels)
                n_labels += len(labels)
                if len(batch_a) >= 5000:
                    flush()
            flush()
            out.executescript(INDEX_AFTER)
            counts = {dim: dict(out.execute("SELECT code, count(*) FROM labels WHERE dimension=? GROUP BY code", (dim,)))
                      for dim in ("topic", "parent", "country", "org")}
            years = dict(out.execute("SELECT substr(date,1,4), count(*) FROM articles GROUP BY 1 ORDER BY 1"))
            span = out.execute("SELECT min(date), max(date), count(*), sum(fulltext) FROM articles").fetchone()
            meta = {"fingerprint": mark, "schema": SCHEMA, "taxonomy": taxonomy()["version"], "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "total": span[2], "fulltext": span[3] or 0, "range": [span[0], span[1]], "labels": n_labels, "years": years,
                    "counts": counts["topic"], "parent_counts": counts["parent"], "sizes": counts,
                    "countries": sorted(({"code": c, "name_zh": SHORT_ZH.get(c) or names.get(c, (c, c))[0], "name_en": names.get(c, (c, c))[1], "reports": n}
                                         for c, n in counts["country"].items()), key=lambda x: -x["reports"]),
                    "groups": [{"code": g, "name_zh": GROUPS[g][0], "name_en": GROUPS[g][1], "reports": counts["org"].get(g, 0)}
                               for g in GROUPS if counts["org"].get(g)]}
            out.executemany("INSERT INTO meta VALUES(?,?)", [(k, json.dumps(v, ensure_ascii=False)) for k, v in meta.items()])
            out.commit()
            out.execute("ANALYZE")
            out.commit()
        finally:
            out.close()
        os.chmod(tmp, 0o644)
        os.replace(tmp, INDEX)
        return {"changed": True, "articles": len(ids), "added": len(ids - before), "removed": len(before - ids), "labels": n_labels}
    finally:
        news.close()


# ---------------------------------------------------------------- reviewed claims
CLAIMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS claims(id TEXT PRIMARY KEY, article_id TEXT NOT NULL, actor TEXT NOT NULL, topic TEXT NOT NULL,
    stance TEXT NOT NULL, reason TEXT, quote TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL,
    speaker TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL,
    title TEXT, url TEXT, date TEXT, added_at TEXT);
CREATE INDEX IF NOT EXISTS claims_lookup ON claims(topic, actor, date DESC, id);
CREATE INDEX IF NOT EXISTS claims_date ON claims(date DESC, id);
"""


def _uri(path: Path) -> str:
    return Path(path).resolve().as_uri() + "?mode=ro"


def open_ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(_uri(path), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def open_claims() -> sqlite3.Connection:
    STORE.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CLAIMS)
    conn.executescript(CLAIMS_SCHEMA)  # rollback journal: the API opens the file read-only
    return conn


def article_body(text_ref: str, article_id: str):
    """The stored text of one article (private chunk files; read for the offset check only, never served)."""
    if not text_ref or not re.fullmatch(r"t\d{4,}", text_ref):
        return None
    path = TEXTS / f"{text_ref}.json"
    if not path.exists():
        return None
    entry = json.loads(path.read_text("utf-8")).get(article_id)
    return entry.get("x") if isinstance(entry, dict) else None


def add_claim(claims: sqlite3.Connection, index: sqlite3.Connection, x: dict) -> bool:
    """File one reviewed claim. True = added, False = the same claim was already there. ValueError = rejected."""
    if not isinstance(x, dict) or any(k not in x for k in CLAIM_FIELDS):
        raise ValueError("Missing reviewed attribution")
    if not all(isinstance(x[k], str) and x[k].strip() for k in ("id", "article_id", "actor", "topic", "stance", "speaker", "reviewer", "reviewed_at")):
        raise ValueError("Missing reviewed attribution")
    if not isinstance(x["quote"], str) or not isinstance(x["reason"], (str, type(None))):
        raise ValueError("Missing reviewed attribution")
    if x["topic"] not in taxonomy()["codes"]:
        raise ValueError("Unknown topic code")
    if not RE_GROUP.fullmatch(x["actor"]):
        raise ValueError("Invalid actor code")
    row = index.execute("SELECT id, title, url, date, text_ref FROM articles WHERE id=?", (x["article_id"],)).fetchone()
    if not row:
        raise ValueError("Unknown evidence article")
    body = article_body(row["text_ref"], row["id"])
    if body is None:
        raise ValueError("Evidence article has no stored text")
    a, b = x["start"], x["end"]
    if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, int) or not isinstance(b, int) \
            or not 0 <= a < b <= len(body) or body[a:b] != x["quote"]:
        raise ValueError("Evidence offsets mismatch")
    if not index.execute("SELECT 1 FROM labels WHERE id=? AND dimension='topic' AND code=?", (row["id"], x["topic"])).fetchone():
        raise ValueError("Unknown article topic")
    values = [x[k] if k != "reason" else (x[k] or "") for k in CLAIM_FIELDS]
    old = claims.execute(f"SELECT {','.join(CLAIM_FIELDS)} FROM claims WHERE id=?", (x["id"],)).fetchone()
    if old:
        if list(old) == values:
            return False
        raise ValueError("Claim id already filed with different content")  # earlier positions are kept, not overwritten
    claims.execute("INSERT INTO claims VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   values + [row["title"], row["url"], row["date"], time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())])
    claims.commit()
    return True


def import_claims(paths: list) -> dict:
    if not INDEX.exists():
        raise SystemExit("no index yet: run `sync` first")
    report = {"added": 0, "already_filed": 0, "rejected": []}
    claims, index = open_claims(), open_ro(INDEX)
    try:
        for file in paths:
            for number, line in enumerate(Path(file).read_text("utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    report["added" if add_claim(claims, index, item) else "already_filed"] += 1
                except ValueError as error:  # json.JSONDecodeError is a ValueError
                    report["rejected"].append({"file": str(file), "line": number, "error": str(error)})
    finally:
        claims.close(); index.close()
    return report


# ---------------------------------------------------------------- queries
def _cursor(value: str):
    try:
        date, ident = json.loads(base64.urlsafe_b64decode(value.encode()).decode())
        if not isinstance(date, str) or not isinstance(ident, str) or not RE_DATE.fullmatch(date) or len(ident) > 200:
            raise ValueError
        return date, ident
    except Exception as error:
        raise ValueError("Invalid cursor") from error


def _next(rows: list, limit: int, key: str):
    if len(rows) < limit:
        return None
    return base64.urlsafe_b64encode(json.dumps([rows[-1]["date"], rows[-1][key]]).encode()).decode()


def clean(topic="", country="", group="", year="", before="", limit=DEFAULT_LIMIT, cursor="") -> dict:
    """Validated filters; anything malformed is a ValueError (→ 400)."""
    for value, pattern, name in ((topic, RE_TOPIC, "topic"), (country, RE_COUNTRY, "country"), (group, RE_GROUP, "group"),
                                 (year, RE_YEAR, "year"), (before, RE_DATE, "before")):
        if value and not pattern.fullmatch(value):
            raise ValueError(f"Invalid {name}")
    try:
        limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid limit") from error
    return {"topic": topic, "country": country, "group": group, "year": year, "before": before, "limit": limit,
            "cursor": _cursor(cursor) if cursor else None}


def _dimensions(f: dict) -> list:
    dims = []
    if f["topic"]:
        dims.append(("topic" if "." in f["topic"] else "parent", f["topic"]))
    if f["country"]:
        dims.append(("country", f["country"]))
    if f["group"]:
        dims.append(("org", f["group"]))
    return dims


def _keys(dims: list, where: list, params: list) -> tuple:
    """SQL giving the (date, id) keys of the articles that carry every label in `dims`, newest first. Each label is
    one ordered range of the labels table; several are intersected by merging those ranges (no per-row lookups)."""
    extra = "".join(f" AND {w}" for w in where)
    if not dims:
        return "SELECT date, id FROM articles" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY date DESC, id", list(params)
    sides, values = [], []
    for dim in dims:
        sides.append("SELECT date, id FROM labels WHERE dimension=? AND code=?" + extra)
        values.extend([*dim, *params])
    return " INTERSECT ".join(sides) + " ORDER BY date DESC, id", values


def events(index: sqlite3.Connection, f: dict) -> dict:
    """The report timeline: newest first, one row per article, never merged into "events"."""
    dims = _dimensions(f)
    where, params = [], []
    if f["year"]:
        where.append("date >= ? AND date < ?"); params.extend([f["year"], str(int(f["year"]) + 1)])
    if f["before"]:
        where.append("date < ?"); params.append(f["before"])
    if f["cursor"]:
        date, ident = f["cursor"]
        where.append("date <= ? AND (date < ? OR id > ?)"); params.extend([date, date, ident])
    sql, values = _keys(dims, where, params)
    keys = [r[1] for r in index.execute(sql + " LIMIT ?", values + [f["limit"]])]
    rows = []
    if keys:
        marks = ",".join("?" * len(keys))
        found = {r["id"]: dict(r) for r in index.execute(
            f"SELECT id, title, title_zh, title_en, date, url, publisher, lang, fulltext FROM articles WHERE id IN ({marks})", keys)}
        tags = {}  # the labels of the page's articles, for the chips on each row
        for ident, dim, code in index.execute(f"SELECT id, dimension, code FROM labels WHERE id IN ({marks}) AND dimension != 'parent'", keys):
            tags.setdefault(ident, {}).setdefault(dim, []).append(code)
        for key in keys:
            r, mine = found[key], tags.get(key, {})
            r["fulltext"] = bool(r["fulltext"])
            r["topics"], r["countries"], r["groups"] = mine.get("topic", []), mine.get("country", []), [g for g in mine.get("org", []) if g in GROUPS]
            rows.append(r)
    result = {"items": rows, "next_cursor": _next(rows, f["limit"], "id"), "mode": "events", "empty_reason": None,
              "note": NOTE, "note_en": NOTE_EN}
    if not f["cursor"]:  # first page: how many reports the filter holds, and their spread over the years
        years = year_counts(index, dims)
        result["years"] = years
        result["total"] = years.get(f["year"], 0) if f["year"] else sum(years.values())
    return result


_years = {}  # (index version, labels) → reports per year: the same for every year, page and cursor of one selection


def year_counts(index: sqlite3.Connection, dims: list) -> dict:
    key = (_stamp()[0], tuple(dims))
    with _cache_lock:
        if key in _years:
            return _years[key]
    if not dims:
        counted = dict(index.execute("SELECT substr(date,1,4), count(*) FROM articles GROUP BY 1 ORDER BY 1"))
    elif len(dims) == 1:
        counted = dict(index.execute("SELECT substr(date,1,4), count(*) FROM labels WHERE dimension=? AND code=? GROUP BY 1 ORDER BY 1", dims[0]))
    else:  # two large labels (a category × the United States: ~0.4 million keys merged) take about a second, once
        sql, values = _keys(dims, [], [])
        counted = dict(index.execute(f"SELECT substr(date,1,4), count(*) FROM ({sql}) GROUP BY 1 ORDER BY 1", values))
    with _cache_lock:
        if len(_years) > 2000:
            _years.clear()
        _years[key] = counted
    return counted


def words_of(q: str) -> list:
    """The words of a search: lower-cased, at most six, the whole query at most 80 characters."""
    q = " ".join(str(q or "").split())
    if len(q) > 80:
        raise ValueError("Invalid q")
    return list(dict.fromkeys(q.lower().split()))[:6]


_sizes, _totals = {}, {}
HAY_FIRST = 20000  # a label on more articles than this is checked after the words, not walked row by row


def _size(dim: tuple) -> int:
    """How many articles carry a label (from the index's own counts), to start a search from the rarest one."""
    stamp = _stamp()[0]
    with _cache_lock:
        if _sizes.get("stamp") != stamp:
            _sizes.clear()
            _sizes.update(stamp=stamp, sizes=read_meta().get("sizes", {}))
    return _sizes["sizes"].get(dim[0], {}).get(dim[1], 0)


def search(index: sqlite3.Connection, f: dict, words: list) -> dict:
    """The text database's list: rows in downloads/search-index.json's format, newest first, twenty a page."""
    dims = sorted(_dimensions(f), key=_size)
    where, params = [], []
    carries = "EXISTS(SELECT 1 FROM labels x WHERE x.dimension=? AND x.code=? AND x.date={0}.date AND x.id={0}.id)"
    if words and (not dims or _size(dims[0]) > HAY_FIRST):
        # words, and no label rare enough to start from: read the search text in date order (one sequential pass)
        # and look the labels up only for the rows that hold the words
        key, source = "h", "hay h"
        for word in words:
            where.append("instr(h.text, ?) > 0"); params.append(word)
        for dim in dims:
            where.append(carries.format("h")); params.extend(dim)
    elif dims and (words or len(dims) == 1):  # from the rarest label's own date-ordered range
        key, source = "k", "labels k" + (" JOIN hay h ON h.date = k.date AND h.id = k.id" if words else "")
        where.append("k.dimension=? AND k.code=?"); params.extend(dims[0])
        for dim in dims[1:]:
            where.append(carries.format("k")); params.extend(dim)
        for word in words:
            where.append("instr(h.text, ?) > 0"); params.append(word)
    elif dims:
        key, source = "k", None  # several labels, no words: the merged ranges, as events()
    else:
        key, source = "h", "hay h"
    counted, count_params = list(where), list(params)
    if f["year"]:
        where.append(f"{key}.date >= ? AND {key}.date < ?"); params.extend([f["year"], str(int(f["year"]) + 1)])
    if f["cursor"]:
        date, ident = f["cursor"]
        where.append(f"{key}.date <= ? AND ({key}.date < ? OR {key}.id > ?)"); params.extend([date, date, ident])
    if source:
        sql = f"SELECT {key}.date, {key}.id FROM {source}" + (" WHERE " + " AND ".join(where) if where else "") + f" ORDER BY {key}.date DESC, {key}.id LIMIT ?"
    else:
        extra, values = [], []
        if f["year"]:
            extra.append("date >= ? AND date < ?"); values.extend([f["year"], str(int(f["year"]) + 1)])
        if f["cursor"]:
            extra.append("date <= ? AND (date < ? OR id > ?)"); values.extend([f["cursor"][0], f["cursor"][0], f["cursor"][1]])
        sql, params = _keys(dims, extra, values)
        sql += " LIMIT ?"
    keys = [r[1] for r in index.execute(sql, params + [f["limit"]])]
    rows = []
    if keys:
        marks = ",".join("?" * len(keys))
        found = {r[0]: r for r in index.execute(
            "SELECT id, date, publisher, title, title_zh, primary_topic, topics, countries, excerpt, text_ref, url, cohort, fulltext "
            f"FROM articles WHERE id IN ({marks})", keys)}
        for k in keys:
            r = found[k]
            rows.append([r[0], r[1], r[2] or "", r[3] or "", r[4] or "", r[5] or "", r[6] or "", r[7] or "", r[8] or "",
                         r[9] or "", "" if r[9] else r[10], r[11] or "s", 1 if r[12] else 0])
    result = {"fields": SEARCH_FIELDS, "rows": rows, "mode": "search",
              "next_cursor": base64.urlsafe_b64encode(json.dumps([rows[-1][1], rows[-1][0]]).encode()).decode() if len(rows) == f["limit"] else None}
    if not f["cursor"]:  # first page: how many records the search holds
        if not words:
            years = year_counts(index, _dimensions(f))
            result["total"] = years.get(f["year"], 0) if f["year"] else sum(years.values())
        else:
            mark = (_stamp()[0], tuple(dims), f["year"], tuple(words))
            with _cache_lock:
                total = _totals.get(mark)
            if total is None:
                if f["year"]:
                    counted.append(f"{key}.date >= ? AND {key}.date < ?"); count_params.extend([f["year"], str(int(f["year"]) + 1)])
                total = index.execute(f"SELECT count(*) FROM {source} WHERE " + " AND ".join(counted), count_params).fetchone()[0]
                with _cache_lock:
                    if len(_totals) > 4000:
                        _totals.clear()
                    _totals[mark] = total
            result["total"] = total
    return result


def positions(index: sqlite3.Connection, f: dict) -> dict:
    """Reviewed positions only. No claim on file → an empty list and the reason, never a guess."""
    rows = []
    if CLAIMS.exists():
        index.execute("ATTACH DATABASE ? AS reviewed", (_uri(CLAIMS),))
        try:
            where, params = [], []
            if f["topic"]:
                where.append("c.topic=?" if "." in f["topic"] else "substr(c.topic,1,3)=?"); params.append(f["topic"])
            actor = f["country"] or f["group"]
            if actor:
                where.append("c.actor=?"); params.append(actor)
            if f["year"]:
                where.append("c.date >= ? AND c.date < ?"); params.extend([f["year"], str(int(f["year"]) + 1)])
            if f["before"]:
                where.append("c.date < ?"); params.append(f["before"])
            if f["cursor"]:
                date, ident = f["cursor"]
                where.append("c.date <= ? AND (c.date < ? OR c.id > ?)"); params.extend([date, date, ident])
            sql = ("SELECT c.article_id AS id, coalesce(a.title, c.title) AS title, c.date, coalesce(a.url, c.url) AS url, "
                   "a.publisher, c.id AS cursor_id, c.actor, c.topic, c.stance, c.reason, c.quote, c.start, c.end, c.speaker, "
                   "c.reviewer, c.reviewed_at FROM reviewed.claims c LEFT JOIN articles a ON a.id = c.article_id"
                   + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY c.date DESC, c.id LIMIT ?")
            rows = [dict(r) for r in index.execute(sql, params + [f["limit"]])]
        finally:
            index.execute("DETACH DATABASE reviewed")
    return {"items": rows, "next_cursor": _next(rows, f["limit"], "cursor_id"), "mode": "positions",
            "empty_reason": None if rows else EMPTY, "empty_reason_en": None if rows else EMPTY_EN,
            "note": NOTE, "note_en": NOTE_EN}


def topics() -> dict:
    """The 14 × 83 dictionary with, for every code, the reports that can be searched and the reviewed positions on
    file — two different numbers, never added together."""
    meta, tax = read_meta(), taxonomy()
    reviewed, actors = {}, {}
    if CLAIMS.exists():
        with closing(open_ro(CLAIMS)) as conn:
            reviewed = dict(conn.execute("SELECT topic, count(*) FROM claims GROUP BY topic"))
            actors = dict(conn.execute("SELECT actor, count(*) FROM claims GROUP BY actor"))
    counts, parents = meta.get("counts", {}), meta.get("parent_counts", {})
    return {
        "version": tax["version"],
        "parents": [{**p, "reports": parents.get(p["code"], 0),
                     "positions": sum(n for code, n in reviewed.items() if code.startswith(p["code"] + "."))} for p in tax["parents"]],
        "subcategories": [{**s, "reports": counts.get(s["code"], 0), "positions": reviewed.get(s["code"], 0)} for s in tax["subcategories"]],
        "counts": {s["code"]: counts.get(s["code"], 0) for s in tax["subcategories"]},
        "position_counts": reviewed, "position_actors": actors,
        "countries": meta.get("countries", []), "groups": meta.get("groups", []),
        "total": meta.get("total", 0), "fulltext": meta.get("fulltext", 0), "range": meta.get("range"), "years": meta.get("years", {}),
        "built_at": meta.get("built_at"), "page_size": DEFAULT_LIMIT, "note": NOTE, "note_en": NOTE_EN,
    }


# ---------------------------------------------------------------- HTTP
ROUTES = {"/api/research/topics", "/api/research/events", "/api/research/positions", "/api/research/search"}
_cache, _cache_lock = {}, threading.Lock()


def _stamp() -> tuple:
    def mtime(path):
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return 0
    return mtime(INDEX), mtime(CLAIMS)


def answer(path: str, query: dict) -> bytes:
    """The JSON body for one request. Raises ValueError for a bad query, FileNotFoundError before the first sync."""
    if not INDEX.exists():
        raise FileNotFoundError("index")
    arg = lambda name: (query.get(name) or [""])[0].strip()
    if path.endswith("/topics"):
        key = ("topics",)
    else:
        f = clean(arg("topic"), arg("country"), arg("group"), arg("year"), arg("before"), arg("limit") or DEFAULT_LIMIT, arg("cursor"))
        words = words_of(arg("q")) if path.endswith("/search") else []
        key = (path, json.dumps(f, sort_keys=True), tuple(words))
    stamp = _stamp()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] == stamp:
            return hit[1]
    if path.endswith("/topics"):
        data = topics()
    else:
        index = open_ro(INDEX)
        try:
            deadline = time.monotonic() + 8
            index.set_progress_handler(lambda: time.monotonic() > deadline, 20000)  # a runaway query is cut off
            data = events(index, f) if path.endswith("/events") else search(index, f, words) if path.endswith("/search") else positions(index, f)
        finally:
            index.close()
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    with _cache_lock:
        if len(_cache) > 400:
            _cache.clear()
        _cache[key] = (stamp, body)
    return body


class Handler(BaseHTTPRequestHandler):
    server_version = "grenn-research"
    sys_version = ""
    timeout = 20

    def _send(self, status: int, body: bytes, cache: str = "no-store"):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path not in ROUTES:
            self._send(404, b'{"error":"Not found"}'); return
        try:
            body = answer(url.path, parse_qs(url.query, max_num_fields=12))
            self._send(200, body, "public, max-age=300" if url.path.endswith("/topics") else "no-store")
        except FileNotFoundError:
            self._send(503, b'{"error":"Index not built"}')
        except (ValueError, sqlite3.Error):
            self._send(400, b'{"error":"Invalid query"}')

    def log_request(self, code="-", size="-"):  # journald: failures only
        if not str(getattr(code, "value", code)).startswith(("2", "3")):
            super().log_request(code, size)


def keep_warm(every: int = 120):
    """Read the search text through every two minutes (and at once after a new index): a search scans that table in
    one pass, a third of a second while it is in the page cache, several seconds from a cold disk."""
    seen = None
    while True:
        try:
            stamp = _stamp()[0]
            if stamp:
                with closing(open_ro(INDEX)) as conn:
                    conn.execute("SELECT sum(length(text)) FROM hay").fetchone()
            seen = stamp
        except sqlite3.Error:
            pass
        for _ in range(every // 5):  # a new index is noticed within five seconds
            time.sleep(5)
            if _stamp()[0] != seen:
                break


def serve(port: int):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # loopback only: nginx is the public face
    server.daemon_threads = True
    threading.Thread(target=keep_warm, daemon=True).start()
    print(f"grenn-research: http://127.0.0.1:{port}/api/research/ (index {INDEX})", flush=True)
    server.serve_forever()


def status() -> dict:
    meta = read_meta()
    filed = 0
    if CLAIMS.exists():
        with closing(open_ro(CLAIMS)) as conn:
            filed = conn.execute("SELECT count(*) FROM claims").fetchone()[0]
    return {"index": str(INDEX), "built_at": meta.get("built_at"), "articles": meta.get("total", 0), "with_fulltext": meta.get("fulltext", 0),
            "labels": meta.get("labels", 0), "range": meta.get("range"), "topics_with_reports": sum(1 for n in meta.get("counts", {}).values() if n),
            "countries": len(meta.get("countries", [])), "groups": [g["code"] for g in meta.get("groups", [])],
            "claims": str(CLAIMS), "reviewed_positions": filed, "taxonomy": taxonomy()["version"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="GRENN research index and evidence API")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("sync", help="rebuild the index from the news database")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("claims", help="file reviewed claims (JSON lines)")
    p.add_argument("--input", nargs="+", required=True)
    p = sub.add_parser("serve", help="the read-only API on 127.0.0.1")
    p.add_argument("--port", type=int, default=8797)
    sub.add_parser("status", help="counts and paths")
    args = parser.parse_args(argv)
    if args.command == "sync":
        print(json.dumps(sync(args.force), ensure_ascii=False))
    elif args.command == "claims":
        report = import_claims(args.input)
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 1 if report["rejected"] else 0
    elif args.command == "serve":
        serve(args.port)
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

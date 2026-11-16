"""Tests for grenn_research.py — the handover's test_store.py cases (repeat import adds nothing, same-day paging,
no evidence → no position, misplaced quotes rejected) on this server's layout, plus the API's own guarantees.
Run: python -m unittest test_grenn_research  (from this folder; standard library only)."""
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import grenn_research as r

NEWS_SCHEMA = """CREATE TABLE news(id INTEGER PRIMARY KEY, record_id TEXT UNIQUE, document_key TEXT, url TEXT UNIQUE, published_date TEXT,
  title_original TEXT, title_zh TEXT, title_en TEXT, source_name TEXT, source_domain TEXT, language TEXT, topics TEXT,
  country_codes TEXT, organization_tags TEXT, research_eligible INTEGER, text_ref TEXT, updated_at TEXT,
  summary_zh TEXT, summary_source TEXT, primary_topic TEXT, cohort TEXT)"""
TEXT = "Minister Li said the government supports scaling up climate finance for adaptation."


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        home = Path(self.tmp.name)
        self.saved = {k: getattr(r, k) for k in ("HOME", "NEWS_DB", "TEXTS", "STORE", "INDEX", "CLAIMS")}
        r.HOME, r.NEWS_DB, r.TEXTS, r.STORE = home, home / "news.db", home / "texts", home / "research"
        r.INDEX, r.CLAIMS = r.STORE / "index.sqlite", r.STORE / "claims.sqlite"
        r.TEXTS.mkdir()
        r._cache.clear(); r._years.clear(); r._totals.clear(); r._sizes.clear()
        self.news = sqlite3.connect(r.NEWS_DB)
        self.news.execute(NEWS_SCHEMA)
        self.chunk = {}

    def tearDown(self):
        self.news.close()
        for k, v in self.saved.items():
            setattr(r, k, v)
        self.tmp.cleanup()

    def add(self, n, date="2025-01-01", topics=("G06.01",), countries=("CN",), orgs=(), eligible=1, text=TEXT):
        ident = f"doc_{n}"
        self.news.execute("INSERT INTO news(record_id,url,published_date,title_original,source_name,source_domain,language,topics,"
                          "country_codes,organization_tags,research_eligible,text_ref,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (ident, f"https://example.org/{n}", date, f"Climate finance {n}", "example.org", "example.org", "en",
                           json.dumps(list(topics)), json.dumps([{"alpha2": c, "name_zh": c, "name_en": c} for c in countries]),
                           json.dumps(list(orgs)), eligible, "t0000" if eligible else None, "2026-11-13"))
        self.news.commit()
        if eligible:
            self.chunk[ident] = {"t": f"Climate finance {n}", "u": f"https://example.org/{n}", "x": text}
            (r.TEXTS / "t0000.json").write_text(json.dumps(self.chunk), "utf-8")
        return ident

    def find(self, mode="events", **filters):
        index = r.open_ro(r.INDEX)
        try:
            return (r.events if mode == "events" else r.positions)(index, r.clean(**filters))
        finally:
            index.close()

    def claim(self, **changes):
        base = {"id": "c1", "article_id": "doc_0", "actor": "CN", "topic": "G06.01", "stance": "支持", "reason": "",
                "quote": TEXT[17:], "start": 17, "end": len(TEXT), "speaker": "Minister Li, named in the report",
                "reviewer": "tester", "reviewed_at": "2026-11-13"}
        base.update(changes)
        return base

    def file(self, claim):
        claims, index = r.open_claims(), r.open_ro(r.INDEX)
        try:
            return r.add_claim(claims, index, claim)
        finally:
            claims.close(); index.close()

    # --- the handover's acceptance cases
    def test_repeat_sync_adds_nothing(self):
        self.add(0); self.add(1)
        first = r.sync()
        self.assertEqual((first["articles"], first["added"]), (2, 2))
        self.assertEqual(r.sync(), {"changed": False, "articles": 2, "added": 0, "removed": 0})
        again = r.sync(force=True)
        self.assertEqual((again["articles"], again["added"], again["removed"]), (2, 0, 0))

    def test_increment_adds_only_the_new(self):
        self.add(0); r.sync()
        self.add(1)
        self.assertEqual(r.sync()["added"], 1)
        self.assertEqual(len(self.find()["items"]), 2)  # the old record is still found

    def test_same_day_cursor_drops_nothing(self):
        for n in range(7):
            self.add(n)
        r.sync()
        seen, cursor = [], ""
        while True:
            page = self.find(limit=2, cursor=cursor)
            seen += [item["id"] for item in page["items"]]
            cursor = page["next_cursor"]
            if not cursor:
                break
        self.assertEqual(len(seen), 7)
        self.assertEqual(len(set(seen)), 7)

    def test_no_evidence_no_position(self):
        self.add(0); r.sync()
        result = self.find("positions")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["empty_reason"], r.EMPTY)

    def test_claim_offsets(self):
        self.add(0); r.sync()
        self.assertTrue(self.file(self.claim()))
        self.assertEqual(len(self.find("positions", country="CN")["items"]), 1)
        self.assertEqual(self.find("positions", country="US")["items"], [])
        with self.assertRaises(ValueError):
            self.file(self.claim(id="c2", quote="fabricated"))
        with self.assertRaises(ValueError):  # right words, wrong place
            self.file(self.claim(id="c3", start=16, end=len(TEXT) - 1))

    def test_unreviewed_claim_rejected(self):
        self.add(0); r.sync()
        for missing in ("reviewer", "reviewed_at", "speaker"):
            with self.assertRaises(ValueError):
                self.file(self.claim(**{missing: ""}))
        incomplete = self.claim(); del incomplete["reviewer"]
        with self.assertRaises(ValueError):
            self.file(incomplete)

    def test_claim_needs_the_articles_topic_and_text(self):
        self.add(0); self.add(1, eligible=0); r.sync()
        with self.assertRaises(ValueError):
            self.file(self.claim(topic="G07.01"))  # the article is not labelled with it
        with self.assertRaises(ValueError):
            self.file(self.claim(topic="G99.99"))
        with self.assertRaises(ValueError):
            self.file(self.claim(article_id="doc_1"))  # metadata-only record: nothing to check the quote against
        with self.assertRaises(ValueError):
            self.file(self.claim(article_id="doc_404"))

    def test_claims_are_idempotent_and_never_overwritten(self):
        self.add(0); r.sync()
        self.assertTrue(self.file(self.claim()))
        self.assertFalse(self.file(self.claim()))
        with self.assertRaises(ValueError):
            self.file(self.claim(stance="反对"))
        self.assertEqual(self.find("positions")["items"][0]["stance"], "支持")

    def test_claims_survive_a_rebuild(self):
        self.add(0); r.sync(); self.file(self.claim())
        self.add(1); r.sync(force=True)
        self.assertEqual(len(self.find("positions", topic="G06.01")["items"]), 1)
        self.assertEqual(len(self.find("positions", topic="G06")["items"]), 1)
        self.assertEqual(r.topics()["position_counts"], {"G06.01": 1})

    def test_article_id_is_the_key_its_text_is_stored_under(self):
        # a daily item that later arrived with its full text keeps its own record_id; document_key names the text
        ident = self.add(0)
        self.news.execute("UPDATE news SET record_id='article_daily', document_key=? WHERE record_id=?", (ident, ident))
        self.news.commit()
        r.sync()
        self.assertEqual(self.find()["items"][0]["id"], ident)
        self.assertTrue(self.file(self.claim()))

    # --- the text database's search (2026-11-14)
    def seek(self, q="", **filters):
        index = r.open_ro(r.INDEX)
        try:
            return r.search(index, r.clean(**filters), r.words_of(q))
        finally:
            index.close()

    def test_search_rows_and_words(self):
        self.add(0, date="2024-05-01", topics=("G06.01", "G04.02"), countries=("CN", "IN"))
        self.add(1, date="2025-03-01", topics=("G06.02",), countries=("US",))
        self.add(2, date="2025-03-02", topics=("G07.01",), countries=("CN",), eligible=0)
        for n, title, zh, blurb, primary, cohort in ((0, "Loss and Damage Fund opens", None, "Ministers agreed on the FUND's first grants. " * 6, "G04.02", "new_cloud_20261107"),
                                                     (1, "Green bonds grow", "绿色债券增长", "A market note", "G06.02", "original_recovery"),
                                                     (2, "Carbon market daily", None, None, None, None)):
            self.news.execute("UPDATE news SET title_original=?, title_zh=?, summary_source=?, primary_topic=?, cohort=?, topics=? WHERE record_id=?",
                              (title, zh, blurb, primary, cohort, json.dumps([primary] + ["G06.01"] if n == 0 else [primary] if primary else ["G07.01"]), f"doc_{n}"))
        self.news.commit()
        r.sync()
        ids = lambda *a, **k: [row[0] for row in self.seek(*a, **k)["rows"]]
        self.assertEqual(ids(), ["doc_2", "doc_1", "doc_0"])
        self.assertEqual(self.seek()["total"], 3)
        self.assertEqual(ids("fund"), ["doc_0"])                      # case-insensitive, title or excerpt
        self.assertEqual(ids("DAMAGE grants"), ["doc_0"])             # every word must occur
        self.assertEqual(ids("damage bonds"), [])
        self.assertEqual(ids("债券"), ["doc_1"])                       # the Chinese title
        self.assertEqual(ids("example.org"), ["doc_2", "doc_1", "doc_0"])  # the publisher
        self.assertEqual(ids("market", country="CN"), ["doc_2"])
        self.assertEqual(ids("market", topic="G06"), ["doc_1"])
        self.assertEqual(ids(topic="G06", country="CN"), ["doc_0"])
        self.assertEqual(ids(year="2025"), ["doc_2", "doc_1"])
        self.assertEqual((self.seek("market")["total"], self.seek("market", year="2024")["total"], self.seek(topic="G06")["total"]), (2, 0, 2))
        row = dict(zip(r.SEARCH_FIELDS, self.seek("fund")["rows"][0]))
        self.assertEqual((row["key"], row["date"], row["publisher"], row["primary_topic"], row["topics"], row["countries"], row["text"], row["url"], row["cohort"], row["research"]),
                         ("doc_0", "2024-05-01", "example.org", "G04.02", "G04.02,G06.01", "CN,IN", "t0000", "", "x", 1))
        self.assertTrue(row["excerpt"].endswith("…") and len(row["excerpt"]) == r.EXCERPT + 1)
        daily = dict(zip(r.SEARCH_FIELDS, self.seek("daily")["rows"][0]))
        self.assertEqual((daily["text"], daily["url"], daily["cohort"], daily["research"]), ("", "https://example.org/2", "d", 0))

    def test_search_pages_do_not_drop_same_day_rows(self):
        for n in range(7):
            self.add(n)
        r.sync()
        seen, cursor = [], ""
        while True:
            page = self.seek("finance", limit=3, cursor=cursor)
            seen += [row[0] for row in page["rows"]]
            cursor = page["next_cursor"]
            if not cursor:
                break
        self.assertEqual(sorted(seen), [f"doc_{n}" for n in range(7)])

    def test_search_refuses_long_queries_and_serves_no_body(self):
        with self.assertRaises(ValueError):
            r.words_of("x" * 81)
        self.assertEqual(r.words_of("  Loss   AND loss damage a b c d e "), ["loss", "and", "damage", "a", "b", "c"])
        self.add(0); r.sync()
        body = r.answer("/api/research/search", {"q": ["government"]}).decode()
        self.assertEqual(json.loads(body)["total"], 0)  # the stored text is not what is searched
        self.assertNotIn(TEXT, r.answer("/api/research/search", {"q": ["finance"]}).decode())

    # --- filters and the dictionary
    def test_filters(self):
        self.add(0, date="2024-05-01", topics=("G06.01", "G04.02"), countries=("CN", "IN"), orgs=("G77", "UN"))
        self.add(1, date="2025-03-01", topics=("G06.02",), countries=("US",))
        self.add(2, date="2025-03-02", topics=("G07.01",), countries=("CN",), eligible=0)
        r.sync()
        ids = lambda **f: [i["id"] for i in self.find(**f)["items"]]
        self.assertEqual(ids(), ["doc_2", "doc_1", "doc_0"])
        self.assertEqual(ids(topic="G06.01"), ["doc_0"])
        self.assertEqual(ids(topic="G06"), ["doc_1", "doc_0"])
        self.assertEqual(ids(country="CN"), ["doc_2", "doc_0"])
        self.assertEqual(ids(topic="G06", country="US"), ["doc_1"])
        self.assertEqual(ids(group="G77"), ["doc_0"])
        self.assertEqual(ids(year="2025"), ["doc_2", "doc_1"])
        self.assertEqual(ids(before="2025-03-02"), ["doc_1", "doc_0"])
        first = self.find(topic="G06")
        self.assertEqual((first["total"], first["years"]), (2, {"2024": 1, "2025": 1}))
        self.assertEqual(self.find(topic="G06", year="2024")["total"], 1)
        item = self.find(topic="G06.01")["items"][0]
        self.assertEqual((item["topics"], item["countries"], item["groups"], item["fulltext"]), (["G04.02", "G06.01"], ["CN", "IN"], ["G77"], True))
        self.assertFalse(self.find(topic="G07.01")["items"][0]["fulltext"])

    def test_all_83_topics_listed_empty_ones_at_zero(self):
        self.add(0); r.sync()
        data = r.topics()
        self.assertEqual((len(data["parents"]), len(data["subcategories"]), len(data["counts"])), (14, 83, 83))
        self.assertEqual(data["counts"]["G06.01"], 1)
        self.assertEqual(sum(data["counts"].values()), 1)
        self.assertEqual([p["reports"] for p in data["parents"] if p["code"] == "G06"], [1])
        self.assertEqual(data["countries"][0]["code"], "CN")
        self.assertNotIn("evidence_regex", data["subcategories"][0])

    def test_bad_queries_are_refused(self):
        for bad in ({"topic": "G6"}, {"topic": "x' OR 1=1"}, {"country": "china"}, {"year": "25"}, {"before": "2025"},
                    {"cursor": "nonsense"}, {"limit": "many"}, {"group": "g77"}):
            with self.assertRaises(ValueError):
                r.clean(**bad)
        self.assertEqual(r.clean(limit="5000")["limit"], 100)
        self.assertEqual(r.clean(limit="-3")["limit"], 1)

    def test_no_body_leaves_the_server(self):
        self.add(0); r.sync(); self.file(self.claim())
        for path in sorted(r.ROUTES):
            body = r.answer(path, {}).decode()
            self.assertNotIn(TEXT, body)
            self.assertNotIn("text_ref", body)
        self.assertIn(TEXT[17:], r.answer("/api/research/positions", {}).decode())  # the reviewed quote, and only that

    def test_http(self):
        self.add(0); r.sync()
        server = ThreadingHTTPServer(("127.0.0.1", 0), r.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urllib.request.urlopen(base + "/api/research/events?topic=G06.01&country=CN&limit=30") as response:
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(len(json.load(response)["items"]), 1)
            for path, code in (("/api/research/fulltext", 404), ("/", 404), ("/api/research/events?topic=bad", 400)):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(base + path)
                self.assertEqual(caught.exception.code, code)
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(urllib.request.Request(base + "/api/research/events", data=b"{}", method="POST"))
            self.assertEqual(caught.exception.code, 501)
        finally:
            server.shutdown(); server.server_close()


if __name__ == "__main__":
    unittest.main()

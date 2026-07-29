from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path

from climate_agent.archive import quality_result, update_archive, validate_public_payload
from climate_agent.briefing import dashboard_payload, render_markdown, save_brief, select_daily_window, select_latest_day, select_latest_week
from climate_agent.cli import ROOT, bootstrap
from climate_agent.collector import NormalizedArticle, parse_feed, parse_gdelt
from climate_agent.db import Database
from climate_agent.delivery import build_push_message
from climate_agent.exporter import export_static_site
from climate_agent.official_data import parse_ndc_csv
from climate_agent.pipeline import event_priority, normalize_url
from climate_agent.source_health import source_is_due, update_source_health
from climate_agent.sync import P0_SOURCE_IDS, _source_scope_match
from climate_agent.translation import detect_places, source_balanced_rows


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "test.db")
        bootstrap(self.db)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def seed_publishable_article(self, *, article_id: str = "article_quality", url: str = "https://example.org/climate") -> None:
        self.db.upsert_articles([{
            "article_id": article_id, "source_id": "INT001", "source_url": url,
            "canonical_url": url, "title_original": "Verified climate finance update",
            "title_zh": "气候资金机制出现新的可核验进展",
            "summary_source": "A documented climate finance mechanism was updated.",
            "published_at_utc": "2026-07-16T00:00:00+00:00", "language": "en",
            "rights_status": "metadata_only", "content_hash": f"hash-{article_id}",
            "fetched_at": "2026-07-16T01:00:00+00:00", "relevance_score": 82,
            "topics": ["气候资金"], "numbers": [], "metadata": {
                "summary_zh": "来源文件显示气候资金机制已经更新，涉及后续执行安排；具体金额和责任仍需回到原始文件逐项核验。",
                "theme_zh": "气候资金", "importance_zh": "可能影响后续资金谈判与履约安排。",
                "translation_status": "human_reviewed", "fact_status": "source_claim_unverified",
                "places": [{"name_zh": "全球", "lon": 20, "lat": 10}],
            },
        }])

    def test_bootstrap_is_idempotent(self) -> None:
        bootstrap(self.db)
        self.assertEqual(self.db.rows("SELECT COUNT(*) AS n FROM sources")[0]["n"], 53)
        self.assertEqual(self.db.rows("SELECT COUNT(*) AS n FROM events")[0]["n"], 3)
        self.assertEqual(self.db.rows("SELECT COUNT(*) AS n FROM articles WHERE article_id LIKE 'curated_%'")[0]["n"], 8)

    def test_dashboard_reconciles_source_counts(self) -> None:
        payload = dashboard_payload(self.db)
        self.assertEqual(payload["metrics"]["source_total"], 53)
        self.assertEqual(payload["metrics"]["source_enabled"], 32)
        self.assertGreaterEqual(len(payload["intelligence"]), 1)
        self.assertGreaterEqual(len({item["source_id"] for item in payload["intelligence"]}), 3)

    def test_brief_is_versioned(self) -> None:
        payload = dashboard_payload(self.db)
        first, second = save_brief(self.db, payload), save_brief(self.db, payload)
        self.assertEqual((first["version"], second["version"]), (1, 2))
        markdown = render_markdown(payload)
        self.assertIn("中国发布“十五五”可再生能源发展规划", markdown)
        self.assertIn("数据边界", markdown)

    def test_url_normalization(self) -> None:
        self.assertEqual(
            normalize_url("HTTPS://Example.com//news/?utm_source=x&id=2#top"),
            "https://example.com/news?id=2",
        )

    def test_priority_is_bounded(self) -> None:
        event = {"negotiation_relevance": 100, "china_relevance": 100, "urgency": 100, "independent_sources": 20, "official_sources": 10, "confidence": 1.0}
        self.assertEqual(event_priority(event), 100)

    def test_rss_and_atom_contract(self) -> None:
        rss = b"""<rss><channel><item><title>Climate policy update</title><link>https://example.org/a?utm_medium=rss</link><pubDate>Thu, 16 Jul 2026 10:00:00 GMT</pubDate><description>Numbers and facts.</description></item></channel></rss>"""
        articles = parse_feed(rss, "TEST", "en")
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].canonical_url, "https://example.org/a")
        self.assertEqual(articles[0].rights_status, "metadata_only")

    def test_unep_nonstandard_feed_contract(self) -> None:
        payload = b'''<rss><channel><item><title>UNEP update</title><path>https://www.unep.org/story</path><field_synopsis><![CDATA[<p>Verified synopsis.</p>]]></field_synopsis><created><![CDATA[<time datetime="2026-07-16T04:26:47+03:00">date</time>]]></created></item></channel></rss>'''
        article = parse_feed(payload, "OFF006", "en")[0]
        self.assertEqual(article.canonical_url, "https://www.unep.org/story")
        self.assertEqual(article.summary_from_source, "Verified synopsis.")
        self.assertTrue(article.published_at_utc.endswith("+00:00"))

    def test_gdelt_contract(self) -> None:
        payload = b'{"articles":[{"url":"https://example.org/a?utm_source=x","title":"Climate finance update","seendate":"20260716T100000Z","language":"English","domain":"example.org"}]}'
        article = parse_gdelt(payload)[0]
        self.assertEqual(article.canonical_url, "https://example.org/a")
        self.assertEqual(article.extraction_method, "gdelt_doc_api")

    def test_regional_sources_have_strict_scope_gates(self) -> None:
        china = NormalizedArticle(
            article_id="c", source_id="API005", source_url="https://www.news.cn/a",
            canonical_url="https://www.news.cn/a", title="China unveils renewable energy plan",
            published_at_raw=None, published_at_utc=None, summary_from_source=None,
            language="en", content_hash="c",
        )
        off_domain = NormalizedArticle(
            article_id="x", source_id="API005", source_url="https://example.org/a",
            canonical_url="https://example.org/a", title="China climate plan",
            published_at_raw=None, published_at_utc=None, summary_from_source=None,
            language="en", content_hash="x",
        )
        mars = NormalizedArticle(
            article_id="m", source_id="OFF014", source_url="https://science.nasa.gov/mars",
            canonical_url="https://science.nasa.gov/mars", title="NASA observes the surface of Mars",
            published_at_raw=None, published_at_utc=None, summary_from_source=None,
            language="en", content_hash="m",
        )
        self.assertTrue(_source_scope_match(china, "API005"))
        self.assertFalse(_source_scope_match(off_domain, "API005"))
        self.assertFalse(_source_scope_match(mars, "OFF014"))
        earth = NormalizedArticle(
            article_id="e", source_id="OFF014", source_url="https://science.nasa.gov/earth/wildfires/a",
            canonical_url="https://science.nasa.gov/earth/wildfires/a", title="Wildfire smoke blankets Oregon",
            published_at_raw=None, published_at_utc=None, summary_from_source=None,
            language="en", content_hash="e",
        )
        self.assertTrue(_source_scope_match(earth, "OFF014"))
        self.assertTrue({"INT008", "INT009", "INT020", "OFF014", "API005"}.issubset(P0_SOURCE_IDS))

    def test_ndc_import_rejects_non_unfccc_and_is_version_aware(self) -> None:
        payload = b"code,party,title,fileType,language,version,status,submissionDate,encodedAbsUrl,originalFilename\nAAA,Alpha,Alpha NDC,NDC,English,1,Active,2025-01-02,https://unfccc.int/a.pdf,a.pdf\nBBB,Beta,Beta NDC,NDC,English,2,Active,2025-01-02,https://example.org/b.pdf,b.pdf\n"
        rows, quality = parse_ndc_csv(payload, cutoff_year=2016)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["version"], "1")
        self.assertEqual(quality["rejection_reasons"]["non_unfccc_url"], 1)

    def test_article_upsert_is_idempotent(self) -> None:
        row = {
            "article_id": "article_a", "source_id": "INT001", "source_url": "https://example.org/a",
            "canonical_url": "https://example.org/a", "title_original": "Climate update", "title_zh": None,
            "summary_source": None, "published_at_utc": "2026-07-16T00:00:00+00:00", "language": "en",
            "rights_status": "metadata_only", "content_hash": "abc", "fetched_at": "2026-07-16T01:00:00+00:00",
            "relevance_score": 80, "topics": ["UNFCCC进程"], "numbers": [], "metadata": {},
        }
        first, second = self.db.upsert_articles([row]), self.db.upsert_articles([row])
        self.assertEqual(first["new"], 1)
        self.assertEqual(second, {"seen": 1, "new": 0, "updated": 0})

    def test_place_detection_supports_map_markers(self) -> None:
        places = detect_places("Hospitals in Europe face heat while Texas recovers from floods")
        self.assertEqual({place["name_zh"] for place in places}, {"欧洲", "美国得州"})
        chinese_places = detect_places("中国和美国发布新的气候政策")
        self.assertEqual({place["name_zh"] for place in chinese_places}, {"中国", "美国"})

    def test_static_export_is_self_contained(self) -> None:
        self.seed_publishable_article()
        static_dir = Path(self.temp.name) / "static"
        output_dir = Path(self.temp.name) / "dist"
        shutil.copytree(ROOT / "static", static_dir)
        result = export_static_site(self.db, static_dir, output_dir)
        payload = json.loads((output_dir / "data" / "dashboard.json").read_text(encoding="utf-8"))
        self.assertTrue((output_dir / "index.html").exists())
        self.assertTrue((output_dir / ".nojekyll").exists())
        self.assertTrue((output_dir / "assets" / "countries-110m.json").exists())
        self.assertTrue((output_dir / "data" / "news_archive.json").exists())
        pdf = (output_dir / "data" / "daily_brief.pdf").read_bytes()
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"/BaseFont /Times-Roman", pdf)
        self.assertIn(b"/F1", pdf)
        self.assertIn("map_events_week", payload)
        self.assertEqual(result["quality_gate"], "passed")
        self.assertEqual(result["articles"], len(payload["intelligence"]))

    def test_push_message_uses_only_user_facing_intelligence(self) -> None:
        payload = {
            "meta": {"date": "2026-07-17"},
            "intelligence": [{
                "title_zh": "中文气候标题", "summary_zh": "这是完整的中文概要。",
                "theme_zh": "气候资金", "why_zh": "影响后续谈判立场。",
            }],
        }
        message = build_push_message(payload, "https://example.org", max_items=3)
        self.assertIn("中文气候标题", message)
        self.assertIn("这是完整的中文概要", message)
        self.assertIn("https://example.org/", message)
        self.assertNotIn("P0", message)

    def test_public_homepage_prioritizes_map_and_information(self) -> None:
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("十年政策脉络", html)
        self.assertNotIn("版本，而不是文件堆积", html)
        self.assertNotIn("智能信息分子", html)
        self.assertNotIn("质量方法", html)
        self.assertNotIn('id="qualityFilter"', html)
        self.assertNotIn("A · 人工校编", html)
        self.assertNotIn("B · AI 编译待复核", html)
        self.assertIn('id="mapPlaceList"', html)
        self.assertIn('data-map-period="today"', html)
        self.assertIn('data-map-period="week"', html)
        self.assertIn('id="assistant"', html)
        app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function planQuestion", app)
        self.assertIn("function comparisonHtml", app)
        self.assertNotIn("function answerRecords", app)
        self.assertNotIn("function latestDayItems", app)
        self.assertIn("items.slice(0, 10)", app)
        self.assertIn("下载今日简报", html)
        self.assertNotIn("下载数据 JSON", html)
        self.assertIn('id="database"', html)
        self.assertIn("CLIMATETEXT-3000", html)
        self.assertLess(html.index('id="map"'), html.index('class="hero"'))

    def test_archive_gate_deduplicates_and_enforces_limit(self) -> None:
        self.seed_publishable_article()
        item = dashboard_payload(self.db)["intelligence"][0]
        self.assertTrue(quality_result(item)["passed"])
        path = Path(self.temp.name) / "news_archive.json"
        first = update_archive(path, [item], limit=1)
        second = update_archive(path, [item], limit=1)
        self.assertEqual(first["total"], 1)
        self.assertEqual(second["total"], 1)
        self.assertEqual(second["statistics"]["added"], 0)
        self.assertEqual(validate_public_payload({"intelligence": [item]}, second), [])

    def test_workflow_runs_daily_with_models_and_writeback(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "30 23 * * *"', workflow)
        self.assertIn("models: read", workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("data/news_archive.json", workflow)
        self.assertIn("data/source_health.json", workflow)
        self.assertIn("CLIMATE_TRANSLATION_LIMIT", workflow)

    def test_latest_day_and_week_use_beijing_calendar(self) -> None:
        rows = [
            {"published_at": "2026-07-20T15:59:00+00:00", "source_id": "A", "relevance_score": 90},
            {"published_at": "2026-07-20T16:01:00+00:00", "source_id": "B", "relevance_score": 80},
            {"published_at": "2026-07-13T16:01:00+00:00", "source_id": "C", "relevance_score": 70},
        ]
        self.assertEqual(select_latest_day(rows), [rows[1]])
        self.assertEqual({row["source_id"] for row in select_latest_week(rows)}, {"A", "B"})

    def test_daily_window_skips_partial_day_and_balances_complete_day(self) -> None:
        rows = [
            {
                "article_id": "partial-a", "source_id": "API", "source_name": "GDELT",
                "title_original": "TCMA launches five engines toward net zero 2050",
                "published_at": "2026-07-29T03:30:00+00:00", "relevance_score": 50, "places": [],
            },
            {
                "article_id": "partial-b", "source_id": "API", "source_name": "GDELT",
                "title_original": "Wire service - TCMA launches five engines toward net zero 2050",
                "published_at": "2026-07-29T03:00:00+00:00", "relevance_score": 50, "places": [],
            },
        ]
        places = [
            {"name_zh": "欧洲", "lon": 10, "lat": 51},
            {"name_zh": "中国", "lon": 105, "lat": 35},
            {"name_zh": "非洲", "lon": 22, "lat": 2},
            {"name_zh": "美国", "lon": -100, "lat": 39},
            {"name_zh": "澳大利亚", "lon": 134, "lat": -25},
        ]
        for index in range(10):
            rows.append({
                "article_id": f"complete-{index}",
                "source_id": f"S{index % 5}",
                "source_name": f"Source {index % 5}",
                "title_original": f"Distinct climate policy event number {index}",
                "published_at": "2026-07-28T02:00:00+00:00",
                "relevance_score": 90 - index,
                "places": [places[index % len(places)]],
            })
        selected = select_daily_window(rows, limit=10)
        source_counts = Counter(row["source_name"] for row in selected)
        self.assertEqual(len(selected), 10)
        self.assertEqual({date.fromisoformat(row["published_at"][:10]) for row in selected}, {date(2026, 7, 28)})
        self.assertLessEqual(max(source_counts.values()), 2)
        self.assertEqual(sum(bool(row["places"]) for row in selected), 10)

    def test_translation_queue_round_robins_sources(self) -> None:
        rows = [
            {"article_id": "a1", "source_id": "A"},
            {"article_id": "a2", "source_id": "A"},
            {"article_id": "b1", "source_id": "B"},
            {"article_id": "c1", "source_id": "C"},
        ]
        selected = source_balanced_rows(rows, 3)
        self.assertEqual([row["source_id"] for row in selected], ["A", "B", "C"])

    def test_translation_queue_round_robins_regions_before_sources(self) -> None:
        rows = [
            {"article_id": "a1", "source_id": "A", "source_region": "Europe"},
            {"article_id": "a2", "source_id": "A", "source_region": "Europe"},
            {"article_id": "b1", "source_id": "B", "source_region": "Europe"},
            {"article_id": "c1", "source_id": "C", "source_region": "Africa"},
            {"article_id": "d1", "source_id": "D", "source_region": "Asia"},
        ]
        selected = source_balanced_rows(rows, 5)
        self.assertEqual([row["source_id"] for row in selected[:3]], ["A", "C", "D"])
        self.assertEqual({row["source_id"] for row in selected}, {"A", "B", "C", "D"})

    def test_source_health_quarantines_only_after_repeated_failures(self) -> None:
        state = {"sources": {}}
        for _ in range(6):
            update_source_health(state, [{"source_id": "X", "status": "failed", "error": "403"}])
        self.assertTrue(source_is_due(state, "X"))
        update_source_health(state, [{"source_id": "X", "status": "failed", "error": "403"}])
        self.assertFalse(source_is_due(state, "X"))
        update_source_health(state, [{"source_id": "X", "status": "success", "error": None}])
        self.assertTrue(source_is_due(state, "X"))


if __name__ == "__main__":
    unittest.main()

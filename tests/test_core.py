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
from climate_agent.corpus_analytics import build_corpus_analytics
from climate_agent.db import Database
from climate_agent.delivery import build_push_message
from climate_agent.exporter import export_static_site
from climate_agent.historical_backfill import article_to_historical_record, upsert_historical_records
from climate_agent.official_data import parse_ndc_csv
from climate_agent.pipeline import event_priority, normalize_url
from climate_agent.source_health import source_is_due, update_source_health
from climate_agent.sync import P0_SOURCE_IDS, _analyse, _google_news_url, _source_scope_match
from climate_agent.translation import _fallback_translation, detect_places, source_balanced_rows


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
        self.assertEqual(payload["metrics"]["source_enabled"], 33)
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
        self.assertTrue({"INT008", "INT009", "INT020", "OFF014", "API005", "API004"}.issubset(P0_SOURCE_IDS))

    def test_daily_gdelt_climate_signals_pass_without_admitting_moon_news(self) -> None:
        heat = NormalizedArticle(
            article_id="h", source_id="API001", source_url="https://example.org/heat",
            canonical_url="https://example.org/heat",
            title="Heat wave brings record-breaking temps and heightened wildfire risk to Western US",
            published_at_raw="20260802T040000Z", published_at_utc="2026-08-02T04:00:00+00:00",
            summary_from_source=None, language="English", content_hash="h",
        )
        moon = NormalizedArticle(
            article_id="m", source_id="INT014", source_url="https://example.org/moon",
            canonical_url="https://example.org/moon",
            title="Buck Moon lights up Devon and Cornwall skies",
            published_at_raw="20260802T040000Z", published_at_utc="2026-08-02T04:00:00+00:00",
            summary_from_source="The July full moon is expected to peak at 15:36 BST.",
            language="English", content_hash="m",
        )
        self.assertGreaterEqual(_analyse(heat, 4)["score"], 45)
        self.assertLess(_analyse(moon, 5)["score"], 45)

    def test_google_news_fallback_is_climate_scoped(self) -> None:
        url = _google_news_url("https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}")
        self.assertIn("news.google.com/rss/search", url)
        self.assertNotIn("{query}", url)
        climate = NormalizedArticle(
            article_id="g", source_id="API004", source_url="https://news.google.com/rss",
            canonical_url="https://example.org/climate", title="Climate summit calls for faster clean energy finance",
            published_at_raw=None, published_at_utc=None, summary_from_source=None,
            language="en", content_hash="g",
        )
        moon = NormalizedArticle(
            article_id="m", source_id="API004", source_url="https://news.google.com/rss",
            canonical_url="https://example.org/moon", title="Buck Moon lights up Devon and Cornwall skies",
            published_at_raw=None, published_at_utc=None, summary_from_source=None,
            language="en", content_hash="m",
        )
        entertainment = NormalizedArticle(
            article_id="s", source_id="API004", source_url="https://news.google.com/rss",
            canonical_url="https://example.org/sesame",
            title="Sesame Workshop launches extreme weather special for families",
            published_at_raw=None, published_at_utc=None, summary_from_source=None,
            language="en", content_hash="s",
        )
        self.assertTrue(_source_scope_match(climate, "API004"))
        self.assertFalse(_source_scope_match(moon, "API004"))
        self.assertFalse(_source_scope_match(entertainment, "API004"))

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

    def test_article_upsert_preserves_translation_metadata(self) -> None:
        original = {
            "article_id": "article_a", "source_id": "INT001", "source_url": "https://example.org/a",
            "canonical_url": "https://example.org/a", "title_original": "Climate update", "title_zh": None,
            "summary_source": None, "published_at_utc": "2026-07-16T00:00:00+00:00", "language": "en",
            "rights_status": "metadata_only", "content_hash": "abc", "fetched_at": "2026-07-16T01:00:00+00:00",
            "relevance_score": 80, "topics": ["UNFCCC杩涚▼"], "numbers": [],
            "metadata": {
                "summary_zh": "这是一条已经翻译完成的中文气候摘要，重复同步时不能被清空。",
                "places": [{"name_zh": "美国", "lon": -100, "lat": 39}],
                "translation_status": "model_generated_needs_review",
            },
        }
        refreshed = dict(original)
        refreshed["content_hash"] = "def"
        refreshed["metadata"] = {"why_zh": "fresh fetch"}
        self.db.upsert_articles([original])
        self.db.upsert_articles([refreshed])
        metadata = json.loads(self.db.rows("SELECT metadata_json FROM articles WHERE canonical_url=?", ("https://example.org/a",))[0]["metadata_json"])
        self.assertEqual(metadata["summary_zh"], original["metadata"]["summary_zh"])
        self.assertEqual(metadata["places"][0]["name_zh"], "美国")
        self.assertEqual(metadata["why_zh"], "fresh fetch")

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
        (Path(self.temp.name) / "climate_text_corpus.jsonl").write_text(
            '{"record_id":"hist_1","published_date":"2026-01-01","topics":["能源与排放"],"country_tags":["中国"],"continent_tags":["Asia"],"source_domain":"example.org"}\n',
            encoding="utf-8",
        )
        (Path(self.temp.name) / "climate_text_corpus.manifest.json").write_text('{"records":1}', encoding="utf-8")
        result = export_static_site(self.db, static_dir, output_dir)
        payload = json.loads((output_dir / "data" / "dashboard.json").read_text(encoding="utf-8"))
        self.assertTrue((output_dir / "index.html").exists())
        self.assertTrue((output_dir / ".nojekyll").exists())
        self.assertTrue((output_dir / "assets" / "countries-110m.json").exists())
        self.assertTrue((output_dir / "data" / "news_archive.json").exists())
        self.assertTrue((output_dir / "data" / "climate_text_corpus.jsonl").exists())
        self.assertTrue((output_dir / "data" / "climate_text_corpus.manifest.json").exists())
        analytics = json.loads((output_dir / "data" / "corpus_analytics.json").read_text(encoding="utf-8"))
        self.assertEqual(analytics["records"], 1)
        self.assertEqual(analytics["top_topics"][0]["name"], "能源与排放")
        self.assertEqual(result["corpus_analytics_records"], 1)
        self.assertTrue((output_dir / "data" / "energy_archive.json").exists())
        self.assertTrue((output_dir / "data" / "energy_dashboard.json").exists())
        self.assertTrue((output_dir / "data" / "energy_corpus_analytics.json").exists())
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
        self.assertIn('id="analytics"', html)
        self.assertIn('id="monthlyTrendChart"', html)
        self.assertIn('id="countryTopicHeatmap"', html)
        self.assertIn('id="modeToggle"', html)
        self.assertIn("切换到能源技术", html)
        self.assertIn("global_climate_analysis_report_latest.html", html)
        self.assertIn('id="assistant"', html)
        app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function renderAnalytics", app)
        self.assertIn("corpus_analytics.json", app)
        self.assertIn("energy_dashboard.json", app)
        self.assertIn("function activateMode", app)
        self.assertIn("function planQuestion", app)
        self.assertIn("function comparisonHtml", app)
        self.assertNotIn("function answerRecords", app)
        self.assertNotIn("function latestDayItems", app)
        self.assertIn("items.slice(0, 10)", app)
        self.assertIn("下载今日简报", html)
        self.assertNotIn("下载数据 JSON", html)
        self.assertIn('id="database"', html)
        self.assertIn("CLIMATETEXT-8760", html)
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

    def test_daily_window_skips_partial_day_and_never_mixes_dates(self) -> None:
        rows = [
            {
                "article_id": "latest-a", "source_id": "API", "source_name": "GDELT",
                "title_original": "TCMA launches five engines toward net zero 2050",
                "published_at": "2026-07-29T03:30:00+00:00", "relevance_score": 50, "places": [],
            },
            {
                "article_id": "latest-b", "source_id": "API", "source_name": "GDELT",
                "title_original": "Wire service - TCMA launches five engines toward net zero 2050",
                "published_at": "2026-07-29T03:00:00+00:00", "relevance_score": 50, "places": [],
            },
        ]
        place_cycle = [
            {"name_zh": "欧洲", "lon": 10, "lat": 51},
            {"name_zh": "中国", "lon": 105, "lat": 35},
            {"name_zh": "非洲", "lon": 22, "lat": 2},
            {"name_zh": "美国", "lon": -100, "lat": 39},
            {"name_zh": "澳大利亚", "lon": 134, "lat": -25},
        ]
        for index in range(10):
            rows.append({
                "article_id": f"older-{index}",
                "source_id": f"S{index % 5}",
                "source_name": f"Source {index % 5}",
                "title_original": f"Distinct climate policy event number {index}",
                "published_at": "2026-07-28T02:00:00+00:00",
                "relevance_score": 90 - index,
                "places": [place_cycle[index % len(place_cycle)]],
            })
        selected = select_daily_window(rows, limit=10)
        source_counts = Counter(row["source_name"] for row in selected)
        self.assertEqual(len(selected), 10)
        self.assertNotIn("latest-a", {row["article_id"] for row in selected})
        self.assertNotIn("latest-b", {row["article_id"] for row in selected})
        self.assertEqual({date.fromisoformat(row["published_at"][:10]) for row in selected}, {date(2026, 7, 28)})
        self.assertLessEqual(max(source_counts.values()), 2)
        self.assertEqual(sum(bool(row["places"]) for row in selected), 10)

    def test_daily_window_uses_fresh_day_and_backfills_when_quality_is_enough(self) -> None:
        rows = []
        for index in range(4):
            rows.append({
                "article_id": f"fresh-{index}",
                "source_id": f"F{index % 2}",
                "source_name": f"Fresh {index % 2}",
                "title_original": f"Fresh climate policy signal {index}",
                "published_at": "2026-08-02T02:00:00+00:00",
                "relevance_score": 88 - index,
                "places": [{"name_zh": "加勒比地区" if index == 0 else "美国", "lon": -75, "lat": 18}],
            })
        for index in range(10):
            rows.append({
                "article_id": f"recent-{index}",
                "source_id": f"S{index % 5}",
                "source_name": f"Source {index % 5}",
                "title_original": f"Recent climate policy event {index}",
                "published_at": "2026-08-01T02:00:00+00:00",
                "relevance_score": 82 - index,
                "places": [{"name_zh": "欧洲", "lon": 10, "lat": 51}],
            })
        selected = select_daily_window(rows, limit=10)
        selected_ids = {row["article_id"] for row in selected}
        self.assertTrue({"fresh-0", "fresh-1", "fresh-2", "fresh-3"}.issubset(selected_ids))
        self.assertEqual(len(selected), 10)
        self.assertEqual(max(date.fromisoformat(row["published_at"][:10]) for row in selected), date(2026, 8, 2))

    def test_place_detection_uses_boundaries_and_caribbean(self) -> None:
        places = detect_places("Caribbean countries face £43 billion in climate disaster losses")
        self.assertEqual(places[0]["name_zh"], "加勒比地区")
        self.assertNotIn("中国", {place["name_zh"] for place in detect_places("China-backed transition minerals projects")})

    def test_archive_repairs_existing_caribbean_geocoding(self) -> None:
        path = Path(self.temp.name) / "archive.json"
        path.write_text(json.dumps({
            "schema_version": "1.0",
            "records": [{
                "record_id": "r1",
                "article_id": "r1",
                "canonical_url": "https://example.org/caribbean-climate-losses",
                "title_original": "Caribbean bears brunt of climate-fuelled damage",
                "title_zh": "加勒比地区遭受气候灾害损失",
                "summary_zh": "研究显示加勒比国家遭受严重气候灾害损失。",
                "source_name": "Example",
                "source_id": "S",
                "authority": 5,
                "relevance_score": 80,
                "published_at": "2026-07-29T11:00:00+00:00",
                "places": [{"name_zh": "中国", "lon": 105, "lat": 35}],
                "quality": {"passed": True, "tier": "B", "score": 80},
                "molecule": {"geo_atoms": ["中国"]},
            }],
            "total": 1,
        }), encoding="utf-8")
        archive = update_archive(path, [], limit=8760)
        self.assertEqual(archive["records"][0]["places"][0]["name_zh"], "加勒比地区")
        self.assertEqual(archive["records"][0]["molecule"]["geo_atoms"], ["加勒比地区"])

    def test_archive_prunes_low_value_news_misfires(self) -> None:
        path = Path(self.temp.name) / "archive.json"
        path.write_text(json.dumps({
            "schema_version": "1.0",
            "records": [{
                "record_id": "r1",
                "article_id": "r1",
                "canonical_url": "https://example.org/sesame",
                "title_original": "Sesame Workshop launches extreme weather special",
                "title_zh": "极端天气风险出现新动态",
                "summary_zh": "来源标题显示该信息涉及极端天气，但更像娱乐宣传，不应进入外交情报。",
                "source_name": "Google News RSS Search",
                "source_id": "API004",
                "authority": 3,
                "relevance_score": 54,
                "published_at": "2026-08-02T02:29:00+00:00",
                "places": [],
                "quality": {"passed": True, "tier": "B", "score": 46},
            }],
            "total": 1,
        }), encoding="utf-8")
        archive = update_archive(path, [], limit=8760)
        self.assertEqual(archive["total"], 0)

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

    def test_translation_fallback_does_not_fabricate_english_title(self) -> None:
        item = _fallback_translation({
            "title_original": "Heat wave brings heightened wildfire risk to Western US",
            "summary_source": "",
        })
        self.assertEqual(item["title_zh"], "")
        self.assertEqual(item["summary_zh"], "")
        self.assertEqual(item["translation_status"], "pending")
        self.assertEqual(item["places"][0]["name_zh"], "美国")

    def test_source_health_quarantines_only_after_repeated_failures(self) -> None:
        state = {"sources": {}}
        for _ in range(6):
            update_source_health(state, [{"source_id": "X", "status": "failed", "error": "403"}])
        self.assertTrue(source_is_due(state, "X"))
        update_source_health(state, [{"source_id": "X", "status": "failed", "error": "403"}])
        self.assertFalse(source_is_due(state, "X"))
        update_source_health(state, [{"source_id": "X", "status": "success", "error": None}])
        self.assertTrue(source_is_due(state, "X"))

    def test_historical_record_has_analysis_tags(self) -> None:
        article = NormalizedArticle(
            article_id="h1", source_id="API001", source_url="https://example.org/a",
            canonical_url="https://example.org/a",
            title="China and the United States discuss climate finance and renewable energy",
            published_at_raw="20260801T000000Z", published_at_utc="2026-08-01T00:00:00+00:00",
            summary_from_source=None, language="English", content_hash="h",
        )
        record = article_to_historical_record(article, fetched_at="2026-08-03T00:00:00+00:00")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["published_date"], "2026-08-01")
        self.assertIn("country_tags", record)
        self.assertIn("continent_tags", record)
        self.assertIn("topics", record)

    def test_historical_records_upsert_to_sqlite(self) -> None:
        record = {
            "record_id": "h1", "canonical_url": "https://example.org/a",
            "source_id": "HIST_GDELT", "source_name": "GDELT historical climate backfill",
            "source_domain": "example.org", "title_original": "Climate finance update",
            "summary_source": None, "language": "English",
            "published_at_utc": "2026-08-01T00:00:00+00:00", "published_date": "2026-08-01",
            "year": 2026, "month": 8, "quarter": "2026Q3", "relevance_score": 70,
            "topics": ["气候资金"], "numbers": [], "places": [],
            "country_tags": ["未标注"], "continent_tags": ["Global/Unspecified"],
            "quality_flags": {"metadata_only": True}, "metadata": {"backfill_method": "test"},
            "fetched_at": "2026-08-03T00:00:00+00:00",
        }
        counts = upsert_historical_records(self.db, [record])
        self.assertEqual(counts["new"], 1)
        self.assertEqual(self.db.rows("SELECT COUNT(*) AS n FROM historical_articles")[0]["n"], 1)

    def test_corpus_analytics_profiles_country_topic_and_time(self) -> None:
        corpus = Path(self.temp.name) / "corpus.jsonl"
        corpus.write_text(
            "\n".join([
                json.dumps({
                    "record_id": "h1", "published_date": "2026-01-01",
                    "topics": ["能源与排放"], "country_tags": ["中国"],
                    "continent_tags": ["Asia"], "source_domain": "example.org",
                    "quality_flags": {"has_country_tag": True},
                }, ensure_ascii=False),
                json.dumps({
                    "record_id": "h2", "published_date": "2026-01-02",
                    "topics": ["气候资金"], "country_tags": ["美国"],
                    "continent_tags": ["North America"], "source_domain": "google:reuters",
                    "quality_flags": {"has_country_tag": True},
                }, ensure_ascii=False),
            ]),
            encoding="utf-8",
        )
        analytics = build_corpus_analytics(corpus)
        self.assertEqual(analytics["records"], 2)
        self.assertEqual(analytics["monthly_records"][0]["month"], "2026-01")
        self.assertEqual(analytics["top_countries"][0]["name"], "中国")
        self.assertIn("亚洲", {item["name"] for item in analytics["continents"]})


if __name__ == "__main__":
    unittest.main()

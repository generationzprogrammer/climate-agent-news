from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from climate_agent.archive import quality_result, update_archive, validate_public_payload
from climate_agent.briefing import dashboard_payload, render_markdown, save_brief
from climate_agent.cli import ROOT, bootstrap
from climate_agent.collector import parse_feed, parse_gdelt
from climate_agent.db import Database
from climate_agent.delivery import build_push_message
from climate_agent.exporter import export_static_site
from climate_agent.official_data import parse_ndc_csv
from climate_agent.pipeline import event_priority, normalize_url
from climate_agent.translation import detect_places


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
        self.assertEqual(self.db.rows("SELECT COUNT(*) AS n FROM sources")[0]["n"], 46)
        self.assertEqual(self.db.rows("SELECT COUNT(*) AS n FROM events")[0]["n"], 3)

    def test_dashboard_reconciles_source_counts(self) -> None:
        payload = dashboard_payload(self.db)
        self.assertEqual(payload["metrics"]["source_total"], 46)
        self.assertEqual(payload["metrics"]["source_enabled"], 25)
        self.assertEqual(len(payload["events"]), 3)
        self.assertGreaterEqual(payload["events"][0]["priority"], payload["events"][-1]["priority"])

    def test_brief_is_versioned(self) -> None:
        payload = dashboard_payload(self.db)
        first, second = save_brief(self.db, payload), save_brief(self.db, payload)
        self.assertEqual((first["version"], second["version"]), (1, 2))
        self.assertIn("事实：", render_markdown(payload))
        self.assertIn("系统研判：", render_markdown(payload))

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

    def test_public_homepage_exposes_database_and_molecule_sections(self) -> None:
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("十年政策脉络", html)
        self.assertNotIn("版本，而不是文件堆积", html)
        self.assertIn('id="mapPlaceList"', html)
        self.assertIn('id="database"', html)
        self.assertIn('id="molecule"', html)
        self.assertIn("ClimateText-3000", html)

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


if __name__ == "__main__":
    unittest.main()

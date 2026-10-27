from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from bs4 import BeautifulSoup
from climate_agent.briefing import select_daily_window, select_daily_map_window, _continent, _ensure_places
from climate_agent.cop_coverage import cop_topics, coverage_regions, prioritize_translation
from climate_agent.cop31_site import write_cop31_entry
from climate_agent.sync import GOOGLE_NEWS_QUERIES, GOOGLE_NEWS_LOCALES, interleave_discovery_batches, _source_scope_match, _analyse, _article_rows
from climate_agent.collector import NormalizedArticle
from climate_agent.taxonomy import organization_tags_for, public_taxonomy
from climate_agent.translation import detect_places, source_balanced_rows
from climate_agent.web import AppHandler

ROOT = Path(__file__).resolve().parents[1]


def row(index, title, code="US", day="2026-10-27", score=80):
    return {"article_id": str(index), "canonical_url": f"https://example.org/{index}",
            "title_original": title, "source_name": f"Publisher {index}", "source_id": str(index),
            "relevance_score": score, "authority": 4, "published_at": day + "T04:00:00+00:00",
            "published_at_utc": day + "T04:00:00+00:00", "country_codes": [{"alpha2": code}],
            "places": [{"name_zh": code, "lon": index * 12 - 100, "lat": 30}]}


class Cop31Tests(unittest.TestCase):
    def test_local_server_serves_standalone_directory_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_bytes(b"main")
            (root / "cop31").mkdir()
            (root / "cop31/index.html").write_bytes(b"COP31")
            handler = SimpleNamespace(static_dir=root, send_response=Mock(), send_header=Mock(), end_headers=Mock(), send_error=Mock(), wfile=BytesIO())
            AppHandler._send_static(handler, "cop31/")
            self.assertEqual(handler.wfile.getvalue(), b"COP31")
            handler.send_error.assert_not_called()

    def test_twelve_same_day_items_and_four_cop_priorities(self):
        titles = ["Wildfire damages forests in California", "Drought cuts crop harvest in Kenya", "Scientists measure Arctic ice", "India installs solar capacity", "Brazil builds electricity grid", "New battery factory opens in France", "Japanese heatwave breaks records", "Germany reforms electricity tariffs"]
        items = [row(i, title, code) for i, (title, code) in enumerate(zip(titles, ["US", "KE", "CA", "IN", "BR", "FR", "JP", "DE"]))]
        items += [row(10, "COP31 negotiators discuss national commitments", "TR", score=70),
                  row(11, "New climate finance pledge for Africa", "NG", score=70),
                  row(12, "Fiji climate adaptation plan approved", "FJ", score=70),
                  row(13, "Russia methane emissions monitoring expanded", "RU", score=70)]
        items.append(row(90, "Yesterday COP31 statement", "TR", day="2026-10-26"))
        selected = select_daily_window(items)
        self.assertEqual(len(selected), 12)
        self.assertGreaterEqual(sum(bool(cop_topics(item)) for item in selected), 4)
        self.assertNotIn("90", {item["article_id"] for item in selected})
        self.assertTrue({"RU", "PACIFIC_ISLANDS"} <= set().union(*(coverage_regions(item) for item in selected)))

    def test_no_old_news_to_fill_target(self):
        self.assertEqual(len(select_daily_window([row(1, "Floods in Brazil", "BR"), row(2, "Climate finance", day="2026-10-26")])), 1)

    def test_russian_language_discovery_is_climate_scoped(self):
        article = SimpleNamespace(title="В России обсуждают климат и выбросы парниковых газов", summary_from_source="", source_id="API004")
        self.assertTrue(_source_scope_match(article, "API004"))
        self.assertGreaterEqual(_analyse(article, 3)["score"], 45)
        self.assertIn("RU", coverage_regions({"title_original": article.title}))
        self.assertEqual(detect_places(article.title)[0]["name_zh"], "俄罗斯")
        self.assertFalse(_source_scope_match(SimpleNamespace(title="В России обсуждают футбол"), "API004"))
        self.assertFalse(_source_scope_match(SimpleNamespace(title="Granta LPG: пропан вместо метана и запас хода 1000 км"), "API004"))
        self.assertTrue(_source_scope_match(SimpleNamespace(title="Новые требования к выбросам метана"), "API004"))

    def test_pacific_islands_are_not_australia_or_pacific_northwest(self):
        for title in ["Australia solar capacity rises", "Pacific Northwest floods"]:
            self.assertNotIn("PACIFIC_ISLANDS", coverage_regions(row(1, title, "AU")))
        self.assertIn("PACIFIC_ISLANDS", coverage_regions(row(1, "Vanuatu adaptation funding", "VU")))
        self.assertIn("PIF", organization_tags_for("Pacific Islands Forum climate declaration"))
        self.assertNotIn("PIF", organization_tags_for("Saudi PIF invests in energy"))
        self.assertTrue(any(org["code"] == "PIF" for group in public_taxonomy()["organization_groups"] for org in group["organizations"]))

    def test_specific_pacific_geocoding(self):
        for name in ("Fiji", "Tuvalu", "Samoa", "Tonga", "Vanuatu", "Kiribati"):
            places = detect_places(name + " climate plan")
            self.assertTrue(places, name)
            self.assertEqual(_continent({"places": places}), "大洋洲")
        for title, name in [("Türkiye hosts COP31", "土耳其"), ("Finnish forest emissions fall", "芬兰"), ("Welsh methane project", "威尔士"), ("图瓦卢适应气候变化", "图瓦卢")]:
            self.assertEqual(detect_places(title)[0]["name_zh"], name)

    def test_query_coverage_and_round_robin_before_cap(self):
        self.assertEqual(len(GOOGLE_NEWS_QUERIES), len(GOOGLE_NEWS_LOCALES))
        batches = [[SimpleNamespace(canonical_url=f"{batch}/{i}") for i in range(100)] for batch in range(16)]
        selected = interleave_discovery_batches(batches)[:150]
        self.assertEqual(len({item.canonical_url.split('/')[0] for item in selected}), 16)
        duplicate = SimpleNamespace(canonical_url="same")
        self.assertEqual(len(interleave_discovery_batches([[duplicate], [duplicate]])), 1)

    def test_headline_island_takes_precedence_over_broad_pacific_context(self):
        item = row(1, "Tonga coastal resilience project shares Pacific voices", "TO")
        item["places"] = [{"name_zh": "太平洋地区", "lon": 165, "lat": -10}]
        self.assertEqual(_ensure_places(item)["places"][0]["name_zh"], "汤加")

    def test_irrelevant_results_do_not_consume_accepted_article_budget(self):
        def article(index, title):
            return NormalizedArticle(str(index), "API004", "https://example.org/rss", f"https://example.org/{index}", title, None, None, None, "en", str(index))
        rows, _ = _article_rows([article(i, "Football game") for i in range(160)] + [article(200, "Russia climate emissions policy")], {"authority": 3})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["article_id"], "200")
        rows, _ = _article_rows([article(i, "Climate emissions policy") for i in range(180)], {"authority": 3})
        self.assertEqual(len(rows), 150)

    def test_translation_priorities_do_not_pull_old_cop_news_ahead_of_today(self):
        rows = [row(1, "Today solar project", "CN"), row(2, "COP31 climate finance", day="2026-10-26")]
        self.assertEqual(prioritize_translation(rows, 1, source_balanced_rows)[0]["article_id"], "1")

    def test_standalone_entry_uses_shared_assets_and_curated_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text((ROOT / "static/index.html").read_text(encoding="utf-8"), encoding="utf-8")
            page = BeautifulSoup(write_cop31_entry(root).read_text(encoding="utf-8"), "html.parser")
            self.assertEqual(page.body["data-edition"], "cop31")
            self.assertEqual(page.base["href"], "../")
            links = {node["href"] for node in page.select("nav a")}
            self.assertIn("./cop31/#map", links)
            self.assertIn("./cop31/#database", links)
            self.assertNotIn("./cop31/#companies", links)
            self.assertFalse(any("innovation" in node.get("src", "") for node in page.select("script")))
            self.assertFalse(page.select_one("#today").has_attr("hidden"))
            self.assertFalse(page.select_one("#assistant").has_attr("hidden"))
            self.assertIn("./cop31/#assistant", links)
            self.assertTrue(page.select_one("#subscribeOpen").has_attr("hidden"))
            self.assertIsNotNone(page.select_one("#subscribeForm"))
            visible = [node.get("id") for node in page.select("main > section") if node.get("id") and not node.has_attr("hidden")]
            self.assertEqual(visible[:2], ["map", "today"])


if __name__ == "__main__":
    unittest.main()

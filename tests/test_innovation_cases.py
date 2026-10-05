import copy
from collections import Counter
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock
from climate_agent.innovation_cases import (
    FACT_FIELDS, InnovationCaseAgent, link_developments,
    safe_public_url, validate_casebook, write_innovation_cases,
)
from climate_agent.innovation_metrics import profile_metrics, validate_profile

ROOT = Path(__file__).resolve().parents[1]


class InnovationCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = json.loads((ROOT / "config/open_innovation_cases.json").read_text(encoding="utf-8"))
        cls.codes = {row["alpha2"] for row in json.loads((ROOT / "config/country_codes.json").read_text(encoding="utf-8"))["countries"]}

    def test_reviewed_seed_integrity(self):
        report = validate_casebook(self.book, self.codes)
        self.assertEqual(report["cases"], 25)
        self.assertEqual(report["sources"], 40)
        self.assertEqual(report["country_tags"], 17)
        self.assertTrue(all(tag in report or tag in self.book for tag in ("cases", "sources")))

    def test_no_unreviewed_case_can_publish(self):
        book = copy.deepcopy(self.book)
        book["cases"][0]["review_status"] = "draft"
        with self.assertRaisesRegex(ValueError, "unreviewed_case"):
            validate_casebook(book, self.codes)

    def test_empty_casebook_and_duplicate_source_rejected(self):
        book = copy.deepcopy(self.book)
        book["cases"] = []
        with self.assertRaisesRegex(ValueError, "empty_or_invalid"):
            validate_casebook(book, self.codes)
        book = copy.deepcopy(self.book)
        book["sources"][1]["url"] = book["sources"][0]["url"]
        with self.assertRaisesRegex(ValueError, "duplicate_source_url"):
            validate_casebook(book, self.codes)

    def test_duplicate_case_and_invalid_country_rejected(self):
        book = copy.deepcopy(self.book)
        book["cases"].append(copy.deepcopy(book["cases"][0]))
        book["cases"][1]["countries"] = ["EU"]
        with self.assertRaisesRegex(ValueError, "duplicate_or_invalid_case"):
            validate_casebook(book, self.codes)

    def test_missing_citation_or_translation_rejected(self):
        for mutation in ("evidence", "translation"):
            book = copy.deepcopy(self.book)
            if mutation == "evidence":
                book["cases"][0]["evidence"] = []
            else:
                book["cases"][0]["title"].pop("en")
            with self.assertRaises(ValueError):
                validate_casebook(book, self.codes)

    def test_no_credentials_or_local_urls(self):
        for value in ("http://example.org", "https://user:secret@example.org",
                      "https://127.0.0.1/a", "https://localhost/a",
                      "https://example.org/?api_key=private", "javascript:alert(1)"):
            self.assertFalse(safe_public_url(value))
        self.assertTrue(safe_public_url("https://example.org/report.pdf?filename=public.pdf"))

    def test_entity_news_linking_is_deduplicated_and_bounded(self):
        case = {"aliases": ["Fraunhofer", "弗劳恩霍夫"]}
        article = {"title_original": "Fraunhofer develops a solar test platform",
                   "title_zh": "弗劳恩霍夫开发太阳能试验平台",
                   "canonical_url": "https://example.org/news/1", "published_at": "2026-10-04"}
        archive = {"records": [article, article, {**article, "canonical_url": "https://example.org/future", "published_at": "2027-01-01"}]}
        result = link_developments(case, [archive], [], date(2026, 10, 5))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"]["en"], article["title_original"])
        self.assertEqual(result[0]["linkage"], "entity_mention")
        self.assertEqual(link_developments(case, [{"records": []}], result, date(2026, 10, 6)), result)
        self.assertEqual(link_developments(case, [], result, date(2027, 3, 1)), [])

    def test_entity_substrings_do_not_match(self):
        self.assertFalse(link_developments({"aliases": ["Eurostars"]}, [{"records": [{
            "title_original": "EurostarsX train service", "published_at": "2026-10-05",
            "canonical_url": "https://example.org/train",
        }]}], [], date(2026, 10, 5)))

    def test_static_export_preserves_reviewed_facts_and_prior_news(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "innovation_cases.json"
            first = write_innovation_cases(ROOT, target, [{"records": [{
                "title_original": "Fraunhofer energy test", "published_at": "2026-10-04",
                "canonical_url": "https://example.org/new",
            }]}], today=date(2026, 10, 5))
            second = write_innovation_cases(ROOT, target, [], today=date(2026, 10, 6))
            self.assertEqual(first["statistics"]["developments"], 1)
            self.assertEqual(second["statistics"]["developments"], 1)
            source = next(c for c in self.book["cases"] if c["id"] == "oi_iea_tcp")
            self.assertEqual(next(c for c in second["cases"] if c["id"] == source["id"])["summary"], source["summary"])
            self.assertTrue(all(c["review_status"] in {"reviewed", "structured_verified"} for c in second["cases"]))
            self.assertGreaterEqual(len(second["cases"]), 300)
            self.assertTrue({c["id"] for c in self.book["cases"]}.issubset({c["id"] for c in second["cases"]}))

    def test_scores_are_recomputed_and_missing_is_not_zero(self):
        self.assertTrue(all(row["score"] is None for row in profile_metrics(None, None).values()))
        project = {"country_count": 6, "company_count": 2, "research_count": 1, "actor_type_count": 3, "eu_grant_million": 3}
        scores = profile_metrics(project, "s1")
        self.assertEqual(scores["crossborder"]["score"], 4)
        self.assertEqual(scores["funding"]["score"], 2)
        c = {"id": "sample", "project": project, "profile": scores, "evidence": [{"source_id": "s1"}]}
        validate_profile(c)
        c["profile"]["industry"]["score"] = 5
        with self.assertRaisesRegex(ValueError, "mismatch"):
            validate_profile(c)

    def test_project_records_have_real_grain_and_no_private_contact_fields(self):
        extra = json.loads((ROOT / "config/open_innovation_projects.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(extra["cases"]), 300)
        self.assertEqual(len({c["project"]["official_id"] for c in extra["cases"]}), len(extra["cases"]))
        for c in extra["cases"]:
            validate_profile(c)
            self.assertGreaterEqual(c["project"]["country_count"], 2)
            self.assertGreater(c["project"]["company_count"], 0)
            self.assertGreater(c["project"]["research_count"], 0)
            self.assertEqual(len(c["participants"]), c["project"]["participant_count"])
            self.assertEqual(len({p["id"] for p in c["participants"]}), len(c["participants"]))
            self.assertEqual(len({p["country"] for p in c["participants"]}), c["project"]["country_count"])
            types = Counter(p["type"] for p in c["participants"])
            self.assertEqual(types["PRC"], c["project"]["company_count"])
            self.assertEqual(types["HES"] + types["REC"], c["project"]["research_count"])
            self.assertEqual(len(types), c["project"]["actor_type_count"])
            self.assertTrue(all(p["country"] in self.codes for p in c["participants"]))
            self.assertFalse(any(k in p for p in c["participants"] for k in ("email", "contactForm", "street", "vatNumber")))
            self.assertEqual(c["project"]["funding_basis"], "maximum_EU_contribution_not_actual_expenditure")

    def test_model_draft_is_grounded_and_cannot_publish(self):
        extract = "The partners jointly run an applied research and testing platform."
        claims = {field: [{"source_id": "s1", "quote": extract}] for field in FACT_FIELDS}
        model = Mock()
        model.complete_json.return_value = {"case": {"title": {"zh": "测试", "en": "Test"}}, "claim_evidence": claims}
        result = InnovationCaseAgent(model).draft({"sources": [{"id": "s1", "url": "https://example.org", "extract": extract}]}, self.book["taxonomy"])
        self.assertEqual(result["publication"], "blocked_pending_review")
        self.assertEqual(result["case"]["review_status"], "draft")
        self.assertIn("untrusted data", model.complete_json.call_args.args[0])

    def test_model_cannot_invent_supporting_quote(self):
        model = Mock()
        model.complete_json.return_value = {"case": {}, "claim_evidence": {
            field: [{"source_id": "s1", "quote": "It is already commercially profitable."}] for field in FACT_FIELDS}}
        with self.assertRaisesRegex(ValueError, "Unverifiable"):
            InnovationCaseAgent(model).draft({"sources": [{"id": "s1", "url": "https://example.org", "extract": "The project is planned."}]}, {})

    def test_invalid_evidence_does_not_call_model(self):
        model = Mock()
        with self.assertRaises(ValueError):
            InnovationCaseAgent(model).draft({"sources": [{"id": "s1", "url": "https://localhost", "extract": "Test"}]}, {})
        model.complete_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()

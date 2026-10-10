import json
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path

from climate_agent.bth_assistant import build_knowledge
from climate_agent.bth_tracker import build_target_tracker, classify_policies

ROOT = Path(__file__).resolve().parents[1]


class BthTrackerTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config/bth_targets.json").read_text(encoding="utf-8"))
        self.taxonomy = json.loads((ROOT / "config/bth_policy_taxonomy.json").read_text(encoding="utf-8"))

    def tracker(self, config=None):
        return build_target_tracker(config or self.config, today=date(2026, 10, 3))

    def test_goals_cover_three_regions_and_preserve_baseline(self):
        rows = self.tracker()["records"]
        self.assertEqual(len(rows), 39)
        self.assertEqual({r["region"] for r in rows}, {"北京市", "天津市", "河北省"})
        self.assertEqual(next(r for r in rows if r["id"] == "tj_carbonintensity_2030")["baseline_year"], 2005)
        self.assertTrue(all(r["source"]["url"].startswith("https://") and r["excerpt"] and r["scope"] for r in rows))

    def test_preliminary_is_not_final_and_future_target_is_not_achieved(self):
        rows = {r["id"]: r for r in self.tracker()["records"]}
        self.assertEqual(rows["bj_re_2025"]["assessment"], "preliminary_met")
        self.assertEqual(rows["bj_re_2030"]["assessment"], "tracking")
        self.assertNotIn("gap_percentage_points", rows["bj_re_2030"])

    def test_missing_is_not_zero_or_failure_after_deadline(self):
        row = next(r for r in self.tracker()["records"] if r["id"] == "tj_nonfossil_2025")
        self.assertEqual(row["period_status"], "past_deadline")
        self.assertEqual(row["assessment"], "awaiting_observation")
        self.assertIsNone(row["observation"])
        self.assertNotIn("completion_ratio", row)

    def test_electricity_quota_or_different_region_cannot_be_matched(self):
        for field, value in [("scope", "全社会用电量"), ("region", "天津市"), ("unit", "万千瓦"), ("baseline_year", 2020)]:
            config = deepcopy(self.config)
            config["observations"][0][field] = value
            row = next(r for r in self.tracker(config)["records"] if r["id"] == "bj_re_2025")
            self.assertIsNone(row["observation"])

    def test_classification_is_non_destructive_and_multilabel(self):
        records = [{"title": "碳排放权交易与环境信息依法披露办法", "policy_id": "a", "keywords": ["减污降碳"]},
                   {"title": "老龄事业发展规划", "policy_id": "b"},
                   {"title": "绿色转型实施方案", "policy_id": "c"}]
        before = deepcopy(records)
        classified = classify_policies(records, self.taxonomy)
        self.assertEqual(records, before)
        self.assertEqual(classified[0]["instrument_categories"], ["economic", "information"])
        self.assertTrue(all(m["basis"] == "title_keyword" for m in classified[0]["instrument_evidence"]))
        self.assertEqual(classified[1]["classification_status"], "unclassified")
        self.assertEqual(classified[2]["instrument_categories"], [])

    def test_target_evidence_is_not_an_observation_and_actual_is_deduplicated(self):
        rows = build_knowledge({}, {}, self.tracker())["records"]
        self.assertEqual(sum(r["kind"] == "target" for r in rows), 39)
        self.assertEqual(sum(r["kind"] == "observation" for r in rows), 1)
        self.assertTrue(all(r["content_scope"] == "verified_policy_target_excerpt" for r in rows if r["kind"] == "target"))

    def test_duplicate_targets_and_nan_rejected(self):
        config = deepcopy(self.config)
        config["targets"].append(config["targets"][0])
        with self.assertRaises(ValueError): self.tracker(config)
        config = deepcopy(self.config)
        config["targets"][0]["value"] = float("nan")
        with self.assertRaises(ValueError): self.tracker(config)

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from climate_agent.bth_assistant import build_knowledge, write_assistant_assets


class BthAssistantTests(unittest.TestCase):
    def fixture(self):
        return {"sources": [{"id": "S", "publisher": "统计局", "title": "统计公报", "url": "https://example.gov.cn/stat"}], "observations": [{"id": "O1", "source_id": "S", "selected": True, "region": "北京市", "year": 2025, "label": "光伏装机", "metric": "solar", "value": 210.2, "unit": "万千瓦", "category": "能源", "notes": "年度口径"}]}

    def test_only_selected_observations_and_provenance(self):
        data = self.fixture()
        data["observations"].append({**data["observations"][0], "id": "O2", "selected": False})
        rows = build_knowledge(data, {})["records"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "D-O1")
        self.assertEqual(rows[0]["notes"], "年度口径")

    def test_invalid_value_rejected(self):
        data = self.fixture()
        data["observations"][0]["value"] = float("nan")
        with self.assertRaises(ValueError): build_knowledge(data, {})

    def test_policy_scope_is_metadata(self):
        row = {"policy_id": "1", "title": "绿色转型政策", "region": "海淀区", "province": "北京市", "published_at": "2026-01-01", "source": "政府", "url": "http://example.gov.cn/policy"}
        policy = build_knowledge({}, {"records": [row]})["records"][0]
        self.assertEqual(policy["content_scope"], "title_metadata_only")

    def test_export_contains_public_configuration_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / "config").mkdir()
            (root / "config/bth_energy_evidence.json").write_text(json.dumps(self.fixture()), encoding="utf-8")
            with patch.dict("os.environ", {"BTH_ASSISTANT_ENDPOINT": "https://assistant.example.com", "BTH_TURNSTILE_SITE_KEY": "PUBLIC", "BTH_LLM_API_KEY": "NEVER_EXPORT_THIS"}):
                result = write_assistant_assets(root, root / "out")
            self.assertTrue(result["configured"])
            self.assertNotIn("NEVER_EXPORT_THIS", (root / "out/bth_assistant_config.json").read_text())

    def test_live_bundle_has_expected_selected_count(self):
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads((root / "config/bth_energy_evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(len(build_knowledge(evidence, {})["records"]), 1214)


if __name__ == "__main__": unittest.main()

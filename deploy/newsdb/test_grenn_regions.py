"""Tests for grenn_regions.py (Taiwan filed under China, 2026-11-15) on the record shapes the site data really has.
Run: python -m unittest test_grenn_regions (from this folder; standard library only)."""
import json
import tempfile
import unittest
from pathlib import Path

import grenn_regions as g

TW = {"alpha2": "TW", "alpha3": "TWN", "name_zh": "中国台湾", "name_en": "Taiwan"}
CN = {"alpha2": "CN", "alpha3": "CHN", "name_zh": "中华人民共和国", "name_en": "China"}
US = {"alpha2": "US", "alpha3": "USA", "name_zh": "美国", "name_en": "United States"}


class RegionTests(unittest.TestCase):
    def test_country_lists(self):
        out, n = g.fix([dict(US), dict(TW)])
        self.assertEqual(out, [US, CN])
        out, n = g.fix([dict(CN), dict(US), dict(TW)])  # China once
        self.assertEqual(out, [CN, US])
        self.assertEqual(g.fix(["US", "TW", "CN"])[0], ["US", "CN"])
        self.assertEqual(g.fix(["中国台湾", "美国", "中华人民共和国"])[0], ["中华人民共和国", "美国"])
        self.assertEqual(g.codes2(["TW", "JP", "CN", "TW"]), ["CN", "JP"])

    def test_record_text_is_left_alone(self):
        record = {"title_zh": "缺失的拼图：台湾如何加强土耳其的气候适应", "title_original": "How Taiwan can bolster Türkiye", "summary_zh": "台湾",
                  "country_codes": [dict(TW)], "molecule": {"country_code_atoms": ["TWN", "TUR"]},
                  "country_evidence": [{**TW, "matched_text": "Taiwan", "start": 4, "end": 10}],
                  "governance_labels_v1": {"evidence": [{"label_type": "country", "label_id": "TW", "alpha3": "TWN", "quote": "Taiwan", "start": 4, "end": 10}]},
                  "company_entities": [{"name": "Taiwan Power Company", "country": "中国台湾"}]}
        out, n = g.fix(record)
        self.assertEqual(out["title_zh"], "缺失的拼图：台湾如何加强土耳其的气候适应")
        self.assertEqual(out["title_original"], "How Taiwan can bolster Türkiye")
        self.assertEqual(out["summary_zh"], "中华人民共和国")  # an exact tag value is a label even under a text key…
        self.assertEqual(out["country_codes"], [CN])
        self.assertEqual(out["molecule"]["country_code_atoms"], ["CHN", "TUR"])
        self.assertEqual(out["country_evidence"][0]["alpha2"], "CN")
        self.assertEqual(out["country_evidence"][0]["matched_text"], "Taiwan")  # …but the words matched stay as written
        ev = out["governance_labels_v1"]["evidence"][0]
        self.assertEqual((ev["label_id"], ev["alpha3"], ev["quote"]), ("CN", "CHN", "Taiwan"))
        self.assertEqual(out["company_entities"][0], {"name": "Taiwan Power Company", "country": "中华人民共和国"})

    def test_companies(self):
        company = {"name_zh": "台湾电力公司", "name_en": "Taiwan Power Company", "country": "中华民国",
                   "overview_zh": "中华民国经济部所属的国营企业，亦是台湾最大的电力公司", "aliases": ["台湾电力公司", "Taiwan Power Company"]}
        out, _ = g.fix(company)
        self.assertEqual(out["country"], "中华人民共和国")
        self.assertEqual(out["overview_zh"], "中国台湾地区经济主管部门所属的国营企业，亦是台湾最大的电力公司")
        self.assertEqual((out["name_zh"], out["name_en"], out["aliases"]), ("台湾电力公司", "Taiwan Power Company", ["台湾电力公司", "Taiwan Power Company"]))

    def test_country_tables_and_counts(self):
        self.assertEqual(g.fix([dict(TW), dict(CN)])[0], [CN])  # the catalogue's country list: China once
        self.assertEqual(g.fix({"TW": 3, "CN": 9, "US": 1})[0], {"CN": 12, "US": 1})
        self.assertEqual(g.fix({"中国台湾": 2, "美国": 5})[0], {"美国": 5, "中华人民共和国": 2})
        rows = [{"name": "中华人民共和国", "count": 9}, {"name": "美国", "count": 4}, {"name": "中国台湾", "count": 2}]
        self.assertEqual(g.fix(rows)[0], [{"name": "中华人民共和国", "count": 11}, {"name": "美国", "count": 4}])
        analytics = [{"id": "CN", "zh": "中华人民共和国", "en": "China", "n": 10}, {"id": "TW", "zh": "中国台湾", "en": "Taiwan", "n": 3}]
        self.assertEqual(g.fix(analytics)[0], [{"id": "CN", "zh": "中华人民共和国", "en": "China", "n": 13}])
        self.assertEqual(g.fix({"text": "TW"})[0], {"text": "CN"})
        self.assertEqual(g.fix({"stats": {"en": "Taiwan", "id": 5}})[0], {"stats": {"en": "China", "id": 5}})

    def test_places(self):
        places = [{"name_zh": "中国", "lat": 35.0, "lon": 105.0}, {"name_zh": "台湾", "lat": 23.7, "lon": 121.0}]
        self.assertEqual(g.fix(places)[0], [{"name_zh": "中国", "lat": 35.0, "lon": 105.0}])
        self.assertEqual(g.fix([{"name_zh": "台湾", "lat": 23.7, "lon": 121.0}])[0], [{"name_zh": "中国", "lat": 35.0, "lon": 105.0}])

    def test_nothing_else_moves(self):
        data = {"records": [{"title": "TWh of power", "country_codes": [US], "tw": "x", "language": "zh-TW"}], "TWh": 3}
        out, n = g.fix(json.loads(json.dumps(data)))
        self.assertEqual((out, n), (data, 0))
        self.assertEqual(g.fix(g.fix([dict(TW)])[0]), ([CN], 0))  # a second pass changes nothing

    def test_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.json").write_text(json.dumps({"records": [{"country_codes": [TW, CN]}]}, ensure_ascii=False), "utf-8")
            (root / "b.jsonl").write_text(json.dumps({"country_codes": [TW]}, ensure_ascii=False) + "\n" + json.dumps({"x": 1}) + "\n", "utf-8")
            (root / "c.csv").write_text("﻿text_id,source_text,country_iso2,country_iso3\r\n1,Taiwan TW,US;TW;CN,USA;TWN;CHN\r\n2,x,TW,TWN\r\n", "utf-8")
            (root / "d.json").write_text(json.dumps({"records": [{"country_codes": [US]}]}), "utf-8")
            report = g.apply(root)
            self.assertEqual(set(report), {"a.json", "b.jsonl", "c.csv"})
            self.assertEqual(json.loads((root / "a.json").read_text("utf-8"))["records"][0]["country_codes"], [CN])
            self.assertEqual(json.loads((root / "b.jsonl").read_text("utf-8").splitlines()[0])["country_codes"], [CN])
            csv_text = (root / "c.csv").read_bytes().decode("utf-8")
            self.assertTrue(csv_text.startswith("﻿text_id"))
            self.assertIn("1,Taiwan TW,US;CN,USA;CHN\r\n", csv_text)  # the text column untouched
            self.assertIn("2,x,CN,CHN\r\n", csv_text)
            self.assertEqual(g.apply(root), {})  # repeatable


if __name__ == "__main__":
    unittest.main()

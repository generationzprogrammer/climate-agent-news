import json
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
from climate_agent.bth_energy import build_energy_database
from climate_agent.bth_energy_update import merge_updates, parse_release
from climate_agent.bth_tracker import build_target_tracker

ROOT = Path(__file__).resolve().parents[1]


class BthEnergyTests(unittest.TestCase):
    def setUp(self):
        self.energy = json.loads((ROOT / "config/bth_energy_evidence.json").read_text(encoding="utf-8"))
        self.targets = build_target_tracker(json.loads((ROOT / "config/bth_targets.json").read_text(encoding="utf-8")))

    def test_all_original_observations_preserved_and_shared_by_monitor(self):
        before = deepcopy(self.energy)
        data = build_energy_database(self.energy, self.targets)
        self.assertEqual(self.energy, before)
        self.assertEqual(len(data["records"]), 1214)
        self.assertEqual({r["id"] for r in data["records"]}, {r["id"] for r in self.energy["observations"]})
        records = {r["id"]: r for r in data["records"]}
        self.assertTrue(all(i in records for m in data["indicators"] for i in m["history_ids"] + m["latest_ids"]))
        self.assertEqual({r["kind"] for r in records.values()}, {"observation"})
        self.assertEqual({r["region"] for r in records.values()}, {"北京市","天津市","河北省"})
        self.assertEqual({r["dimension"] for r in records.values()}, {c["id"] for c in data["categories"]})
        self.assertTrue(all(records[i]["metric"] == m["metric"] for m in data["indicators"] for i in m["latest_ids"]))

    def test_future_and_actual_are_not_mixed(self):
        data = build_energy_database(self.energy, self.targets, today=date(2026,10,10))
        self.assertTrue(all(r["year"] <= 2026 for r in data["records"]))
        self.assertTrue(any(r["year"] == 2030 for r in data["targets"]))
        self.assertNotIn("neutrality_score",data)
        self.assertTrue(all(r["published_at"] is None for r in data["records"] if not r["source"].get("published_at") and not r.get("published_at")))

    def test_missing_region_not_filled_from_other_region(self):
        data = build_energy_database(self.energy,self.targets)
        power = next(i for i in data["indicators"] if i["metric"] == "power_society")
        records = {r["id"]:r for r in data["records"]}
        tj = next(records[i] for i in power["latest_ids"] if records[i]["region"] == "天津市")
        self.assertEqual(tj["year"],2020)

    def test_non_finite_or_future_values_rejected(self):
        for key,value in [("value",float("nan")),("year",2030)]:
            energy=deepcopy(self.energy); energy["observations"][0][key]=value
            with self.assertRaises(ValueError): build_energy_database(energy,self.targets,today=date(2026,10,10))

    def test_additive_update_and_conflict_queue(self):
        first = self.energy["observations"][0]
        new = {**first,"id":"W-NEW","year":2024}
        conflict = {**first,"id":"W-CONFLICT","value":first["value"]+1}
        prior={"observations":[new],"sources":[]}
        result=merge_updates(self.energy,prior,[],[new,first,conflict])
        self.assertEqual(result["observations"],[new])
        self.assertEqual(result["review_queue"][0]["id"],"W-CONFLICT")
        self.assertEqual(len(merge_updates(self.energy,result,[],[conflict])["review_queue"]),1)
        self.assertEqual(prior,{"observations":[new],"sources":[]})

    def test_explicit_annual_numeric_rule_and_unit(self):
        source={"region":"北京市","publisher":"北京市统计局"}
        raw=(ROOT/"tests/fixtures/bth_energy_annual.html").read_text(encoding="utf-8")
        citation,rows=parse_release(raw,source,"https://tjj.beijing.gov.cn/annual")
        self.assertEqual(citation["year"],2025)
        self.assertEqual(citation["published_at"],"2026-03-01")
        self.assertEqual({r["metric"]:r["value"] for r in rows},{"population":2180.0,"power_society":1447.5})
        self.assertTrue(all(r["excerpt"] and r["selected"] for r in rows))
        for title in ["2026年1-8月经济运行情况","2025年能源规划","2026年统计公报"]:
            self.assertEqual(parse_release(raw.replace("2025年国民经济和社会发展统计公报",title),source,"https://tjj.beijing.gov.cn/annual")[1],[])

    def test_target_growth_with_old_ids_preserved(self):
        ids={r["id"] for r in self.targets["records"]}
        self.assertTrue({"bj_re_2025","tj_nonfossil_2025","hb_forest_2030"}<=ids)
        self.assertGreaterEqual(len(ids),29); self.assertLessEqual(len(ids),47)
        self.assertTrue(all(r["excerpt"] and r["scope"] and r["source"]["publisher"] for r in self.targets["records"]))

    def test_strict_target_comparator(self):
        config=json.loads((ROOT/"config/bth_targets.json").read_text(encoding="utf-8"))
        target=next(r for r in config["targets"] if r["id"]=="tj_recapacity_2025")
        config["observations"].append({"id":"TEST","region":target["region"],"metric":target["metric"],"year":2025,"value":800,"unit":target["unit"],"scope":target["scope"],"source_id":"tj_peak","status":"final"})
        row=next(r for r in build_target_tracker(config)["records"] if r["id"]==target["id"])
        self.assertEqual(row["assessment"],"below")

    def test_monthly_output_is_not_annual_stock(self):
        raw='<html><head><title>2026年1-8月北京规模以上工业运行情况</title><meta name="PubDate" content="2026-09-21"></head><body><p>其中，新能源汽车41.7万辆，增长11.3%。</p></body></html>'
        _,rows=parse_release(raw,{"region":"北京市","publisher":"北京市统计局"},"https://jxj.beijing.gov.cn/industry")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["metric"],"nev_output_ytd")
        self.assertEqual(rows[0]["period"],"2026-08")
        self.assertEqual(rows[0]["frequency"],"year_to_date")
        self.assertEqual(rows[0]["value"],41.7)
        next_month={**rows[0],"id":"NEXT","period":"2026-09","value":48.0}
        result=merge_updates({}, {"sources":[],"observations":rows},[],[next_month])
        self.assertEqual(len(result["observations"]),2)
        self.assertEqual(result["review_queue"],[])


if __name__ == "__main__": unittest.main()

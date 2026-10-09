import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from climate_agent.innovation_cases import write_innovation_cases
from climate_agent.innovation_analysis import economy_group, annotate_cases, build_analysis

ROOT=Path(__file__).resolve().parents[1]

class InnovationAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            cls.book=write_innovation_cases(ROOT,Path(d)/"book.json",[])

    def test_old_cases_and_sources_preserved(self):
        for filename in ("open_innovation_cases.json","open_innovation_projects.json","open_innovation_us_projects.json"):
            old=json.loads((ROOT/"config"/filename).read_text(encoding="utf-8"))
            current={c["id"]:c for c in self.book["cases"]}
            self.assertTrue({c["id"] for c in old["cases"]}<=current.keys())
            for c in old["cases"]:
                for k in c:
                    self.assertEqual(c[k],current[c["id"]][k],(c["id"],k))
            sources={s['id']:s for s in self.book['sources']}
            for s in old['sources']:
                self.assertEqual(s,sources[s['id']])

    def test_region_tags_match_actual_location_not_university_name(self):
        current={c["id"]:c for c in self.book["cases"]}
        self.assertEqual(current["oi_tju_idim"]["research_annotation"]["province"],"CN-ZJ")
        self.assertEqual(current["oi_tsinghua_sz_storage"]["research_annotation"]["province"],"CN-GD")
        self.assertNotIn("province",current["oi_cerc"]["research_annotation"])
        regions={p["id"]:p for p in self.book["analysis"]["provinces"]}
        self.assertGreaterEqual(regions["CN-GD"]["count"],8)
        self.assertGreaterEqual(regions["CN-ZJ"]["count"],10)

    def test_models_are_complete_and_not_performance_scores(self):
        sources={s['id'] for s in self.book['sources']}
        for m in self.book["analysis"]["profiles"]:
            self.assertTrue(m["case_ids"] and m["source_ids"])
            self.assertTrue(set(m['source_ids'])<=sources)
            for k in ("conditions","mechanism","government","boundary","factors"):
                self.assertTrue(all(m[k].get(l) for l in ("zh","en")))
        self.assertTrue(all(c["research_annotation"]["primary_model"] for c in self.book["cases"]))
        self.assertNotIn("country_scores",self.book["analysis"])

    def test_macro_exclusive_counts_and_denominators_reconcile(self):
        for grain in ("project","platform"):
            subset=[c for c in self.book["cases"] if c["research_annotation"]["grain"]==grain]
            for dim in ("continent","economy"):
                rows=[r for r in self.book["analysis"]["macro"] if r["grain"]==grain and r["dimension"]==dim]
                self.assertEqual(sum(r["count"] for r in rows),len(subset))
                for group in {r["group"] for r in rows}:
                    rs=[r for r in rows if r["group"]==group]
                    n=rs[0]["denominator"]
                    self.assertEqual(sum(r["count"] for r in rs),n)
                    self.assertEqual(sum(rs[0]["source_cohorts"].values()),n)
                    if n:self.assertAlmostEqual(sum(r["share"] for r in rs),1)
                    else:self.assertTrue(all(r["share"] is None for r in rs))

    def test_coordinator_not_all_participants_is_macro_location(self):
        for c in self.book["cases"]:
            if c.get("project",{}).get("funding_basis")=="maximum_EU_contribution_not_actual_expenditure":
                self.assertEqual(c["research_annotation"]["country"],c["project"]["coordinator_country"])
        self.assertEqual(economy_group("SG"),"developing")
        self.assertEqual(economy_group("JP"),"developed")
        self.assertEqual(economy_group(None),"unclassified")

    def test_export_is_stable_across_daily_rebuilds(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"cases.json"
            one=write_innovation_cases(ROOT,p,[])
            two=write_innovation_cases(ROOT,p,[])
            self.assertEqual(one["analysis"],two["analysis"])
            self.assertEqual([c["research_annotation"] for c in one["cases"]],[c["research_annotation"] for c in two["cases"]])

    def test_additive_coverage_preserves_all_previous_factual_fields(self):
        previous=json.loads((ROOT/'config/open_innovation_regional_cases.json').read_text(encoding='utf-8'))
        current={c['id']:c for c in self.book['cases']}
        sources={s['id']:s for s in self.book['sources']}
        for old in previous['cases']:
            for key in ('title','summary','actors','mechanism','observed','constraints','transfer','countries','evidence'):
                self.assertEqual(old[key],current[old['id']][key])
        for source in previous['sources']:self.assertEqual(source,sources[source['id']])

    def test_undercovered_continents_and_provinces_have_traceable_cases(self):
        extra=json.loads((ROOT/'config/open_innovation_coverage.json').read_text(encoding='utf-8'))
        current={c['id']:c for c in self.book['cases']}
        self.assertEqual(len(extra['cases']),43)
        self.assertEqual(len(self.book['analysis']['provinces']),21)
        expected={'africa':7,'south_america':6,'oceania':6,'asia':23,'north_america':1}
        self.assertEqual(dict(Counter(current[c['id']]['research_annotation']['continent'] for c in extra['cases'])),expected)
        for c in extra['cases']:
            a=current[c['id']]['research_annotation']
            self.assertEqual(a['cohort'],'coverage_review')
            if a['province']:self.assertEqual(a['country'],'CN');self.assertTrue(a['city'])
            self.assertTrue(c['evidence'])
        self.assertEqual(economy_group('MX'),'developing')
        self.assertEqual(economy_group('CA'),'developed')
        self.assertEqual(economy_group('MU'),'developing')

    def test_unknown_province_is_rejected_instead_of_silently_dropped(self):
        import copy
        config=json.loads((ROOT/'config/open_innovation_models.json').read_text(encoding='utf-8'))
        c=copy.deepcopy(next(c for c in self.book['cases'] if c['research_annotation'].get('province')))
        c['research_annotation']['province']='CN-BAD'
        with self.assertRaisesRegex(ValueError,'invalid_innovation_province'):
            annotate_cases([c],config)

if __name__=="__main__":unittest.main()

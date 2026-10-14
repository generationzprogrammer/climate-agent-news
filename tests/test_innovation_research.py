import copy
import json
import unittest
from datetime import date
from pathlib import Path
from climate_agent.innovation_research import china_plan,decade,period_sort,annotate_research,factor_pairs

ROOT=Path(__file__).resolve().parents[1]
class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book=json.loads((ROOT/'static/data/innovation_cases.json').read_text(encoding='utf-8'))
        cls.config=json.loads((ROOT/'config/innovation_research_framework.json').read_text(encoding='utf-8'))
        cls.history=json.loads((ROOT/'config/innovation_chronology.json').read_text(encoding='utf-8'))
    def test_plan_boundaries(self):
        for y,p in [(2005,10),(2006,11),(2010,11),(2011,12),(2015,12),(2016,13),(2020,13),(2021,14),(2025,14),(2026,15)]:self.assertEqual(china_plan(y),f'cn_fyp_{p}')
        self.assertIsNone(china_plan(None));self.assertIsNone(decade(True));self.assertEqual(decade(1998),'1990s')
        self.assertLess(period_sort('cn_fyp_9'),period_sort('cn_fyp_10'))
    def test_current_groups_not_historical_sponsorship(self):
        org={o['id']:o for o in self.config['organizations']}
        self.assertEqual(len(org['OECD']['country_members']),38)
        self.assertEqual(len(org['EU']['country_members']),27)
        self.assertNotIn('GB',org['EU']['country_members'])
        self.assertNotIn('ES',org['G20']['country_members'])
        self.assertEqual(len(org['G7']['country_members']),7)
    def test_original_facts_preserved(self):
        current={c['id']:c for c in self.book['cases']}
        for p in (ROOT/'config').glob('open_innovation_*.json'):
            for c in json.loads(p.read_text(encoding='utf-8')).get('cases',[]):
                for key,value in c.items():
                    if key!='research_annotation':self.assertEqual(current[c['id']][key],value,(c['id'],key))
    def test_unknown_dates_not_imputed(self):
        c=next(c for c in self.book['cases'] if c['id']=='oi_ssl_factory')
        self.assertIsNone(c['timeline']['origin_year'])
    def test_future_event_blocked(self):
        history=copy.deepcopy(self.history);history['events'][0]['date']='2099';history['events'][0]['date_precision']='year'
        with self.assertRaisesRegex(ValueError,'innovation_chronology_evidence'):
            annotate_research(copy.deepcopy(self.book),self.config,history,as_of=date(2026,10,14))
    def test_bad_source_blocked(self):
        history=copy.deepcopy(self.history);history['events'][0]['source_ids']=['missing']
        with self.assertRaises(ValueError):annotate_research(copy.deepcopy(self.book),self.config,history,as_of=date(2026,10,14))
    def test_factor_arithmetic(self):
        for row in factor_pairs(self.book['cases'],self.book['taxonomy']):
            self.assertLessEqual(row['count'],min(row['first_count'],row['second_count']))
            if row['jaccard'] is not None:self.assertAlmostEqual(row['jaccard'],row['count']/(row['first_count']+row['second_count']-row['count']))
    def test_temporal_counts(self):
        for r in self.book['research']['temporal']:
            self.assertEqual(r['count'],len(set(r['case_ids'])))
            self.assertEqual(r['count'],sum(r['models'].values()))
        self.assertGreaterEqual(len(self.book['cases']),754)
if __name__=='__main__':unittest.main()

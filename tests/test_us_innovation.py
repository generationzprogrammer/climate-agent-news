import json
import sys
import unittest
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from collect_arpae_projects import complete_records, parse_response
from select_us_innovation_projects import candidates
from import_us_innovation_projects import read_reviews
from climate_agent.innovation_metrics import validate_profile
from climate_agent.innovation_cases import write_innovation_cases


class USInnovationTests(unittest.TestCase):
    def test_interrupted_last_node_never_recovers_partial_facts(self):
        node = {'type':'node--project','attributes':{'drupal_internal__nid':'123','fields':{'title':'Complete'}}}
        text = '{"jsonapi":{},"data":['+json.dumps(node)+',{"type":"node--project","attributes":'
        self.assertEqual(complete_records(text), [node])
        with self.assertRaises(ValueError):
            parse_response(text)
        self.assertEqual(complete_records('{"data":[{}]}'), [])

    def test_public_us_records_have_named_partners_and_currency_boundary(self):
        book = json.loads((ROOT/'config/open_innovation_us_projects.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(book['cases']),150)
        self.assertEqual(len({c['project']['official_id'] for c in book['cases']}),len(book['cases']))
        sources = {s['id']:s for s in book['sources']}
        for c in book['cases']:
            validate_profile(c)
            self.assertEqual(c['countries'],['US'])
            self.assertEqual(c['scope'],'national')
            self.assertEqual(c['project']['funding_basis'],'listed_ARPAE_award_not_actual_expenditure')
            self.assertNotIn('eu_grant_eur',c['project'])
            self.assertTrue(all(v['score'] is None and v['raw'] is None for v in c['profile'].values()))
            self.assertGreaterEqual(len(c['participants']),2)
            self.assertEqual(c['participants'][0]['country'],'US')
            self.assertTrue(all(p['country'] is None and p['type'] is None for p in c['participants'][1:]))
            self.assertTrue(all(set(p)=={'id','name','country','type','role'} for p in c['participants']))
            self.assertGreaterEqual(len(c['summary']['zh']),45)
            self.assertGreaterEqual(len(c['mechanism']['zh']),15)
            s=sources[c['evidence'][0]['source_id']]
            self.assertTrue(s['url'].startswith('https://arpa-e.energy.gov/programs-and-initiatives/search-all-projects/'))
            self.assertEqual(len(s['snapshot_sha256']),64)
            self.assertTrue(s['fetched_at_utc'].endswith('+00:00'))

    def test_explicit_review_register_matches_imported_ids(self):
        reviews = read_reviews(ROOT/'config/innovation_us_review.txt')
        cases = json.loads((ROOT/'config/open_innovation_us_projects.json').read_text(encoding='utf-8'))['cases']
        self.assertEqual(set(reviews),{c['id'].removeprefix('oi_arpae_') for c in cases})
        omissions=json.loads((ROOT/'config/innovation_us_exclusions.json').read_text(encoding='utf-8'))['public_partner_omissions']
        self.assertTrue(all('partner_label' not in row and len(row['partner_label_sha256'])==64 for row in omissions))

    def test_next_day_export_preserves_us_and_prior_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'innovation_cases.json'
            first=write_innovation_cases(ROOT,output,[],today=date(2026,10,5))
            second=write_innovation_cases(ROOT,output,[],today=date(2026,10,6))
            expected=sum(len(json.loads((ROOT/'config'/name).read_text(encoding='utf-8'))['cases'])
                         for name in ('open_innovation_cases.json','open_innovation_projects.json',
                                      'open_innovation_us_projects.json','open_innovation_regional_cases.json',
                                      'open_innovation_coverage.json','open_innovation_expansion.json'))
            self.assertEqual(first['statistics']['cases'],expected)
        self.assertEqual(first['sources'],second['sources'])
        self.assertEqual(first['cases'],second['cases'])
        expected_us=sum('US' in c['countries'] for name in ('open_innovation_cases.json',
            'open_innovation_projects.json','open_innovation_us_projects.json',
            'open_innovation_regional_cases.json','open_innovation_coverage.json','open_innovation_expansion.json') for c in
            json.loads((ROOT/'config'/name).read_text(encoding='utf-8'))['cases'])
        self.assertEqual(sum('US' in c['countries'] for c in second['cases']),expected_us)
        self.assertEqual(second['updated_at'],'2026-10-06')

    def test_research_operator_is_not_misclassified_as_industry(self):
        row = {'attributes':{'drupal_internal__nid':'1','title':'Cooling technology',
            'fields':{'organization':[{'attributes':{'title':'University X'},'fields':{'type':[{'name':'University'}]}}],
                      'partner_organizations':[{'value':'Alliance for Sustainable Energy, LLC - NREL'}],
                      'project_description':'thermal research '*30,'state':'CA','status':'Active'}},
               '_snapshot':{}}
        accepted,excluded=candidates([row])
        self.assertEqual(accepted,[])
        self.assertEqual(excluded,{'no_named_science_industry_interface':1})


if __name__=='__main__':
    unittest.main()

import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import update_innovation_registries as registry
from climate_agent.innovation_cases import validate_casebook

class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book=json.loads((ROOT/'static/data/innovation_cases.json').read_text(encoding='utf-8'))
        cls.layer=json.loads((ROOT/'config/open_innovation_registries.json').read_text(encoding='utf-8'))
    def test_schema_and_at_least_thousand(self):
        codes={r['alpha2'] for r in json.loads((ROOT/'config/country_codes.json').read_text(encoding='utf-8'))['countries']}
        self.assertEqual(validate_casebook(self.book,codes)['status'],'passed')
        self.assertGreaterEqual(len(self.book['cases']),1000)
    def test_previous_release_preserved(self):
        previous=json.loads((ROOT/'analysis/innovation_research_20261014_r2/data/cases_nested.json').read_text(encoding='utf-8'))
        now={c['id']:c for c in self.book['cases']}
        for old in previous['cases']:
            self.assertIn(old['id'],now)
            for k in ['title','summary','actors','mechanism','observed','evidence','start_year','end_year']:
                self.assertEqual(old.get(k),now[old['id']].get(k),(old['id'],k))
    def test_country_balance_in_new_admission(self):
        counts={code:sum(c['countries']==[code] for c in self.layer['cases']) for code in ['US','CN','BR','AU','JP']}
        for code,n in counts.items():self.assertGreaterEqual(n,30,code)
        self.assertGreaterEqual(len({c['research_annotation']['country'] for c in self.layer['cases']}),20)
    def test_designation_is_not_founding(self):
        rows=[c for c in self.book['cases'] if c.get('registry_record',{}).get('designation_year')]
        self.assertEqual(len(rows),71)
        for c in rows:
            self.assertIsNone(c['timeline']['origin_year'])
            self.assertEqual(c['timeline']['events'][0]['kind'],'documented_activity')
    def test_currency_and_metrics_not_mixed(self):
        for c in self.book['cases']:
            if c.get('project',{}).get('source_type')=='AU_CRCP':
                self.assertGreater(c['project']['registered_grant_aud'],0)
                self.assertNotIn('eu_grant_eur',c['project'])
                self.assertIsNone(c['profile']['funding']['score'])
    def test_no_personal_contacts_in_registry(self):
        for c in self.layer['cases']:
            self.assertNotRegex(json.dumps(c,ensure_ascii=False),r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
            self.assertIn('registry_record',c)
    def test_complete_african_geography(self):
        from climate_agent.innovation_analysis import COUNTRY_REGION
        for code in ['BJ','BF','DJ','GM','GN','NE','TG','MZ','ZM']:self.assertEqual(COUNTRY_REGION[code],'africa')
    def test_failure_never_deletes_cases(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'static/data').mkdir(parents=True);(root/'config').mkdir();(root/'data').mkdir()
            (root/'static/data/innovation_cases.json').write_text(json.dumps(self.book),encoding='utf-8')
            path=root/'config/open_innovation_registries.json';path.write_text(json.dumps(self.layer),encoding='utf-8')
            with patch.object(registry,'ROOT',root),patch.object(registry,'OUT',path),patch.object(registry,'load_candidates',return_value=([],[{'status':'failed'}])):
                with self.assertRaisesRegex(RuntimeError,'unavailable'):registry.run()
            result=json.loads(path.read_text(encoding='utf-8'));self.assertEqual(self.layer['cases'],result['cases'])
    def test_duplicate_run_no_new_admissions(self):
        r=self.layer['cases'][0]['registry_record']
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'static/data').mkdir(parents=True);(root/'config').mkdir();(root/'data').mkdir()
            (root/'static/data/innovation_cases.json').write_text(json.dumps(self.book),encoding='utf-8')
            path=root/'config/open_innovation_registries.json';path.write_text(json.dumps(self.layer),encoding='utf-8')
            with patch.object(registry,'ROOT',root),patch.object(registry,'OUT',path),patch.object(registry,'load_candidates',return_value=([r],[{'status':'ok'}])):
                audit=registry.run()
            self.assertEqual(audit['added'],0);self.assertEqual(audit['candidate_decisions']['already_present'],1)
if __name__=='__main__':unittest.main()

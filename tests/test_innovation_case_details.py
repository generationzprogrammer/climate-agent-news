import copy
import json
import unittest
from pathlib import Path
from climate_agent.innovation_case_details import apply_case_details

ROOT=Path(__file__).resolve().parents[1]
class CaseDetailTests(unittest.TestCase):
    def test_additive_idempotent_evidence_and_bilingual_fields(self):
        b=json.loads((ROOT/'config/open_innovation_registries.json').read_text(encoding='utf-8'))
        old=copy.deepcopy(b['cases']);apply_case_details(b,ROOT)
        first=copy.deepcopy(b);apply_case_details(b,ROOT);self.assertEqual(first,b)
        self.assertEqual(len(b['cases']),len(old))
        for a,c in zip(old,b['cases']):
            for key in a:
                if key!='evidence':self.assertEqual(c[key],a[key])
            self.assertTrue(all(e in c['evidence'] for e in a['evidence']))
        details=[c['case_detail'] for c in b['cases'] if c.get('case_detail')]
        self.assertEqual(len(details),6)
        self.assertEqual(len({s['url'] for s in b['sources']}),len(b['sources']))
        sources={s['id'] for s in b['sources']}
        for d in details:
            self.assertIn(d['source_id'],sources)
            self.assertNotIn('@',json.dumps(d))
            for f in d['facts']:
                self.assertTrue(f['locator']);self.assertIn(f['source_id'],sources)
                self.assertIn(f['status'],['research_scope','reported_facility'])

    def test_unknown_case_rejected_before_mutation(self):
        b={'cases':[],'sources':[]};old=copy.deepcopy(b)
        with self.assertRaises(ValueError):apply_case_details(b,ROOT)
        self.assertEqual(b,old)

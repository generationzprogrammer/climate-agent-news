import copy
import json
import unittest
from pathlib import Path
from climate_agent.innovation_review import diagnostic_tables, normalized_title

ROOT=Path(__file__).resolve().parents[1]

class ReviewerDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book=json.loads((ROOT/'static/data/innovation_cases.json').read_text(encoding='utf-8'))

    def test_previous_release_facts_are_preserved(self):
        old=json.loads((ROOT/'analysis/innovation_research_20261014/data/cases_nested.json').read_text(encoding='utf-8'))
        current={c['id']:c for c in self.book['cases']}
        dynamic={'research_annotation','timeline','organization_tags','organization_participant_tags','organization_basis','developments'}
        for case in old['cases']:
            self.assertIn(case['id'],current)
            for field,value in case.items():
                if field not in dynamic:self.assertEqual(current[case['id']][field],value,(case['id'],field))

    def test_no_normalised_or_project_identifier_duplicates(self):
        audit=diagnostic_tables(self.book)['audit']
        self.assertEqual(audit['duplicate_normalized_titles'],[])
        self.assertEqual(audit['duplicate_official_project_keys'],[])
        self.assertEqual(audit['sources_not_linked_to_case_event_or_profile'],[])
        self.assertEqual(normalized_title(' A—B '),'a b')

    def test_coverage_reconciles_at_record_level(self):
        ds=diagnostic_tables(self.book)
        rows={r['group']:r for r in ds['quality'] if r['dimension']=='grain'}
        self.assertEqual(sum(r['cases'] for r in rows.values()),len(self.book['cases']))
        self.assertLess(rows['platform']['origin_coverage'],1)
        self.assertEqual(rows['project']['origin_coverage'],1)
        self.assertGreaterEqual(rows['platform']['supported_origins'],46)

    def test_sensitivity_denominators_and_ranges(self):
        ds=diagnostic_tables(self.book)
        keys={(r['grain'],r['omitted_cohort']) for r in ds['model_sensitivity']}
        for grain,omitted in keys:
            rows=[r for r in ds['model_sensitivity'] if r['grain']==grain and r['omitted_cohort']==omitted]
            self.assertEqual(sum(r['count'] for r in rows),rows[0]['denominator'])
            if rows[0]['denominator']:self.assertAlmostEqual(sum(r['share'] for r in rows),1)
            else:self.assertTrue(all(r['share'] is None for r in rows))
        for row in ds['factor_sensitivity']:
            self.assertIn('not_confidence_interval',row['range_type'])
            for value in row['source_cohort_results']:
                if value['jaccard'] is not None:self.assertAlmostEqual(value['jaccard'],value['count']/value['union'])

    def test_evidence_ledger_resolves_and_is_not_independent_validation(self):
        ledger=json.loads((ROOT/'config/innovation_peer_evidence.json').read_text(encoding='utf-8'))
        ids={c['id'] for c in self.book['cases']};sources={s['id']:s for s in self.book['sources']}
        self.assertEqual(len(ledger['claims']),25)
        for row in ledger['claims']:
            self.assertIn(row['case_id'],ids)
            self.assertEqual(row['source_url'],sources[row['source_id']]['url'])
            self.assertFalse(row['independent_validation'])
            self.assertTrue(row['source_locator'])

if __name__=='__main__':unittest.main()

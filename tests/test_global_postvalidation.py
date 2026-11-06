"""Regression checks for contextual country aliases and policy evidence."""
import unittest
from climate_agent.governance_taxonomy_v2 import label
from postvalidate_global_labels import enrich


class PostvalidationTests(unittest.TestCase):
    def doc(self, body, url='https://example.org/article'):
        return enrich({'title': 'Climate update', 'source_text': body, 'url': url,
                       'labels': label('Climate update', body)})

    def test_jersey_official_context(self):
        d = self.doc('Jersey has extended its climate commitments.', 'https://www.gov.je/News/a')
        self.assertIn('JE', d['labels']['country_mentions'])
        for e in d['labels']['evidence']:
            self.assertEqual(d[e['field']][e['start']:e['end']], e['quote'])

    def test_new_jersey_not_island(self):
        d = self.doc('New Jersey announced a climate plan.')
        self.assertNotIn('JE', d['labels']['country_mentions'])

    def test_french_territory_alias(self):
        d = self.doc('Saint-Pierre et Miquelon faces rising sea levels.')
        self.assertIn('PM', d['labels']['country_mentions'])

    def test_policy_coherence_requires_climate_paragraph(self):
        d = self.doc('Policy coherence is needed for tax administration.\n\nClimate news follows.')
        self.assertFalse(any(e.get('method') == 'policy_coherence_with_climate_anchor_in_same_paragraph'
                             for e in d['labels']['evidence']))

    def test_policy_coherence_climate_evidence(self):
        d = self.doc('Policy coherence is necessary to achieve net-zero emissions.')
        self.assertIn('G02.06', d['labels']['subcategory_mentions'])


if __name__ == '__main__':
    unittest.main()

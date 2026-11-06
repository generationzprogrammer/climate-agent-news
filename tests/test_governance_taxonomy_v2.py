import unittest
from climate_agent.governance_taxonomy_v2 import dictionary,label

class GovernanceTaxonomyTests(unittest.TestCase):
 def test_counts(self):
  d=dictionary(); self.assertEqual(len(d['parents']),14); self.assertEqual(len(d['subcategories']),83)
  self.assertEqual(sum(x['origin'].startswith('authorized') for x in d['subcategories']),9)
 def test_evidence_and_overlap(self):
  title='EU carbon border adjustment'; body='China reviewed renewable energy. Article 6.4 concerns carbon credits.'
  result=label(title,body)
  self.assertIn('G07.02',result['subcategory_mentions']); self.assertIn('G11.03',result['subcategory_mentions'])
  for e in result['evidence']:
   self.assertEqual({'title':title,'source_text':body}[e['field']][e['start']:e['end']],e['quote'])
 def test_not_developing_china(self):
  result=label('欧盟将对发展中国家提供气候资金','资金将用于适应气候变化。')
  self.assertNotIn('CN',result['country_mentions'])
 def test_territories(self):
  result=label('Trinidad and Tobago energy policy','Hong Kong reviewed emissions. The Government of Jersey adopted a climate plan.')
  self.assertTrue({'TT','HK','JE'}<=set(result['country_mentions']))
 def test_no_invented_labels(self):
  self.assertIsNone(label('A cooking recipe','Mix flour with water.')['primary_subcategory'])
if __name__=='__main__': unittest.main()

import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from expansion_quality import eligible
from postvalidate_global_labels import enrich
from climate_agent.governance_taxonomy_v2 import label
class ExpansionQualityTests(unittest.TestCase):
 def test_source_tail_is_not_missing_prose(self):
  d={'source_text':'A complete climate report explains how policy changes affect emissions and describes the verified findings.\n\nRead more: another article','quality_flags':['last_block_needs_review'],'source_block_coverage':1,'last_block_present':True}
  good,review,flags=eligible(d);self.assertTrue(good);self.assertFalse(flags);self.assertFalse(review['text_modified'])
 def test_missing_source_blocks_remain_review(self):
  d={'source_text':'This article is incomplete and stops','quality_flags':['source_blocks_missing'],'source_block_coverage':.5,'last_block_present':False}
  self.assertFalse(eligible(d)[0])
 def test_contextual_policy_coherence(self):
  d={'title':'Government must improve policy coherence on net zero','source_text':'The climate plan needs coordination.'};d['labels']=label(d['title'],d['source_text']);enrich(d)
  self.assertIn('G02.06',d['labels']['subcategory_mentions'])
  for e in d['labels']['evidence']:self.assertEqual(d[e['field']][e['start']:e['end']],e['quote'])
 def test_no_generic_policy_forcing(self):
  d={'title':'Policy coherence in education','source_text':'The school programme has changed.'};d['labels']=label(d['title'],d['source_text']);enrich(d)
  self.assertNotIn('G02.06',d['labels']['subcategory_mentions'])
 def test_territory_alias_evidence(self):
  d={'title':'Solar energy in Åland and Pitcairn','source_text':'Palestinian renewable energy projects are expanding.'};d['labels']=label(d['title'],d['source_text']);enrich(d)
  self.assertTrue({'AX','PN','PS'}<=set(d['labels']['country_mentions']))
if __name__=='__main__':unittest.main()

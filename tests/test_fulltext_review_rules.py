import sys
import unittest
import importlib.util
from pathlib import Path
if importlib.util.find_spec('trafilatura') is None:
    raise unittest.SkipTest('optional fulltext environment required')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import fulltext_review_rules as r

class ReviewTests(unittest.TestCase):
    def doc(self,ending):
        return {'source_text':'Intro.\n\n'+('The policies reduce emissions and provide support for public transport. '*3)+'\n\n'+ending,'completeness_flags':['last_block_needs_review'],'extraction_method':'semantic_article_dom','source_block_coverage':1,'first_block_present':True,'last_block_present':True}
    def test_reporting_credit(self): self.assertIsNotNone(r.review_terminal(self.doc('Reporting credit: ChavoBart Digital Media')))
    def test_doi(self): self.assertIsNotNone(r.review_terminal(self.doc('Citation:\n\nStudy (2025), doi:10.12345/abc123')))
    def test_incomplete_prose_not_promoted(self):
        d=self.doc('Reporting credit: Name'); d['source_text']=d['source_text'].replace('transport.','transport')
        self.assertIsNone(r.review_terminal(d))
    def test_unknown_tail_not_promoted(self): self.assertIsNone(r.review_terminal(self.doc('The policy will change next year if')))
    def test_missing_container_not_promoted(self):
        d=self.doc('Reporting credit: Name'); d['extraction_method']='trafilatura_recall'; self.assertIsNone(r.review_terminal(d))
    def test_known_branding(self): self.assertTrue(r.title_identity('我国碳市场发展 - 新华网','我国碳市场发展','GDELT','https://www.news.cn/a'))
    def test_unknown_domain_not_stripped(self): self.assertFalse(r.title_identity('我国碳市场发展 - 新华网','我国碳市场发展','GDELT','https://example.org/a'))
    def test_verified_nigeria_branding(self):
        self.assertTrue(r.title_identity('Transparency supports climate action - EnviroNews Nigeria','Transparency supports climate action - EnviroNews - latest environment news, climate change, renewable energy','EnviroNews Nigeria','https://www.environewsnigeria.com/a'))
    def test_numbers_preserved(self): self.assertFalse(r.title_identity('Targets 20 percent','Targets 30 percent','X','https://example.org/a'))
    def test_apostrophe_only(self): self.assertTrue(r.title_identity('Summer isnt breaking records','Summer isn’t breaking records','X','https://example.org/a'))
    def test_resolved_date_must_be_verified(self):
        import bulk_fulltext as b
        d={'title':'Climate policy funding','page_title':'Climate policy funding','source_text':'Climate news. '*100,'status':'candidate_complete','url':'https://example.org/a','date':'2025-01-01','resolved_identity':{'identity':{'date_check':'source_date_missing'}}}
        self.assertIn('resolved_publisher_date_unverified',b.quality(d)['quality_flags'])
        d['resolved_identity']['identity']['date_check']='within_31_days_of_rss_date'
        self.assertEqual(b.quality(d)['delivery_class'],'candidate_full_article')

if __name__=='__main__': unittest.main()

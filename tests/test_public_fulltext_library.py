import importlib.util
import sys
import unittest
from pathlib import Path
if importlib.util.find_spec('trafilatura') is None:
    raise unittest.SkipTest('optional fulltext environment required')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect_public_fulltext_library as lib

class LibraryTests(unittest.TestCase):
    def test_explicit_wire_attribution_filtered(self):
        self.assertTrue(lib.p.restricted_syndication('LONDON (Reuters) — A report.'))
        self.assertTrue(lib.p.restricted_syndication('NEW YORK (AP) — A report.'))
        self.assertFalse(lib.p.restricted_syndication('Researchers told Reuters about their results.'))
        posts=[{'content':{'rendered':'<p>NEW YORK (AP) — Original body.</p>'}}]
        self.assertEqual(lib.policy_filtered_posts(posts)[0]['content']['rendered'],'')
    def test_climate_headline(self):
        self.assertTrue(lib.relevance('COP30 climate finance negotiations','Public evidence.')[0])
    def test_energy_headline(self):
        self.assertTrue(lib.relevance('Solar power costs continue to fall','Public evidence.')[0])
    def test_unrelated_article_not_counted(self):
        self.assertFalse(lib.relevance('New frog species discovered','A detailed account of taxonomy. '*50)[0])
    def test_incidental_climate_mention_not_counted(self):
        self.assertFalse(lib.relevance('A new species','Researchers described the animal. '*30+' Climate change is also a threat.')[0])
    def test_multi_topic_body(self):
        self.assertTrue(lib.relevance('The year ahead','Climate policy, carbon markets and renewable energy are being debated.')[0])
    def fixture(self):
        title='Countries agree on new climate finance targets'
        row={'id':'one','url':'https://news.google.com/rss/articles/opaque','title':title+' - Climate Desk','date':'2025-01-01','source':'Climate Desk'}
        post={'link':'https://example.org/news','title':{'rendered':title},'date_gmt':'2025-01-02'}
        source={'source_id':'X','name':'Climate Desk','allowed_hosts':['example.org']}
        return row,post,source,{lib.normalized(title):[row]}
    def test_original_title_publisher_date_match(self):
        row,post,source,index=self.fixture()
        self.assertEqual(lib.matching_originals(post,source,{},index)[0]['id'],'one')
    def test_wrong_publisher_not_original(self):
        row,post,source,index=self.fixture(); row['source']='Different Publisher'
        self.assertEqual(lib.matching_originals(post,source,{},index),[])
    def test_wrong_year_not_original(self):
        row,post,source,index=self.fixture(); row['date']='2023-01-01'
        self.assertEqual(lib.matching_originals(post,source,{},index),[])

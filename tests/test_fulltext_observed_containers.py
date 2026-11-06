import importlib.util
import sys
import unittest
from pathlib import Path
if importlib.util.find_spec('trafilatura') is None:
    raise unittest.SkipTest('optional fulltext environment required')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import fulltext_pilot as p

class ContainerTests(unittest.TestCase):
    def test_physics_author_card_removed_but_license_retained(self):
        prose='Climate researchers examined energy and emissions trajectories. '*8
        markup='<html><title>Climate policy</title><article><p>'+prose+'</p><div class="author-card"><p>AUTHOR BIOGRAPHY</p></div><p>This article is republished under a Creative Commons license.</p></article></html>'
        text,_=p.extract(markup,'Climate policy','https://phys.org/news/example.html')
        self.assertNotIn('AUTHOR BIOGRAPHY',text)
        self.assertIn('Creative Commons license',text)
    def test_scitech_marketing_footer_removed(self):
        prose='Climate researchers examined energy and emissions trajectories. '*8
        markup='<html><title>Climate policy</title><article><p>'+prose+'</p><p><b>Never miss a breakthrough:</b> Join the newsletter.</p></article></html>'
        text,_=p.extract(markup,'Climate policy','https://scitechdaily.com/example/')
        self.assertNotIn('Never miss a breakthrough',text)
    def test_tagdiv_related_cards_excluded(self):
        prose='Climate policy supports clean energy and emissions reductions. '*8
        markup='<html><title>Climate policy</title><article><h1>Climate policy</h1><div class="tdb_single_content td-post-content"><p>'+prose+'</p></div><h3>RELATED DISTRACTION</h3></article></html>'
        text,checks=p.extract(markup,'Climate policy','https://carboncredits.com/example')
        self.assertNotIn('RELATED DISTRACTION',text)
        self.assertIn(prose.strip(),text)
        self.assertEqual(checks['extraction_method'],'semantic_article_dom')
    def test_govuk_semantic_body(self):
        prose='The government will implement its climate and energy commitments. '*8
        markup='<html><title>Climate policy</title><main><h1>Climate policy</h1><div class="gem-c-govspeak"><p>'+prose+'</p></div><p>RELATED DISTRACTION</p></main></html>'
        text,checks=p.extract(markup,'Climate policy','https://www.gov.uk/government/news/example')
        self.assertNotIn('RELATED DISTRACTION',text)
        self.assertEqual(checks['extraction_method'],'semantic_article_dom')

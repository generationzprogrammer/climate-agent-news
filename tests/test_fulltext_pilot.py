"""Offline integrity tests; no source site is contacted."""
import importlib.util
import pathlib
import unittest

if importlib.util.find_spec('trafilatura') is None:
    raise unittest.SkipTest('Optional fulltext pilot environment is not installed')

FILE = pathlib.Path(__file__).resolve().parents[1] / "scripts/fulltext_pilot.py"
SPEC = importlib.util.spec_from_file_location("fulltext_pilot", FILE)
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class FulltextPilotTests(unittest.TestCase):
    def test_mid_article_fundraising_does_not_truncate(self):
        tail='Important late policy evidence and the final emissions target. '*10
        page=self.article('<div class="icn-donate-block"><p>This story is funded by readers like you.</p><p>DONATION BOILERPLATE</p></div><p>'+tail+'</p>')
        text,_=pilot.extract(page,'Climate finance agreement','https://insideclimatenews.org/news/example',api=True)
        self.assertIn('Important late policy evidence',text)
        self.assertNotIn('DONATION BOILERPLATE',text)
    def test_unwrapped_interstitial_is_not_end_marker(self):
        page=self.article('<p>This story is funded by readers like you.</p><p>Later independent policy evidence must remain in the source text.</p>')
        text,_=pilot.extract(page,'Climate finance agreement','https://example.org/news',api=True)
        self.assertIn('Later independent policy evidence',text)
    def test_navigation_h1_does_not_hide_matching_og_headline(self):
        page=self.article().replace('<body>','<meta property="og:title" content="Climate finance agreement"><body><h1>News navigation</h1>')
        text,checks=pilot.extract(page,'Climate finance agreement','https://example.org/news')
        self.assertEqual(checks['page_title'],'Climate finance agreement')
        self.assertIn('Final conclusion.',text)
    def article(self, extra=""):
        return '<html><title>Climate finance agreement</title><body><h1>Climate finance agreement</h1><article><h2>Details</h2><p>' + 'Countries discussed their climate finance agreement and implementation timetable. ' * 10 + '</p><p>Short paragraph.</p><table><tr><td>2025</td><td>42 MW</td></tr></table><figure><figcaption>Wind farm near the coast.</figcaption></figure><p>Final conclusion.</p>' + extra + '</article><footer>DO NOT INCLUDE FOOTER</footer></body></html>'

    def test_preserves_whole_text_short_blocks_tables_captions(self):
        text, checks = pilot.extract(self.article(), 'Climate finance agreement', 'https://example.org/news', api=True)
        for value in ('Details', 'Short paragraph.', '42 MW', 'Wind farm near the coast.', 'Final conclusion.'):
            self.assertIn(value, text)
        self.assertNotIn('DO NOT INCLUDE FOOTER', text)
        self.assertEqual(checks['source_block_coverage'], 1)

    def test_no_excerpt_length_cap(self):
        content = self.article('<p>' + 'Renewable generation increased steadily. ' * 300 + '</p>')
        text, _ = pilot.extract(content, 'Climate finance agreement', 'https://example.org/news', api=True)
        self.assertGreater(len(text), 10000)

    def test_paywall_not_extracted(self):
        content = self.article().replace('<title>', '<script type="application/ld+json">{"isAccessibleForFree":false}</script><title>')
        with self.assertRaises(pilot.StopFetch) as cm:
            pilot.extract(content, 'Climate finance agreement', 'https://example.org/news')
        self.assertEqual(cm.exception.reason, 'declared_paywall')

    def test_hidden_registration_wall_body_not_extracted(self):
        with self.assertRaises(pilot.StopFetch) as cm:
            pilot.extract(self.article('<div id="mepr-paywall-block">Create an account</div>'), 'Climate finance agreement', 'https://example.org/news')
        self.assertEqual(cm.exception.reason, 'registration_wall_detected')

    def test_related_article_cards_excluded(self):
        text, _ = pilot.extract(self.article('<div data-current-post-id="1"><h2>More like this</h2><p>UNRELATED RECOMMENDATION</p></div>'), 'Climate finance agreement', 'https://example.org/news', api=True)
        self.assertNotIn('UNRELATED RECOMMENDATION', text)

    def test_inline_word_not_split(self):
        text, _ = pilot.extract(self.article('<p><span>E</span>urope reduced CO<sub>2</sub> emissions.</p>'), 'Climate finance agreement', 'https://example.org/news', api=True)
        self.assertIn('Europe reduced CO2 emissions.', text)

    def test_unclosed_navigation_cannot_delete_main_news(self):
        content='<html><title>Climate finance agreement</title><nav><div><main><article id="post-1"><h1>Climate finance agreement</h1><div itemprop="articleBody"><p>'+('Energy investment supports climate mitigation. '*30)+'</p></div></article></main></div></nav></html>'
        text,_=pilot.extract(content,'Climate finance agreement','https://example.org/news')
        self.assertIn('Energy investment supports climate mitigation.',text)

    def test_small_teaser_is_not_the_main_article(self):
        content=self.article().replace('<body>','<body><article>Teaser only.</article>')
        text,_=pilot.extract(content,'Climate finance agreement','https://example.org/news')
        self.assertIn('Final conclusion.',text)

    def test_title_mismatch(self):
        with self.assertRaises(pilot.StopFetch):
            pilot.extract(self.article(), 'Unrelated electric vehicles technology', 'https://example.org/news')

    def test_pagination_requires_review(self):
        _, checks = pilot.extract(self.article('<a href="?page=2" rel="next">Next page</a>'), 'Climate finance agreement', 'https://example.org/news', api=True)
        self.assertEqual(checks['status'], 'needs_completeness_review')

    def test_restricted_sources(self):
        self.assertTrue(pilot.restricted('https://www.reuters.com/world/article'))
        self.assertFalse(pilot.restricted('https://reuters.com.example.org/'))

    def test_wire_funding_footer_is_restricted(self):
        self.assertTrue(pilot.restricted_syndication('Climate news. AP is solely responsible for all content.'))
        self.assertFalse(pilot.restricted_syndication('The minister answered a question from the Associated Press.'))

    def test_xinhua_source_container(self):
        content='<html><title>我国碳市场发展</title><body><div>Navigation</div><span id="detailContent"><p>'+('能源转型推动经济发展，清洁能源投资持续增长。'*30)+'</p></span><div>Unrelated navigation</div></body></html>'
        text,checks=pilot.extract(content,'我国碳市场发展','https://www.news.cn/a')
        self.assertEqual(checks['extraction_method'],'semantic_article_dom')
        self.assertNotIn('Unrelated navigation',text)

    def test_bbc_external_accessibility_marker(self):
        content=self.article('<p>Final conclusion.<span class="visually-hidden">, external</span></p>')
        text,checks=pilot.extract(content,'Climate finance agreement','https://www.bbc.co.uk/news/articles/a')
        self.assertNotIn(', external',text)
        self.assertNotIn('last_block_needs_review',checks['completeness_flags'])

    def test_private_address_refused(self):
        fetcher = pilot.Fetcher()
        with self.assertRaises(pilot.StopFetch):
            fetcher.public('http://127.0.0.1/private', {'dns_seconds': 0})

    def test_malformed_url_rejected_before_request(self):
        fetcher=pilot.Fetcher()
        for url in ('https://example.org/bad path','https://example.org/\nnews','https://example.org:notaport/a'):
            with self.subTest(url=url),self.assertRaises(pilot.StopFetch):
                fetcher.public(url,{'dns_seconds':0})

    def test_robots_unavailable_is_not_allow(self):
        fetcher = pilot.Fetcher()
        fetcher.raw = lambda *a, **kw: (503, {}, b'Unavailable')
        with self.assertRaises(pilot.StopFetch):
            fetcher.robots('https://example.org/news', {'robots_seconds': 0})

    def test_probability_sample_80_stress_20(self):
        frame = [{'id': str(i), 'url': 'https://example.org/'+str(i), 'stratum': 'public_wordpress' if i<200 else 'google_wrapper', 'language':'en', 'publisher_homepage':None} for i in range(1000)]
        sample = pilot.select_sample(frame)
        self.assertEqual(len(sample), 100)
        self.assertEqual(sum(r['sample_group']=='representative' for r in sample), 80)
        self.assertEqual(len({r['id'] for r in sample}), 100)
        self.assertAlmostEqual(sum(r['design_weight'] for r in sample if r['sample_group']=='representative'),1000)


if __name__ == '__main__':
    unittest.main()

import unittest
from unittest.mock import patch
from climate_agent.collector import parse_feed
from climate_agent.publisher_links import public_url,resolve_publisher

TITLE='Government approves coastal adaptation funding programme'

class PublisherLinkTests(unittest.TestCase):
    def test_feed_keeps_the_publisher_homepage(self):
        xml=b'<rss><channel><item><title>News</title><link>https://news.google.com/a</link><source url="https://example.org">Publisher</source></item></channel></rss>'
        self.assertEqual(parse_feed(xml,'T')[0].publisher_homepage,'https://example.org')

    def test_only_an_actual_matching_publisher_link_is_returned(self):
        html=('<a href="/unrelated">Different topic</a><a href="/climate">'+TITLE+'</a>').encode()
        with patch('climate_agent.publisher_links.read_public',return_value=html):
            self.assertEqual(resolve_publisher(TITLE+' - Publisher','https://example.org'),'https://example.org/climate')
            self.assertIsNone(resolve_publisher('Entirely different article about electricity prices','https://example.org'))

    def test_only_advertised_feeds_are_followed(self):
        homepage=b'<link rel="alternate" type="application/rss+xml" href="/news.xml">'
        feed=('<rss><channel><item><title>'+TITLE+'</title><link>https://example.org/climate</link></item></channel></rss>').encode()
        with patch('climate_agent.publisher_links.read_public',side_effect=[homepage,feed]) as read:
            self.assertEqual(resolve_publisher(TITLE,'https://example.org'),'https://example.org/climate')
            self.assertEqual(read.call_args_list[1].args[0],'https://example.org/news.xml')

    def test_private_urls_are_rejected(self):
        for url in ['http://127.0.0.1/a','http://10.0.0.1','http://localhost/a','https://user:secret@example.org','file:///tmp/a']:
            self.assertFalse(public_url(url))

if __name__=='__main__':unittest.main()

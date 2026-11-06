import importlib.util
import sys
import unittest
from pathlib import Path
if importlib.util.find_spec('trafilatura') is None:
    raise unittest.SkipTest('optional acquisition environment required')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import bulk_fulltext as b

class BulkTests(unittest.TestCase):
    def test_tracking_key(self):
        self.assertEqual(b.key('https://example.org/a/?utm_source=x#r'),'https://example.org/a')
        self.assertNotEqual(b.key('https://example.org/a?id=1'),b.key('https://example.org/a?id=2'))
    def test_opaque_token_not_fabricated(self):
        self.assertIsNone(b.embedded_url('https://news.google.com/rss/articles/ABCDEF'))
    def test_literal_url(self):
        import base64
        token=base64.urlsafe_b64encode(b'\x08\x01https://example.org/article\x00').decode().rstrip('=')
        self.assertEqual(b.embedded_url('https://news.google.com/rss/articles/'+token),'https://example.org/article')
    def post(self):
        return {'link':'https://example.org/news','title':{'rendered':'Climate finance agreement'},'date_gmt':'2025-01-02T00:00:00','content':{'rendered':'<p>'+'Climate finance expanded with new agreements. '*25+'</p>','protected':False}}
    def row(self): return {'url':'https://example.org/news','title':'Climate finance agreement','date':'2025-01-02'}
    def test_batch_full_body(self):
        text,checks=b.accept_post(self.row(),self.post()); self.assertGreater(len(text),900); self.assertEqual(checks['identity']['date_check'],'within_31_days_of_rss_date')
    def test_mismatch_not_replacement(self):
        post=self.post(); post['link']='https://example.org/different'
        with self.assertRaises(b.p.StopFetch): b.accept_post(self.row(),post)
    def test_protected_content(self):
        post=self.post(); post['content']['protected']=True
        with self.assertRaises(b.p.StopFetch): b.accept_post(self.row(),post)
    def test_wrong_year(self):
        post=self.post(); post['date_gmt']='2024-01-02'
        with self.assertRaises(b.p.StopFetch): b.accept_post(self.row(),post)
    def test_video_not_counted_full_article(self):
        d={'title':'Wildfire in France – video','source_text':'x'*1000,'status':'candidate_complete'}
        self.assertEqual(b.quality(d)['delivery_class'],'review_or_other_text')
    def test_live_lead_not_counted_full_article(self):
        d={'title':'Security Council LIVE: Critical minerals','source_text':'x'*600,'status':'candidate_complete'}
        self.assertEqual(b.quality(d)['document_genre'],'live_page_excerpt')
    def gz_fetch(self,data,cap):
        import gzip
        from unittest.mock import Mock
        class Response:
            code=200
            headers={'Content-Encoding':'gzip'}
            position=0
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,n):
                out=gzip.compress(data)[self.position:self.position+n]
                self.position+=len(out)
                return out
        f=b.p.Fetcher(); f.public=Mock(); f.opener=Mock(); f.opener.open.return_value=Response()
        return f.raw('https://example.org/news',b.timing(),cap)
    def test_compressed_response(self):
        self.assertEqual(self.gz_fetch(b'original news '*100,4096)[2],b'original news '*100)
    def test_compression_bomb_size_bound(self):
        with self.assertRaises(b.p.StopFetch) as cm: self.gz_fetch(b'x'*10000,1000)
        self.assertEqual(cm.exception.reason,'decompressed_response_size_limit')

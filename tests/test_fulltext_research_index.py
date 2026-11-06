import importlib.util
import sys
import unittest
from pathlib import Path
if importlib.util.find_spec('trafilatura') is None:
    raise unittest.SkipTest('optional fulltext environment required')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_fulltext_research_index as r

class EvidenceTests(unittest.TestCase):
    def test_paragraph_offsets(self):
        text='北京 climate.\n\nSecond paragraph!\n\n最后一段。'
        spans=r.paragraph_spans(text)
        self.assertEqual([text[x['start']:x['end']] for x in spans],['北京 climate.','Second paragraph!','最后一段。'])
        self.assertTrue(all(r.p.digest(text[x['start']:x['end']].encode())==x['sha256'] for x in spans))
    def test_single_and_empty(self):
        self.assertEqual(r.paragraph_spans(''),[])
        self.assertEqual(len(r.paragraph_spans('A')),1)
    def test_trailing_whitespace_and_long_paragraph(self):
        text='  '+('climate '*20000)+'\n '
        spans=r.paragraph_spans(text)
        self.assertEqual(len(spans),1)
        self.assertEqual(text[spans[0]['start']:spans[0]['end']],text.strip())
    def test_multiple_blank_lines(self):
        text=' A\n\n\n  \n B \n\n '
        spans=r.paragraph_spans(text)
        self.assertEqual([text[x['start']:x['end']] for x in spans],['A','B'])
    def test_unicode_codepoint_offsets(self):
        text='🌍 climate\n\n能源'
        spans=r.paragraph_spans(text)
        self.assertEqual(text[spans[1]['start']:spans[1]['end']],'能源')
        self.assertEqual(spans[1]['start'],11)
    def test_normalization(self):
        self.assertEqual(r.normalized_hash('Climate\n change'),r.normalized_hash('CLIMATE change'))
        self.assertNotEqual(r.normalized_hash('10 tonnes'),r.normalized_hash('100 tonnes'))
    def test_unknown_timezone_not_invented(self):
        self.assertIsNone(r.utc_date({'date':'2025-01-01T09:00:00'}))
    def test_utc_conversion(self):
        self.assertEqual(r.utc_date({'date':'2025-01-01T09:00:00+08:00'}),'2025-01-01T01:00:00Z')
    def test_original_body_immutable(self):
        text='Climate policy and carbon markets. '*40
        doc={'id':'a','source_text':text,'text_sha256':r.p.digest(text.encode()),'title':'Climate policy','source':'Publisher','url':'https://example.org/a','delivery_class':'candidate_full_article'}
        out=r.record(doc,'original_recovery',{doc['text_sha256']:['original-1']})
        self.assertEqual(doc['source_text'],text)
        self.assertEqual(out['source_record_ids'],['original-1'])
        self.assertTrue(out['primary_research_candidate'])

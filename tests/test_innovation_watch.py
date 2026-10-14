import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch
from io import BytesIO
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('innovation_watch',ROOT/'scripts/update_innovation_watch.py')
watch=importlib.util.module_from_spec(spec);spec.loader.exec_module(watch)
class WatchTests(unittest.TestCase):
    def test_archive_records(self):self.assertEqual(watch.records({'records':[{'id':1}]}),[{'id':1}])
    def test_link_text_is_preserved(self):
        parser=watch.Links();parser.feed('<a href="/news/1">Research <b>collaboration</b></a>')
        self.assertEqual(parser.items,[('/news/1','Research collaboration')])
    def test_credentials_never_enter_candidates(self):
        for url in ['https://example.org/?token=secret','https://u:p@example.org/news','mailto:research@example.org']:
            self.assertFalse(watch.public_url(url))
        self.assertTrue(watch.public_url('https://example.org/news?id=123'))
    def test_empty_fetch_not_success(self):
        from email.message import Message
        response=BytesIO(b'');response.headers=Message()
        with patch.object(watch.request,'urlopen',return_value=response):
            with self.assertRaisesRegex(ValueError,'empty_response'):watch.fetch('https://example.org/')
if __name__=='__main__':unittest.main()

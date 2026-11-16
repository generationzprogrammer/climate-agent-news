import copy, json, os, sqlite3, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import daily_fulltext_v2 as d
import daily_fulltext_state as state
from prepare_daily_fulltext import local_day

class Model:
    base_url='https://dashscope.aliyuncs.com/compatible-mode/v1';model='fixture';calls=0
    def complete_json(self,prompt,payload):
        self.calls+=1
        return {'paragraphs':[{'id':p['id'],'text_zh':'这是用于验证分段完整性及数字保留的中文测试译文。'+p['text']} for p in payload['paragraphs']]}

class Fetcher:
    calls=0
    def get(self,url,timing):
        self.calls+=1
        return url,'html',b'html',{}
    def resolve(self,row,known,timing):return 'https://example.org/resolved','fixture'

class Tests(unittest.TestCase):
    def test_translation_cache_budget_and_alignment(self):
        with tempfile.TemporaryDirectory() as t:
            db=d.init(Path(t)/'state.sqlite'); m=Model();budget=[2]
            body='Investment in 2025 is 100 dollars.\n\nCarbon emissions declined by 20%.'
            translated=d.translated(db,body,m,budget)
            self.assertEqual(m.calls,1);self.assertEqual(budget,[1])
            self.assertEqual(d.translated(db,body,m,[0]),translated)
            self.assertEqual(len(translated.split('\n\n')),2);db.close()

    def test_segment_no_truncation(self):
        s=('Climate policy research with long paragraphs. '*200)+'\n\nThe final sentence.'
        self.assertEqual(''.join(d.segments(s)).replace(' ',''),s.replace('\n','').replace(' ',''))

    def test_bad_translation_not_cached(self):
        with tempfile.TemporaryDirectory() as t:
            db=d.init(Path(t)/'db');m=Model()
            with patch.object(m,'complete_json',return_value={'paragraphs':[{'id':'0','text_zh':'这里没有保留原文数字。'}]}):
                with self.assertRaisesRegex(ValueError,'numbers'):d.translated(db,'Investment is 999 dollars.',m,[1])
            with patch.object(m,'complete_json',return_value={'paragraphs':[]}):
                with self.assertRaisesRegex(ValueError,'alignment'):d.translated(db,'Investment is 999 dollars.',m,[1])
            self.assertEqual(db.execute('SELECT count(*) FROM ft_segments').fetchone()[0],0);db.close()

    def test_all_candidates_persist_target_and_rerun(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);inputfile=root/'input.json';fetch=Fetcher();m=Model()
            rows=[{'url':'https://example.org/'+str(i),'title':'Climate policy '+str(i)} for i in range(14)]
            inputfile.write_text(json.dumps(rows))
            def extract(html,title,url):return (('Climate policy transition and renewable electricity. '*25)+url+'.',{'completeness_flags':[]})
            with patch.object(d,'extract',side_effect=extract):
                a=d.run(inputfile,root/'out','2026-11-16',100,m,fetcher=fetch)
                self.assertTrue(a['target_met']);self.assertEqual(a['total'],14);self.assertEqual(a['selected'],12)
                first=m.calls; d.run(inputfile,root/'out','2026-11-16',100,m,fetcher=fetch)
                self.assertEqual(fetch.calls,14);self.assertEqual(m.calls,first)
                d.run(inputfile,root/'out','2026-11-17',100,m,fetcher=fetch)
                self.assertEqual(fetch.calls,14);self.assertEqual(m.calls,first)
            self.assertTrue((root/'out/2026-11-16.json').exists())

    def test_body_saved_when_api_unavailable(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'in.json';p.write_text(json.dumps([{'url':'https://example.org/a','title':'Climate policy'}]))
            m=Model()
            with patch.object(d,'extract',return_value=('Climate policy news. '*100,{'completeness_flags':[]})),patch.object(m,'complete_json',side_effect=d.Deferred('model_http_401')):
                report=d.run(p,root/'out','2026-11-16',100,m,fetcher=Fetcher())
            self.assertFalse(report['target_met'])
            row=json.loads((root/'out/2026-11-16.json').read_text('utf-8'))[0]
            self.assertTrue(row['source_text']);self.assertIsNone(row['fulltext_zh'])
            self.assertEqual(row['failure_reason'],'model_http_401')

    def test_incomplete_body_never_translated(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'in.json';p.write_text(json.dumps([{'url':'https://example.org/a','title':'Climate policy'}]));m=Model()
            with patch.object(d,'extract',return_value=('Climate policy. '*100,{'completeness_flags':['pagination']})):
                report=d.run(p,root/'out','2026-11-16',100,m,fetcher=Fetcher())
            self.assertEqual(m.calls,0);self.assertEqual(report['ready_unique'],0)

    def test_exact_duplicate_not_counted_as_two(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'in.json';p.write_text(json.dumps([{'url':'https://example.org/'+str(i),'title':'Climate'} for i in range(2)]));m=Model()
            with patch.object(d,'extract',return_value=('Climate policy. '*100,{'completeness_flags':[]})):
                report=d.run(p,root/'out','2026-11-16',100,m,fetcher=Fetcher())
            self.assertEqual(report['ready_unique'],1)

    def test_url_and_day(self):
        self.assertEqual(d.clean_url('https://example.org/a?utm_source=x#anchor'),'https://example.org/a')
        with self.assertRaises(ValueError):d.clean_url('https://example.org/?api_key=private')
        self.assertEqual(local_day('2026-11-15T18:00:00Z'),'2026-11-16')
        self.assertIsNone(local_day('2026-11-16'))

    def test_encrypted_checkpoint_roundtrip_and_wrong_key(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'DAILY_FULLTEXT_STORAGE_KEY':'test-only-key-'*4}):
            root=Path(t)/'source';db=d.init(root/'daily_fulltext.sqlite');db.close()
            d.atomic_json(root/'2026-11-16.json',[{'source_text':'private original'}])
            dest=Path(t)/'archive.fulltext.enc';state.seal(root,dest)
            self.assertNotIn(b'private original',dest.read_bytes())
            state.unseal(dest,Path(t)/'restored')
            self.assertEqual((Path(t)/'restored/2026-11-16.json').read_bytes(),(root/'2026-11-16.json').read_bytes())
            with patch.dict(os.environ,{'DAILY_FULLTEXT_STORAGE_KEY':'different-test-key-'*3}):
                with self.assertRaises(Exception):state.unseal(dest,Path(t)/'bad')

    def test_model_budget_counts_attempts_before_network(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'DAILY_FULLTEXT_API_KEY':'test-not-real'}):
            db=d.init(Path(t)/'db');m=d.BailianModel(db,max_requests=0)
            with patch.object(m.opener,'open') as request:
                with self.assertRaises(d.Deferred):m.complete_json('test',{})
                request.assert_not_called()
            db.close()

if __name__=='__main__':unittest.main()

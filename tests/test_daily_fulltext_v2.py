import copy, json, os, sqlite3, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import daily_fulltext_v2 as d
import daily_fulltext_state as state
from prepare_daily_fulltext import local_day, prepare
from daily_evidence import numbers, nonprose, PublisherRecovery

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
                with self.assertRaisesRegex(ValueError,'numbers'):d.translated(db,'Investment is 999 dollars.',m,[2])
            with patch.object(m,'complete_json',return_value={'paragraphs':[]}):
                with self.assertRaisesRegex(ValueError,'alignment'):d.translated(db,'Investment is 999 dollars.',m,[2])
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

    def test_invalid_batch_repaired_once(self):
        with tempfile.TemporaryDirectory() as t:
            db=d.init(Path(t)/'db');m=Model();budget=[2]
            good={'paragraphs':[{'id':'0','text_zh':'这项政策规定投资金额为999美元。'}]}
            with patch.object(m,'complete_json',side_effect=[{'paragraphs':[]},good]) as call:
                self.assertIn('999',d.translated(db,'Investment is 999 dollars.',m,budget))
                self.assertEqual(call.call_count,2)
            db.close()

    def test_summary_fallback_separate_and_upgrades_to_fulltext(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'in.json'
            evidence='The government announced new climate policy and funding for renewable electricity. '*15
            text='政府公布气候政策，提出支持可再生能源电力发展，并明确通过资金安排推动相关工作。'*8
            p.write_text(json.dumps([{'url':'https://example.org/a','title':'Climate policy','source_summary':evidence}]))
            m=Model()
            with patch.object(Fetcher,'get',side_effect=d.StopFetch('http_403')),patch.object(m,'complete_json',return_value={'claims':[{'text_zh':text,'evidence':evidence[:400]}]}):
                report=d.run(p,root/'out','2026-11-16',10,m,target=1,fetcher=Fetcher())
            self.assertTrue(report['target_met']);self.assertEqual(report['fulltext_ready_unique'],0)
            row=json.loads((root/'out/2026-11-16.selected.json').read_text('utf-8'))[0]
            self.assertEqual(row['content_mode'],'summary');self.assertIsNone(row['source_text']);self.assertIsNone(row['fulltext_zh'])
            self.assertEqual(row['status'],'blocked');self.assertEqual(report['pending_total'],1)
            db=d.init(root/'out/daily_fulltext.sqlite')
            db.execute("UPDATE ft_articles SET body=?,body_sha=?,zh=?,status='translated'",(evidence,d.digest(evidence),'完整译文'))
            db.commit();r=d.export_result(db,root/'out','2026-11-16',1);db.close()
            self.assertEqual(r['fulltext_ready_unique'],1);self.assertEqual(r['summary_ready_unique'],0)

    def test_summary_refuses_short_source_and_fake_quotes(self):
        m=Model();job={'metadata':json.dumps({'source_summary':'Only a headline.'}),'body':None,'title':'Climate'}
        with self.assertRaisesRegex(ValueError,'insufficient'):d.fallback_summary(job,m,[2])
        self.assertEqual(m.calls,0)
        job['body']='Verified climate policy details. '*40
        with patch.object(m,'complete_json',return_value={'claims':[{'text_zh':'气候政策'*100,'evidence':'This quotation does not occur in the source.'}]}):
            with self.assertRaisesRegex(ValueError,'evidence_mismatch'):d.fallback_summary(job,m,[2])

    def test_ingest_refreshes_evidence_preserving_old_summary(self):
        with tempfile.TemporaryDirectory() as t:
            db=d.init(Path(t)/'db');rows=[{'url':'https://example.org/a','title':'Climate'}]
            d.ingest(db,rows,'2026-11-16')
            db.execute('UPDATE ft_articles SET metadata=?',(json.dumps({'summary_zh':'已验证摘要'}),));db.commit()
            rows[0]['source_summary']='New evidence';d.ingest(db,rows,'2026-11-16')
            meta=json.loads(db.execute('SELECT metadata FROM ft_articles').fetchone()[0]);db.close()
            self.assertEqual(meta['source_summary'],'New evidence');self.assertEqual(meta['summary_zh'],'已验证摘要')

    def test_prepare_preserves_original_rss_summary(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'data').mkdir();db=sqlite3.connect(root/'data/climate.db')
            db.executescript('CREATE TABLE sources(source_id TEXT,name TEXT); CREATE TABLE articles(source_id TEXT,relevance_score INTEGER,published_at_utc TEXT,canonical_url TEXT,summary_source TEXT,metadata_json TEXT,topics_json TEXT,title TEXT);')
            db.execute('INSERT INTO sources VALUES(?,?)',('s','Publisher'))
            db.execute('INSERT INTO articles VALUES(?,?,?,?,?,?,?,?)',('s',90,'2026-11-16T10:00:00Z','https://example.org/a','Original RSS evidence','{}','[]','Climate'));db.commit();db.close()
            self.assertEqual(prepare(root,'2026-11-16')[0]['source_summary'],'Original RSS evidence')

    def test_short_headings_are_not_incomplete_translation(self):
        batch=[{'id':'0','text':'Adaptation','key':'fixture'}]
        self.assertEqual(d.checked_batch(batch,{'paragraphs':[{'id':'0','text_zh':'适应'}]})[0][1],'适应')
        self.assertTrue(nonprose('Jane Smith'))
        self.assertFalse(nonprose('Investment is 999 dollars.'))

    def test_current_archive_records_are_reused_without_old_news(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'data').mkdir()
            records=[{'canonical_url':'https://example.org/'+str(i),'published_at':date,
                      'relevance_score':90,'title_original':'Climate policy','summary_source':'Raw publisher excerpt'}
                     for i,date in enumerate(['2026-11-16T10:00:00Z','2026-11-14T10:00:00Z'])]
            (root/'data/news_archive.json').write_text(json.dumps({'records':records}))
            result=prepare(root,'2026-11-16')
            self.assertEqual(len(result),1);self.assertEqual(result[0]['source_summary'],'Raw publisher excerpt')

    def test_cop_and_month_numbers_are_source_grounded(self):
        self.assertTrue(numbers('第31届会议于11月16日召开').issubset(numbers('COP31 meets on November 16')))
        self.assertFalse(numbers('第32届会议').issubset(numbers('COP31 meets on November 16')))

    def test_summary_uses_evidence_ids_without_model_retyping(self):
        m=Model();body='The government announced support for renewable electricity. '*20
        job={'metadata':'{}','body':body,'title':'Climate policy'}
        text='政府公布气候政策，提出支持可再生能源电力发展，并明确通过资金安排推动相关工作。'*8
        with patch.object(m,'complete_json',return_value={'claims':[{'text_zh':text,'evidence_ids':['E1']}]}):
            result=d.fallback_summary(job,m,[2])
        self.assertIn(result['summary_evidence'][0]['evidence'],body)
        with patch.object(m,'complete_json',return_value={'claims':[{'text_zh':text,'evidence_ids':['INVALID']}]}):
            with self.assertRaisesRegex(ValueError,'evidence_mismatch'):d.fallback_summary(job,m,[2])

    def test_publisher_recovery_reuses_bounded_public_resolver(self):
        fetch=Fetcher();recovery=PublisherRecovery(fetch,0)
        with patch('daily_evidence.discover_publisher',return_value=[{'publisher_url':'https://example.org/story'}]) as discover:
            result=recovery.resolve('Original headline',{'publisher_homepage':'https://example.org','publisher_name':'Publisher'}, {})
            self.assertEqual(result,'https://example.org/story')
            self.assertEqual(discover.call_args.args[0]['source'],'Publisher')

if __name__=='__main__':unittest.main()

import hashlib,json,os,tempfile,unittest,urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from climate_agent.research_archives import parse_archive_post,text_of
from climate_agent.research_translation import chunks,numeric_values,valid_translation,_tasks,apply_translations,translate_corpus
from climate_agent.research import make_text_record,save_jsonl,load_jsonl,write_research
from climate_agent.site_metrics import write_site_metrics

TEXT='The United States approved $2 billion in climate adaptation funding. The programme supports coastal flood protection and warning systems. Communities will receive funding in 2027.'
ZH='美国批准了20亿美元的气候适应资金。该计划支持沿海洪水防护和预警系统。社区将在2027年获得资金。'
SOURCE={'source_id':'T','name':'Fixture','homepage':'https://example.org','allowed_hosts':['example.org']}
def post():return {'link':'https://example.org/climate','date_gmt':'2026-01-01T00:00:00','title':{'rendered':'US climate funding approved'},'excerpt':{'rendered':'<p>'+TEXT+'</p>'},'content':{'rendered':TEXT}}
def record():return make_text_record({'canonical_url':'https://example.org/climate','title_original':'US climate funding approved','published_at_utc':'2026-01-01T00:00:00+00:00','source_name':'Fixture','language':'en'},TEXT,'source_excerpt')

class ResearchExpansionTests(unittest.TestCase):
    def test_publisher_api_preserves_actual_excerpt(self):
        article,reason=parse_archive_post(post(),SOURCE)
        self.assertIsNone(reason);self.assertEqual(article.summary_from_source,TEXT)
        self.assertEqual(article.extraction_method,'public_wordpress_excerpt')
    def test_publisher_api_rejects_wrong_host_and_nonclimate(self):
        p=post();p['link']='https://malicious.example/a'
        self.assertEqual(parse_archive_post(p,SOURCE)[1],'unexpected_host')
        p=post();p['title']['rendered']='Local transport';p['excerpt']['rendered']='Regular municipal information. '*20;p['content']['rendered']=''
        self.assertEqual(parse_archive_post(p,SOURCE)[1],'outside_climate_scope')
        p['content']['rendered']='A short local report. '*80+' Climate change is discussed in a related article.'
        self.assertEqual(parse_archive_post(p,SOURCE)[1],'outside_climate_scope')
    def test_gzip_named_jsonl_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'audit.jsonl.gz';save_jsonl(path,[{'id':'safe'}])
            self.assertEqual(path.read_bytes()[:2],b'\x1f\x8b');self.assertEqual(load_jsonl(path),[{'id':'safe'}])
    def test_missing_or_future_date_rejected(self):
        p=post();p['date_gmt']=None
        self.assertEqual(parse_archive_post(p,SOURCE)[1],'missing_utc_date')
        p['date_gmt']='2099-01-01T00:00:00'
        self.assertEqual(parse_archive_post(p,SOURCE)[1],'future_date')
    def test_html_cleanup_removes_scripts_and_signup(self):
        self.assertEqual(text_of('<script>bad</script><aside>subscribe</aside><p>Climate &amp; energy</p>'),'Climate & energy')
    def test_chunking_does_not_drop_source_characters(self):
        text=TEXT*30;self.assertEqual(''.join(chunks(text)),text)
        self.assertLessEqual(max(map(len,chunks(text))),1200)
    def test_numeric_magnitudes_and_missing_fact_guard(self):
        self.assertEqual(numeric_values('2 billion'),numeric_values('20亿美元'))
        self.assertTrue(valid_translation(TEXT,ZH,'zh'))
        self.assertFalse(valid_translation(TEXT,ZH.replace('2027','2028'),'zh'))
    def test_translation_keeps_english_original_and_is_cached(self):
        row=record();tasks,expected=_tasks([row],{});task=tasks[0]
        cache={task['id']:{'text_zh':ZH,'title_zh':'美国批准气候适应资金','model':'fixture','translated_at':'2026-11-02T00:00:00Z'}}
        self.assertEqual(apply_translations([row],cache,expected),1)
        self.assertEqual(row['source_text'],TEXT);self.assertEqual(row['source_text_en'],TEXT)
        self.assertEqual(row['source_text_zh'],ZH);self.assertFalse(_tasks([row],cache)[0])
    def test_source_change_invalidates_cache(self):
        row=record();tasks,_=_tasks([row],{});cache={tasks[0]['id']:True}
        row['source_text']+=' More evidence.';row['text_sha256']=hashlib.sha256(row['source_text'].encode()).hexdigest()
        self.assertTrue(_tasks([row],cache)[0])
    def test_unverified_paid_backend_is_not_used_for_bulk(self):
        model=SimpleNamespace(base_url='https://paid.example',model='unknown')
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(translate_corpus(folder,model)['status'],'disabled')
    def test_429_stops_and_original_is_preserved(self):
        class Model:
            base_url='https://generativelanguage.googleapis.com/v1beta/openai';model='gemini-3.5-flash-lite';timeout=1
            def complete_json(self,*args):raise urllib.error.HTTPError('https://example.org',429,'quota',{},None)
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{},clear=False):
            root=Path(folder);save_jsonl(root/'data/research_texts.jsonl',[record()])
            result=translate_corpus(root,Model(),max_requests=20)
            self.assertEqual(result['batches_completed'],1);self.assertEqual(result['pending_records'],1)
            self.assertEqual(load_jsonl(root/'data/research_texts.jsonl')[0]['source_text'],TEXT)
    def test_list_model_response_is_accepted_without_crashing(self):
        class Model:
            base_url='https://generativelanguage.googleapis.com/v1beta/openai';model='gemini-3.5-flash-lite';timeout=1
            def complete_json(self,system,payload):return [{'id':r['id'],'title_zh':'美国批准气候适应资金','text_zh':ZH} for r in payload['items']]
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{},clear=False):
            root=Path(folder);save_jsonl(root/'data/research_texts.jsonl',[record()])
            result=translate_corpus(root,Model(),max_requests=1)
            self.assertEqual(result['bilingual_ready'],1)
    def test_invalid_response_shape_stays_pending(self):
        class Model:
            base_url='https://generativelanguage.googleapis.com/v1beta/openai';model='gemini-3.5-flash-lite';timeout=1
            def complete_json(self,*args):return 'invalid'
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{},clear=False):
            root=Path(folder);save_jsonl(root/'data/research_texts.jsonl',[record()])
            self.assertEqual(translate_corpus(root,Model(),max_requests=1)['pending_records'],1)
    def test_metric_counts_real_texts_not_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);save_jsonl(root/'data/research_texts.jsonl',[record()])
            result=write_site_metrics(root/'data/climate_text_corpus.jsonl',root/'data/visitor_history.json',root/'site/metrics.json')
            self.assertEqual(result['archive_cumulative'][-1]['value'],1)
            self.assertEqual(result['visitor_metric'],'page_views')

if __name__=='__main__':unittest.main()

import copy
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from climate_agent.stance_pilot import build_pilot, digest, evidence_span, validate_assertion, write_stance_pilot, update_candidates

ROOT=Path(__file__).resolve().parents[1]

class StancePilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book=json.loads((ROOT/'config/stance_pilot.json').read_text(encoding='utf-8'))
        cls.registry=json.loads((ROOT/'data/stance_evidence.json').read_text(encoding='utf-8'))
        cls.sources={s['id']:s for s in cls.registry['sources']}
        cls.sample=copy.deepcopy(cls.registry['assertions'][0])

    def test_real_registry_has_exact_evidence_and_three_topics_seven_actors(self):
        payload=build_pilot(ROOT)
        self.assertEqual(len(payload['topics']),3)
        self.assertEqual(len(payload['actors']),7)
        self.assertTrue({'CN','US','EU'}<={a['id'] for a in payload['actors']})
        self.assertEqual(payload['statistics']['assertions'],21)
        self.assertEqual(len(payload['cells']),63)
        self.assertTrue(any(c['stance']=='insufficient' for c in payload['cells']))
        self.assertIsNone(payload['method']['accuracy'])
        for row in payload['assertions']:
            self.assertTrue(row['source_sha256'])
            self.assertEqual(row['evidence']['quote'],row['evidence_quote'])
            self.assertTrue(row['summary_zh'] and row['summary_en'])

    def validate(self,row):return validate_assertion(row,self.sources,self.book)

    def test_fabricated_quote_rejected(self):
        row=copy.deepcopy(self.sample);row['evidence_quote']='This statement does not appear in the source.'
        with self.assertRaises(ValueError):self.validate(row)

    def test_unstated_reason_rejected(self):
        row=copy.deepcopy(self.sample);row['reasons']=[{'quote':'invented motive','text_zh':'猜测','text_en':'Guess'}]
        with self.assertRaises(ValueError):self.validate(row)

    def test_actor_mention_or_group_membership_does_not_transfer_stance(self):
        row=copy.deepcopy(self.sample);row['actor_id']='G77'
        with self.assertRaises(ValueError):self.validate(row)

    def test_qualified_requires_original_condition(self):
        row=copy.deepcopy(self.sample);row['stance']='qualified';row.pop('qualifier_quote',None)
        with self.assertRaises(ValueError):self.validate(row)

    def test_future_or_imprecise_dates_rejected(self):
        for day in ['2099-01-01','2025','2025-01-01T12:00:00']:
            row=copy.deepcopy(self.sample);row['statement_date']=day
            with self.assertRaises(ValueError):self.validate(row)

    def test_unsafe_or_wrong_official_host_rejected(self):
        for url in ['javascript:alert(1)','https://mee.gov.cn.example.org/a','https://user:pass@www.mee.gov.cn/a']:
            sources=copy.deepcopy(self.sources);sources[self.sample['source_id']]['url']=url
            with self.assertRaises(ValueError):validate_assertion(self.sample,sources,self.book)

    def test_unicode_offsets_are_exact(self):
        text='前言。支持扩大气候资金。'
        span=evidence_span(text,'支持扩大气候资金')
        self.assertEqual(text[span['start']:span['end']],span['quote'])

    def fixture(self,folder,rows):
        root=Path(folder);(root/'config').mkdir();(root/'data').mkdir()
        (root/'config/stance_pilot.json').write_text(json.dumps(self.book),encoding='utf-8')
        (root/'data/stance_evidence.json').write_text(json.dumps({'sources':[self.sources[self.sample['source_id']]],'assertions':rows}),encoding='utf-8')
        return root

    def test_latest_statement_not_repost_majority_and_same_day_conflict_visible(self):
        old=copy.deepcopy(self.sample);old['id']='old';old['statement_date']='2024-01-01'
        new=copy.deepcopy(self.sample);new.update(id='new',statement_date='2025-01-01',stance='oppose')
        with tempfile.TemporaryDirectory() as folder:
            root=self.fixture(folder,[old,old,old,new]);p=build_pilot(root)
            c=next(c for c in p['cells'] if c['actor_id']==new['actor_id'] and c['proposition_id']==new['proposition_id'])
            self.assertEqual(c['stance'],'oppose');self.assertEqual(c['statement_events'],2)
            peer=copy.deepcopy(new);peer.update(id='peer',stance='support',event_id='second-event')
            registry={'sources':[self.sources[self.sample['source_id']]],'assertions':[old,new,peer]}
            (root/'data/stance_evidence.json').write_text(json.dumps(registry),encoding='utf-8')
            p=build_pilot(root);self.assertTrue(any(c['stance']=='mixed' for c in p['cells']))

    def test_machine_candidates_never_publish(self):
        row=copy.deepcopy(self.sample);row['review_status']='requires_editorial_source_review'
        with tempfile.TemporaryDirectory() as folder:
            root=self.fixture(folder,[row]);self.assertEqual(build_pilot(root)['assertions'],[])

    def test_csv_json_and_dictionary_export_without_mutating_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.fixture(folder,[self.sample]);(root/'data/news_archive.json').write_text('{"keep":true}')
            before=(root/'data/news_archive.json').read_bytes()
            result=write_stance_pilot(root,root/'site/data');self.assertEqual(result['assertions'],1)
            self.assertEqual((root/'data/news_archive.json').read_bytes(),before)
            records=list(csv.DictReader(io.StringIO((root/'site/data/stance_assertions.csv').read_text(encoding='utf-8-sig'))))
            self.assertEqual(records[0]['evidence_quote'],self.sample['evidence_quote'])
            self.assertTrue(json.loads((root/'site/data/stance_codebook.json').read_text(encoding='utf-8'))['method'])

    def test_optional_export_is_safe_for_older_fixtures(self):
        with tempfile.TemporaryDirectory() as folder:self.assertEqual(write_stance_pilot(Path(folder),Path(folder)/'out')['status'],'not_configured')

    def test_no_paid_or_unverified_backend(self):
        class Model:base_url='https://paid.example.com';model='other'
        self.assertEqual(update_candidates(ROOT,Model())['status'],'disabled')

    def test_two_pass_candidates_remain_unpublished_and_cached(self):
        from climate_agent.research import load_jsonl as original_load
        source={'text_id':'t1','source_text':'China supports climate finance for developing countries.','text_sha256':'hash1','title_original':'Climate finance','published_at':'2025-01-01','publisher_url':'https://www.mee.gov.cn/example'}
        class Model:
            base_url='https://generativelanguage.googleapis.com';model='gemini-3.5-flash-lite';calls=0
            def complete_json(self,prompt,payload):
                self.calls+=1
                if self.calls==1:return {'items':[{'source_id':'t1','actor_id':'CN','proposition_id':'finance_delivery','stance':'support','evidence_quote':source['source_text'],'summary_zh':'支持气候资金。','summary_en':'Supports climate finance.','reasons':[]}]}
                return {'items':[{'index':0,**{k:True for k in ['actor_supported','proposition_supported','stance_supported','reason_supported','conditions_preserved']}}]}
        with tempfile.TemporaryDirectory() as folder:
            root=self.fixture(folder,[]);model=Model()
            def load(path):return [source] if Path(path).name=='research_texts.jsonl.gz' else original_load(path)
            with patch('climate_agent.stance_pilot.load_jsonl',side_effect=load),patch('climate_agent.stance_pilot.extract_positions',return_value=[{'text_id':'t1','actor':'CN','date':'2025-01-01'}]):
                result=update_candidates(root,model)
                self.assertEqual(result['published'],0);self.assertEqual(model.calls,2)
                saved=original_load(root/'data/stance_candidates.jsonl')[0]
                self.assertEqual(saved['publication_status'],'not_published')
                self.assertTrue(saved['candidates'][0]['verifier_passed'])
                self.assertEqual(update_candidates(root,model)['status'],'up_to_date')
                self.assertEqual(model.calls,2)

    def test_exhausted_model_budget_preserves_existing_candidates(self):
        from climate_agent.research import load_jsonl as original_load
        source={'text_id':'t2','source_text':'China supports climate finance.','text_sha256':'hash2','title_original':'Climate finance'}
        class Model:
            base_url='https://generativelanguage.googleapis.com';model='gemini-3.5-flash-lite'
            def complete_json(self,*args):raise RuntimeError('budget exhausted')
        with tempfile.TemporaryDirectory() as folder:
            root=self.fixture(folder,[]);path=root/'data/stance_candidates.jsonl'
            path.write_text('{"text_id":"old","source_sha256":"old","profile":"old"}\n',encoding='utf-8');before=path.read_bytes()
            def load(path):return [source] if Path(path).name=='research_texts.jsonl.gz' else original_load(path)
            with patch('climate_agent.stance_pilot.load_jsonl',side_effect=load),patch('climate_agent.stance_pilot.extract_positions',return_value=[{'text_id':'t2','actor':'CN'}]):
                self.assertEqual(update_candidates(root,Model())['status'],'deferred')
                self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':unittest.main()

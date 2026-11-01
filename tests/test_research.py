import gzip
import hashlib
import json
import os
import tempfile
import unittest
import urllib.error
from datetime import UTC,datetime
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from climate_agent.research import (annotations,build_events,clean,collect_texts,extract_positions,
    freeze_release,load_jsonl,make_text_record,real_embedded_url,save_jsonl,substantive,version_comparisons,write_research)
from climate_agent.source_lookup import lookup_publishers
from climate_agent.research_documents import update_documents
from climate_agent.article_content import extract_article_text


TEXT=('The government approved a coastal adaptation programme with funding of $24 million. '
      'The programme covers flood barriers, community warning systems and coastal restoration. '
      'The published implementation period is 2027 to 2030, and the first projects will protect coastal communities.')

def row(url='https://example.org/one',title='Government approves coastal adaptation funding programme'):
    return {'record_id':'test1','canonical_url':url,'title_original':title,'title_zh':'政府批准沿海适应资金计划',
            'summary_source':TEXT,'published_at_utc':'2026-11-01T01:00:00+00:00','source_name':'Fixture source',
            'source_id':'T','language':'en','country_codes':[{'alpha2':'GB','alpha3':'GBR','name_zh':'英国','name_en':'United Kingdom'}]}


class ResearchTests(unittest.TestCase):
    def test_article_container_wins_over_longer_page_boilerplate(self):
        html='<title>Coastal adaptation funding</title><p>'+('Unrelated recommendations and site information. '*40)+'</p><article><p>'+TEXT+'</p></article>'
        result=extract_article_text(html)
        self.assertEqual(result['basis'],'article_paragraphs')
        self.assertEqual(result['text'],TEXT)

    def test_title_only_is_not_a_substantive_source_text(self):
        title='Government approves coastal adaptation funding programme'
        self.assertFalse(substantive(title+' - Example newspaper',title))
        self.assertFalse(substantive('https://example.org',title))
        self.assertTrue(substantive(TEXT,title))

    def test_original_text_and_offsets_are_inspectable(self):
        record=make_text_record(row(),TEXT,'source_excerpt')
        self.assertEqual(record['source_text'],TEXT)
        self.assertEqual(record['text_sha256'],hashlib.sha256(TEXT.encode()).hexdigest())
        for category in ['governance_themes','policy_tools','policy_stages']:
            for item in record[category]:self.assertTrue(record['source_text'][item['start']:item['end']])
        self.assertTrue(any('$24 million'==claim['value_text'] for claim in record['quantitative_claims']))
        self.assertIsNone(record['event_date'])

    def test_source_text_never_comes_from_an_ai_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            first=row();first['summary_source']=first['title_original'];first['summary_zh']='模型生成的概括。'*30
            save_jsonl(root/'data/climate_text_corpus.jsonl',[first])
            self.assertEqual(collect_texts(root)['usable_texts'],0)

    def test_offline_seeding_is_idempotent_and_keeps_previous_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            save_jsonl(root/'data/climate_text_corpus.jsonl',[row()])
            self.assertEqual(collect_texts(root)['usable_texts'],1)
            self.assertEqual(collect_texts(root)['new_text_records'],0)
            save_jsonl(root/'data/climate_text_corpus.jsonl',[])
            self.assertEqual(collect_texts(root)['usable_texts'],1)

    def test_failed_fetch_preserves_existing_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            save_jsonl(root/'data/climate_text_corpus.jsonl',[row()])
            with patch('climate_agent.research.fetch_article_text',return_value={'text':'','basis':'http_403'}):
                status=collect_texts(root,fetch_limit=1)
            self.assertEqual(status['usable_texts'],1)
            self.assertEqual(load_jsonl(root/'data/research_texts.jsonl')[0]['source_text'],TEXT)

    def test_opaque_google_link_is_not_fabricated_as_a_publisher_url(self):
        self.assertIsNone(real_embedded_url('https://news.google.com/rss/articles/not-a-publisher-url'))
        self.assertEqual(real_embedded_url('https://example.org/news'),'https://example.org/news')

    def test_event_links_are_conservative(self):
        a=make_text_record(row(),'First report. '+TEXT,'source_excerpt')
        b=make_text_record(row('https://example.net/one'),TEXT,'source_excerpt');b['text_id']='b'
        c=make_text_record(row('https://example.org/other','Government reviews national methane regulation'),TEXT,'source_excerpt');c['text_id']='c'
        groups=build_events([a,b,c])
        self.assertEqual(sorted(len(g['records']) for g in groups),[1,2])

    def test_negation_is_not_labelled_support(self):
        record=make_text_record(row(),'The United Kingdom does not support the proposal on carbon markets. '+TEXT,'source_excerpt')
        positions=extract_positions([record])
        self.assertTrue(positions)
        self.assertEqual(positions[0]['position_type'],'qualified_statement')

    def test_missing_position_does_not_become_opposition(self):
        record=make_text_record(row(),TEXT,'source_excerpt')
        self.assertEqual(extract_positions([record]),[])

    def test_negated_opposition_is_not_opposition(self):
        record=make_text_record(row(),'The United Kingdom does not oppose the proposal on carbon markets. '+TEXT,'source_excerpt')
        self.assertEqual(extract_positions([record])[0]['position_type'],'qualified_statement')

    def test_reported_actor_is_not_the_earlier_speaker(self):
        record=make_text_record(row(),'The United Kingdom said the United States supports the proposal on climate finance. '+TEXT,'source_excerpt')
        record['country_mentions']=[{'alpha2':'US','name_zh':'美国','name_en':'United States'}]
        positions=extract_positions([record])
        self.assertEqual([p['actor'] for p in positions],['US'])

    def test_real_policy_family_comparison_uses_stored_texts(self):
        a=make_text_record(row(),TEXT,'licensed_document_text');a.update(document_family='UK-NDC',document_country='GB',published_at='2022-09-23')
        b=make_text_record(row('https://example.org/new'),TEXT+' The target is revised.','licensed_document_text');b.update(document_family='UK-NDC',document_country='GB',published_at='2025-01-30')
        comparison=version_comparisons([a,b])[0]
        self.assertEqual(comparison['scope'],'official_documents_with_explicit_version_labels')
        self.assertTrue(comparison['diff'])

    def test_frozen_release_is_immutable_and_hash_matches(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            save_jsonl(root/'data/research_texts.jsonl',[make_text_record(row(),TEXT,'source_excerpt')])
            release=freeze_release(root);target=root/'data/research_releases'/release['id']/'corpus.jsonl.gz'
            self.assertEqual(hashlib.sha256(gzip.decompress(target.read_bytes())).hexdigest(),release['sha256'])
            self.assertEqual(freeze_release(root),release)
            before=target.read_bytes();save_jsonl(root/'data/research_texts.jsonl',[]);freeze_release(root)
            self.assertEqual(target.read_bytes(),before)

    def test_emails_and_obvious_credentials_not_retained(self):
        text=clean('Contact private@example.org or use sk-'+('x'*32))
        self.assertNotIn('private@example.org',text)
        self.assertNotIn('sk-',text)

    def test_lookup_disabled_without_explicit_google_configuration(self):
        class Model:base_url='https://example.org';api_key='fixture'
        with patch.dict(os.environ,{'CLIMATE_RESEARCH_GROUNDED_LOOKUP':'1'}):
            self.assertEqual(lookup_publishers(Path('.'),None,Model())['status'],'disabled')

    def test_grounded_discovery_stores_fetched_text_not_model_prose(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            item=row('https://news.google.com/rss/articles/opaque');item['published_at_utc']=datetime.now(UTC).isoformat()
            save_jsonl(root/'data/climate_text_corpus.jsonl',[item])
            response={'candidates':[{'groundingMetadata':{'groundingChunks':[{'web':{'uri':'https://example.org/full'}}]},
                'content':{'parts':[{'text':json.dumps({'articles':[{'id':0,'url':'https://example.org/full'}]})}]}}]}
            class Response:
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def read(self):return json.dumps(response).encode()
            model=SimpleNamespace(base_url='https://generativelanguage.googleapis.com/v1beta/openai',api_key='fixture-not-a-real-key')
            with patch.dict(os.environ,{'CLIMATE_RESEARCH_GROUNDED_LOOKUP':'1'}),patch('climate_agent.source_lookup.urllib.request.urlopen',return_value=Response()),patch('climate_agent.source_lookup.fetch_article_text',return_value={'title':item['title_original'],'text':TEXT,'basis':'article_paragraphs'}):
                status=lookup_publishers(root,None,model)
            self.assertEqual(status['texts_added'],1)
            self.assertEqual(load_jsonl(root/'data/research_texts.jsonl')[0]['source_text'],TEXT)

    def test_discovery_quota_error_stops_without_paid_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            item=row('https://news.google.com/rss/articles/opaque');item['published_at_utc']=datetime.now(UTC).isoformat()
            save_jsonl(root/'data/climate_text_corpus.jsonl',[item])
            model=SimpleNamespace(base_url='https://generativelanguage.googleapis.com/v1beta/openai',api_key='fixture-not-a-real-key')
            with patch.dict(os.environ,{'CLIMATE_RESEARCH_GROUNDED_LOOKUP':'1'}),patch('climate_agent.source_lookup.urllib.request.urlopen',side_effect=urllib.error.HTTPError('https://example.org',429,'rate limited',{},None)) as call:
                status=lookup_publishers(root,None,model)
            self.assertEqual(call.call_count,1)
            self.assertEqual(status['texts_added'],0)
            self.assertEqual(status['errors'],['HTTPError:429'])

    def test_compressed_repository_corpus_can_be_restored(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'research_texts.jsonl'
            save_jsonl(path,[row()]);raw=path.read_bytes()
            self.assertEqual(gzip.decompress(path.with_suffix('.jsonl.gz').read_bytes()),raw)
            path.unlink()
            self.assertEqual(load_jsonl(path)[0]['record_id'],'test1')

    def test_licensed_documents_have_no_network_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(update_documents(Path(folder))['requested'],0)


if __name__=='__main__':unittest.main()

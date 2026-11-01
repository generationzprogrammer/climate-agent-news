import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from climate_agent.model_budget import ModelBudgetExceeded, reserve_request, record_usage
from climate_agent.summary_utils import sanitize_summary
from climate_agent.english_brief import fingerprint
from climate_agent.db import Database
from climate_agent.translation import translate_pending, _write_translation
from datetime import datetime, UTC


class ExpandedSummaryTests(unittest.TestCase):
    def test_long_summary_preserves_late_numeric_fact(self):
        text = '沿海适应项目已获批准，建设内容包括堤防、社区预警和海岸生态修复。' * 7
        text += '其中首批资金为24亿美元，项目将在2028年完成。'
        result = sanitize_summary(text)
        self.assertGreater(len(result), 220)
        self.assertIn('24亿美元', result)
        self.assertIn('2028年', result)

    def test_generic_sentence_removed_without_losing_detailed_summary(self):
        text = '来源消息显示，涉及气候政策受到关注。政府批准新的海岸适应计划，实施期为2027年至2030年。'
        self.assertEqual(sanitize_summary(text), '政府批准新的海岸适应计划，实施期为2027年至2030年。')

    def test_changed_chinese_summary_invalidates_english_cache(self):
        self.assertNotEqual(fingerprint({'summary_zh': '旧概要'}), fingerprint({'summary_zh': '新的详细概要'}))

    def test_budget_shared_across_models_and_reloaded_between_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'usage.json'
            with patch.dict(os.environ, {'CLIMATE_MODEL_USAGE_PATH': str(path), 'CLIMATE_MODEL_DAILY_REQUEST_LIMIT': '2',
                                         'CLIMATE_MODEL_MIN_INTERVAL_SECONDS': '0'}):
                reserve_request('gemini-test')
                record_usage({'prompt_tokens': 400, 'completion_tokens': 700})
                reserve_request('other-task-model')
                with self.assertRaises(ModelBudgetExceeded):
                    reserve_request('gemini-test')
                saved = json.loads(path.read_text())
                self.assertEqual(saved['requests'], 2)
                self.assertEqual(saved['output_tokens'], 700)
                self.assertNotIn('api_key', saved)

    def test_corrupt_ledger_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'usage.json'
            path.write_text('not-json')
            with patch.dict(os.environ, {'CLIMATE_MODEL_USAGE_PATH': str(path)}):
                with self.assertRaises(ModelBudgetExceeded):
                    reserve_request('gemini-test')

    def test_four_record_bilingual_batches_are_cached_for_next_update(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder)/'news.db'); db.initialize()
            db.execute("INSERT INTO sources(source_id,name,source_type,region,languages_json,focus,homepage_url,access_method,storage_policy,compliance_note,phase,enabled,authority,climate_relevance,machine_readability,poll_interval_minutes,updated_at) VALUES('T','Test','official','global','[]','','https://example.org','rss','metadata','','P0',1,5,5,5,60,'2026-11-01')")
            now = datetime.now(UTC).isoformat()
            db.upsert_articles([{'article_id':f'a{i}','source_id':'T','source_url':f'https://example.org/{i}',
                'canonical_url':f'https://example.org/{i}','title_original':'Coastal adaptation fund approved',
                'summary_source':'The government approved flood protection funding.','published_at_utc':now,
                'language':'en','rights_status':'metadata_only','content_hash':f'h{i}','fetched_at':now,
                'relevance_score':90,'topics':['气候适应'],'numbers':[],'metadata':{}} for i in range(5)])
            class Model:
                model='gemini-test'; sizes=[]
                def complete_json(self, system, payload):
                    self.sizes.append(len(payload['articles']))
                    return {'translations':[{'article_id':r['article_id'],'title_zh':'政府批准沿海适应基金',
                        'summary_zh':'政府批准沿海适应基金，资金用于建设防洪设施和社区预警系统。',
                        'title_en':'Coastal adaptation fund approved','summary_en':'The government approved funding for flood protection and warning systems.'} for r in payload['articles']]}
            model=Model()
            with patch('climate_agent.translation.fetch_article_text',return_value={'text':'A public source description.','basis':'article_paragraphs'}):
                self.assertEqual(translate_pending(db,model,limit=5)['translated'],5)
                self.assertEqual(translate_pending(db,model,limit=5)['pending'],0)
            self.assertEqual(model.sizes,[4,1])
            row=db.rows("SELECT * FROM articles WHERE article_id='a0'")[0]
            self.assertFalse(_write_translation(db,row,{'title_zh':'政府批准沿海适应基金','summary_zh':'较短的来源摘要，仅提及沿海基金和防洪设施。'},fallback=True))


if __name__ == '__main__':
    unittest.main()

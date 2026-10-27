import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from climate_agent.english_brief import enrich_daily_english, english_fields
from climate_agent.pdf_brief import write_daily_brief_pdf


class MemoryDB:
    metadata = '{}'
    def rows(self, *_):
        return [{'metadata_json': self.metadata}]
    def execute(self, _, args):
        self.metadata = args[0]


class EnglishBriefTests(unittest.TestCase):
    def test_cache_and_changed_facts(self):
        class Model:
            calls=0
            def complete_json(self, *_):
                self.calls+=1
                return {'translations':[{'article_id':'a','title_en':'Adaptation funding approved','summary_en':'The government approved funding for coastal adaptation and local early warning systems.'}]}
        db, model = MemoryDB(), Model()
        record={'article_id':'a','title_zh':'批准适应资金','summary_zh':'政府批准海岸适应资金','title_original':'Adaptation funding approved'}
        enrich_daily_english(db,[dict(record)],model)
        enriched=dict(record);enrich_daily_english(db,[enriched],model)
        self.assertEqual(model.calls,1)
        self.assertIn('funding',enriched['summary_en'])
        changed={**record,'summary_zh':'政府批准新一轮适应资金'}
        enrich_daily_english(db,[changed],model)
        self.assertEqual(model.calls,2)

    def test_foreign_source_fallback_never_masquerades_as_english(self):
        title,summary=english_fields({'title_original':'中文题目','summary_source':'中文概括'})
        self.assertNotIn('中文',title+summary)

    def test_both_pdf_editions_rebuild_for_a_new_day(self):
        with tempfile.TemporaryDirectory() as folder:
            item={'title_zh':'沿海地区批准气候适应资金','summary_zh':'政府批准建设沿海防护设施及早期预警系统，资金用于降低洪灾风险。','title_en':'Coastal adaptation funding approved','summary_en':'The government approved coastal protection and early warning funding to reduce flood risks.','canonical_url':'https://example.org/news','source_name':'Official statement'}
            for day in ('2026-10-27','2026-10-28'):
                payload={'meta':{'latest_news_date':day},'intelligence':[item]*12}
                for language in ('zh','en'):
                    path=write_daily_brief_pdf(payload,Path(folder)/f'{day}-{language}.pdf',language=language)
                    data=path.read_bytes()
                    self.assertTrue(data.startswith(b'%PDF-1.4'))
                    self.assertIn(b'/BaseFont /Times-Roman',data)
                    self.assertIn(b'/Subtype /Link',data)


if __name__=='__main__': unittest.main()

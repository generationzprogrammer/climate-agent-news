import importlib.util
import sys
import unittest
from pathlib import Path
if importlib.util.find_spec('trafilatura') is None:
    raise unittest.SkipTest('optional fulltext environment required')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_public_fulltext_library import relevance

class BilingualRelevanceTests(unittest.TestCase):
    def test_chinese_climate(self):
        accepted,tags=relevance('气候变化将重塑非洲疟疾流行版图','研究分析了疾病传播的未来变化。')
        self.assertTrue(accepted)
        self.assertEqual(tags['relevance_evidence']['climate_governance'],'气候变化')
    def test_chinese_carbon(self):
        self.assertTrue(relevance('我国首次开展碳效领跑者企业遴选','推动产业低碳发展。')[0])
    def test_irrelevant_chinese(self):
        self.assertFalse(relevance('城市养老服务体系建设规划','本项目完善养老和托育公共服务。')[0])
    def test_existing_english(self):
        self.assertTrue(relevance('Solar power and storage expand','Developers announced new installations.')[0])

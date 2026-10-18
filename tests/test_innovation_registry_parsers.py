import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import extract_innovation_registry_candidates as parser
from update_innovation_registries import register_date

class ParserTests(unittest.TestCase):
    def parse(self,key,html,fn,extra=None):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);(folder/(key+'.html')).write_text(html,encoding='utf-8')
            for name,value in (extra or {}).items():(folder/(name+'.html')).write_text(value,encoding='utf-8')
            with patch.object(parser,'CACHE',folder):return fn()
    def test_nsf_nested_rows_not_duplicated(self):
        html='<div class="row"><div class="row"><div class="title"><a href="/sample">Test Centre</a></div><div class="focus"><li>Energy and Environment (Primary Area)</li></div><div class="universities"><li>University A</li></div><div class="members"><li>Company B</li></div><div class="year">2010</div></div></div>'
        rows=self.parse('nsf_iucrc',html,parser.nsf)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['year'],2010)
        self.assertEqual(rows[0]['focus'],['Energy and Environment'])
    def test_embrapii_schema_and_facts(self):
        html='<table><tr><th>Name</th></tr><tr><td>UNIT</td><td>Materials</td><td>Testing</td><td>University</td><td>City / SP</td></tr></table>'
        rows=self.parse('embrapii_export',html,parser.embrapii)
        self.assertEqual(rows[0]['location'],'City / SP')
        with self.assertRaises(ValueError):self.parse('embrapii_export',html.replace('<td>Testing</td>',''),parser.embrapii)
    def test_au_partner_boundaries_and_round(self):
        html='<h2>Round 1</h2><table><tr><td>Battery manufacturing</td><td>Firm A<br>University B</td><td>Technical objective</td><td>1/7/2020 - 30/6/2023</td><td>$100</td><td>$200</td></tr></table>'
        rows=self.parse('australia_crcp',html,parser.australia)
        self.assertEqual(rows[0]['institutions'],['Firm A','University B'])
        self.assertEqual(rows[0]['round'],'Round 1')
    def test_africa_country_tabs_and_rowspans(self):
        html='<div id="tab-title-1">Ghana</div><div class="elementor-tab-content" id="tab-content-1"><li><a href="/test">Engineering Centre</a>, Host</li></div>'
        second='<table><tr><td rowspan="2">University Ethiopia</td><td>Rail Centre</td></tr><tr><td>Water Centre</td></tr></table>'
        rows=self.parse('africa_ace',html,parser.africa,{'africa_ace2':second})
        self.assertEqual([r['country'] for r in rows],['GH','ET','ET'])
    def test_japan_platform_not_overview_label(self):
        html='<table><tr><td>Carbon platform</td><td>University</td><td><a href="/pf/platform/overview/test.pdf">Overview</a></td></tr></table>'
        rows=self.parse('jst_coinext',html,parser.japan)
        self.assertEqual(rows[0]['name'],'Carbon platform')
        self.assertEqual(rows[0]['institutions'],['University'])
    def test_dates_accept_original_variants_not_invalid_dates(self):
        self.assertEqual(register_date('1/7/2020').isoformat(),'2020-07-01')
        self.assertEqual(register_date('1 July 2020').isoformat(),'2020-07-01')
        with self.assertRaises(ValueError):register_date('29 Feb 2025')
if __name__=='__main__':unittest.main()

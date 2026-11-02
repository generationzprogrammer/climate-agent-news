import unittest
from climate_agent.translation import detect_places
from climate_agent.taxonomy import country_codes_for
from climate_agent.briefing import _ensure_places,_map_events
from climate_agent.archive import _repair_places
class MapQueueTests(unittest.TestCase):
    def test_developing_countries_does_not_mean_china(self):
        text='欧盟将对发展中国家的气候资金提升至323亿欧元'
        self.assertEqual([p['name_zh'] for p in detect_places(text)],['欧盟'])
        self.assertEqual(country_codes_for(text),[])
        self.assertEqual([p['name_zh'] for p in detect_places('中国支持其他发展中国家')],['中国'])
    def test_old_wrong_china_pin_is_replaced_by_eu(self):
        row={'title_original':'EU lifts climate finance for developing nations','title_zh':'欧盟将对发展中国家的气候资金提升至323亿欧元','places':[{'name_zh':'中国','lon':105,'lat':35}],'country_tags':['中国']}
        self.assertEqual(_ensure_places(row)['places'][0]['name_zh'],'欧盟')
        self.assertEqual(_repair_places(row)[0]['name_zh'],'欧盟')
    def test_unknown_location_is_not_inherited_from_legacy_tags(self):
        row={'title_original':'Climate finance for developing countries','title_zh':'发展中国家的气候资金','places':[{'name_zh':'中国','lon':105,'lat':35}],'country_tags':['中国'],'country_codes':[{'name_zh':'中国'}]}
        self.assertEqual(_ensure_places(row)['places'],[])
    def test_all_twelve_real_records_remain_in_queue_without_fake_pins(self):
        rows=[{'article_id':str(i),'title_original':'Climate finance talks','title_zh':'全球气候资金讨论','summary_zh':'各方讨论全球气候资金安排的相关议题。','source_name':'Fixture','canonical_url':'https://example.org/'+str(i),'published_at':'2026-11-02'} for i in range(12)]
        self.assertEqual(len(_map_events(rows,include_unlocated=True)),12)
        self.assertEqual(_map_events(rows),[])
        self.assertTrue(all(r['lon'] is None and r['lat'] is None for r in _map_events(rows,include_unlocated=True)))
if __name__=='__main__':unittest.main()

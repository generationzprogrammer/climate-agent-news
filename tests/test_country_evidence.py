import unittest
from climate_agent.taxonomy import country_codes_for,country_mentions_with_evidence

class CountryEvidenceTests(unittest.TestCase):
    def codes(self,text):return {r['alpha2'] for r in country_codes_for(text)}
    def test_new_mexico_is_us_not_mexico(self):
        self.assertEqual(self.codes('New Mexico approves solar and storage funding.'),{'US'})
        self.assertEqual(self.codes('New Mexico and Mexico discuss cross-border electricity.'),{'US','MX'})
    def test_longer_country_and_subdivision_names_take_precedence(self):
        for text,expected in [('Papua New Guinea climate plan',{'PG'}),('Guinea-Bissau adaptation finance',{'GW'}),('South Sudan drought',{'SS'}),('Northern Ireland net-zero plan',{'GB'}),('British Columbia wildfire',{'CA'}),('Democratic Republic of the Congo forest policy',{'CD'}),('North Korean emissions',{'KP'}),('索马里应对气候变化',{'SO'})]:
            self.assertEqual(self.codes(text),expected,text)
    def test_pronouns_currency_names_and_urls_do_not_create_countries(self):
        for text in ['Help us act on climate change.','The project costs US$24 million.','U.S. dollars fund the global programme.','Michael Jordan and Chad Smith sign an appeal.','Georgia state lawmakers meet in Atlanta.','A link https://example.org/india/climate','The Korean Peninsula climate outlook']:
            self.assertEqual(self.codes(text),set(),text)
    def test_disambiguating_country_context_is_used(self):
        self.assertEqual(self.codes('Georgia sets a climate target, officials in Tbilisi said.'),{'GE'})
        self.assertEqual(self.codes('Turkey hosts COP31, the Turkish government said.'),{'TR'})
        self.assertEqual(self.codes('Jordan adopts a water plan in Amman.'),{'JO'})
    def test_evidence_offsets_reproduce_the_original_text(self):
        text='北京 and New Mexico compare adaptation plans with Papua New Guinea.'
        for item in country_mentions_with_evidence(text):self.assertEqual(text[item['start']:item['end']],item['matched_text'])
    def test_explicit_iso_codes_remain_supported(self):
        self.assertEqual({r['alpha2'] for r in country_codes_for('',country_tags=['USA','CN'])},{'US','CN'})

if __name__=='__main__':unittest.main()

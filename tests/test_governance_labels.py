import unittest
from climate_agent.governance_labels import label_text,group_brief_items,TOPICS

class GovernanceTests(unittest.TestCase):
    def test_taxonomy(self):
        self.assertEqual(len(TOPICS),12);self.assertEqual(len({t[0] for t in TOPICS}),12)
    def test_country_not_substring(self):
        x=label_text('欧盟将对发展中国家提供气候资金','')
        self.assertNotIn('CN',x['country_mentions']);self.assertIn('EU',x['organization_mentions'])
    def test_us_pronoun(self):
        self.assertNotIn('US',label_text('Climate change affects us','')['country_mentions'])
    def test_evidence(self):
        title='China and EU discuss carbon markets';body='Climate finance and adaptation finance are on the agenda.'
        x=label_text(title,body)
        for e in x['evidence']:self.assertEqual({'title':title,'source_text':body}[e['field']][e['start']:e['end']],e['quote'])
        self.assertIn('markets',x['topics']);self.assertIn('finance',x['topics'])
    def test_not_forced(self):
        self.assertEqual(label_text('Football game','A sporting event')['primary_topic'],'unclassified')
    def test_group_preserves_every_record(self):
        rows=[{'title_original':'Climate finance talks'},{'title_original':'Solar power expands'},{'title_original':'Climate finance pledge'}]
        self.assertEqual(sum(len(items) for _,items in group_brief_items(rows)),3)
    def test_new_mexico(self):
        x=label_text('New Mexico expands solar power','New Mexico is a US state.')
        self.assertIn('US',x['country_mentions']);self.assertNotIn('MX',x['country_mentions'])
    def test_fast_country_spans_equivalent(self):
        from climate_agent.taxonomy import _country_patterns,_literal_country_spans,_normalise
        pattern,terms=_country_patterns()
        for text in ('New Mexico, China, United States and South Africa.','欧盟与发展中国家、英国、印度、南非。','North Korea and South Korea; United States of America.','U.S. dollar and US$ 5 million.','Republic of the Congo and Democratic Republic of the Congo.'):
            old=[(m.start(),m.end(),terms.get(_normalise(m.group()),())) for m in pattern.finditer(text)]
            self.assertEqual(old,_literal_country_spans(text))

if __name__=='__main__':unittest.main()

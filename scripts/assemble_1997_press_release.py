"""Reconstruct the complete official Kyoto adoption press release from public HTML."""
import gzip,re
from bs4 import BeautifulSoup
import fulltext_pilot as p
dest=p.ROOT/'data/private_global_expansion_20261106/historical'
raw=gzip.decompress((dest/'early_unfccc/indust.htm.gz').read_bytes());soup=BeautifulSoup(raw,'lxml')
paragraphs=[re.sub(r'\s+',' ',x.get_text(' ',strip=True)).strip() for x in soup.select('p')]
title='Industrialized countries to cut greenhouse gas emissions by 5.2%'
assert title in paragraphs
start=next(i for i,x in enumerate(paragraphs) if x.startswith('Kyoto, 11 December 1997 -'))
body='\n\n'.join(x for x in paragraphs[start:] if x)
assert body.endswith('http://www.unfccc.de.') and len(body)>3000
d={'id':'unfccc_1997_12_11_kyoto_adoption','title':title,'url':'https://unfccc.int/cop3/fccc/info/indust.htm','source':'UNFCCC','source_id':'UNFCCC_HISTORICAL','language':'en','date':'1997-12-11','date_precision':'day','source_text':body,'text_sha256':p.digest(body.encode()),'raw_html_sha256':p.digest(raw),'document_genre':'news_or_commentary','content_origin_hint':'official_press_release','collection_cohort':'historical_article_supplement','extraction_method':'complete_legacy_HTML_paragraphs','quality_flags':[],'research_eligible':True,'source_block_coverage':1,'first_block_present':True,'last_block_present':True,'acquired_at':p.stamp(),'rights_status':'private_research_copy_permission_not_established_for_redistribution','public_redistribution_allowed':False,'verification':{'date_quote':'Kyoto, 11 December 1997','headline_quote':title,'article_boundary':'all nonempty paragraphs from dateline through final press-contact paragraph','date_not_inferred_from_mentioned_event':True,'reviewer':'assistant_source_structure_check'}}
p.dump(dest/'unfccc_1997_article_verified.json',d);print({'characters':len(body),'date':d['date']})

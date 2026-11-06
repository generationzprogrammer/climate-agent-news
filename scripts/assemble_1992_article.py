"""Reconstruct one complete article from visually checked OCR column geometry.

The source is Acid News 3, June 1992, p.14. Caption, cartoon, running footer and
duplicated pull quote are excluded. Printed wording and numbers are retained.
"""
import json,re
import fulltext_pilot as p
ROOT=p.ROOT;dest=ROOT/'data/private_global_expansion_20261106/historical/airclim_june_1992'
ocr=json.loads((dest/'ocr_page_14_english.json').read_text('utf-8'));items=ocr['items']
def xy(item):return min(v[0] for v in item['box']),min(v[1] for v in item['box'])
left=[i for i,v in enumerate(items) if xy(v)[0]<390 and 170<xy(v)[1]<1540]
middle=[i for i,v in enumerate(items) if 390<=xy(v)[0]<760 and 770<xy(v)[1]<1540 and i not in [71,75,79]]
right=[i for i,v in enumerate(items) if 760<=xy(v)[0]<950 and 770<xy(v)[1]<1540]
order=[]
for ids in [left,middle,right]:order+=sorted(ids,key=lambda i:(round(xy(items[i])[1]/10),xy(items[i])[0]))
paragraph_starts={2,19,35,81,99,56,112,72};paragraphs=[];current=[];corrections=[]
for i in order:
 text=items[i]['text'].strip();fixed=text
 # OCR misreads small-cap country abbreviations; each correction is logged.
 fixed=re.sub(r'\bUs\b','US',fixed);fixed=re.sub(r'\bEc\b','EC',fixed)
 fixed=re.sub(r'\b(?:co2|C02)\b','CO2',fixed)
 if i==34:fixed=fixed+'.'
 if fixed!=text:corrections.append({'ocr_line':i,'before':text,'after':fixed,'basis':'page_14_scan_visual_check'})
 if i in paragraph_starts and current:paragraphs.append(current);current=[]
 current.append(fixed)
if current:paragraphs.append(current)
def join(lines):
 out=lines[0]
 for line in lines[1:]:out=out[:-1]+line if out.endswith('-') else out+' '+line
 return out
body='\n\n'.join(join(lines) for lines in paragraphs)
assert body.startswith('TRUE TRASH!') and body.endswith('the year 2000.')
doc={'id':'airclim_1992_06_p14_chief_stumblingblock','title':'Chief stumblingblock','url':'https://www.airclim.org/acidnews/no-3-june-1992','pdf_url':'https://www.airclim.org/sites/default/files/acid-news-pdf/2023-06/AN3-1992.pdf','source':'Air Pollution & Climate Secretariat — Acid News','source_id':'AIRCLIM_ARTICLE','language':'en','date':'1992-06','date_precision':'month','source_text':body,'text_sha256':p.digest(body.encode()),'pdf_sha256':p.digest((dest/'source.pdf').read_bytes()),'pdf_pages':[14],'author':'Reinhold Pape','document_genre':'news_or_commentary','collection_cohort':'historical_article_supplement','extraction_method':'English_OCR_column_order_visual_source_check','quality_flags':[],'research_eligible':True,'source_block_coverage':1,'last_block_present':True,'acquired_at':p.stamp(),'rights_status':'private_research_copy_permission_not_established_for_redistribution','public_redistribution_allowed':False,'verification':{'reviewer':'assistant_visual_source_check_not_independent_human_annotation','article_boundary':'complete article on page 14; title and author identifiable','issue_date_evidence':'ACID NEWS 3, JUNE 1992, printed page footer and issue cover','ocr_line_order':order,'excluded_material':['cartoon','caption','duplicate pull quote','page footer'],'corrections':corrections,'original_scan_retained':True}}
p.dump(dest.parent/'airclim_1992_article_verified.json',doc)
p.dump(dest/'article_reconstruction_audit.json',doc['verification'])
print(json.dumps({'characters':len(body),'paragraphs':len(paragraphs),'date':doc['date'],'records':1}))

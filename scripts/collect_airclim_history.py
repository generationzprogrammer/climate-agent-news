"""Official periodical archive, separate genre; one issue is not many news items."""
import gzip,io,json,re,time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from pypdf import PdfReader
import fulltext_pilot as p
import bulk_fulltext as b
from collect_public_fulltext_library import relevance,state_write

ROOT=p.ROOT; OUT=ROOT/'analysis/global_expansion_20261106'
DEST=ROOT/'data/private_global_expansion_20261106/historical'

def main():
 DEST.mkdir(parents=True,exist_ok=True); p.ACCEPT_ENCODING='gzip'; p.TIMEOUT=30
 f=p.Fetcher(); probe=json.loads((OUT/'historical_probe.json').read_text('utf-8'))
 links={x['url']:x for x in probe[0]['links'] if re.search(r'199[2-9]|200\d|201[0-4]',x['text']) and '/acidnews/' in x['url']}
 attempts=[]
 for url,item in sorted(links.items(),key=lambda x:re.search(r'(19|20)\d{2}',x[1]['text']).group()):
  ident='airclim_'+p.digest(url.encode())[:20]; dest=DEST/(ident+'.json')
  if dest.exists(): continue
  try:
   final,page,raw,_=f.get(url,b.timing()); soup=BeautifulSoup(page,'lxml')
   pdflinks=[urljoin(final,a['href']) for a in soup.find_all('a',href=True) if '.pdf' in a['href'].lower()]
   if not pdflinks: raise p.StopFetch('no_official_PDF_link')
   yearstr=re.search(r'(?:19|20)\d{2}',item['text']).group()
   issue=re.search(r'No\.?\s*(\d+)',item['text'],re.I)
   matching=[u for u in pdflinks if issue and re.search(r'AN0?'+issue.group(1)+r'[-_]'+yearstr+r'\.pdf',u,re.I)]
   if len(matching)!=1: raise p.StopFetch('issue_PDF_identity_needs_review')
   pdfurl=matching[0]; _,_,pdf,_=f.get(pdfurl,b.timing())
   if not pdf.startswith(b'%PDF'): raise p.StopFetch('not_PDF')
   (DEST/(ident+'.pdf')).write_bytes(pdf)
   reader=PdfReader(io.BytesIO(pdf)); pages=[page.extract_text() or '' for page in reader.pages]
   text='\n\n'.join(pages)
   if min(map(len,pages),default=0)<50 or len(text)<800: raise p.StopFetch('scanned_or_incomplete_text_layer_needs_OCR')
   ok,tags=relevance(item['text'],text)
   if not ok: raise p.StopFetch('not_focal_climate_energy')
   year=int(re.search(r'(?:19|20)\d{2}',item['text']).group())
   monthmatch=re.search(r'January|February|March|April|May|June|July|August|September|October|November|December',item['text'],re.I)
   months=['january','february','march','april','may','june','july','august','september','october','november','december']
   date=str(year)+(f'-{months.index(monthmatch.group().lower())+1:02d}' if monthmatch else '')
   doc={'id':ident,'title':'Acid News — '+item['text'],'url':url,'pdf_url':pdfurl,'source':'Air Pollution & Climate Secretariat','source_id':'AIRCLIM','language':'en','date':date,'date_precision':'month' if monthmatch else 'year','source_text':text,'text_sha256':p.digest(text.encode()),'pdf_sha256':p.digest(pdf),'pdf_pages':len(pages),'page_character_counts':list(map(len,pages)),'extraction_method':'pypdf_all_pages','research_eligible':False,'quality_flags':['PDF_reading_order_needs_visual_review'],'document_genre':'periodical_issue','acquired_at':p.stamp(),'rights_status':'private_research_copy_permission_not_established_for_redistribution','public_redistribution_allowed':False,'collection_cohort':'historical_periodical_supplement',**tags}
   (DEST/(ident+'.pdf')).write_bytes(pdf); state_write(dest,doc)
   attempts.append({'url':url,'status':'text_layer_acquired','date':date,'characters':len(text),'pages':len(pages)})
   print(json.dumps(attempts[-1]),flush=True)
  except Exception as e: attempts.append({'url':url,'status':getattr(e,'reason',type(e).__name__)})
  state_write(OUT/'airclim_attempts.json',attempts)
 state_write(OUT/'airclim_requests.json',f.requests)
if __name__=='__main__': main()

"""Small, audited HTML supplement for geographic/topic gaps."""
import concurrent.futures as cf,gzip,json,re
from datetime import datetime
from bs4 import BeautifulSoup
import fulltext_pilot as p
import bulk_fulltext as b
from expansion_quality import eligible
from collect_public_fulltext_library import relevance

ROOT=p.ROOT;DEST=ROOT/'data/private_global_expansion_20261106/targeted';OUT=ROOT/'analysis/global_expansion_20261106'
def dates(value):
 if isinstance(value,dict):
  if value.get('datePublished'):yield value['datePublished']
  for child in value.values():yield from dates(child)
 elif isinstance(value,list):
  for child in value:yield from dates(child)

def main():
 DEST.mkdir(parents=True,exist_ok=True);p.ACCEPT_ENCODING='gzip';p.TIMEOUT=25;f=p.Fetcher()
 items=json.loads((ROOT/'config/global_coverage_seeds_20261106.json').read_text('utf-8'))['items']
 blocked=set()
 for prior in OUT.glob('targeted_attempts*.json'):
  for row in json.loads(prior.read_text('utf-8')):
   if re.search(r'403|401|429|robots_disallowed',row.get('status','')):blocked.add(row['url'])
 def collect(seed):
  url=seed['url'];ident='target_'+p.digest(url.encode())[:24];file=DEST/(ident+'.json')
  if url in blocked:return {'url':url,'status':'prior_access_restriction_respected'}
  if file.exists():return {'url':url,'status':'already_saved'}
  try:
   final,html,raw,_=f.get(url,b.timing());soup=BeautifulSoup(html,'lxml')
   h1=soup.select_one('main h1,article h1,h1')
   if not h1:raise p.StopFetch('no_headline')
   title=h1.get_text(' ',strip=True); ds=[]
   meta=soup.find('meta',attrs={'property':'article:published_time'})
   if meta:ds.append(meta.get('content'))
   for script in soup.find_all('script',type='application/ld+json'):
    try:ds+=list(dates(json.loads(script.string or script.get_text())))
    except (ValueError,TypeError):pass
   times=soup.select('article time[datetime],main time[datetime]');ds+=[t.get('datetime') for t in times]
   date=next((str(d) for d in ds if re.match(r'^(?:19|20)\d{2}-\d{2}-\d{2}',str(d))),None)
   text,checks=p.extract(html,title,final,compare_alternative=False)
   if len(text)<800:raise p.StopFetch('short_text')
   ok,tags=relevance(title,text)
   if not ok:raise p.StopFetch('relevance_needs_review')
   doc={'id':ident,'url':final,'title':title,'source':p.host(final),'source_id':'TARGETED_'+p.host(final),'language':(soup.html.get('lang','und') if soup.html else 'und'),'date':date or 'unknown','source_text':text,'text_sha256':p.digest(text.encode()),'raw_html_sha256':p.digest(raw),'acquired_at':p.stamp(),'country_retrieval_hint':seed['country_hint'],'country_hint_not_asserted':True,'collection_cohort':'targeted_geographic_supplement','rights_status':'private_research_copy_permission_not_established_for_redistribution','public_redistribution_allowed':False,**checks,**tags}
   doc.update(b.quality(doc));doc['document_genre']=seed.get('genre','news_or_commentary')
   good,review,flags=eligible(doc)
   if not date:flags.append('source_publication_date_unresolved');good=False
   doc.update(research_eligible=good,terminal_adjudication=review,quality_flags=flags)
   savedir=DEST if date else DEST.parent/'targeted_undated'
   savedir.mkdir(parents=True,exist_ok=True)
   (savedir/(ident+'.html.gz')).write_bytes(gzip.compress(raw,mtime=0));p.dump(savedir/(ident+'.json'),doc)
   return {'url':url,'status':'eligible' if good else 'review','date':date,'characters':len(text),'flags':flags}
  except Exception as e:return {'url':url,'status':getattr(e,'reason',type(e).__name__)}
 with cf.ThreadPoolExecutor(max_workers=4) as pool:
  results=[]
  for x in pool.map(collect,items):results.append(x);print(json.dumps(x),flush=True)
 runid=datetime.now().strftime('%Y%m%d_%H%M%S')
 p.dump(OUT/('targeted_attempts_'+runid+'.json'),results);p.dump(OUT/('targeted_requests_'+runid+'.json'),f.requests)
if __name__=='__main__':main()

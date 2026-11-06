"""Versioned, resumable publisher-API expansion; never edits old corpora.

Public API discovery -> robots -> frozen pagination -> extraction -> relevance
-> completeness -> exact body/URL dedup -> private shards and audit ledger.
One in-flight request per host; existing Fetcher enforces delays and circuits.
"""
from __future__ import annotations
import argparse, collections, concurrent.futures as cf, gzip, json, re, sqlite3, threading, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
import fulltext_pilot as p
import bulk_fulltext as b
import collect_public_fulltext_library as lib
from fulltext_review_rules import review_terminal
from expansion_quality import adjudicate

ROOT=p.ROOT
OUT=ROOT/'analysis/global_expansion_20261106'
PRIVATE=ROOT/'data/private_global_expansion_20261106'
VERSION='global-fulltext-expansion-1.0'

def relevance(title,text,language):
 ok,tags=lib.relevance(title,text)
 # Multilingual evidence is stored verbatim; no machine-generated source text.
 extra={
  'es':r'cambio clim[aá]tico|calentamiento global|descarboniz|energ[ií]a renovable|energ[ií]a solar|emisiones de carbono|gases de efecto invernadero|deforestaci[oó]n|transici[oó]n energ[eé]tica|combustibles f[oó]siles|justicia clim[aá]tica',
  'id':r'perubahan iklim|pemanasan global|dekarbonisasi|energi terbarukan|energi surya|emisi karbon|gas rumah kaca|deforestasi|transisi energi|bahan bakar fosil|krisis iklim|batubara|batu bara',
 }
 if language in extra:
  regex=re.compile(extra[language],re.I); hits=list(regex.finditer(text))
  ok=bool(regex.search(title)) or (len(hits)>=3 and hits[0].start()<2500)
  tags.update(multilingual_relevance_evidence=[{'text':m.group(),'start':m.start(),'end':m.end()} for m in hits[:8]],relevance_rule='native_language_title_hit OR >=3 body_hits with first within 2500 characters')
 # Reviews, retail promotions and giveaways are outside governance research.
 if re.search(r'\b(?:giveaway|discount code|coupon|black friday|hands.on review|test drive|unboxing|accessories review)\b',title,re.I):
  return False,{**tags,'exclusion':'consumer_promotion_or_product_review'}
 if tags.get('topic_tags')==['climate_impacts'] and not re.search(r'climat|global warming|carbon|emission|adaptation|resilien',title+' '+text[:6000],re.I):
  return False,{**tags,'exclusion':'weather_without_climate_context'}
 return ok,tags

def run(args):
 OUT.mkdir(parents=True,exist_ok=True); PRIVATE.mkdir(parents=True,exist_ok=True)
 (PRIVATE/'batches').mkdir(exist_ok=True)
 configfile=OUT/'run_config.json'
 if configfile.exists(): config=json.loads(configfile.read_text('utf-8'))
 else:
  probes=json.loads((OUT/'source_probes.json').read_text('utf-8'))
  sources=[s for s in probes if s.get('verified')]
  sources+=json.loads((ROOT/'config/research_archives.json').read_text('utf-8'))['sources']
  for s in sources:
   s['language']={'MONGABAY_ES':'es','MONGABAY_ID':'id'}.get(s['source_id'],'en')
  config={'version':VERSION,'after':'1992-01-01T00:00:00','before':datetime.now(timezone.utc).replace(tzinfo=None,microsecond=0).isoformat(),'sources':sources,'rights':'Private analytical research copy only; permission for redistribution not established.','model_calls':0}
  lib.state_write(configfile,config)
 db=sqlite3.connect(PRIVATE/('ledger'+('_'+args.ledger if args.ledger else '')+'.sqlite'),check_same_thread=False)
 db.execute('PRAGMA journal_mode=WAL')
 db.executescript('CREATE TABLE IF NOT EXISTS bodies(sha TEXT PRIMARY KEY,url TEXT UNIQUE,id TEXT,corpus TEXT); CREATE TABLE IF NOT EXISTS attempts(source TEXT,page INTEGER,url TEXT,status TEXT,details TEXT);')
 if not db.execute("SELECT 1 FROM bodies WHERE corpus='baseline' LIMIT 1").fetchone():
  for name in ('original_recovery_labeled_fulltexts.jsonl.gz','new_library_labeled_fulltexts.jsonl.gz'):
   file=ROOT/'analysis/governance_handover_20261105_final'/name
   with gzip.open(file,'rt',encoding='utf-8') as stream:
    for line in stream:
     d=json.loads(line); text=d.get('source_text') or d.get('fulltext') or ''
     if text: db.execute('INSERT OR IGNORE INTO bodies VALUES(?,?,?,?)',(p.digest(text.encode()),b.key(d.get('publisher_url') or d.get('url') or ''),d.get('id') or d['document_id'],'baseline'))
  db.commit()
 # Rebuild only the generated dedup index from durable shards after a crash.
 # Original corpus rows and original files are untouched.
 db.execute("DELETE FROM bodies WHERE corpus='expansion'")
 for file in PRIVATE.glob('*.jsonl.gz'):
  with gzip.open(file,'rt',encoding='utf-8') as stream:
   for line in stream:
    d=json.loads(line); db.execute('INSERT OR IGNORE INTO bodies VALUES(?,?,?,?)',(d['text_sha256'],b.key(d['url']),d['id'],'expansion'))
 db.commit()
 lock=threading.RLock(); fetcher=p.Fetcher(); p.ACCEPT_ENCODING='gzip'; p.TIMEOUT=30
 deadline=time.monotonic()+args.minutes*60
 sources=config['sources']
 if args.probes:
  sources=[{**s,'language':'en'} for s in json.loads((OUT/args.probes).read_text('utf-8')) if s.get('verified')]
 sources=[s for s in sources if not args.sources or s['source_id'] in args.sources.split(',')]
 def event(source,page,url,status,details=None):
  with lock: db.execute('INSERT INTO attempts VALUES(?,?,?,?,?)',(source,page,url,status,json.dumps(details or {},ensure_ascii=False)))
 def worker(source):
  sid=source['source_id']; statefile=OUT/(sid+'_state.json')
  state=json.loads(statefile.read_text('utf-8')) if statefile.exists() else {'next_page':1,'accepted':0,'review':0,'screened':0}
  if state.get('complete'): return
  for page in range(state['next_page'],5001):
   if time.monotonic()>deadline: break
   url=source['endpoint']+'?'+urlencode(dict(per_page=50,page=page,after=config['after'],before=config['before'],orderby='date',order='desc',_fields='id,link,title,date,date_gmt,content'))
   batchfile=PRIVATE/'batches'/f'{sid}_{page:05d}.json.gz'
   t=time.monotonic()
   try:
    if batchfile.exists():
     saved=json.loads(gzip.decompress(batchfile.read_bytes())); posts=saved['posts']; heads=saved['headers']
    else:
     final,body,_,headers=fetcher.get(url,b.timing()); posts=json.loads(body)
     if '?' not in final: raise p.StopFetch('API_redirect_discards_pagination_parameters')
     if not isinstance(posts,list): raise p.StopFetch('not_public_post_list')
     posts=lib.policy_filtered_posts(posts); heads={k.lower():v for k,v in headers.items() if k.lower() in ('x-wp-total','x-wp-totalpages','date')}
     saved={'request_url':url,'retrieved_at':p.stamp(),'headers':heads,'posts':posts}
     batchfile.write_bytes(gzip.compress(p.jsonbytes(saved),mtime=0))
   except Exception as e:
    reason=getattr(e,'reason',type(e).__name__); event(sid,page,url,reason)
    state.update(last_failure=reason,at=p.stamp()); lib.state_write(statefile,state)
    with lock: db.commit()
    return
   state.pop('last_failure',None)
   state.update(total_posts=heads.get('x-wp-total'),total_pages=heads.get('x-wp-totalpages'))
   documents=[]
   for post in posts:
    state['screened']+=1; articleurl=post.get('link',''); title=lib.clean_title(post.get('title',{}).get('rendered',''))
    try:
     if post.get('body_omitted'): raise p.StopFetch(post['body_omitted'])
     if p.host(articleurl) not in source['allowed_hosts'] or not title: raise p.StopFetch('publisher_identity_missing')
     with lock: duplicate=db.execute('SELECT 1 FROM bodies WHERE url=?',(b.key(articleurl),)).fetchone()
     if duplicate: raise p.StopFetch('duplicate_url')
     date=post.get('date_gmt') or post.get('date')
     if not config['after']<=str(date)<=config['before']: raise p.StopFetch('date_outside_frozen_window')
     row={'id':'exp_'+p.digest(b.key(articleurl).encode())[:24],'url':articleurl,'title':title,'date':date,'source':source['name'],'source_id':sid,'language':source['language'],'_skip_alternative':True}
     text,checks=b.accept_post(row,post)
     if len(text)<800: raise p.StopFetch('short_text_below_800_characters')
     ok,tags=relevance(title,text,source['language'])
     if not ok: raise p.StopFetch('not_focal_climate_governance_or_transition')
     doc={**row,**checks,**tags,'source_text':text,'text_sha256':p.digest(text.encode()),'text_characters':len(text),'acquired_at':p.stamp(),'pipeline_version':VERSION,'request_url':url,'raw_batch_path':str(batchfile.relative_to(ROOT)),'publisher_api_post_id':post['id'],'public_redistribution_allowed':False,'rights_status':'private_research_copy_permission_not_established_for_redistribution','translation':False,'collection_cohort':'new_expansion_20261106'}
     terminal=adjudicate(doc)
     if terminal:
      doc['terminal_adjudication']=terminal; doc['completeness_flags']=[v for v in doc['completeness_flags'] if v!='last_block_needs_review']
      if not doc['completeness_flags']: doc['status']='candidate_complete'
     doc.update(b.quality(doc))
     if doc['document_genre']!='news_or_commentary': raise p.StopFetch('non_article_genre')
     critical=set(doc['quality_flags'])-{'last_block_needs_review'}
     if critical: raise p.StopFetch('critical_quality_flags:'+','.join(sorted(critical)))
     doc['research_eligible']=not doc['quality_flags'] and doc['status']=='candidate_complete'
     with lock:
      cursor=db.execute('INSERT OR IGNORE INTO bodies VALUES(?,?,?,?)',(doc['text_sha256'],b.key(articleurl),doc['id'],'expansion'))
      if not cursor.rowcount: raise p.StopFetch('duplicate_body')
     documents.append(doc); state['accepted']+=int(doc['research_eligible']); state['review']+=int(not doc['research_eligible'])
     event(sid,page,articleurl,'eligible' if doc['research_eligible'] else 'terminal_review',{'id':doc['id'],'sha256':doc['text_sha256']})
    except Exception as e: event(sid,page,articleurl,getattr(e,'reason',type(e).__name__))
   # A page shard is immutable on successful checkpoint. Crash recovery uses
   # ledger reconciliation (see --reconcile) before continuing an interrupted page.
   shard=PRIVATE/f'{sid}_{page:05d}.jsonl.gz'
   if documents:
    if shard.exists():
     previous=[json.loads(line) for line in gzip.open(shard,'rt',encoding='utf-8')]
     merged={d['id']:d for d in previous+documents}; documents=list(merged.values())
    temporary=shard.with_suffix('.tmp'); temporary.write_bytes(gzip.compress(b''.join(p.jsonbytes(d)+b'\n' for d in documents),mtime=0)); temporary.replace(shard)
   with lock: db.commit()
   state.update(next_page=page+1,at=p.stamp(),last_page_seconds=round(time.monotonic()-t,2))
   # Respect server page-size caps; total-pages controls pagination.
   if not posts:
    state.update(complete=True,completion_reason='empty_API_page',advertised_total_not_fully_retrieved=bool(state['total_pages'] and page<int(state['total_pages'])))
   elif state['total_pages'] and page>=int(state['total_pages']): state['complete']=True
   lib.state_write(statefile,state)
   if page%10==0 or state.get('complete'): print(json.dumps({'source':sid,**state}),flush=True)
   if state.get('complete'): break
 with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
  for future in cf.as_completed([pool.submit(worker,s) for s in sources]):
   try: future.result()
   except Exception as e: print(json.dumps({'worker_error':type(e).__name__,'detail':str(e)[:150]}),flush=True)
 db.commit(); db.close(); p.dump(OUT/('requests_'+str(int(time.time()))+'.json'),fetcher.requests)

if __name__=='__main__':
 a=argparse.ArgumentParser(); a.add_argument('--minutes',type=int,default=240); a.add_argument('--workers',type=int,default=6); a.add_argument('--sources',default=''); a.add_argument('--ledger',default=''); a.add_argument('--probes',default='')
 args=a.parse_args()
 if not 1<=args.minutes<=300 or not 1<=args.workers<=8: a.error('bounded execution required')
 run(args)

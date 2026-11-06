"""Incremental, evidence-addressable relabeling; all old files stay untouched."""
import argparse,collections,concurrent.futures as cf,gzip,hashlib,json,re,time
from pathlib import Path
import fulltext_pilot as p
from expansion_quality import eligible
from climate_agent.governance_taxonomy_v2 import label,dictionary,VERSION

ROOT=p.ROOT; PRIVATE=ROOT/'data/private_global_expansion_20261106'; OUT=ROOT/'analysis/global_expansion_20261106'; CACHE=PRIVATE/'labeled'

def mask_navigation(body):
 chars=list(body); ranges=[]
 for m in re.finditer(r'(?m)^(?:Read more:|Also see:|Related:|News item from |By [A-Z][A-Za-z .\-]{3,65}$|\*?Imagen principal:|\*?Foto:|\*?Liputan ini merupakan)[^\n]*',body,re.I):
  ranges.append({'start':m.start(),'end':m.end(),'reason':'navigation_or_attribution_not_topic_evidence'})
  chars[m.start():m.end()]=' '*(m.end()-m.start())
 return ''.join(chars),ranges

def annotate(d):
 baseline='document_key' in d
 body=d['source_text']; title=d['title']; masked,ranges=mask_navigation(body)
 tags=label(title,masked)
 for e in tags['evidence']:
  assert {'title':title,'source_text':body}[e['field']][e['start']:e['end']]==e['quote']
 sha=hashlib.sha256(body.encode()).hexdigest()
 if sha!=d['text_sha256']: raise ValueError('immutable source checksum mismatch')
 if baseline:
  ident=d['document_id']; date=d['published_date']; source=d['publisher']; cohort=d['cohort']; good=d['research_eligible']; flags=d.get('source_quality_flags',[]); review=None
 else:
  ident=d['id'];date=d['date'][:10]; source=d['source'];cohort=d.get('collection_cohort','new_expansion_20261106');good,review,flags=eligible(d)
  if d.get('document_genre')=='periodical_issue': good=False
 # Clearly labelled product reviews are preserved but not research-eligible.
 if d.get('source_id') in ('THEDRIVEN','ELECTREK') and re.search(r'\breview\b|\btest drive\b|\bvideo\b|\bdeal\b',title,re.I):
  good=False;flags=flags+['consumer_review_or_promotion_scope_review']
 return {'document_id':ident,'cohort':cohort,'title':title,'url':d['url'],'publisher':source,'published_raw':d.get('published_raw') or d.get('source_published_at') or d.get('date'),'published_utc':d.get('published_utc') or d.get('source_published_at_utc'),'published_date':date,'date_precision':d.get('date_precision','day'),'year':int(date[:4]),'month':date[:7] if len(date)>=7 else None,'language':d.get('language','und'),'source_text':body,'text_sha256':sha,'normalized_sha256':hashlib.sha256(re.sub(r'\s+',' ',body).strip().casefold().encode()).hexdigest(),'research_eligible':bool(good),'quality_flags':flags,'terminal_adjudication':review,'document_genre':d.get('document_genre','news_or_commentary'),'labels':tags,'excluded_evidence_ranges':ranges,'raw_batch_path':d.get('raw_batch_path'),'rights_status':d.get('rights_status'),'public_redistribution_allowed':False,'source_metadata':{k:d.get(k) for k in ('request_url','publisher_api_post_id','source_block_coverage','source_blocks','acquired_at','pdf_url','pdf_pages','pdf_sha256') if d.get(k) is not None}}

def inputs():
 base=ROOT/'analysis/governance_handover_20261105_final'
 if (PRIVATE/'baseline_shards').exists(): yield from sorted((PRIVATE/'baseline_shards').glob('*.gz'))
 else:
  yield base/'original_recovery_labeled_fulltexts.jsonl.gz'
  yield base/'new_library_labeled_fulltexts.jsonl.gz'
 yield from sorted(PRIVATE.glob('*.jsonl.gz'))
 yield from sorted((PRIVATE/'historical').glob('*.json'))
 yield from sorted((PRIVATE/'targeted').glob('*.json'))

def main(args):
 CACHE.mkdir(parents=True,exist_ok=True); p.dump(OUT/'taxonomy_14_83.json',dictionary())
 codehash=p.digest((ROOT/'src/climate_agent/governance_taxonomy_v2.py').read_bytes()+(ROOT/'scripts/expansion_quality.py').read_bytes()+(ROOT/'scripts/label_global_expansion.py').read_bytes())
 deadline=time.monotonic()+args.minutes*60; manifestfile=OUT/('label_cache_manifest_p'+str(args.part)+'.json')
 manifest=json.loads(manifestfile.read_text('utf-8')) if manifestfile.exists() else {}
 with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
  while time.monotonic()<deadline:
   pending=0
   for file in inputs():
    if int(p.digest(str(file.relative_to(ROOT)).encode())[:8],16)%args.parts!=args.part:continue
    if time.monotonic()>deadline:break
    # Files are atomically replaced by the collectors; sha binds exact input.
    raw=file.read_bytes(); digest=p.digest(raw); name=str(file.relative_to(ROOT)); old=manifest.get(name,{})
    if old.get('input_sha256')==digest and old.get('code_sha256')==codehash and (CACHE/old.get('file','missing')).exists():continue
    pending+=1
    docs=[json.loads(line) for line in gzip.decompress(raw).decode('utf-8').splitlines()] if file.suffix=='.gz' else [json.loads(raw)]
    dest=CACHE/(p.digest(name.encode())[:16]+'_'+digest[:12]+'_'+codehash[:8]+'.jsonl.gz'); tmp=dest.with_suffix('.tmp')
    counts=collections.Counter(); country=collections.Counter(); focal=collections.Counter(); sub=collections.Counter(); subfocal=collections.Counter(); years=collections.Counter()
    with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=3) as stream:
     for d in pool.map(annotate,docs,chunksize=25):
      stream.write(json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n');counts['records']+=1
      counts['eligible']+=int(d['research_eligible']);years[str(d['year'])]+=int(d['research_eligible'])
      if d['research_eligible']:
       country.update(d['labels']['country_mentions']);focal.update(d['labels']['country_focal_candidates']);sub.update(d['labels']['subcategory_mentions']);subfocal.update(d['labels']['focal_subcategory_candidates'])
    tmp.replace(dest)
    manifest[name]={'input_sha256':digest,'code_sha256':codehash,'file':dest.name,**counts,'countries':dict(country),'focal_countries':dict(focal),'subcategories':dict(sub),'focal_subcategories':dict(subfocal),'years':dict(years)}
    p.dump(manifestfile,manifest)
    print(json.dumps({'labeled_input':name,**counts}),flush=True)
   if not args.watch:break
   if not pending:time.sleep(15)
def prepare_baseline():
 target=PRIVATE/'baseline_shards';target.mkdir(parents=True,exist_ok=True);mapping={}
 for file in (ROOT/'analysis/governance_handover_20261105_final').glob('*labeled_fulltexts.jsonl.gz'):
  count=0;lines=[];part=0
  with gzip.open(file,'rb') as stream:
   for line in stream:
    lines.append(line);count+=1
    if len(lines)==500:
     name=file.stem+f'_{part:04d}.jsonl.gz';(target/name).write_bytes(gzip.compress(b''.join(lines),mtime=0));lines=[];part+=1
   if lines:(target/(file.stem+f'_{part:04d}.jsonl.gz')).write_bytes(gzip.compress(b''.join(lines),mtime=0))
  mapping[str(file.relative_to(ROOT))]={'sha256':p.digest(file.read_bytes()),'records':count,'shards':part+bool(lines)}
 p.dump(OUT/'baseline_split_map.json',mapping)

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--watch',action='store_true');a.add_argument('--minutes',type=int,default=240);a.add_argument('--workers',type=int,default=1);a.add_argument('--part',type=int,default=0);a.add_argument('--parts',type=int,default=1);a.add_argument('--prepare',action='store_true');args=a.parse_args()
 if args.prepare:prepare_baseline()
 else:main(args)

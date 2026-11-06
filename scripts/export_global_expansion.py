"""Freeze cached annotations into a validated private research handover.

No inferred dates, synthetic bodies, automatic public upload, or fabricated
country coverage. All joins use immutable text identities and evidence offsets.
"""
import argparse,collections,gzip,hashlib,itertools,json,re,shutil,sqlite3,time
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
import fulltext_pilot as p
from climate_agent.governance_taxonomy_v2 import dictionary
from postvalidate_global_labels import enrich

ROOT=p.ROOT;PRIVATE=ROOT/'data/private_global_expansion_20261106';ANALYSIS=ROOT/'analysis/global_expansion_20261106'
def canon(url):
 u=urlsplit(url);return urlunsplit((u.scheme.lower(),u.netloc.lower(),u.path.rstrip('/'),u.query,''))
def dumps(d):return json.dumps(d,ensure_ascii=False,separators=(',',':'))
def file_hash(file):
 h=hashlib.sha256()
 with open(file,'rb') as stream:
  for chunk in iter(lambda:stream.read(2*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def main(args):
 from label_global_expansion import inputs
 entries={}
 for file in sorted(ANALYSIS.glob('label_cache_manifest_p*.json')):entries.update(json.loads(file.read_text('utf-8')))
 pending=[str(f.relative_to(ROOT)) for f in inputs() if str(f.relative_to(ROOT)) not in entries]
 if pending and not args.allow_incomplete:raise SystemExit('Annotation unfinished for '+str(len(pending))+' inputs; not sealing incomplete handover.')
 dest=ANALYSIS/args.name
 if dest.exists():raise SystemExit('Use a new snapshot name; existing deliveries are immutable.')
 dest.mkdir(parents=True);db=sqlite3.connect(dest/'climate_governance.sqlite')
 db.executescript('''PRAGMA journal_mode=WAL;
 CREATE TABLE articles(article_id TEXT PRIMARY KEY,cohort TEXT,title TEXT,url TEXT,publisher TEXT,published_date TEXT,date_precision TEXT,year INTEGER,language TEXT,eligible INTEGER,genre TEXT,source_text TEXT,text_sha256 TEXT,normalized_sha256 TEXT,metadata_json TEXT);
 CREATE TABLE labels(article_id TEXT,dimension TEXT,label TEXT,focal INTEGER,PRIMARY KEY(article_id,dimension,label));
 CREATE TABLE evidence(article_id TEXT,dimension TEXT,label TEXT,field TEXT,start INTEGER,end INTEGER,quote TEXT,method TEXT);
 CREATE TABLE lineage(article_id TEXT,cohort TEXT,source_document_id TEXT,input_file TEXT,relation TEXT);
 CREATE TABLE acquisition_inputs(input_file TEXT PRIMARY KEY,input_sha256 TEXT,annotation_sha256 TEXT,code_sha256 TEXT,records INTEGER);
 CREATE INDEX by_date ON articles(published_date);CREATE INDEX by_source ON articles(publisher);CREATE INDEX by_label ON labels(dimension,label);
 CREATE VIEW annual_source_coverage AS SELECT year,publisher,count(*) articles FROM articles WHERE eligible=1 GROUP BY year,publisher;
 CREATE VIEW annual_topic_mentions AS SELECT a.year,l.label,count(*) articles FROM articles a JOIN labels l USING(article_id) WHERE a.eligible=1 AND l.dimension='subcategory' GROUP BY a.year,l.label;
 CREATE VIEW annual_country_mentions AS SELECT a.year,l.label,count(*) articles FROM articles a JOIN labels l USING(article_id) WHERE a.eligible=1 AND l.dimension='country' GROUP BY a.year,l.label;
 ''')
 counts=collections.Counter();sources=collections.Counter();years=collections.Counter();countries=collections.Counter();topics=collections.Counter();focal_countries=collections.Counter();focal_topics=collections.Counter();cohorts=collections.defaultdict(collections.Counter)
 seen={};urls={};samples=collections.defaultdict(list);examples={};bytecount=0;stale=[]
 streams={k:gzip.open(dest/(k+'.jsonl.gz'),'wt',encoding='utf-8',compresslevel=6) for k in ['original_recovery','new_library','review_required']}
 try:
  for input_name,info in sorted(entries.items(),key=lambda kv:('baseline_shards' not in kv[0],kv[0])):
   input_path=ROOT/input_name;file=PRIVATE/'labeled'/info['file']
   if not input_path.exists() or p.digest(input_path.read_bytes())!=info['input_sha256']:
    stale.append(input_name);continue
   db.execute('INSERT INTO acquisition_inputs VALUES(?,?,?,?,?)',(input_name,info['input_sha256'],p.digest(file.read_bytes()),info['code_sha256'],info['records']))
   with gzip.open(file,'rt',encoding='utf-8') as stream:
    for line in stream:
     d=enrich(json.loads(line));body=d['source_text'];tags=d['labels'];counts['input_records']+=1
     d['publisher_name_original']=d['publisher'];d['publisher']=(urlsplit(d['url']).hostname or d['publisher']).lower().removeprefix('www.')
     assert p.digest(body.encode())==d['text_sha256'],'source checksum mismatch'
     for e in tags['evidence']:
      assert d[e['field']][e['start']:e['end']]==e['quote'],'evidence offset mismatch'
     norm=d['normalized_sha256'];url=canon(d['url']);old=seen.get(norm) or urls.get(url)
     if old:
      counts['duplicates_preserved_as_lineage']+=1
      db.execute('INSERT INTO lineage VALUES(?,?,?,?,?)',(old,d['cohort'],d['document_id'],input_name,'same_normalized_body' if norm in seen else 'same_canonical_url'))
      continue
     ident='doc_'+norm[:32];seen[norm]=ident;urls[url]=ident;good=bool(d['research_eligible'])
     # Historical issue-level text remains a separate review supplement.
     if d.get('document_genre')=='periodical_issue':good=False
     d['research_eligible']=good;d['article_id']=ident
     attribution=re.search(r'(?mi)^News item from ([^\n]+)',body)
     if attribution:
      d['content_origin_hint']='publisher_distributed_press_release'
      d['origin_attribution']={'name':attribution.group(1),'start':attribution.start(),'end':attribution.end(),'quote':attribution.group()}
     else:d['content_origin_hint']='publisher_article_origin_not_independently_verified'
     # Disallow AI regex false positives matching the substring in "said".
     ev=[];removed=0
     for e in tags['evidence']:
      if e['label_type']=='subcategory' and e['label_id']=='G08.05' and re.match(r'^ai.{0,25}climate',e['quote'],re.I):
       text=d[e['field']];i=e['start']
       if (i and text[i-1].isalpha()) or (i+2<len(text) and text[i+2].isalpha()):removed+=1;continue
      ev.append(e)
     if removed:
      tags['evidence']=ev;d['post_label_validation']={'removed_AI_substring_matches':removed,'rule':'AI must be a token, not part of said/again'}
      if not any(e['label_type']=='subcategory' and e['label_id']=='G08.05' for e in ev):
       for key in ['subcategory_mentions','focal_subcategory_candidates']:tags[key]=[x for x in tags[key] if x!='G08.05']
       tags['scores'].pop('G08.05',None)
       tags['category_mentions']=sorted({x[:3] for x in tags['subcategory_mentions']})
       if tags['primary_subcategory']=='G08.05':
        tags['primary_subcategory']=max(tags['scores'],key=tags['scores'].get) if tags['scores'] else None
        tags['primary_category']=tags['primary_subcategory'][:3] if tags['primary_subcategory'] else None
     metadata={k:v for k,v in d.items() if k not in ['source_text','labels']}
     db.execute('INSERT INTO articles VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(ident,d['cohort'],d['title'],d['url'],d['publisher'],d['published_date'],d['date_precision'],d['year'],d['language'],int(good),d['document_genre'],body,d['text_sha256'],norm,dumps(metadata)))
     db.execute('INSERT INTO lineage VALUES(?,?,?,?,?)',(ident,d['cohort'],d['document_id'],input_name,'retained'))
     dims={'country':'country_mentions','organization':'organization_mentions','subcategory':'subcategory_mentions','category':'category_mentions','policy_tool':'policy_tool_mentions','policy_stage':'policy_stage_mentions'}
     for dim,key in dims.items():
      focal=set(tags.get({'country':'country_focal_candidates','subcategory':'focal_subcategory_candidates'}.get(dim,''),[]))
      for lab in set(tags[key]):db.execute('INSERT INTO labels VALUES(?,?,?,?)',(ident,dim,lab,int(lab in focal)))
     for e in tags['evidence']:db.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',(ident,e['label_type'],e['label_id'],e['field'],e['start'],e['end'],e['quote'],e.get('method','lexical_evidence_candidate')))
     bucket='review_required' if not good else ('original_recovery' if 'original' in d['cohort'] else 'new_library')
     payload=dumps(d)+'\n';streams[bucket].write(payload);bytecount+=len(payload.encode())
     counts['unique_records']+=1;counts['eligible']+=int(good);counts['review_required']+=int(not good);cohorts[d['cohort']]['unique']+=1;cohorts[d['cohort']]['eligible']+=int(good)
     if good:
      sources[d['publisher']]+=1;years[str(d['year'])]+=1;countries.update(tags['country_mentions']);topics.update(tags['subcategory_mentions']);focal_countries.update(tags['country_focal_candidates']);focal_topics.update(tags['focal_subcategory_candidates'])
      for e in tags['evidence']:
       if e['label_type'] not in ('country','subcategory'):continue
       key=e['label_type']+':'+e['label_id'];score=100 if e['field']=='title' else (30 if e['start']<1500 else 1)
       if key not in examples or score>examples[key]['selection_score']:
        value=d[e['field']];examples[key]={'article_id':ident,'title':d['title'],'url':d['url'],'published_date':d['published_date'],'selection_score':score,'evidence':e,'context':value[max(0,e['start']-120):min(len(value),e['end']+200)]}
      if len(samples[d['publisher']])<5:samples[d['publisher']].append({'article_id':ident,'title':d['title'],'url':d['url'],'published_date':d['published_date'],'head':body[:600],'tail':body[-600:],'source_text_sha256':d['text_sha256'],'reviewer_assessment':None})
   db.commit()
   if counts['unique_records']%500<60:print(dumps(dict(counts)),flush=True)
 finally:
  for stream in streams.values():stream.close()
 db.commit();integrity=db.execute('PRAGMA integrity_check').fetchone()[0];assert integrity=='ok'
 db.execute('PRAGMA wal_checkpoint(TRUNCATE)');db.execute('PRAGMA journal_mode=DELETE');db.close()
 taxonomy=dictionary();p.dump(dest/'taxonomy_14_83.json',taxonomy)
 shutil.copy2(ROOT/'config/country_codes.json',dest/'country_codes.json')
 p.dump(dest/'stratified_review_sample.json',dict(samples))
 p.dump(dest/'coverage_evidence_examples.json',examples)
 p.dump(dest/'coverage.json',{'counting_unit':'deduplicated_article','eligible_only':True,'years':dict(sorted(years.items())),'publishers':dict(sources.most_common()),'country_mentions':dict(countries),'country_focal_candidates':dict(focal_countries),'subcategory_mentions':dict(topics),'focal_subcategory_candidates':dict(focal_topics),'cohorts':{k:dict(v) for k,v in cohorts.items()},'warning':'Mention coverage is not balanced reporting or validated actor positions. Focal labels are candidates.'})
 base=ROOT/'analysis/governance_handover_20261105_final'
 for name in ['policy_timeline.json','policy_timeline_ready.json']:
  if (base/name).exists():shutil.copy2(base/name,dest/name)
 p.dump(dest/'validation.json',{'completed_at':p.stamp(),'counts':dict(counts),'sqlite_integrity':integrity,'body_hash_check':'all retained and duplicate input records checked','evidence_offset_check':'all input evidence checked against immutable originals','stale_inputs_excluded':stale,'unlabeled_inputs':pending,'snapshot_complete':not pending and not stale,'uncompressed_jsonl_bytes':bytecount,'country_coverage':len(countries),'subcategory_coverage':len(topics),'human_label_accuracy':'not independently measured','model_generated_source_texts':0})
 manifest={f.name:{'bytes':f.stat().st_size,'sha256':file_hash(f)} for f in dest.iterdir() if f.is_file()}
 p.dump(dest/'manifest.json',manifest)
 print(dumps({'output':str(dest),'counts':dict(counts),'countries':len(countries),'subtopics':len(topics),'stale_inputs':len(stale)}),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--name',required=True);parser.add_argument('--allow-incomplete',action='store_true');main(parser.parse_args())

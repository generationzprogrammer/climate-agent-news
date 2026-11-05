"""Offline fulltext annotation + visualization-ready relational exports.

Never changes source bodies. Inputs/outputs and hashes are explicit; no model,
network, credentials or private subscriber lists are used.
"""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, itertools, json, re, shutil, sqlite3, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from climate_agent.governance_labels import VERSION, TOPICS, TOOL_PATTERNS, STAGES, label_text
from climate_agent.taxonomy import country_index, ORGANIZATION_GROUPS

def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def table(path,fields,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
        for r in rows:
            # Spreadsheet safety; logical strings remain unmodified in JSON/SQLite.
            w.writerow({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in r.items()})
def date_fields(d):
    raw=d.get('source_published_at') or d.get('date') or ''
    utc=d.get('source_published_at_utc')
    if not utc:
        try:
            x=datetime.fromisoformat(raw.replace('Z','+00:00'))
            if x.tzinfo:utc=x.astimezone(timezone.utc).isoformat()
        except (ValueError,TypeError):pass
    day=None
    try:day=datetime.fromisoformat(str(utc or raw).replace('Z','+00:00')).date().isoformat()
    except (ValueError,TypeError):pass
    return raw,utc,day

def annotate_input(arg):
    d,title=arg
    return d,title,label_text(title,d['source_text'])

def input_batches(handle,prior,cohort,size=128):
    batch=[]
    for line in handle:
        d=json.loads(line);key=cohort+':'+d['id']
        title=prior.get(key,{}).get('title') or d.get('page_title') or d['title']
        batch.append((d,title))
        if len(batch)>=size:yield batch;batch=[]
    if batch:yield batch

def annotated_records(handle,prior,cohort,pool):
    for batch in input_batches(handle,prior,cohort):
        yield from pool.map(annotate_input,batch,chunksize=8)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='analysis/governance_handover_20261105');ap.add_argument('--limit',type=int,default=0);a=ap.parse_args()
    out=ROOT/a.output;out.mkdir(parents=True,exist_ok=True)
    dbpath=out/'governance.sqlite'
    if dbpath.exists():raise SystemExit('Output already exists; use a fresh directory')
    conn=sqlite3.connect(dbpath)
    conn.executescript('''CREATE TABLE articles (document_key TEXT PRIMARY KEY,cohort TEXT,document_id TEXT,title TEXT,url TEXT,publisher TEXT,published_raw TEXT,published_utc TEXT,published_date TEXT,year INTEGER,month TEXT,language TEXT,text_sha256 TEXT,normalized_sha256 TEXT,source_text TEXT,complete_candidate INTEGER,research_eligible INTEGER,primary_topic TEXT,label_version TEXT,review_status TEXT);
    CREATE TABLE labels(document_key TEXT,label_type TEXT,label_id TEXT,PRIMARY KEY(document_key,label_type,label_id));
    CREATE TABLE evidence(document_key TEXT,label_type TEXT,label_id TEXT,field TEXT,start INTEGER,end INTEGER,quote TEXT);
    CREATE TABLE lineage(document_key TEXT,original_record_id TEXT);
    CREATE INDEX labels_lookup ON labels(label_type,label_id);
    CREATE INDEX date_lookup ON articles(published_date);
    CREATE INDEX evidence_lookup ON evidence(document_key,label_type,label_id);''')
    prior={}
    selection=ROOT/'analysis/fulltext_followup_20261104/research_selection/labels_with_evidence.jsonl.gz'
    with gzip.open(selection,'rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line);prior[r['key']]=r
    lineage=collections.defaultdict(list)
    for r in json.loads((ROOT/'data/private_fulltext_bulk_20261104/original_to_document.json').read_text('utf-8')):lineage[r['sha256']].append(r['target_id'])
    inputs=[('original_recovery',ROOT/'data/private_fulltext_bulk_20261104/fulltexts.jsonl.gz'),('new_library',ROOT/'data/private_public_fulltext_library_20261104/new_fulltexts.jsonl.gz')]
    before={str(p.relative_to(ROOT)):sha(p) for _,p in inputs}
    counts=collections.Counter();freq=collections.Counter();primary=collections.Counter();years=collections.Counter();source_year=collections.Counter();source_topic=collections.Counter();topic_year=collections.Counter();pairs=collections.Counter();entities=collections.Counter();entity_pairs=collections.Counter();links=collections.Counter();eligible_keys=set();norms=set();review_sample=[];sample_per=collections.Counter();url_keys=collections.defaultdict(list)
    handles={c:gzip.open(out/(c+'_labeled_fulltexts.jsonl.gz'),'wt',encoding='utf-8') for c,_ in inputs}
    pool=ProcessPoolExecutor(max_workers=6)
    for cohort,path in inputs:
        with gzip.open(path,'rt',encoding='utf-8') as f:
            for d,title,labels in annotated_records(f,prior,cohort,pool):
                text=d['source_text'];key=cohort+':'+d['id']
                assert hashlib.sha256(text.encode()).hexdigest()==d['text_sha256']
                raw,utc,day=date_fields(d);year=int(day[:4]) if day else None;month=day[:7] if day else None
                url=d.get('publisher_url') or d['url'];host=(urlsplit(url).hostname or '').removeprefix('www.')
                normalized=hashlib.sha256(re.sub(r'\s+',' ',text).strip().casefold().encode()).hexdigest()
                eligible=key in prior and normalized not in norms
                norms.add(normalized);complete=d.get('delivery_class')=='candidate_full_article'
                record={'document_key':key,'cohort':cohort,'document_id':d['id'],'title':title,'url':url,'publisher':host,'published_raw':raw,'published_utc':utc,'published_date':day,'year':year,'month':month,'language':d.get('language') or 'und','text_sha256':d['text_sha256'],'normalized_sha256':normalized,'source_text':text,'complete_candidate':int(complete),'research_eligible':int(eligible),'primary_topic':labels['primary_topic'],'label_version':VERSION,'review_status':'machine_candidate'}
                conn.execute('INSERT INTO articles VALUES ('+','.join('?' for _ in record)+')',tuple(record.values()))
                for e in labels['evidence']:
                    conn.execute('INSERT OR IGNORE INTO labels VALUES (?,?,?)',(key,e['label_type'],e['label_id']))
                    conn.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?)',(key,e['label_type'],e['label_id'],e['field'],e['start'],e['end'],e['quote']))
                original_ids=lineage.get(d['text_sha256'],[]) if cohort=='original_recovery' else []
                conn.executemany('INSERT INTO lineage VALUES (?,?)',[(key,x) for x in original_ids])
                handles[cohort].write(json.dumps({**record,'labels':labels,'source_record_ids':original_ids,'source_quality_flags':d.get('quality_flags',[]),'rights_status':d.get('rights_status'),'public_redistribution_allowed':False},ensure_ascii=False)+'\n')
                counts[cohort]+=1;counts['complete_candidate']+=complete;counts['research_eligible']+=eligible;counts['missing_date']+=not bool(day);counts['timezone_unresolved']+=not bool(utc)
                url_keys[url.rstrip('/')].append(key)
                if eligible:
                    eligible_keys.add(key);years[year]+=1;source_year[(host,year)]+=1;primary[labels['primary_topic']]+=1
                    topics=labels['topics'];freq.update(topics)
                    for t in topics:topic_year[(year,t)]+=1;source_topic[(host,year,t)]+=1
                    for x,y in itertools.combinations(sorted(topics),2):pairs[(x,y)]+=1
                    es=sorted(['country:'+x for x in labels['country_mentions']]+['organization:'+x for x in labels['organization_mentions']])
                    entities.update(es)
                    for x,y in itertools.combinations(es,2):entity_pairs[(x,y)]+=1
                    for e,t in itertools.product(es,topics):links[(e,t)]+=1
                    t=labels['primary_topic']
                    if sample_per[t]<20:
                        review_sample.append({'document_key':key,'title':title,'url':url,'primary_topic':t,'topic_labels':'|'.join(topics),'country_mentions':'|'.join(labels['country_mentions']),'human_topics':'','human_country_mentions':'','reviewer':'','notes':''});sample_per[t]+=1
                if sum(counts[c] for c,_ in inputs)%1000==0:conn.commit();print(json.dumps({'processed':sum(counts[c] for c,_ in inputs)}),flush=True)
                if a.limit and counts[cohort]>=a.limit:break
    pool.shutdown()
    for h in handles.values():h.close()
    conn.commit()
    # All aggregations use one row per eligible unique text, never count joins.
    table(out/'articles.csv',list(record.keys())[:14]+['complete_candidate','research_eligible','primary_topic','label_version','review_status'],(dict(zip([c[0] for c in cur.description],r)) for cur in [conn.execute('SELECT * FROM articles')] for r in cur))
    table(out/'article_labels.csv',['document_key','label_type','label_id'],(dict(zip(['document_key','label_type','label_id'],r)) for r in conn.execute('SELECT * FROM labels')))
    annual=[]
    for y in sorted(years,key=lambda x:x or 0):
        for t,*_ in TOPICS:
            sources=[s for s,yy in source_year if yy==y]
            rate=sum(source_topic[(s,y,t)]/source_year[(s,y)] for s in sources)/len(sources) if sources else 0
            annual.append({'year':y,'topic_id':t,'articles':topic_year[(y,t)],'denominator_articles':years[y],'share':topic_year[(y,t)]/years[y],'active_publishers':len(sources),'equal_publisher_mean_share':rate})
    table(out/'topic_year.csv',['year','topic_id','articles','denominator_articles','share','active_publishers','equal_publisher_mean_share'],annual)
    table(out/'source_year_coverage.csv',['publisher','year','articles'],({'publisher':s,'year':y,'articles':n} for (s,y),n in sorted(source_year.items(),key=str)))
    table(out/'topic_cooccurrence.csv',['topic_a','topic_b','cooccurring_articles','articles_a','articles_b','jaccard'],({'topic_a':x,'topic_b':y,'cooccurring_articles':pairs[(x,y)],'articles_a':freq[x],'articles_b':freq[y],'jaccard':pairs[(x,y)]/(freq[x]+freq[y]-pairs[(x,y)]) if freq[x]+freq[y] else 0} for x,y in itertools.combinations([t[0] for t in TOPICS],2)))
    table(out/'entity_cooccurrence.csv',['entity_a','entity_b','cooccurring_articles','articles_a','articles_b','jaccard'],({'entity_a':x,'entity_b':y,'cooccurring_articles':n,'articles_a':entities[x],'articles_b':entities[y],'jaccard':n/(entities[x]+entities[y]-n)} for (x,y),n in entity_pairs.most_common()))
    table(out/'entity_topic.csv',['entity','topic_id','articles'],({'entity':e,'topic_id':t,'articles':n} for (e,t),n in links.most_common()))
    table(out/'human_review_sample.csv',list(review_sample[0]) if review_sample else ['document_key'],review_sample)
    # Existing source-checked statements are a separate policy timeline. No
    # publication date from ordinary news is upgraded to an event date.
    timeline=[];milestone_links=[];seen=set()
    for path in [ROOT/'data/stance_evidence.json',ROOT/'data/stance_evidence_expansion_20261102.json']:
        data=json.loads(path.read_text('utf-8'));sources={r['id']:r for r in data.get('sources',[])}
        for row in data.get('assertions',[]):
            if row['id'] in seen:continue
            seen.add(row['id']);s=sources.get(row['source_id'],{});url=s.get('url','')
            timeline.append({'event_id':row['id'],'date':row.get('statement_date'),'date_basis':row.get('date_basis','dated_statement_from_existing_curated_layer'),'actor':row.get('actor_id'),'topic_proposition':row.get('proposition_id'),'title':s.get('title'),'summary_zh':row.get('summary_zh'),'source_url':url,'evidence_quote':row.get('evidence_quote'),'review_status':row.get('review_status'),'independent_human_validation':False})
            for key in url_keys.get(url.rstrip('/'),[]):milestone_links.append({'event_id':row['id'],'document_key':key,'relation':'exact_source_url','human_verified':False})
    dump(out/'policy_timeline.json',timeline)
    table(out/'policy_document_links.csv',['event_id','document_key','relation','human_verified'],milestone_links)
    taxonomy={'version':VERSION,'topics':[{'id':x[0],'parent':x[1],'name_zh':x[2],'name_en':x[3],'pattern':x[4]} for x in TOPICS],'policy_tools':TOOL_PATTERNS,'policy_stages':STAGES,'countries':country_index(),'organizations':[{'id':c,'name_zh':n} for g in ORGANIZATION_GROUPS for c,n,_ in g['items']],'unknown_policy':'unclassified; never force equal class sizes','tag_semantics':'text mentions only; not asserted policy stance, cooperation, jurisdiction, impact or causality'}
    dump(out/'taxonomy.json',taxonomy)
    assert conn.execute('SELECT COUNT(*) FROM evidence e LEFT JOIN articles a USING(document_key) WHERE a.document_key IS NULL').fetchone()[0]==0
    assert conn.execute('SELECT COUNT(*) FROM articles').fetchone()[0]==sum(counts[c] for c,_ in inputs)
    assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    conn.close()
    after={str(p.relative_to(ROOT)):sha(p) for _,p in inputs};assert before==after
    manifest={'version':VERSION,'created_at':datetime.now(timezone.utc).isoformat(),'counts':dict(counts),'primary_topics':dict(primary),'multilabel_topics':dict(freq),'input_sha256':before,'inputs_unchanged':before==after,'statistics_scope':'research_eligible=1; inherited strict relevant corpus eligibility; exact normalized duplicates suppressed','human_validation':'not performed; review sample is blank, not a gold standard','country_scope':'full source_text plus cleaned headline; names and disambiguation rules only','date_scope':'publisher publication date; unknown timezone retained, never assumed UTC','policy_timeline_events':len(timeline),'policy_document_links':len(milestone_links),'public_redistribution_allowed':False,'checks':['body SHA256 round-trip','all evidence offsets round-trip','foreign keys','SQLite integrity','input hashes unchanged'],'limitations':['No forced class balance. Sparse topics are retained under five parent domains.','Mention networks do not imply cooperation. Cooccurrence does not imply causal effect.','Equal-source weighting does not eliminate selection bias. No claim of 1995-present completeness.','Topic labels and policy-stage mentions are automatic candidates; stages are not attached to specific actions.','Non-English/Chinese recall is limited; und language is retained.','Publisher ownership and syndicated near duplicates are not resolved.']}
    dump(out/'manifest.json',manifest)
    shutil.copy2(ROOT/'docs/GOVERNANCE_HANDOVER.txt',out/'交接说明与数据字典.txt')
    code=out/'reproducibility';code.mkdir(exist_ok=True)
    for p in ['scripts/build_governance_handover.py','scripts/query_governance_example.py','src/climate_agent/governance_labels.py','src/climate_agent/taxonomy.py','config/country_codes.json','tests/test_governance_labels.py']:
        dest=code/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/p,dest)
    dump(out/'checksums.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='checksums.json'})
    archive=out.parent/(out.name+'_交接包.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(out)))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'counts':dict(counts)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()

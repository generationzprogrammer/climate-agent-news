"""Separate, source-labelled historical fulltext library explicitly authorized by user.

2015-present, five already registered public publisher APIs. Original-corpus
matches go back to the original acquisition ledger, not into new-article counts.
No translation, model, paid endpoint, access bypass or public publication.
"""
from __future__ import annotations
import argparse
import collections
import concurrent.futures as cf
import gzip
import html
import json
import re
import threading
import time
import urllib.parse as up
import zipfile
from datetime import datetime,timezone
from pathlib import Path

import bulk_fulltext as bulk
import fulltext_pilot as p
from climate_agent.publisher_recovery import identity, normalized, title_text

ROOT=p.ROOT
OUT=ROOT/'analysis/public_fulltext_library_20261104'
PRIVATE=ROOT/'data/private_public_fulltext_library_20261104'
VERSION='public-climate-energy-library-1.1'

def state_write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_bytes(p.jsonbytes(value))
    temporary.replace(path)
# Broad energy/climate coverage, with evidence saved. Mere publisher boilerplate
# or one incidental climate mention in a species story is not sufficient.
TOPICS={
 'climate_governance':r'\b(?:climate (?:change|crisis|policy|policies|action|finance|talks|summit|negotiations|justice)|COP\s*\d{1,2}|UNFCCC|Paris [Aa]greement|nationally determined contribution|net[ -]zero|decarboni[sz])',
 'emissions_carbon':r'\b(?:carbon (?:emission|dioxide|market|credit|tax|price|pricing|capture|removal|budget|storage|sink|footprint)|greenhouse gas|methane|CO2\b|emissions? (?:cut|reduction|trading|target)|global warming)',
 'clean_energy':r'\b(?:renewable(?: energy| power|s\b)|solar (?:power|energy|panel|farm|installation)|wind (?:power|energy|farm|turbine)|clean (?:energy|power)|energy transition|hydrogen|geothermal|nuclear (?:energy|power)|electric(?:ity)? grid|energy storage|batter(?:y|ies)|electric vehicle|EVs?\b|heat pump|energy efficiency)',
 'fossil_energy':r'\b(?:fossil fuel|coal(?:[ -](?:fired|power)| phase| mine| mining| plant| production)|oil (?:and gas|drilling|production|industry|pipeline)|natural gas|liquefied natural gas|LNG\b|petroleum)',
 'climate_impacts':r'\b(?:heatwave|heat wave|extreme heat|wildfire|drought|flood(?:ing|s)?\b|hurricane|cyclone|extreme rainfall|climate (?:risk|impact|adaptation|resilience)|sea.level rise|melting (?:ice|glacier)|ocean warming|climate attribution|El Ni[nñ]o|La Ni[nñ]a)',
 'land_climate':r'\b(?:deforestation|reforestation|forest carbon|REDD\+|carbon sequestration|land.use emission)',
}
CHINESE_TOPICS={
 'climate_governance':r'气候(?:变化|危机|政策|行动|融资|资金|谈判|大会|治理|正义)|碳中和|碳达峰|巴黎协定|自主贡献|双碳|氣候變化|碳達峰',
 'emissions_carbon':r'碳(?:排放|市场|交易|定价|税|捕集|捕获|封存|汇|足迹|效)|温室气体|甲烷减排|二氧化碳|碳排放|溫室氣體',
 'clean_energy':r'可再生能源|新能源|太阳能|光伏|风电|风能|储能|氢能|核电|核能|地热能|能源转型|清洁能源|电动汽车|电动车|热泵|节能|節能|能源效率|风力发电|太陽能|風電|儲能',
 'fossil_energy':r'化石(?:燃料|能源)|煤电|煤炭|燃煤|天然气|液化天然气|石油(?:开采|勘探|生产|行业)|煤電|天然氣',
 'climate_impacts':r'高温热浪|极端(?:高温|天气|降雨)|海平面上升|冰川(?:融化|消融|退缩)|气候(?:风险|影响|适应|韧性)|全球变暖|全球暖化',
 'land_climate':r'森林碳汇|植树造林|毁林|土地利用(?:变化|排放)|森林砍伐|生态碳汇',
}
PATTERNS={k:re.compile('(?:'+v+')|(?:'+CHINESE_TOPICS[k]+')',re.I) for k,v in TOPICS.items()}

def relevance(title,text):
    lead=text[:2500]; body=text[:12000]
    headline=[k for k,v in PATTERNS.items() if v.search(title)]
    lead_hits=[k for k,v in PATTERNS.items() if v.search(lead)]
    body_hits=[k for k,v in PATTERNS.items() if v.search(body)]
    match_count=sum(len(v.findall(body)) for v in PATTERNS.values())
    accepted=bool(headline) or len(lead_hits)>=2 or (bool(lead_hits) and match_count>=3)
    evidence={}
    for name in set(headline+lead_hits+body_hits):
        match=PATTERNS[name].search(title+'\n'+body)
        if match: evidence[name]=match.group()
    return accepted,{'topic_tags':sorted(evidence),'relevance_evidence':evidence,'relevance_match_count':match_count,'relevance_rule':'headline>=1 OR lead_topic_groups>=2 OR (body_matches>=3 AND lead_topic_groups>=1); dictionary-v2-en-zh','relevance_review':'deterministic_screen_not_independent_human_annotation'}

def clean_title(value): return title_text(html.unescape(value)) if isinstance(value,str) else ''

def policy_filtered_posts(posts):
    """Do not archive wire-service bodies received inside a public API batch."""
    for post in posts:
        if not isinstance(post,dict): continue
        content=(post.get('content') or {}).get('rendered','')
        plain=html.unescape(re.sub('<[^>]+>',' ',content))
        if p.restricted_syndication(plain):
            post['content']={'rendered':'','protected':True}
            post['body_omitted']='metadata_only_syndicated_source_policy'
    return posts

def matching_originals(post,source,url_index,title_index):
    url=post.get('link',''); title=clean_title(post.get('title',{}).get('rendered',''))
    possible=list(url_index.get(bulk.key(url),[]))+list(title_index.get(normalized(title),[]))
    matched={}
    for row in possible:
        direct=bulk.key(row['url'])==bulk.key(url)
        old_source=normalized(row.get('source') or '')
        publisher_ok=direct or p.host(row.get('publisher_homepage') or '').removeprefix('www.') in {h.removeprefix('www.') for h in source['allowed_hosts']}
        publisher_ok=publisher_ok or old_source==normalized(source['name']) or (old_source.startswith('mongabay') and source['source_id']=='INT007')
        if not publisher_ok: continue
        if not direct and len(normalized(title).split())<6: continue
        candidates=[title_text(row['title'],row.get('source')),title_text(row['title'],source['name'])]
        for h in source['allowed_hosts']: candidates.append(title_text(row['title'],h))
        match=next((m for t in candidates if (m:=identity(t,title,expected_date=row.get('date'),candidate_date=post.get('date_gmt') or post.get('date')))),None)
        if match: matched[row['id']]={**row,'resolved_identity':match}
    return list(matched.values())

def run(args):
    OUT.mkdir(parents=True,exist_ok=True); PRIVATE.mkdir(parents=True,exist_ok=True)
    for sub in ('articles','raw','response_batches'): (PRIVATE/sub).mkdir(exist_ok=True)
    rows=bulk.prepare()
    sources=json.loads((ROOT/'config/research_archives.json').read_text('utf-8'))['sources']
    confpath=OUT/'run_config.json'
    if confpath.exists(): config=json.loads(confpath.read_text('utf-8'))
    else:
        config={'version':VERSION,'after':'2015-01-01T00:00:00','before':datetime.now(timezone.utc).replace(microsecond=0,tzinfo=None).isoformat(),'sources':sources,'scope':'New private publisher API corpus, separate from original targets; English-keyword screening; no global representativeness claim.'}
        state_write(confpath,config)
    url_index=collections.defaultdict(list); title_index=collections.defaultdict(list)
    for row in rows:
        url_index[bulk.key(row['url'])].append(row)
        title_index[normalized(title_text(row['title'],row.get('source')))].append(row)
    original_docs={}; original_hashes=set()
    for file in (bulk.PRIVATE/'articles').glob('*.json'):
        doc=json.loads(file.read_text('utf-8')); original_hashes.add(doc['text_sha256'])
        original_docs[bulk.key(doc.get('publisher_url') or doc['url'])]=doc
    existing={}
    for file in (PRIVATE/'articles').glob('*.json'):
        doc=json.loads(file.read_text('utf-8')); existing[doc['text_sha256']]=doc
    seen_urls={bulk.key(x['url']) for x in existing.values()}
    per_source=collections.Counter(x['source_id'] for x in existing.values())
    fetcher=p.Fetcher(); p.ACCEPT_ENCODING='gzip'; lock=threading.RLock()
    # Original acquisition must have finished before this process starts.
    for file in (bulk.OUT/'circuits.json',OUT/'circuits.json'):
        if file.exists():
            state=json.loads(file.read_text('utf-8'))
            if time.time()-state.get('timestamp',0)<86400: fetcher.stop_hosts.update(state.get('hosts',{}))
    started=time.monotonic(); deadline=started+args.minutes*60
    with (OUT/'run_start_manifests.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({'started_at':p.stamp(),'pipeline_version':VERSION,'minutes':args.minutes,'target':args.target,'code_sha256':{name:p.digest((ROOT/name).read_bytes()) for name in ('scripts/collect_public_fulltext_library.py','scripts/bulk_fulltext.py','scripts/fulltext_pilot.py','src/climate_agent/publisher_recovery.py')}},ensure_ascii=False)+'\n')
    def event(value):
        with lock:
            with (OUT/'screening.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(value,ensure_ascii=False)+'\n')
    def add_original(post,source,text,checks,raw,matches,request_url):
        count=0
        with lock:
            for row in matches:
                if (bulk.PRIVATE/'articles'/f"{row['id']}.json").exists(): continue
                docrow={**row,'url':post['link'],'publisher_url':post['link'],'stratum':'direct_other'}
                result=bulk.save_doc(docrow,text,checks,raw,'publisher_historical_library_match',request_url)
                with (bulk.OUT/'attempts.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(result,ensure_ascii=False)+'\n')
                count+=1
        return count
    def worker(source):
        statefile=OUT/(source['source_id']+'_checkpoint.json')
        state=json.loads(statefile.read_text('utf-8')) if statefile.exists() else {'next_page':1,'screened':0,'accepted':0,'original_matches':0}
        if state.get('complete'): return
        for page in range(state['next_page'],args.max_pages+1):
            if time.monotonic()>deadline or len(existing)>=args.target or per_source[source['source_id']]>=args.per_source: break
            request_url=source['endpoint']+'?'+up.urlencode({'per_page':50,'page':page,'after':config['after'],'before':config['before'],'orderby':'date','order':'desc','_fields':'id,link,title,date,date_gmt,content'})
            timer=bulk.timing(); tick=time.monotonic()
            for attempt in range(2):
                try:
                    _,content,raw,headers=fetcher.get(request_url,timer)
                    posts=json.loads(content)
                    if not isinstance(posts,list): raise p.StopFetch('api_not_list')
                    state.pop('last_failure',None)
                    break
                except (p.StopFetch,ValueError) as e:
                    reason=getattr(e,'reason',type(e).__name__)
                    event({'source_id':source['source_id'],'page':page,'attempt':attempt+1,'status':reason})
                    transient=reason.startswith('network_') or reason in ('http_502','http_503','http_504','response_wall_time_limit')
                    if attempt==0 and transient and time.monotonic()+3<deadline:
                        time.sleep(2)
                        continue
                    state.update(last_failure=reason,at=p.stamp())
                    state_write(statefile,state)
                    return
            lower_headers={k.lower():v for k,v in headers.items()}
            total_pages=lower_headers.get('x-wp-totalpages')
            total_posts=lower_headers.get('x-wp-total')
            state.update(api_total_posts=total_posts,api_total_pages=total_pages)
            posts=policy_filtered_posts(posts)
            raw=p.jsonbytes(posts)
            batchpath=PRIVATE/'response_batches'/f"{source['source_id']}_{page:04d}_{p.digest(raw)[:16]}.json.gz"
            temporary=batchpath.with_suffix('.tmp')
            temporary.write_bytes(gzip.compress(raw,mtime=0)); temporary.replace(batchpath)
            whole_page=True
            for post in posts:
                if len(existing)>=args.target or per_source[source['source_id']]>=args.per_source:
                    whole_page=False; break
                if not isinstance(post,dict):
                    event({'source_id':source['source_id'],'page':page,'status':'invalid_post_object'}); continue
                url=post.get('link') or ''; title=clean_title((post.get('title') or {}).get('rendered',''))
                state['screened']+=1
                base={'source_id':source['source_id'],'url':url,'post_id':post.get('id'),'page':page}
                if post.get('body_omitted'):
                    event({**base,'status':post['body_omitted']}); continue
                if not bulk.public_homepage(url) or p.host(url) not in source['allowed_hosts'] or not title:
                    event({**base,'status':'publisher_identity_missing'}); continue
                if re.match(r'^\s*(sponsored|advertorial|partner content|paid content)\b',title,re.I):
                    event({**base,'status':'declared_promotional_content'}); continue
                matches=matching_originals(post,source,url_index,title_index)
                with lock: old=original_docs.get(bulk.key(url)); duplicate_url=bulk.key(url) in seen_urls
                if old:
                    checks={k:v for k,v in old.items() if k not in ('id','url','original_url','aliases','source_text','title')}
                    state['original_matches']+=add_original(post,source,old['source_text'],checks,p.jsonbytes(post),matches,request_url)
                    event({**base,'status':'already_in_original_fulltexts'}); continue
                if duplicate_url:
                    event({**base,'status':'already_in_new_library'}); continue
                if not matches and bulk.key(url) in url_index:
                    event({**base,'status':'known_original_url_identity_needs_review'}); continue
                row={'id':'library_'+p.digest(bulk.key(url).encode())[:20],'url':url,'title':title,'date':post.get('date_gmt') or post.get('date'),'source':source['name'],'source_id':source['source_id'],'language':'und','source_language_hint':'en','original_url':url}
                try:
                    date=datetime.fromisoformat(str(row['date']).replace('Z','+00:00')).replace(tzinfo=None)
                    if not datetime.fromisoformat(config['after'])<=date<=datetime.fromisoformat(config['before']): raise ValueError('date_out_of_range')
                    text,checks=bulk.accept_post(row,post)
                except (p.StopFetch,ValueError,TypeError,AttributeError,KeyError) as e:
                    event({**base,'status':getattr(e,'reason',str(e)[:80])}); continue
                sha=p.digest(text.encode())
                if matches:
                    state['original_matches']+=add_original(post,source,text,checks,p.jsonbytes(post),matches,request_url)
                    with lock: original_hashes.add(sha); original_docs[bulk.key(url)]={**row,**checks,'source_text':text,'text_sha256':sha}
                    event({**base,'status':'matched_original_records','original_ids':[x['id'] for x in matches]}); continue
                accepted,tags=relevance(title,text)
                if not accepted or len(text)<800:
                    event({**base,'status':'not_focal_climate_energy' if not accepted else 'short_text','characters':len(text)}); continue
                doc={**row,**checks,**tags,'source_text':text,'text_sha256':sha,'text_characters':len(text),'text_utf8_bytes':len(text.encode()),'acquired_at':p.stamp(),'pipeline_version':VERSION,'rights_status':'private_research_copy_permission_not_established_for_redistribution','public_redistribution_allowed':False,'translated':False,'publisher_api_post_id':post['id'],'request_url':request_url,'raw_batch_path':str(batchpath.relative_to(ROOT)),'raw_batch_sha256':p.digest(raw),'raw_batch_kind':'parsed_API_posts_with_restricted_syndicated_bodies_removed','original_record_match':'not_matched_by_url_publisher_title_date; unresolved_aliases_may_remain'}
                doc.update(bulk.quality(doc))
                critical={'possible_article_pagination_not_followed','unicode_replacement_character','possible_script_or_serialized_data_noise','source_block_coverage_below_90pct','strict_title_identity_needs_review','interface_dominant_text'}
                if doc['document_genre']!='news_or_commentary' or critical.intersection(doc['quality_flags']):
                    event({**base,'status':'quality_review_not_admitted','flags':doc['quality_flags']}); continue
                with lock:
                    if sha in original_hashes or sha in existing:
                        event({**base,'status':'duplicate_body'}); continue
                    if len(existing)>=args.target or per_source[source['source_id']]>=args.per_source: continue
                    file=PRIVATE/'articles'/f"{row['id']}.json"
                    temp=file.with_suffix('.tmp'); temp.write_bytes(p.jsonbytes(doc)); temp.replace(file)
                    existing[sha]=doc; seen_urls.add(bulk.key(url)); per_source[source['source_id']]+=1; state['accepted']+=1
                    if len(existing)%250==0: print(json.dumps({'new_unique_fulltexts':len(existing),'source_counts':dict(per_source),'seconds':round(time.monotonic()-started)}),flush=True)
                event({**base,'status':'admitted','sha256':sha,'quality_flags':doc['quality_flags']})
            state.update(next_page=page+1 if whole_page else page,at=p.stamp(),last_page_seconds=round(time.monotonic()-tick,3))
            if whole_page and (len(posts)<50 or (total_pages and page>=int(total_pages))): state['complete']=True
            state_write(statefile,state)
            if state.get('complete'): break
    with cf.ThreadPoolExecutor(max_workers=5) as pool:
        futures=[pool.submit(worker,s) for s in sources]
        for f in cf.as_completed(futures):
            try: f.result()
            except Exception as e: event({'status':'worker_exception','error_type':type(e).__name__}); print('worker_exception',type(e).__name__,flush=True)
    with (OUT/'requests.jsonl').open('a',encoding='utf-8') as f:
        for x in fetcher.requests: f.write(json.dumps(x,ensure_ascii=False)+'\n')
    state_write(OUT/'circuits.json',{'timestamp':time.time(),'hosts':fetcher.stop_hosts})
    with (OUT/'runs.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps({'at':p.stamp(),'seconds':time.monotonic()-started,'requests':len(fetcher.requests),'target':args.target,'minutes':args.minutes})+'\n')
    export()
    bulk.export()

def export():
    docs=[]
    original_ids=collections.defaultdict(list)
    for f in (bulk.PRIVATE/'articles').glob('*.json'):
        item=json.loads(f.read_text('utf-8'))
        if not p.restricted_syndication(item['source_text']): original_ids[item['text_sha256']].append(item['id'])
    original_hashes=set(original_ids); reclassified=[]
    cross_duplicates=0
    excluded_on_replay=0
    seen_hashes={}; duplicate_aliases=[]
    for file in sorted((PRIVATE/'articles').glob('*.json')):
        d=json.loads(file.read_text('utf-8'))
        if p.digest(d['source_text'].encode())!=d['text_sha256']: raise RuntimeError('Body checksum mismatch')
        if d.get('admission_status')=='excluded_on_replay':
            excluded_on_replay+=1
            continue
        if d['text_sha256'] in original_hashes:
            cross_duplicates+=1
            reclassified.append({'new_library_id':d['id'],'original_record_ids':original_ids[d['text_sha256']],'sha256':d['text_sha256'],'reason':'Original record now linked; original private library file remains preserved.'})
            continue
        if d['text_sha256'] in seen_hashes:
            duplicate_aliases.append({'id':d['id'],'representative_id':seen_hashes[d['text_sha256']],'sha256':d['text_sha256']})
            continue
        seen_hashes[d['text_sha256']]=d['id']
        docs.append(d)
    docs.sort(key=lambda x:(x['date'],x['id']))
    plain=0
    with gzip.open(PRIVATE/'new_fulltexts.jsonl.gz','wb') as f:
        for d in docs:
            b=p.jsonbytes(d)+b'\n'; f.write(b); plain+=len(b)
    summary={'updated_at':p.stamp(),'new_unique_body_count':len(docs),'candidate_complete_count':sum(d['delivery_class']=='candidate_full_article' for d in docs),'terminal_block_review_count':sum(bool(d['quality_flags']) for d in docs),'source_counts':dict(collections.Counter(d['source'] for d in docs)),'year_counts':dict(sorted(collections.Counter(d['date'][:4] for d in docs).items())),'topic_counts':dict(collections.Counter(t for d in docs for t in d['topic_tags'])),'jsonl_uncompressed_bytes':plain,'jsonl_gzip_bytes':(PRIVATE/'new_fulltexts.jsonl.gz').stat().st_size,'raw_batch_gzip_bytes':sum(f.stat().st_size for f in (PRIVATE/'response_batches').glob('*.gz')),'model_requests':0,'translation':False,'original_database_unchanged':bulk.inputs()==json.loads((bulk.OUT/'input_before.json').read_text('utf-8')),'limitations':['Five publisher API corpus, not a representative global sample.','Deterministic relevance and completeness checks, not independent human validation.','Original-corpus overlaps matched by URL and publisher/title/date are excluded; unrecognized historical aliases may remain.','Private research use; no public redistribution rights assumed.']}
    summary['cross_corpus_exact_duplicates_excluded']=cross_duplicates
    summary['relevance_exclusions_on_offline_replay']=excluded_on_replay
    summary['within_library_exact_duplicates_excluded']=len(duplicate_aliases)
    state_write(OUT/'exact_duplicate_aliases.json',duplicate_aliases)
    state_write(OUT/'cross_corpus_reclassified.json',reclassified)
    state_write(OUT/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)

def package():
    export()
    note='新增公开来源历史正文库\n\n本库与原数据库补齐结果分别统计。收集2015年至今的已登记发布者公开API文字，按气候与能源主题筛选；已匹配原库的文章回填原库，不重复计入新增数。原文未翻译、未用模型补写。\n\nnew_fulltexts.jsonl.gz每行一个JSON：包含原网址、原文标题、时间、来源、正文source_text、主题标签、筛选依据、文本指纹和质量标记。候选完整与末段待核查分开；最后一段无终止标点往往是署名或表格，不等同已证实截断，仍保留标记。\n\n来源集中于五个媒体，不能视作全球随机样本或全球报道总量。本次为确定性筛选，未作逐篇独立人工审核。尚未识别的历史聚合网址别名可能造成跨库未识别重叠。\n\n全文默认私有研究留存，不代表已获得公开转载授权。请勿上传公开GitHub或网站。原始API响应另存本地private_public_fulltext_library_20261104/response_batches，精简交付包不含原响应。\n'
    (OUT/'文件说明.txt').write_text(note,encoding='utf-8')
    dest=OUT/'新增历史气候能源全文库_本地研究用.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.write(PRIVATE/'new_fulltexts.jsonl.gz','new_fulltexts.jsonl.gz')
        for name in ('summary.json','run_config.json','runs.jsonl','delivery_audit.json','source_policy_review.json','文件说明.txt'):
            if (OUT/name).exists(): z.write(OUT/name,name)
    with zipfile.ZipFile(dest) as z:
        if z.testzip(): raise RuntimeError('ZIP failed integrity check')
    print('PACKAGE',dest,'BYTES',dest.stat().st_size,flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('--mode',choices=['collect','export','package'],default='collect'); a.add_argument('--minutes',type=int,default=90); a.add_argument('--target',type=int,default=25000); a.add_argument('--per-source',type=int,default=7000); a.add_argument('--max-pages',type=int,default=250)
    args=a.parse_args()
    if not 1<=args.minutes<=110 or not 1<=args.target<=50000: a.error('bounded run required')
    if args.mode=='collect': run(args)
    elif args.mode=='export': export()
    else: package()

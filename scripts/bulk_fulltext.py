"""Resumable private fulltext acquisition of EXISTING news, never substitutes.

Publisher batch APIs first; bounded domain-parallel requests; no model calls.
All output is separate from production inputs. Use --mode prepare|direct|resolve|export.
"""
from __future__ import annotations
import argparse
import base64
import collections
import concurrent.futures as cf
import csv
import gzip
import html
import json
import re
import sqlite3
import threading
import time
import urllib.parse as up
import zipfile
from pathlib import Path

import fulltext_pilot as p
from climate_agent.publisher_recovery import identity, normalized, title_text, discover_publisher, public_homepage
from recover_fulltext_urls import prepare_catalog

ROOT = p.ROOT
OUT = ROOT/'analysis/fulltext_bulk_20261104'
PRIVATE = ROOT/'data/private_fulltext_bulk_20261104'
VERSION = 'bulk-original-news-1.2'

def quality(doc):
    from fulltext_review_rules import title_identity
    flags=list(doc.get('completeness_flags') or [])
    title=doc.get('title',''); text=doc.get('source_text',''); url=doc.get('publisher_url') or doc.get('url','')
    genre='news_or_commentary'
    if doc.get('fulltext_url','').endswith('/fullTextXML') or doc.get('rights_status')=='licensed_open_access_repository_copy':
        genre='scholarly_article'
    elif re.search(r'/av/|/videos?/',up.urlsplit(url).path,re.I) or re.search(r'(?:[–—-]\s*video(?: explainer)?|watch:\s)',title,re.I):
        genre='video_description'; flags.append('video_page_not_article_fulltext')
    elif re.search(r'\bLIVE[:：]|live updates|liveblog|[–—-]\s*live\s*$',title,re.I) and len(text)<2500:
        genre='live_page_excerpt'; flags.append('live_updates_not_verified')
    if re.search(r'Close C|Read description|Follow Thunderstorms',text) and len(text)<800:
        flags.append('interface_dominant_text')
    if not title_identity(title,doc.get('page_title') or doc.get('source_page_title') or title,doc.get('source'),url):
        flags.append('strict_title_identity_needs_review')
    resolved=doc.get('resolved_identity') or {}
    checked=resolved.get('identity',resolved)
    if checked and checked.get('date_check') in ('source_date_missing','unparsed_date') and doc.get('date'):
        flags.append('resolved_publisher_date_unverified')
    return {'document_genre':genre,'quality_flags':list(dict.fromkeys(flags)),
            'delivery_class':'candidate_full_article' if genre=='news_or_commentary' and not flags and doc.get('status')=='candidate_complete' else 'review_or_other_text'}

def key(url):
    x=up.urlsplit(url)
    query=up.urlencode([(k,v) for k,v in up.parse_qsl(x.query) if not k.lower().startswith('utm_') and k not in ('fbclid','gclid')])
    return up.urlunsplit((x.scheme.lower(),x.netloc.lower(),x.path.rstrip('/'),query,''))

def embedded_url(url):
    """Old public RSS tokens sometimes literally contain a URL: local decoding only."""
    if p.host(url)!='news.google.com':
        return None
    token=up.urlsplit(url).path.split('/')[-1]
    try:
        raw=base64.urlsafe_b64decode(token+'='*(-len(token)%4))
    except (ValueError,TypeError):
        return None
    candidates=[]
    for match in re.finditer(rb'https?://[^\x00-\x20\x7f-\xff<>"\\]+',raw):
        u=match.group().decode('ascii')
        if public_homepage(u) and p.host(u)!='news.google.com': candidates.append(u)
    return candidates[0] if len(set(candidates))==1 else None

def inputs():
    value=p.input_hashes()
    for file in (ROOT/'static/data/energy_archive.json',ROOT/'static/data/news_archive.json'):
        if file.exists(): value[str(file.relative_to(ROOT))]={'bytes':file.stat().st_size,'sha256':p.digest(file.read_bytes())}
    return value

def prepare():
    OUT.mkdir(parents=True,exist_ok=True); PRIVATE.mkdir(parents=True,exist_ok=True)
    if (OUT/'targets.json').exists():
        if json.loads((OUT/'input_before.json').read_text('utf-8'))!=inputs():
            raise RuntimeError('Inputs changed; keep this frozen run, use a new release directory')
        return json.loads((OUT/'targets.json').read_text('utf-8'))
    p.dump(OUT/'input_before.json',inputs())
    frame,_,_=p.make_frame()
    records={key(x['url']):dict(x) for x in frame}
    homes,endpoints,_=prepare_catalog()
    def add(u,title,date,source,home=None,language=None,source_id=None):
        if not u or not title: return
        k=key(u)
        if k in records:
            records[k]['publisher_homepage']=records[k].get('publisher_homepage') or home
            return
        records[k]={'url':u,'title':title,'date':date,'source':source,'publisher_homepage':home,
                    'language':language,'source_id':source_id,'aliases':[u]}
    db=sqlite3.connect((ROOT/'data/climate.db').resolve().as_uri()+'?mode=ro',uri=True)
    for u,t,d,m,s,lang,sid in db.execute('SELECT a.canonical_url,a.title_original,a.published_at_utc,a.metadata_json,s.name,a.language,a.source_id FROM articles a JOIN sources s USING(source_id)'):
        m=json.loads(m or '{}'); add(u,t,d,m.get('publisher_name') or s,m.get('publisher_homepage'),lang,sid)
    db.close()
    for file in (ROOT/'data/news_archive.json',ROOT/'static/data/news_archive.json',ROOT/'static/data/energy_archive.json'):
        if not file.exists(): continue
        raw=json.loads(file.read_text('utf-8')); rows=raw if isinstance(raw,list) else raw.get('items',raw.get('articles',[]))
        for x in rows: add(x.get('canonical_url') or x.get('url'),x.get('title_original') or x.get('title'),x.get('published_at') or x.get('published_at_utc'),x.get('source_name'),x.get('publisher_homepage'),x.get('language'),x.get('source_id'))
    for x in records.values():
        x['original_url']=x['url']
        x['id']='bulk_'+p.digest(key(x['url']).encode())[:20]
        x['publisher_homepage']=public_homepage(x.get('publisher_homepage')) or homes.get(normalized(x.get('source') or ''))
        candidate=embedded_url(x['url'])
        if candidate:
            x['url']=candidate; x['url_resolution']='literal_url_in_existing_rss_token'
        x['stratum']='google_wrapper' if p.host(x['url'])=='news.google.com' else 'direct_other'
        x['api_endpoint']=x.get('api_endpoint') or endpoints.get(p.host(x['url']))
    index=collections.defaultdict(list)
    for x in records.values():
        if x['stratum']!='google_wrapper': index[normalized(title_text(x['title'],x.get('source')))].append(x)
    for x in records.values():
        if x['stratum']!='google_wrapper': continue
        hits=[]
        for y in index.get(normalized(title_text(x['title'],x.get('source'))),[]):
            same_source=normalized(x.get('source') or '')==normalized(y.get('source') or '')
            same_domain=x.get('publisher_homepage') and p.host(x['publisher_homepage']).removeprefix('www.')==p.host(y['url']).removeprefix('www.')
            if (same_source or same_domain) and identity(x['title'],y['title'],publisher=x.get('source'),expected_date=x.get('date'),candidate_date=y.get('date')): hits.append(y)
        if len({key(y['url']) for y in hits})==1:
            y=hits[0]; x.update(url=y['url'],stratum='direct_other',api_endpoint=y.get('api_endpoint'),archive_post_id=y.get('archive_post_id'),url_resolution='local_title_publisher_date_index')
    rows=list(records.values())
    p.dump(OUT/'targets.json',rows)
    p.dump(OUT/'population.json',{'frozen_at':p.stamp(),'target_records':len(rows),'unique_original_urls':len({key(x['original_url']) for x in rows}),'known_publisher_urls':sum(x['stratum']!='google_wrapper' for x in rows),'unresolved_wrappers':sum(x['stratum']=='google_wrapper' for x in rows),'wrapper_homepage_known':sum(x['stratum']=='google_wrapper' and bool(x.get('publisher_homepage')) for x in rows),'known_url_groups':len({key(x['url']) for x in rows if x['stratum']!='google_wrapper'}),'scope':'Existing climate and energy news records; case, company, policy and report catalogues excluded.'})
    return rows

def timing(): return collections.defaultdict(float)

def accept_post(row,post):
    u=post.get('link','')
    if key(u)!=key(row['url']): raise p.StopFetch('api_identity_mismatch')
    title=post.get('title',{}).get('rendered','')
    match=identity(row['title'],html.unescape(title),publisher=row.get('source'),expected_date=row.get('date'),candidate_date=post.get('date_gmt') or post.get('date'))
    if not match: raise p.StopFetch('api_title_or_date_mismatch')
    if post.get('content',{}).get('protected'): raise p.StopFetch('api_protected_content')
    text,checks=p.extract('<html><title>'+title+'</title><h1>'+title+'</h1><article>'+post.get('content',{}).get('rendered','')+'</article></html>',row['title'],u,api=True,compare_alternative=not row.get('_skip_alternative',False))
    return text,{**checks,'identity':match,'source_published_at':post.get('date_gmt') or post.get('date'),
                 'source_published_at_utc':(post['date_gmt']+'Z') if post.get('date_gmt') and not post['date_gmt'].endswith('Z') else post.get('date_gmt'),
                 'raw_response_kind':'parsed_public_api_post_object'}

def save_doc(row,text,details,raw,route,request_url=None):
    doc={**row,**details,'source_text':text,'text_characters':len(text),'text_utf8_bytes':len(text.encode()),'text_sha256':p.digest(text.encode()),'fetched_at':p.stamp(),'acquisition_route':route,'request_url':request_url,'pipeline_version':VERSION,'translated':False,'public_redistribution_allowed':False,'rights_status':'private_research_copy_permission_not_established_for_redistribution','manual_review':'not_independently_human_reviewed'}
    for d in ('articles','raw'): (PRIVATE/d).mkdir(parents=True,exist_ok=True)
    dest=PRIVATE/'articles'/f"{row['id']}.json"
    temp=dest.with_suffix('.tmp'); temp.write_bytes(p.jsonbytes(doc)); temp.replace(dest)
    (PRIVATE/'raw'/f"{row['id']}.response.gz").write_bytes(gzip.compress(raw,mtime=0))
    return {k:v for k,v in doc.items() if k!='source_text'}

def run(args):
    rows=prepare(); p.PRIVATE=PRIVATE
    manifest={'started_at':p.stamp(),'version':VERSION,'mode':args.mode,'minutes':args.minutes,'workers':args.workers,'retry_transient':args.retry_transient,'code_sha256':{name:p.digest((ROOT/name).read_bytes()) for name in ('scripts/bulk_fulltext.py','scripts/fulltext_pilot.py','scripts/fulltext_review_rules.py','src/climate_agent/publisher_recovery.py')},'target_sha256':p.digest((OUT/'targets.json').read_bytes())}
    with (OUT/'run_start_manifests.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(manifest,ensure_ascii=False)+'\n')
    p.ACCEPT_ENCODING='gzip'
    registered=json.loads((ROOT/'config/research_archives.json').read_text('utf-8'))['sources']
    registered_endpoints={h:s['endpoint'] for s in registered for h in s['allowed_hosts']}
    events=p.load_lines(OUT/'attempts.jsonl')
    done={x['id']:x for x in events}
    previous_results=dict(done)
    attempt_counts=collections.Counter(x['id'] for x in events)
    if args.retry_transient:
        for ident,result in list(done.items()):
            status=result.get('status','')
            if not result.get('text_characters') and attempt_counts[ident]<2 and (status.startswith('network_') or status.startswith('robots_unknown_unavailable_network_') or status in ('response_wall_time_limit','page_title_mismatch_or_missing')):
                del done[ident]
    # A completed body file survives interruption before the attempt append.
    for file in (PRIVATE/'articles').glob('*.json'):
        x=json.loads(file.read_text('utf-8')); done[x['id']]={k:v for k,v in x.items() if k!='source_text'}
    old_docs={}
    for folder in (ROOT/'data/private_fulltext_pilot_20261103/articles',ROOT/'data/private_fulltext_recovery_20261103/articles',PRIVATE/'articles'):
        for file in folder.glob('*.json'):
            doc=json.loads(file.read_text('utf-8'))
            if not doc.get('source_text') or p.restricted_syndication(doc['source_text']): continue
            for u in (doc.get('original_url'),doc.get('publisher_url'),doc.get('url')):
                if u: old_docs[key(u)]=(doc,file)
    fetcher=p.Fetcher(); lock=threading.RLock(); started=time.monotonic(); deadline=started+args.minutes*60
    # Reuse current-day circuit breakers, with a bounded 24h expiry.
    if (OUT/'circuits.json').exists():
        saved=json.loads((OUT/'circuits.json').read_text('utf-8'))
        if time.time()-saved.get('timestamp',0)<86400: fetcher.stop_hosts.update(saved.get('hosts',{}))
    def record(result):
        with lock:
            done[result['id']]=result
            with (OUT/'attempts.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(result,ensure_ascii=False)+'\n')
            if len(done)%50==0: print(json.dumps({'processed':len(done),'bodies':sum(bool(x.get('text_characters')) for x in done.values()),'seconds':round(time.monotonic()-started)}),flush=True)
    selected=[]
    for x in rows:
        if x['id'] in done: continue
        prior=previous_results.get(x['id'],{})
        located=prior.get('publisher_url')
        if args.retry_transient and located and p.host(located)!='news.google.com' and prior.get('resolved_identity'):
            # Retain the frozen original record; reuse a verified locator after
            # a transient fetch failure instead of repeating publisher search.
            x={**x,'url':located,'stratum':'direct_other','resolved_identity':prior['resolved_identity'],'url_resolution':'prior_verified_publisher_locator','api_endpoint':prior.get('api_endpoint'),'archive_post_id':prior.get('archive_post_id')}
        reused=old_docs.get(key(x['original_url'])) or old_docs.get(key(x['url']))
        if reused:
            doc,file=reused
            if identity(x['title'],doc.get('title',''),publisher=x.get('source'),expected_date=x.get('date'),candidate_date=doc.get('date')):
                rawpath=file.parent.parent/'raw'/f"{doc['id']}.response.gz"
                raw=gzip.decompress(rawpath.read_bytes()) if rawpath.exists() else b''
                clean={k:v for k,v in doc.items() if k not in ('id','url','original_url','aliases','source_text','title')}
                record(save_doc(x,doc['source_text'],clean,raw,'previous_verified_acquisition',str(file.relative_to(ROOT))))
                continue
        if args.mode=='direct' and x['stratum']!='google_wrapper': selected.append(x)
        if args.mode=='resolve' and x['stratum']=='google_wrapper':
            if not x.get('publisher_homepage') and re.fullmatch(r'(?:[\w-]+\.)+[a-z]{2,}',x.get('source') or '',re.I):
                x={**x,'publisher_homepage':'https://'+x['source'].lower()+'/'}
            if x.get('publisher_homepage') and p.host(x['publisher_homepage'])!='news.google.com': selected.append(x)
    # Prefer recent recoverable records; do not spend the limited run budget
    # on the oldest records merely because they came first in a frozen input.
    selected.sort(key=lambda x:str(x.get('date') or ''),reverse=True)
    groups=collections.defaultdict(list)
    for x in selected: groups[p.host(x.get('publisher_homepage') or x['url']) if args.mode=='resolve' else p.host(x['url'])].append(x)
    # Each host has one serial queue; different hosts run in parallel.
    cache=collections.OrderedDict()
    cache_bytes=[0]
    def host_worker(group):
        batchable=collections.defaultdict(list); pending=[]
        for x in group:
            if args.mode=='direct' and x.get('api_endpoint'): batchable[x['api_endpoint']].append(x)
            else: pending.append(x)
        for endpoint,targets in batchable.items():
            for start in range(0,len(targets),25):
                if time.monotonic()>deadline: return
                batch=targets[start:start+25]
                params={'per_page':50,'_fields':'id,link,title,date,date_gmt,content'}
                if all(x.get('archive_post_id') for x in batch): params['include']=','.join(str(x['archive_post_id']) for x in batch)
                else: params['slug']=','.join(dict.fromkeys(up.unquote(up.urlsplit(x['url']).path.rstrip('/').split('/')[-1]) for x in batch))
                url=endpoint+'?'+up.urlencode(params)
                clock=timing(); tick=time.monotonic()
                try:
                    _,content,raw,_=fetcher.get(url,clock); posts=json.loads(content)
                    if not isinstance(posts,list): raise p.StopFetch('api_not_list')
                    index={key(y.get('link','')):y for y in posts}
                    for row in batch:
                        try:
                            post=index.get(key(row['url']))
                            if not post: raise p.StopFetch('api_post_missing')
                            text,checks=accept_post(row,post)
                            result=save_doc(row,text,checks,p.jsonbytes(post),'public_wordpress_batch',url)
                            result['batch_elapsed_seconds']=time.monotonic()-tick
                            record(result)
                        except p.StopFetch: pending.append(row)
                except (p.StopFetch,ValueError,TypeError): pending.extend(batch)
        for row in pending:
            if time.monotonic()>deadline: return
            current=dict(row); notes=[]
            def read(url):
                with lock:
                    if url in cache:
                        cache.move_to_end(url)
                        return cache[url]
                try: value=fetcher.get(url,timing())[2]
                except p.StopFetch as e: notes.append({'url':url,'reason':e.reason}); value=b''
                # Bounded shared discovery cache: avoid redownloading publisher
                # homepages/declared maps for each title, without unbounded RAM.
                with lock:
                    previous=cache.pop(url,None)
                    if previous is not None: cache_bytes[0]-=len(previous)
                    cache[url]=value; cache_bytes[0]+=len(value)
                    while len(cache)>600 or cache_bytes[0]>64*1024*1024:
                        _,expired=cache.popitem(last=False); cache_bytes[0]-=len(expired)
                return value
            if args.mode=='resolve':
                try:
                    matches=discover_publisher(row,read,sitemap_limit=3)
                except Exception as e:
                    record({**row,'status':'publisher_discovery_error_'+type(e).__name__,'access_notes':notes,'finished_at':p.stamp()})
                    continue
                if len(matches)!=1:
                    record({**row,'status':'publisher_url_unresolved','access_notes':notes,'finished_at':p.stamp()}); continue
                hit=matches[0]
                # A newly discovered REST endpoint is a metadata locator, not
                # authorization to fetch a registration-gated article via API.
                endpoint=registered_endpoints.get(p.host(hit['publisher_url'])) if hit.get('route')!='publisher_wordpress_all_types_search' else None
                current.update(url=hit['publisher_url'],stratum='direct_other',api_endpoint=endpoint,archive_post_id=hit.get('archive_post_id'),resolved_identity=hit)
            current['pipeline_version']=VERSION
            result=p.perform(current,fetcher,{})
            record(result)
    groups_sorted=sorted(groups.values(),key=lambda g:(not any(x.get('api_endpoint') for x in g),-len(g)))
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        tasks=[pool.submit(host_worker,g) for g in groups_sorted]
        for task in cf.as_completed(tasks):
            try: task.result()
            except Exception as e: print('host_worker_error',type(e).__name__,flush=True)
    with (OUT/'requests.jsonl').open('a',encoding='utf-8') as f:
        for x in fetcher.requests: f.write(json.dumps(x,ensure_ascii=False)+'\n')
    p.dump(OUT/'circuits.json',{'timestamp':time.time(),'hosts':fetcher.stop_hosts})
    with (OUT/'runs.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps({'at':p.stamp(),'mode':args.mode,'elapsed_seconds':time.monotonic()-started,'requests':len(fetcher.requests),'workers':args.workers,'time_budget_minutes':args.minutes})+'\n')
    export()

def export():
    rows=json.loads((OUT/'targets.json').read_text('utf-8'))
    population=json.loads((OUT/'population.json').read_text('utf-8'))
    population['wrapper_homepage_known']=sum(x['stratum']=='google_wrapper' and bool(x.get('publisher_homepage')) and p.host(x['publisher_homepage'])!='news.google.com' for x in rows)
    population['publisher_homepage_definition']='Publisher domain only; Google aggregator homepage excluded.'
    p.dump(OUT/'population.json',population)
    attempts={x['id']:x for x in p.load_lines(OUT/'attempts.jsonl')}
    docs=[]; hashes={}; aliases=[]; policy_exclusions=[]
    for file in sorted((PRIVATE/'articles').glob('*.json')):
        doc=json.loads(file.read_text('utf-8')); text=doc.get('source_text','')
        if not text or p.digest(text.encode())!=doc.get('text_sha256'): raise RuntimeError('Invalid stored body '+file.name)
        if p.restricted_syndication(text):
            metadata={k:v for k,v in doc.items() if k not in ('source_text','text_characters','text_utf8_bytes')}
            metadata['status']='metadata_only_syndicated_source_policy'
            attempts[doc['id']]=metadata
            policy_exclusions.append({'id':doc['id'],'url':doc.get('publisher_url') or doc['url'],'reason':'explicit_wire_attribution','previous_private_version_retained':True})
            continue
        doc.update(quality(doc))
        attempts[doc['id']]=doc
        sha=doc['text_sha256']; representative=hashes.setdefault(sha,doc['id'])
        aliases.append({'target_id':doc['id'],'document_id':representative,'original_url':doc.get('original_url') or doc['url'],'publisher_url':doc.get('publisher_url') or doc['url'],'sha256':sha})
        if representative==doc['id']: docs.append(doc)
    packed=PRIVATE/'fulltexts.jsonl.gz'
    plain=0
    with gzip.open(packed,'wb') as f:
        for x in docs:
            b=p.jsonbytes(x)+b'\n'; f.write(b); plain+=len(b)
    with gzip.open(PRIVATE/'candidate_full_articles.jsonl.gz','wb') as f:
        for x in docs:
            if x['delivery_class']=='candidate_full_article': f.write(p.jsonbytes(x)+b'\n')
    p.dump(PRIVATE/'original_to_document.json',aliases)
    summary={'updated_at':p.stamp(),'target_records':len(rows),'attempted_records':len(attempts),'records_with_body':len(aliases),'unique_body_hashes':len(docs),'candidate_complete_unique':sum(x.get('status')=='candidate_complete' for x in docs),'needs_review_unique':sum(x.get('status')!='candidate_complete' for x in docs),'statuses':dict(collections.Counter(x.get('status') for x in attempts.values())),'jsonl_plain_bytes':plain,'jsonl_gzip_bytes':packed.stat().st_size,'raw_gzip_bytes':sum(f.stat().st_size for f in (PRIVATE/'raw').glob('*.gz')),'source_body_utf8_bytes':sum(len(x['source_text'].encode()) for x in docs),'input_files_unchanged':inputs()==json.loads((OUT/'input_before.json').read_text('utf-8')),'model_requests':0,'translation':False,'scope':'Only original input records; no substitute articles. Candidate-complete is automated, not human gold-standard validation.'}
    summary['genres']=dict(collections.Counter(x['document_genre'] for x in docs))
    summary['candidate_full_news_unique']=sum(x['delivery_class']=='candidate_full_article' for x in docs)
    summary['quality_flags']=dict(collections.Counter(flag for x in docs for flag in x['quality_flags']))
    summary['retained_previous_texts_excluded_from_delivery_by_policy']=len(policy_exclusions)
    p.dump(OUT/'delivery_policy_exclusions.json',policy_exclusions)
    p.dump(OUT/'summary.json',summary)
    fields=['id','status','source','title','original_url','publisher_url','text_characters','text_sha256']
    with (OUT/'records.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for row in rows:
            x=attempts.get(row['id'],{**row,'status':'not_attempted'})
            w.writerow({k:(' '+str(x[k]) if isinstance(x.get(k),str) and x[k].startswith(('=','+','-','@')) else x.get(k,'')) for k in fields})
    print(json.dumps(summary,ensure_ascii=False),flush=True)

def package():
    export()
    s=json.loads((OUT/'summary.json').read_text('utf-8'))
    note=(f"历史新闻正文阶段交付\n生成时间（UTC）：{s['updated_at']}\n\n"
          f"冻结目标：{s['target_records']}条。已有正文覆盖原记录{s['records_with_body']}条，正文哈希去重后{s['unique_body_hashes']}篇。\n"
          f"严格机器筛选的候选完整新闻{s['candidate_full_news_unique']}篇；其余为待复核正文、视频说明、直播导语或论文，分类见每条document_genre、delivery_class与quality_flags。\n"
          "候选完整不是逐篇人工全文核验。不要把全部文字记录数写成完整新闻篇数。\n\n"
          "文件说明\n"
          "fulltexts.jsonl.gz：全部已保存原始语言文字，每行一个JSON，包含标题、原网址、来源、时间、正文、指纹与质量标记。\n"
          "candidate_full_articles.jsonl.gz：通过更严格机器检查的新闻与评论正文子集。\n"
          "original_to_document.json：原记录与去重正文的映射，多个原网址不重复计作多篇正文。\n"
          "records.csv：全部原始目标的逐条状态，not_attempted表示未到队列，不表示永久无法获取。\n"
          "summary.json：成功数、各状态、字节数与原数据保留检查。runs.jsonl记录各阶段实际耗时。\n"
          "数据保持原文，不翻译，不用AI补写。不包含API Key或订阅名单。原数据库未被此任务覆盖。\n\n"
          "使用边界\n文字默认限本地研究，不代表已获得全文公开转载许可，不应上传公开GitHub或网站。"
          "原响应单独保存在本地data/private_fulltext_bulk_20261104/raw，未打入此精简交付包。"
          "无法获取的记录保留原有元数据及失败原因，没有替换为其他新闻凑数。\n")
    (OUT/'交付说明.txt').write_text(note,encoding='utf-8')
    destination=OUT/'历史新闻正文_阶段交付_本地研究用.zip'
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in ('fulltexts.jsonl.gz','candidate_full_articles.jsonl.gz','original_to_document.json'): z.write(PRIVATE/name,name)
        for name in ('records.csv','summary.json','population.json','input_before.json','runs.jsonl','交付说明.txt'):
            path=OUT/name
            if path.exists(): z.write(path,name)
    with zipfile.ZipFile(destination) as z:
        if z.testzip() is not None: raise RuntimeError('ZIP failed integrity check')
    print('PACKAGE',destination,'BYTES',destination.stat().st_size,flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('--mode',choices=['prepare','direct','resolve','export','package'],default='prepare'); a.add_argument('--minutes',type=float,default=30); a.add_argument('--workers',type=int,default=12); a.add_argument('--retry-transient',action='store_true',help='One extra attempt for network/time failures only, never access denials')
    args=a.parse_args()
    if not 1<=args.workers<=24 or not 0<args.minutes<=120: a.error('workers 1..24, minutes 0..120')
    if args.mode=='prepare': prepare(); print((OUT/'population.json').read_text('utf-8'))
    elif args.mode=='export': export()
    elif args.mode=='package': package()
    else: run(args)

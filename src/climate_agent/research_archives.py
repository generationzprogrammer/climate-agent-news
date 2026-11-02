"""Bounded collection from publisher-advertised, public WordPress archives.

Only attributed source excerpts are retained. Original HTML/content responses
are processed in memory; no images, full articles or contact details are saved.
"""
from __future__ import annotations
import hashlib,json,re,time,urllib.error,urllib.request,html
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC,datetime
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from bs4 import BeautifulSoup
from .article_content import USER_AGENT,_robots_allows
from .collector import NormalizedArticle
from .pipeline import normalize_url,stable_id
from .research import clean,excerpt,load_jsonl,save_jsonl,persist_texts,make_text_record,substantive,stamp,title_key

CORE=re.compile(r'climat|greenhouse|global warming|net[ -]?zero|decarbon|carbon (?:pric|market|tax|capture|emission)|emissions?|methane|renewable|fossil fuel|clean energy|clean power|paris agreement|\bCO2\b|sea.level|heatwave|heat wave|极端高温|气候|碳排放|碳中和|可再生能源',re.I)

def text_of(value):
    soup=BeautifulSoup(str(value or ''),'html.parser')
    for node in list(soup.select('script,style,figure,aside,form,iframe,nav')):node.decompose()
    for node in list(soup.find_all(class_=re.compile(r'newsletter|subscribe|related-post|share-button|donate|author-bio',re.I))):
        if node.parent:node.decompose()
    return clean(soup.get_text(' ',strip=True))

def parse_archive_post(item,source):
    title=text_of((item.get('title') or {}).get('rendered'))
    url=normalize_url(str(item.get('link') or ''))
    if not title or urlsplit(url).scheme!='https':return None,'invalid_identity'
    if urlsplit(url).hostname not in source['allowed_hosts']:return None,'unexpected_host'
    raw_date=item.get('date_gmt')
    try:published=datetime.fromisoformat(str(raw_date).replace('Z','+00:00')).replace(tzinfo=UTC)
    except ValueError:return None,'missing_utc_date'
    if published>datetime.now(UTC):return None,'future_date'
    short=text_of((item.get('excerpt') or {}).get('rendered'))
    body=text_of((item.get('content') or {}).get('rendered'))
    # Source-provided summaries take precedence. Short teasers are supplemented
    # with a bounded passage from the actual public article content field.
    basis='public_wordpress_excerpt' if substantive(short,title) else 'public_wordpress_content_excerpt'
    text=excerpt(short if basis=='public_wordpress_excerpt' else body,800)
    if not substantive(text,title):return None,'no_substantive_source_text'
    if not CORE.search(title+' '+text):return None,'outside_climate_scope'
    article=NormalizedArticle(article_id=stable_id('article',url),source_id=source['source_id'],
        source_url=url,canonical_url=url,title=title,published_at_raw=raw_date,
        published_at_utc=published.isoformat(),summary_from_source=text,language='en',
        content_hash=hashlib.sha256((title+'\n'+text).encode()).hexdigest(),
        rights_status='source_attributed_excerpt_not_full_text',extraction_method=basis,
        parser_version='public-wordpress-archive.v1',publisher_name=source['name'],
        publisher_homepage=source['homepage'])
    return article,None

def collect_archive(root,source,*,max_pages=100):
    root=Path(root);cache=root/'data/research_archive_cache';cache.mkdir(parents=True,exist_ok=True)
    path=cache/(source['source_id']+'.jsonl');checkpoint=cache/(source['source_id']+'.json')
    saved=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {}
    records={r['canonical_url']:r for r in load_jsonl(path)}
    if saved.get('complete'):return {'source_id':source['source_id'],'status':'cached','accepted':len(records),**saved}
    now=datetime.now(UTC);after=now.replace(year=now.year-3,hour=0,minute=0,second=0,microsecond=0).isoformat()
    before=saved.get('before') or now.isoformat();page=int(saved.get('next_page') or 1)
    rejected=Counter(saved.get('rejected',{}));seen_pages=set();requests=0;status='bounded';error=None
    while requests<max_pages:
        query={'per_page':50,'page':page,'after':after,'before':before,'orderby':'date','order':'desc',
               '_fields':'id,link,date_gmt,title,excerpt,content,type'}
        url=source['endpoint']+'?'+urlencode(query);p=urlsplit(url)
        if not _robots_allows(p.scheme,p.netloc,url):status='robots_disallowed';break
        request=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/json'})
        try:
            requests+=1
            with urllib.request.urlopen(request,timeout=18) as response:
                payload=response.read(8_000_001)
            if len(payload)>8_000_000:status='response_too_large';break
            items=json.loads(payload)
            if not isinstance(items,list):status='schema_changed';break
            signature=hashlib.sha256(json.dumps([r.get('id') for r in items]).encode()).hexdigest()
            if signature in seen_pages:status='repeated_page';break
            seen_pages.add(signature)
            if not items:status='complete';break
            for item in items:
                article,reason=parse_archive_post(item,source)
                if reason:rejected[reason]+=1;continue
                row={'article_id':article.article_id,'record_id':article.article_id,
                     'canonical_url':article.canonical_url,'title_original':article.title,
                     'summary_source':article.summary_from_source,'source_name':source['name'],
                     'source_id':source['source_id'],'source_type':'professional_climate_media',
                     'published_at_utc':article.published_at_utc,'language':article.language}
                record=make_text_record(row,article.summary_from_source,
                    'source_excerpt' if article.extraction_method=='public_wordpress_excerpt' else 'article_excerpt',
                    basis=article.extraction_method)
                record.update(archive_source_endpoint=source['endpoint'],archive_collected_at=stamp(),
                              published_at_raw=article.published_at_raw)
                records[record['canonical_url']]=record
            page+=1
            save_jsonl(path,records.values())
            checkpoint.write_text(json.dumps({'next_page':page,'before':before,'after':after,
                'rejected':dict(rejected),'complete':False},ensure_ascii=False),encoding='utf-8')
            if len(items)<50:status='complete';break
            time.sleep(2)
        except urllib.error.HTTPError as exc:
            if exc.code==400:
                try:code=json.loads(exc.read(20_000)).get('code')
                except (ValueError,OSError):code=None
                status='complete' if code=='rest_post_invalid_page_number' else 'http_400'
            else:status='http_'+str(exc.code)
            break
        except (OSError,ValueError) as exc:status='failed';error=type(exc).__name__;break
    save_jsonl(path,records.values())
    state={'next_page':page,'before':before,'after':after,'rejected':dict(rejected),
           'complete':status=='complete','status':status,'requests':requests,'accepted':len(records),'error':error}
    checkpoint.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'source_id':source['source_id'],**state}

def expand_archives(root,*,target_unique=3650,max_pages=100):
    root=Path(root);sources=json.loads((root/'config/research_archives.json').read_text(encoding='utf-8'))['sources']
    with ThreadPoolExecutor(max_workers=min(5,len(sources))) as pool:
        statuses=list(pool.map(lambda s:collect_archive(root,s,max_pages=max_pages),sources))
    old=load_jsonl(root/'data/research_texts.jsonl')
    identities={normalize_url(r.get('publisher_url') or r['canonical_url']) for r in old}|{r['canonical_url'] for r in old}
    hashes={r['text_sha256'] for r in old};titles={(title_key(r['title_original']),str(r.get('published_at'))[:10]) for r in old}
    candidates=[]
    for source in sources:
        for r in load_jsonl(root/'data/research_archive_cache'/(source['source_id']+'.jsonl')):
            if not CORE.search(r['title_original']+' '+r['source_text']):continue
            key=(title_key(r['title_original']),str(r.get('published_at'))[:10])
            if r['canonical_url'] in identities or r['text_sha256'] in hashes or key in titles:continue
            candidates.append(r);identities.add(r['canonical_url']);hashes.add(r['text_sha256']);titles.add(key)
    # Reproducible uniform hash selection from the eligible source archive frame;
    # no fixed monthly quota that would flatten the time trend artificially.
    candidates.sort(key=lambda r:hashlib.sha256(('green-archive-20261102:'+r['canonical_url']).encode()).hexdigest())
    needed=max(0,target_unique-len({r['text_sha256'] for r in old}));chosen=candidates[:needed]
    for r in chosen:r.update(sample_frame='public_archives_20261102',sampling_method='deterministic_uniform_url_hash',
                             sampling_probability=min(1,needed/max(1,len(candidates))))
    persist_texts(root/'data/research_texts.jsonl',sorted([*old,*chosen],key=lambda r:r.get('published_at') or '',reverse=True))
    result={'old_records':len(old),'old_unique':len({r['text_sha256'] for r in old}),
            'eligible_new_archive_records':len(candidates),'added':len(chosen),'new_records':len(old)+len(chosen),
            'new_unique':len({r['text_sha256'] for r in [*old,*chosen]}),'target_unique':target_unique,
            'sources':statuses,'added_by_source':dict(Counter(r['source_id'] for r in chosen)),'created_at':stamp()}
    (root/'data/research_expansion_20261102.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

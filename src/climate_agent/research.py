"""Versioned source-text evidence and conservative research views.

Never substitutes generated prose for original text. Network work is explicit;
ordinary static exports are offline. The append-only observation ledger retains
unavailable records separately from the usable text corpus.
"""
from __future__ import annotations

import base64
import collections
import csv
import difflib
import hashlib
import gzip
import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from functools import lru_cache
from urllib.parse import urlsplit

from .article_content import fetch_article_text, METADATA_ONLY_HOSTS
from .taxonomy import country_codes_for, country_index,country_mentions_with_evidence

VERSION = '1.1.0'
THEMES = (
    ('finance','气候资金','Climate finance',r'climate financ|adaptation financ|green climate fund|气候资[金融]|适应资金'),
    ('carbon_markets','碳市场','Carbon markets',r'carbon market|carbon credit|emissions trading|article\s*6|碳市场|碳交易|第六条'),
    ('adaptation','适应与韧性','Adaptation and resilience',r'adaptation|resilien|early warning|气候适应|韧性|预警'),
    ('mitigation','减缓与减排','Mitigation',r'mitigation|emission|methane|decarboni|net.zero|减排|甲烷|碳中和|净零'),
    ('loss_damage','损失与损害','Loss and damage',r'loss and damage|损失[与和]损害'),
    ('energy','能源与产业','Energy and industry',r'energy|renewable|solar|wind power|coal|hydrogen|steel|能源|光伏|风电|煤炭|氢能|钢铁'),
    ('justice','公正转型','Just transition',r'just transition|climate justice|indigenous|公正转型|气候正义|原住民'),
    ('transparency','透明度与核查','Transparency and reporting',r'transparency|\bmrv\b|biennial transparency|透明度|核查'),
    ('science','气候科学与风险','Climate science and risk',r'climate change|warming|drought|flood|wildfire|temperature|气候变化|变暖|干旱|洪水|高温|野火'),
)
TOOLS = (
    ('pricing','碳定价','Carbon pricing',r'carbon tax|carbon pric|emissions trading|碳税|碳价|碳排放权交易'),
    ('subsidy','补贴与激励','Subsidies and incentives',r'subsid|tax credit|incentive|补贴|税收抵免|激励'),
    ('standards','标准与监管','Standards and regulation',r'emission standard|mandate|regulation|排放标准|强制|监管|条例'),
    ('investment','公共投入与融资','Public investment and finance',r'public investment|funding|grant|公共投资|资金|拨款'),
    ('cooperation','合作与技术支持','Cooperation and technology',r'cooperation|technology transfer|capacity.building|合作|技术转让|能力建设'),
)
STAGES = (
    ('withdrawn','撤回','Withdrawn',r'withdrawn|repealed|rescinded|撤回|废止'),
    ('in_force','生效','In force',r'entered into force|takes effect|生效|正式施行'),
    ('adopted','通过','Adopted',r'\badopted\b|\bapproved\b|通过了|获批|正式批准'),
    ('proposed','提出','Proposed',r'\bproposed\b|\bproposal\b|提议|拟议|征求意见'),
    ('implementation','实施','Implementation',r'\bimplemented\b|\bimplementation\b|实施|落实'),
)
STOP = set('the a an and or of in on to for with from by as at is are was were has have will its this that new climate says said report reports'.split())


def stamp():
    return datetime.now(UTC).isoformat()


def load_jsonl(path):
    path=Path(path)
    if path.exists():
        content=path.read_bytes();raw=(gzip.decompress(content) if content.startswith(b'\x1f\x8b') else content).decode('utf-8')
    elif path.with_suffix(path.suffix+'.gz').exists():raw=gzip.decompress(path.with_suffix(path.suffix+'.gz').read_bytes()).decode('utf-8')
    else:return []
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def save_jsonl(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    raw=''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows).encode('utf-8')
    temporary.write_bytes(gzip.compress(raw,mtime=0) if path.suffix=='.gz' else raw)
    temporary.replace(path)
    if path.name in ['research_texts.jsonl','research_document_versions.jsonl','research_text_versions.jsonl','research_translations.jsonl','research_country_corrections.jsonl']:
        compressed=path.with_suffix(path.suffix+'.gz')
        compressed_tmp=compressed.with_suffix(compressed.suffix+'.tmp')
        compressed_tmp.write_bytes(gzip.compress(path.read_bytes(),mtime=0));compressed_tmp.replace(compressed)


def persist_texts(path,rows):
    path=Path(path);rows=list(rows)
    history_path=path.parent/'research_text_versions.jsonl'
    history=load_jsonl(history_path);keys={(r['text_id'],r['text_sha256']) for r in history}
    for record in [*load_jsonl(path),*rows]:
        key=(record['text_id'],record['text_sha256'])
        if key not in keys:history.append(record);keys.add(key)
    save_jsonl(history_path,history)
    save_jsonl(path,rows)


def clean(value):
    value=re.sub(r'<[^>]+>', ' ', str(value or ''))
    value=re.sub(r'[A-Za-z0-9.!#$%&*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[email redacted]', value)
    value=re.sub(r'\b(?:AIza[\w-]{30,}|sk-[\w-]{24,})\b','[credential redacted]',value)
    return re.sub(r'\s+', ' ', value).strip()


def title_key(value):
    value = unicodedata.normalize('NFKC',re.split(r'\s[-|–]\s', clean(value))[0]).casefold()
    return ''.join(character for character in value if character.isalnum())


def substantive(text, title):
    text = clean(text)
    if len(text) < (65 if re.search(r'[\u3400-\u9fff]',text) else 160):
        return False
    a,b=title_key(text),title_key(title)
    if not a or not b or a==b or (len(a)<len(b)*1.35 and difflib.SequenceMatcher(None,a,b).ratio()>.72):
        return False
    if re.search(r'access denied|enable javascript|verify you are human|just a moment|page not found',text,re.I):
        return False
    return True


def excerpt(text, limit=800):
    text=clean(text)
    if len(text)<=limit:return text
    end=max(text.rfind(x,0,limit) for x in ['. ','。','! ','? '])
    return text[:end+1] if end>limit//2 else text[:limit].rsplit(' ',1)[0]


def real_embedded_url(url):
    """Decode only a literal publisher URL already embedded in an RSS link.

    Opaque Google identifiers remain unresolved. No private RPC, CAPTCHA or
    anti-bot circumvention is used.
    """
    if urlsplit(url).hostname!='news.google.com':return url
    try:
        token=urlsplit(url).path.rstrip('/').split('/')[-1]
        raw=base64.urlsafe_b64decode(token+'='*((-len(token))%4))
        match=re.search(rb'https?://[^\x00-\x20\x7f]+',raw)
        if match:
            candidate=match.group().decode('utf-8',errors='ignore')
            if urlsplit(candidate).hostname and urlsplit(candidate).hostname!='news.google.com':return candidate
    except (ValueError,TypeError):pass
    return None


def news_records(root, db=None):
    by_url={}
    for row in load_jsonl(root/'data/climate_text_corpus.jsonl'):
        if row.get('canonical_url'):by_url[row['canonical_url']]=row
    archive_path=root/'data/news_archive.json'
    if archive_path.exists():
        for row in json.loads(archive_path.read_text(encoding='utf-8')).get('records',[]):
            url=row.get('canonical_url')
            if url:by_url[url]={**by_url.get(url,{}),**row}
    if db:
        for row in db.rows('SELECT a.*,s.name AS source_name,s.source_type FROM articles a JOIN sources s USING(source_id)'):
            url=row['canonical_url']
            # Only enrich the climate research population, not all energy news.
            if url not in by_url:
                if int(row.get('relevance_score') or 0)<65 or str(row.get('published_at_utc') or '')<(datetime.now(UTC)-timedelta(days=7)).isoformat():continue
                by_url[url]={'canonical_url':url,'record_id':row['article_id'],'title_original':row['title_original'],
                             'source_id':row['source_id'],'source_name':row['source_name'],
                             'relevance_score':row['relevance_score'],'language':row.get('language')}
            meta=json.loads(row.get('metadata_json') or '{}')
            current=by_url[url]
            current['source_name']=meta.get('publisher_name') or row['source_name']
            current['publisher_homepage']=meta.get('publisher_homepage')
            current['summary_model']=meta.get('translation_model')
            current.update({k:row[k] for k in ['article_id','source_type','published_at_utc']})
            for key in ['title_zh','summary_zh','summary_en','title_en']:
                if meta.get(key) or row.get(key):current[key]=meta.get(key) or row.get(key)
            if row.get('summary_source'):current['summary_source']=row['summary_source']
    return list(by_url.values())


def annotations(text):
    result={}
    for field,definitions in [('governance_themes',THEMES),('policy_tools',TOOLS),('policy_stages',STAGES)]:
        values=[]
        for code,zh,en,pattern in definitions:
            match=re.search(pattern,text,re.I)
            if match:values.append({'id':code,'label_zh':zh,'label_en':en,'start':match.start(),'end':match.end(),'evidence':text[max(0,match.start()-90):match.end()+140]})
        result[field]=values
    result['track']='negotiations' if re.search(r'\bCOP\s*\d+\b|UNFCCC|nationally determined|Article\s*6|气候谈判|缔约方|国家自主贡献',text,re.I) else 'action'
    result['country_mentions']=country_codes_for(text)
    result['annotation_method']='dictionary-evidence-v1'
    result['review_status']='machine_extracted_not_human_verified'
    return result


def document_type_for(row,kind):
    if kind=='licensed_document_text':return 'official_policy_document','curated_licensed_document_registry'
    if re.match(r'^(?:Analysis|Commentary|Opinion|Editorial|Guest (?:post|commentary))\s*[:：]|^(?:分析|评论|社论|客座文章|专家解读)\s*[:：]',str(row.get('title_original') or ''),re.I):
        return 'commentary_or_analysis','explicit_title_prefix'
    return 'source_report','document_genre_not_independently_established'


def make_text_record(row, text, kind, *, resolved_url=None, basis=None):
    from .governance_labels import label_text
    text=clean(text)
    url=row['canonical_url']
    digest=hashlib.sha256(text.encode()).hexdigest()
    claims=[]
    for match in re.finditer(r'(?<!\w)(?:[$€£]\s*)?\d[\d,.]*(?:\s*(?:%|percent|billion|million|trillion|GW|MW|MtCO2e|tonnes|亿美元|亿元|万吨|兆瓦|吉瓦))',text,re.I):
        start=max(text.rfind('.',0,match.start()),text.rfind('。',0,match.start()))+1
        endings=[p for p in [text.find('.',match.end()),text.find('。',match.end())] if p>=0]
        end=min(endings)+1 if endings else min(len(text),match.end()+180)
        claims.append({'value_text':match.group(),'start':match.start(),'end':match.end(),'evidence':text[start:end],
                       'interpretation':'target_or_commitment' if re.search(r'target|commit|pledge|by 20\d\d|目标|承诺',text[start:end],re.I) else 'not_classified'})
    return {'text_id':'text_'+hashlib.sha256(url.encode()).hexdigest()[:20],
            'record_id':row.get('record_id') or row.get('article_id'),'canonical_url':url,
            'publisher_url':resolved_url or url,'title_original':row.get('title_original',''),
            'title_zh':row.get('title_zh'),'title_en':row.get('title_en'),
            'summary_zh':row.get('summary_zh'),'summary_en':row.get('summary_en'),
            'source_name':row.get('source_name'),'source_id':row.get('source_id'),
            'source_type':row.get('source_type'),'language':row.get('language'),
            'published_at':row.get('published_at') or row.get('published_at_utc') or row.get('published_date'),
            'source_text':text,'text_kind':kind,'text_characters':len(text),'text_sha256':digest,
            'text_basis':basis or kind,'collected_at':stamp(),'extractor_version':VERSION,
            'document_type':document_type_for(row,kind)[0],
            'document_type_basis':document_type_for(row,kind)[1],
            'event_date':None,'event_date_precision':None,'source_updated_at':None,
            'policy_direction':None,'legal_effect':None,'summary_model':row.get('summary_model'),
            'quantitative_claims':claims[:30],
            'conference_ids':list(dict.fromkeys('COP'+m for m in re.findall(r'\bCOP\s*-?\s*(\d{1,2})\b',text,re.I))),
            'agenda_item_id':None,'thematic_day_id':None,
            'rights_status':'source_attributed_excerpt_not_full_text',
            'country_codes':country_codes_for(text+'\n'+row.get('title_original','')),
            'governance_labels_v1':label_text(row.get('title_original',''),text),
            'governance_label_title':row.get('title_original',''),
            **annotations(text)}


def collect_texts(root,db=None,*,fetch_limit=0):
    """Seed substantive source excerpts and bounded original-page backfill."""
    root=Path(root); path=root/'data/research_texts.jsonl'; records=news_records(root,db)
    previous=load_jsonl(path); texts={r['canonical_url']:r for r in previous}
    attempts_path=root/'data/research_text_attempts.json'
    attempts=json.loads(attempts_path.read_text(encoding='utf-8')) if attempts_path.exists() else {}
    for row in records:
        url=row['canonical_url']
        if url not in texts and substantive(row.get('summary_source'),row.get('title_original')):
            texts[url]=make_text_record(row,excerpt(row['summary_source']),'source_excerpt')
        elif url in texts:
            # Refresh translations without modifying the original source text.
            for key in ['title_zh','summary_zh','summary_en','title_en']:
                if row.get(key) and not (key.startswith('title_') and texts[url].get('translation_source_sha256')==texts[url].get('text_sha256')):texts[url][key]=row[key]
    title_urls={title_key(r.get('title_original')):r['canonical_url'] for r in records if urlsplit(r['canonical_url']).hostname!='news.google.com'}
    eligible=[]
    cutoff=(datetime.now(UTC)-timedelta(days=14)).isoformat()
    for row in records:
        url=row['canonical_url']; prior=texts.get(url)
        if prior and prior['text_kind'] in ['article_excerpt','licensed_document_text'] and prior.get('collected_at','')>cutoff:continue
        attempt=attempts.get(url,{})
        if attempt.get('attempted_at','')>cutoff and not (
            attempt.get('status')=='publisher_url_unresolved' and row.get('publisher_homepage')):continue
        resolved=real_embedded_url(url) or title_urls.get(title_key(row.get('title_original')))
        homepage=row.get('publisher_homepage')
        if not resolved and homepage and str(row.get('published_at_utc') or row.get('published_at') or '')>cutoff:
            resolved=homepage
        if not resolved:
            attempts[url]={'status':'publisher_url_unresolved','attempted_at':stamp()};continue
        host=urlsplit(resolved).hostname or ''
        if any(host==x or host.endswith('.'+x) for x in METADATA_ONLY_HOSTS):
            attempts[url]={'status':'metadata_only_source','attempted_at':stamp()};continue
        eligible.append((row,resolved))
    eligible.sort(key=lambda pair:(bool(pair[0].get('source_id','').startswith('OFF')),pair[0].get('published_at_utc') or pair[0].get('published_at') or ''),reverse=True)
    # Round-robin domains prevents one publisher consuming the backfill batch.
    buckets=collections.defaultdict(list)
    for item in eligible:buckets[urlsplit(item[1]).hostname].append(item)
    selected=[]
    while len(selected)<fetch_limit and any(buckets.values()):
        for bucket in buckets.values():
            if bucket and len(selected)<fetch_limit:selected.append(bucket.pop(0))
    def fetch(item):
        row,url=item
        if urlsplit(row['canonical_url']).hostname=='news.google.com' and url==row.get('publisher_homepage'):
            from .publisher_links import resolve_publisher
            url=resolve_publisher(row['title_original'],url)
            if not url:return row,None,'publisher_link_not_found'
        try:page=fetch_article_text(url)
        except Exception:return row,None,'extraction_failed'
        text=page.get('text','')
        if not substantive(text,row.get('title_original')):return row,None,page.get('basis','no_substantive_text')
        if not title_matches(row.get('title_original'),page.get('title')):return row,None,'page_title_mismatch'
        # Only attributed short excerpts are published, never copyrighted HTML.
        record=make_text_record(row,excerpt(text,1200),'article_excerpt',resolved_url=url,basis=page.get('basis'))
        record['source_page_title']=page.get('title')
        record['page_title_verified']=True
        return row,record,'success'
    # Each domain appears at most once per wave; same-domain requests are spaced.
    # Global pool size is bounded and the upstream fetcher enforces robots/timeouts.
    pending=selected[:]; fetched=0;stopped_hosts=set()
    while pending:
        wave=[];seen=set();rest=[]
        for item in pending:
            host=urlsplit(item[1]).hostname
            if host in stopped_hosts:continue
            if host not in seen and len(wave)<4:wave.append(item);seen.add(host)
            else:rest.append(item)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for row,result,status in pool.map(fetch,wave):
                url=row['canonical_url'];attempts[url]={'status':status,'attempted_at':stamp()}
                if result:texts[url]=result;fetched+=1
                if status in ['http_401','http_403','http_429']:
                    original=next((target for source,target in wave if source['canonical_url']==url),url)
                    stopped_hosts.add(urlsplit(original).hostname)
        pending=rest
        if pending:time.sleep(2)
    persist_texts(path,sorted(texts.values(),key=lambda r:r.get('published_at') or '',reverse=True))
    attempts_path.parent.mkdir(parents=True,exist_ok=True)
    attempts_path.write_text(json.dumps(attempts,ensure_ascii=False,indent=2),encoding='utf-8')
    status={'source_records':len(records),'usable_texts':len(texts),'existing_texts':len(previous),
            'unique_source_texts':len({r['text_sha256'] for r in texts.values()}),
            'new_text_records':len(texts)-len(previous),'pages_requested':len(selected),'pages_with_text':fetched,
            'text_kinds':dict(collections.Counter(r['text_kind'] for r in texts.values())),
            'attempt_statuses':dict(collections.Counter(r['status'] for r in attempts.values())),'updated_at':stamp()}
    return status


def words(title):
    return {x for x in re.findall(r'[a-z]{3,}',re.split(r'\s[-|–]\s',str(title or '').lower())[0]) if x not in STOP}


def title_matches(expected,actual):
    a,b=words(expected),words(actual)
    if len(a)>=3:return len(a&b)>=min(3,len(a)) and len(a&b)/max(1,len(a|b))>=.40
    left,right=title_key(expected),title_key(actual)
    return bool(left and right) and difflib.SequenceMatcher(None,left,right).ratio()>=.6


@lru_cache(maxsize=8192)
def headline_countries(title):
    return frozenset(c['alpha2'] for c in country_codes_for(title))


def build_events(records):
    clusters=[];index=collections.defaultdict(set)
    for row in sorted(records,key=lambda r:r.get('published_at') or '',reverse=True):
        tokens=words(row.get('title_original','')); candidates=set()
        for token in tokens:candidates.update(index[token])
        best=None
        for ci in sorted(candidates):
            other=clusters[ci]['records'][0]; right=words(other.get('title_original',''))
            left_countries=headline_countries(row.get('title_original',''))
            right_countries=headline_countries(other.get('title_original',''))
            if left_countries and right_countries and not left_countries & right_countries:continue
            shared=tokens & right; union=tokens | right
            left_date=str(row.get('published_at') or '')[:10];right_date=str(other.get('published_at') or '')[:10]
            try:days=abs((datetime.fromisoformat(left_date)-datetime.fromisoformat(right_date)).days)
            except ValueError:days=999
            if days<=30 and len(shared)>=5 and len(shared)/max(1,len(union))>=.64:
                best=ci;break
        if best is None:
            best=len(clusters);clusters.append({'event_id':'event_'+row['text_id'][5:],'records':[]})
        clusters[best]['records'].append(row)
        for token in tokens:index[token].add(best)
    for cluster in clusters:
        first=cluster['records'][0]
        cluster.update({'title_zh':first.get('title_zh'),'title_original':first['title_original'],
                        'latest_date':first.get('published_at'),'article_count':len(cluster['records']),
                        'link_method':'conservative-title-overlap-v1','review_status':'candidate_event_link'})
    return sorted(clusters,key=lambda c:(c['article_count']>1,c['latest_date'] or ''),reverse=True)


def extract_positions(records):
    positions=[]
    groups=[('EU','欧盟','European Union',r'European Union|\bEU\b|欧盟'),('AOSIS','小岛屿国家联盟','AOSIS',r'\bAOSIS\b|Alliance of Small Island States|小岛屿国家联盟'),('G77','七十七国集团和中国','G77 and China',r'G77(?:\s+and\s+China)?|G77\+China|七十七国集团'),('LDC','最不发达国家集团','LDCs',r'Least Developed Countries|\bLDCs\b|最不发达国家集团')]
    for row in records:
        text=row['source_text']
        entities=groups[:]
        aliases={'US':r'United States(?: of America)?|\bU\.?S\.?\b|美国','GB':r'United Kingdom|\bUK\b|Britain|英国','RU':r'Russia|俄罗斯','KR':r'South Korea|韩国','CN':r'China|中国'}
        seen_codes=set()
        for c in [*(row.get('country_codes') or []),*(row.get('country_mentions') or [])]:
            if isinstance(c,dict) and c.get('alpha2') not in seen_codes:
                seen_codes.add(c.get('alpha2'))
                entities.append((c.get('alpha2'),c.get('name_zh'),c.get('name_en'),aliases.get(c.get('alpha2'),re.escape(c.get('name_en') or 'UNMATCHABLE')+'|'+re.escape(c.get('name_zh') or 'UNMATCHABLE'))))
        for sentence in re.split(r'(?<=[.!?])\s+|(?<=[。！？])',text):
            for code,zh,en,pattern in entities:
                match=re.search(r'(?P<actor>'+pattern+r')[^.!?。！？]{0,55}?(?P<verb>\bsupports?\b|\bopposes?\b|\brejects?\b|\bcall(?:ed|s)? for\b|\burges?\b|\badvocates?\b|支持|反对|呼吁|主张|敦促)',sentence,re.I)
                if not match:continue
                verb=match.group('verb').lower()
                between=sentence[match.start('actor'):match.start('verb')]
                gap=sentence[match.end('actor'):match.start('verb')]
                # Do not attribute an embedded country's statement to an earlier
                # speaker (e.g. "UK said the United States supports ...").
                if any(other!=code and re.search(other_pattern,gap,re.I)
                       for other,_,_,other_pattern in entities):continue
                stance=('qualified_statement' if re.search(r'\bnot\b|n.t|不|未',gap,re.I)
                        else ('opposition' if re.search(r'oppos|reject|反对',verb) else 'support_or_call'))
                positions.append({'position_id':row['text_id']+'_'+str(code)+'_'+str(len(positions)),
                                  'actor':code,'actor_zh':zh,'actor_en':en,'position_type':stance,
                                  'claim_original':sentence,'date':row.get('published_at'),'themes':row['governance_themes'],
                                  'source_name':row.get('source_name'),'url':row.get('publisher_url'),
                                  'text_id':row['text_id'],'source_type':'official_self_statement' if row.get('document_country')==code else 'reported_statement',
                                  'review_status':'rule_extracted_requires_verification'})
                break
    return positions


def version_comparisons(records):
    """Compare only actual stored passages sharing an explicit policy family."""
    families=collections.defaultdict(list)
    patterns=[('ndc',r'nationally determined contribution|\bNDC\b|国家自主贡献'),('ets',r'emissions trading system|\bEU ETS\b|碳排放权交易'),('cbam',r'carbon border adjustment|\bCBAM\b|碳边境调节')]
    for row in records:
        if row.get('document_family'):
            families[(row.get('document_country') or 'unknown',row['document_family'])].append(row)
            continue
        text=row['title_original']+' '+row['source_text']
        if not re.search(r'updated?|revised?|new version|amend|修订|更新|新版',text,re.I):continue
        for family,pattern in patterns:
            if re.search(pattern,text,re.I):
                for country in row.get('country_codes') or []:
                    if isinstance(country,dict):families[(country.get('alpha2'),family)].append(row)
    comparisons=[]
    for (country,family),rows in families.items():
        rows=sorted(rows,key=lambda r:r.get('published_at') or '')
        if len(rows)<2:continue
        left,right=rows[-2:]
        if left['text_sha256']==right['text_sha256']:continue
        comparisons.append({'comparison_id':country+'_'+family,'country':country,'family':family,
                            'scope':'official_documents_with_explicit_version_labels' if left.get('document_family') else 'stored_source_excerpts_not_complete_policy_documents',
                            'left':left,'right':right,
                            'diff':list(difflib.unified_diff(re.split(r'(?<=[.。])\s+',left['source_text']),re.split(r'(?<=[.。])\s+',right['source_text']),lineterm=''))[:30],
                            'review_status':'automatic_passage_comparison_not_legal_assessment'})
    return comparisons


FIELDS=[('text_id','语料标识','Text identifier'),('canonical_url','原记录链接','Original record URL'),('publisher_url','真实发布页','Publisher URL'),('source_text','原文摘录','Original source excerpt'),('text_kind','文本类型','Text kind'),('text_sha256','文本指纹','Text hash'),('published_at','来源发布时间','Publication time'),('collected_at','采集时间','Collection time'),('country_mentions','原文提及国家','Country mentions'),('governance_themes','治理议题与证据位置','Governance themes and evidence offsets'),('policy_tools','政策工具与证据位置','Policy tools and evidence offsets'),('policy_stages','政策阶段措辞','Policy-stage wording'),('track','谈判或行动轨道','Negotiations or action track'),('review_status','复核状态','Review status'),('rights_status','留存权限','Retention scope')]
FIELDS += [('document_type','文件类型','Document type'),('quantitative_claims','数字原句与字符位置','Quantitative statements and offsets'),('conference_ids','明确提及的会议编号','Explicit conference identifiers'),('event_date','事件日期，未确认时为空','Event date; null unless established'),('source_updated_at','原文修订时间，未知时为空','Source update time; null if unknown'),('summary_model','概括模型，已记录时提供','Summary model where recorded'),('document_family','政策文件系列','Policy-document family'),('version_label','文件版本与目标周期','Version and target horizon'),('licence_url','来源许可依据','Source licence URL')]
FIELDS += [
    ('source_text_zh','来源文字的中文译文；原文另存','Chinese translation; original retained separately'),
    ('source_text_en','来源文字的英文原文或译文','English source text or translation'),
    ('country_evidence','国别匹配原词及来源字段与位置','Country evidence, source field and character offsets'),
    ('governance_labels_v1','12类治理议题及全文匹配证据候选','Twelve governance topics and candidate evidence spans'),
    ('governance_label_title','治理标签的原始题名定位字段','Original headline addressed by governance evidence'),
    ('country_tag_version','国别标注方法版本','Country annotation version'),
    ('exact_duplicate_of','相同来源文字的主记录；保留不同报道记录','Primary record with identical source text; distinct report records retained'),
    ('source_language_declared','原采集接口语言声明','Initially declared source language'),
    ('detected_source_language','本地识别来源语言','Locally detected source language'),
    ('translation_status','机器翻译待复核状态','Machine translation review status'),
    ('translation_profile','翻译规则版本','Translation profile'),
    ('translation_model','翻译模型','Translation model'),
    ('translation_source_sha256','所译原文字指纹','Hash of the translated source'),
    ('translation_at','翻译时间','Translation timestamp'),
    ('archive_api','发布者公开档案接口','Publisher public archive API'),
    ('archive_post_id','来源档案文章编号','Publisher archive post ID'),
    ('sampling_frame','采样框及范围','Sampling frame and scope'),
    ('inclusion_probability','本次返回候选集合的入选概率','Inclusion probability within returned eligible candidates'),
    ('archive_source_endpoint','来源公开档案接口','Public source archive endpoint'),
    ('archive_collected_at','档案接口采集时间','Archive API collection timestamp'),
    ('published_at_raw','来源原始发布时间','Raw source publication timestamp'),
    ('sample_frame','本次档案候选集合','Archive sampling frame identifier'),
    ('sampling_method','档案采样方法','Archive selection method'),
    ('sampling_probability','候选记录被本次采样选中的概率','Selection probability within the eligible candidate frame'),
    ('record_id','关联新闻标识','Linked news record identifier'),
    ('source_id','采集接口标识','Collection-source identifier'),
    ('source_name','采集来源名称；发布页见publisher_url','Collection source; publisher page is given separately'),
    ('source_type','来源接口或机构类型，与文件类型分开','Source/interface type, separate from document genre'),
    ('title_original','原始题名','Original title'),('title_zh','中文题名','Chinese title'),('title_en','英文题名','English title'),
    ('summary_zh','中文编译，与原文分开保存','Chinese compiled summary, separate from source text'),
    ('summary_en','英文概括，与原文分开保存','English summary, separate from source text'),
    ('language','来源语言标记','Source language tag'),('text_characters','所存文字字符数','Stored text character count'),
    ('text_basis','正文提取位置或来源摘录类型','Extraction location or source-excerpt basis'),
    ('extractor_version','抽取器版本','Extractor version'),('annotation_method','自动标注方法版本','Annotation method version'),
    ('country_codes','ISO国别检索标签，不等同政策管辖地','ISO country search tags, not policy jurisdictions'),
    ('event_date_precision','事件日期精度，未知时为空','Event-date precision; null if unknown'),
    ('policy_direction','政策方向，未核实时为空','Policy direction; null unless established'),
    ('legal_effect','法律效力，未核实时为空','Legal effect; null unless established'),
    ('agenda_item_id','正式议程编号，未知时为空','Formal agenda identifier; null if unknown'),
    ('thematic_day_id','主题日编号，未知时为空','Thematic-day identifier; null if unknown'),
    ('document_country','许可政策文件所属国','Country of the licensed policy document'),
    ('target_year','文件明确给出的目标年份','Explicit target year'),
    ('rights_evidence','来源许可或留存依据','Source-specific permission or retention evidence'),
    ('text_transformations','文本清理与隐私遮蔽记录','Text cleaning and privacy-redaction operations'),
    ('source_page_title','回源网页题名','Fetched publisher-page title'),
    ('page_title_verified','回源题名是否通过自动匹配','Whether fetched title passed automatic matching'),
    ('publisher_discovery','发布者链接发现方法','Publisher-link discovery method'),
    ('document_type_basis','文件类型判定依据','Document-genre classification basis'),
]


def repair_country_tags(root,texts):
    path=Path(root)/'data/research_country_corrections.jsonl'
    history=load_jsonl(path);seen={r['audit_id'] for r in history};changes=0
    for row in texts:
        evidence=[]
        for field in ['title_original','source_text']:
            evidence.extend({**item,'source_field':field} for item in country_mentions_with_evidence(row.get(field,'')))
        first={}
        for item in evidence:first.setdefault((item['alpha2'],item['source_field']),item)
        evidence=list(first.values());codes={v['alpha2'] for v in evidence}
        previous={v.get('alpha2') for v in row.get('country_codes',[]) if isinstance(v,dict) and v.get('alpha2')}
        if previous!=codes:
            changes+=1
            identity=hashlib.sha256((row['text_id']+row['text_sha256']+str(sorted(previous))+str(sorted(codes))).encode()).hexdigest()
            if identity not in seen:
                history.append({'audit_id':identity,'text_id':row['text_id'],'source_sha256':row['text_sha256'],
                                'previous_codes':sorted(previous),'revised_codes':sorted(codes),'changed_at':stamp(),
                                'method':'country-span-v2','reason':'recomputed_from_stored_source_and_headline_not_publisher_location'})
                seen.add(identity)
        row['country_codes']=[dict(c) for c in country_index() if c['alpha2'] in codes]
        body_codes={e['alpha2'] for e in evidence if e['source_field']=='source_text'}
        row['country_mentions']=[dict(c) for c in country_index() if c['alpha2'] in body_codes]
        row['country_evidence']=evidence;row['country_tag_version']='country-span-v2'
    save_jsonl(path,history)
    return {'changed_records':changes,'audit_records':len(history),'method':'country-span-v2'}


def write_research(root, db, data_dir):
    root=Path(root);data_dir=Path(data_dir);data_dir.mkdir(parents=True,exist_ok=True)
    status=collect_texts(root,db,fetch_limit=0)
    texts=load_jsonl(root/'data/research_texts.jsonl')
    sampling_path=root/'data/research_expansion_20261102.json'
    sampling=json.loads(sampling_path.read_text(encoding='utf-8')).get('scope_review',{}) if sampling_path.exists() else {}
    if sampling.get('eligible_sampling_frame') and 0<sampling.get('inclusion_probability',0)<=1:
        for row in texts:
            if row.get('sample_frame') in ['public_archives_20261102','public_archives_scope_review_20261102']:
                row.update(sample_frame='public_archives_scope_review_20261102',sampling_method='two_stage_uniform_url_hash_with_scope_screen',sampling_probability=sampling['inclusion_probability'])
    country_catalog={c['alpha2']:c for c in country_index()}
    primary_text={}
    for row in sorted(texts,key=lambda r:(r.get('collected_at') or '',r['text_id'])):
        primary=primary_text.setdefault(row['text_sha256'],row['text_id'])
        if primary!=row['text_id']:row['exact_duplicate_of']=primary
        else:row.pop('exact_duplicate_of',None)
    for i,row in enumerate(texts):
        if 'quantitative_claims' not in row or 'document_type' not in row:
            texts[i]={**make_text_record(row,row['source_text'],row['text_kind'],resolved_url=row.get('publisher_url'),basis=row.get('text_basis')),**row}
        for field in ['country_codes','country_mentions']:
            texts[i][field]=[{**c,**country_catalog.get(c.get('alpha2'),{})} if isinstance(c,dict) else c
                             for c in texts[i].get(field,[])]
        texts[i]['document_type'],texts[i]['document_type_basis']=document_type_for(texts[i],texts[i]['text_kind'])
    country_review=repair_country_tags(root,texts)
    persist_texts(root/'data/research_texts.jsonl',texts)
    # Full source corpus remains downloadable; the interactive payload is bounded.
    recent=texts[:10000]
    # Preserve selectable policy versions when daily news exceeds the UI window.
    recent.extend(r for r in texts[10000:] if r.get('document_family'))
    events=build_events(recent)
    positions=extract_positions(texts)
    comparisons=version_comparisons(texts)
    corpus_hash=hashlib.sha256((root/'data/research_texts.jsonl').read_bytes()).hexdigest()
    payload={'version':VERSION,'generated_at':stamp(),'statistics':status,'corpus_sha256':corpus_hash,
             'coverage':{'publication_min':min((r.get('published_at') or '' for r in texts),default=None),
                         'publication_max':max((r.get('published_at') or '' for r in texts),default=None),
                         'publishers':len({r.get('source_name') for r in texts if r.get('source_name')}),
                         'interactive_records':len(recent),
                         'archive_sampling':sampling,
                         'scope':'Climate news source passages plus separately identified licensed policy reference documents.'},
             'records':recent,'events':[{**e,'records':[{'text_id':r['text_id']} for r in e['records']]} for e in events],'positions':positions[-400:],'comparisons':comparisons[:40],
             'countries':list(country_catalog.values()),
             'themes':[{'id':r[0],'label_zh':r[1],'label_en':r[2]} for r in THEMES],
             'fields':[{'id':a,'label_zh':b,'label_en':c} for a,b,c in FIELDS],
             'methods':{'event_link':'Title overlap at least 0.64, at least five shared content words, no more than 30 days. Candidate linkage, not expert-confirmed event identity.',
                        'labels':'Dictionary matches with character offsets into the original source excerpt. Mentions are not attributed actions.',
                        'positions':'Explicit actor-plus-verb source sentences only. Reported claims, not official positions unless independently verified.',
                        'comparison':'Stored source excerpts about the same country and named instrument. Not a complete legal-document redline.',
                        'rights':'Attributed limited excerpts plus explicitly licensed official documents, with per-record retention scope. Missing or restricted originals are never reconstructed by AI.'}}
    release_path=root/'data/research_release.json'
    if release_path.exists():payload['release']=json.loads(release_path.read_text(encoding='utf-8'))
    payload['country_review']=country_review
    payload['translation']={'ready':sum(bool(r.get('source_text_zh') and r.get('source_text_en')) for r in texts),'records':len(texts)}
    (data_dir/'research_index.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    (data_dir/'research_catalog.json').write_text(json.dumps({k:v for k,v in payload.items() if k not in ['records','events','positions','comparisons']},ensure_ascii=False,indent=2),encoding='utf-8')
    import shutil
    for frame in root.glob('data/research_sampling_frame_*.jsonl.gz'):shutil.copy2(frame,data_dir/frame.name)
    if (root/'data/research_releases').exists():shutil.copytree(root/'data/research_releases',data_dir/'research_releases',dirs_exist_ok=True)
    shutil.copy2(root/'data/research_texts.jsonl',data_dir/'research_texts.jsonl')
    with (data_dir/'research_records.csv').open('w',encoding='utf-8-sig',newline='') as file:
        keys=['text_id','title_original','title_zh','title_en','published_at','collected_at','source_id','source_name','publisher_url','language','country_iso2','country_iso3','theme_ids','track','text_kind','source_text','source_text_zh','source_text_en','text_sha256','rights_status','review_status','translation_status']
        writer=csv.writer(file);writer.writerow(keys)
        for row in texts:
            flat={**row,'country_iso2':';'.join(c['alpha2'] for c in row['country_codes']),
                  'country_iso3':';'.join(c['alpha3'] for c in row['country_codes']),
                  'theme_ids':';'.join(t['id'] for t in row.get('governance_themes',[]))}
            values=[str(flat.get(k) or '') for k in keys]
            writer.writerow(["'"+v if v.lstrip().startswith(('=','+','-','@')) else v for v in values])
    return {'texts':len(texts),'events':len(events),'multi_article_events':sum(c['article_count']>1 for c in events),
            'positions':len(positions),'passage_comparisons':len(comparisons),'corpus_sha256':corpus_hash}


def freeze_release(root):
    import gzip
    root=Path(root);raw=(root/'data/research_texts.jsonl').read_bytes()
    digest=hashlib.sha256(raw).hexdigest();release_id=VERSION+'-'+datetime.now(UTC).strftime('%Y%m%d')+'-'+digest[:8]
    folder=root/'data/research_releases'/release_id;folder.mkdir(parents=True,exist_ok=True)
    target=folder/'corpus.jsonl.gz'
    if not target.exists():target.write_bytes(gzip.compress(raw,mtime=0))
    if (folder/'manifest.json').exists():
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        (root/'data/research_release.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        return manifest
    manifest={'id':release_id,'version':VERSION,'sha256':digest,'records':len(raw.splitlines()),'released_at':stamp(),
              'rights':'Source-specific: attributed excerpts and explicitly licensed documents. No blanket full-text redistribution licence.'}
    if (root/'.git').exists():
        import subprocess
        try:manifest['software_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True,timeout=10).strip()
        except (OSError,subprocess.SubprocessError):pass
    manifest['country_rules_sha256']=hashlib.sha256((Path(__file__).with_name('taxonomy.py')).read_bytes()).hexdigest()
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'data/research_release.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest

"""Bounded official-source watch and persistent news observations.

Newly found links are candidates, never automatically promoted to case facts.
No API keys or language-model calls are required.
"""
from __future__ import annotations
import argparse
from datetime import date,datetime,timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib import request,error,parse,robotparser

ROOT=Path(__file__).resolve().parents[1]
UA='GruenInnovationResearch/1.0 (+https://generationzprogrammer.github.io/climate-agent-news/innovation/)'
TERMS=re.compile(r'research|innovation|collaborat|partner|technolog|产业|科研|合作|成果|创新|中试',re.I)
def public_url(url):
    parts=parse.urlsplit(url)
    sensitive={'token','access_token','api_key','apikey','key','password','secret','signature','credential','authorization'}
    return parts.scheme in ('http','https') and not parts.username and not parts.password and not any(k.casefold() in sensitive for k,v in parse.parse_qsl(parts.query))
def read(path,default):return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
def records(data):return data if isinstance(data,list) else data.get('records',data.get('items',data.get('events',[])))
class Links(HTMLParser):
    def __init__(self):super().__init__();self.items=[];self.href=None;self.words=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.href=dict(attrs).get('href');self.words=[]
    def handle_data(self,data):
        if self.href:self.words.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.href:
            self.items.append((self.href,' '.join(' '.join(self.words).split())));self.href=None
def fetch(url,limit=2_000_000):
    with request.urlopen(request.Request(url,headers={'User-Agent':UA}),timeout=8) as response:
        body=response.read(limit+1)
        if len(body)>limit:raise ValueError('response_too_large')
        if not body.strip():raise ValueError('empty_response')
        charset=response.headers.get_content_charset() or 'utf-8'
        return body,body.decode(charset,errors='replace')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--max-pages',type=int,default=16);ap.add_argument('--offline',action='store_true');args=ap.parse_args()
    now=datetime.now(timezone.utc).isoformat();today=date.today().isoformat()
    book=read(ROOT/'static/data/innovation_cases.json',{});cases=book['cases']
    state=read(ROOT/'data/innovation_watch.json',{'sources':{},'candidates':[],'observations':[]})
    for item in state['sources'].values():
        if item.get('status')=='ok' and not item.get('bytes'):item['status']='empty_response'
    news=records(read(ROOT/'data/news_archive.json',[]))
    seen={x['id'] for x in state['observations']}
    for row in news:
        text=' '.join(str(row.get(k,'')) for k in ('title','title_zh','summary','summary_zh'))
        matches=[]
        for case in cases:
            if case.get('project'):continue
            names=[case['title'].get('en',''),*case.get('aliases',[])]
            if any(len(n)>=5 and n.casefold() in text.casefold() for n in names):matches.append(case['id'])
        url=row.get('url') or row.get('link')
        if not matches or not url or not public_url(url):continue
        identifier='obs_'+hashlib.sha256(url.encode()).hexdigest()[:16]
        if identifier in seen:continue
        seen.add(identifier);state['observations'].append({'id':identifier,'case_ids':matches,'url':url,'title':row.get('title',''),'title_zh':row.get('title_zh',''),'published_at':row.get('published_at') or row.get('date'),'first_observed_at':now,'status':'news_association_not_verified_milestone'})
    sources={s['id']:s for s in book['sources']};eligible={}
    for case in cases:
        if case.get('project'):continue
        for ref in case['evidence']:
            s=sources[ref['source_id']]
            if parse.urlparse(s['url']).scheme in ('http','https'):eligible.setdefault(s['url'],s)
    ordered=sorted(eligible.values(),key=lambda s:(state['sources'].get(s['id'],{}).get('checked_at',''),s['id']))
    robots={};blocked=set();last={};checks=0;candidate_urls={c['url'] for c in state['candidates']}|{s['url'] for s in sources.values()}
    for source in ([] if args.offline else ordered[:max(0,min(args.max_pages,32))]):
        url=source['url'];parts=parse.urlsplit(url);origin=parts.scheme+'://'+parts.netloc
        if origin in blocked:continue
        result={'checked_at':now,'url':url,'status':'unavailable'}
        try:
            if origin not in robots:
                try:_,text=fetch(origin+'/robots.txt',200_000)
                except error.HTTPError as e:
                    if e.code not in (404,410):raise
                    text='User-agent: *\nDisallow:'
                rp=robotparser.RobotFileParser();rp.parse(text.splitlines());robots[origin]=rp
            if not robots[origin].can_fetch(UA,url):result['status']='robots_disallowed';continue
            gap=2-(time.monotonic()-last.get(origin,0))
            if gap>0:time.sleep(gap)
            body,text=fetch(url);last[origin]=time.monotonic();checks+=1
            result.update(status='ok',sha256=hashlib.sha256(body).hexdigest(),bytes=len(body))
            parser=Links();parser.feed(text)
            for href,title in parser.items:
                target=parse.urljoin(url,href).split('#')[0];target_parts=parse.urlsplit(target)
                if target_parts.netloc!=parts.netloc or not public_url(target) or not 12<=len(title)<=250 or not TERMS.search(title) or target in candidate_urls or re.search(r'\b[^\s@]+@[^\s@]+\.[^\s@]+\b',title):continue
                if len(state['candidates'])>=10000:break
                candidate_urls.add(target);state['candidates'].append({'id':'candidate_'+hashlib.sha256(target.encode()).hexdigest()[:16],'url':target,'title_original':title,'discovery_source_id':source['id'],'discovered_at':now,'status':'pending_editorial_review'})
        except error.HTTPError as e:
            result['status']='http_'+str(e.code)
            if e.code in (401,403,429):blocked.add(origin)
        except Exception as e:result['status']=type(e).__name__
        finally:state['sources'][source['id']]=result
    state.update(updated_at=now,last_run_date=today,method='bounded_official_source_watch_and_news_alias_matching',review_policy='Candidates and news associations are not verified case facts. Editorial review is required before promotion.')
    (ROOT/'data/innovation_watch.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'source_requests_succeeded':checks,'candidates':len(state['candidates']),'observations':len(state['observations']),'offline':args.offline}))
if __name__=='__main__':main()

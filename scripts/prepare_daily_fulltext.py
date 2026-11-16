"""Adapt the existing daily selection and fresh article database, without clipping to 12."""
import argparse, json, sqlite3, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from daily_fulltext_v2 import atomic_json, clean_url, day_now

def local_day(value):
    try:
        date = datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if date.tzinfo is None: return None
        return date.astimezone(timezone(timedelta(hours=8))).date().isoformat()
    except (ValueError, TypeError): return None

def prepare(root, day):
    rows = {}; selected = []
    dashboard = root/'static/data/dashboard.json'
    if dashboard.exists():
        selected = json.loads(dashboard.read_text('utf-8')).get('intelligence', [])
    for i,r in enumerate(selected):
        if local_day(r.get('published_at') or r.get('published_at_utc')) == day:
            rows[clean_url(r['canonical_url'])] = {**r,'priority':i}
    dbfile = root/'data/climate.db'
    if dbfile.exists():
        db=sqlite3.connect(dbfile.resolve().as_uri()+'?mode=ro',uri=True); db.row_factory=sqlite3.Row
        for item in db.execute('SELECT a.*,s.name AS source_name FROM articles a JOIN sources s USING(source_id) ORDER BY a.relevance_score DESC,a.published_at_utc DESC'):
            r=dict(item)
            if local_day(r.get('published_at_utc')) != day: continue
            url=clean_url(r['canonical_url'])
            if int(r.get('relevance_score') or 0)<65 and url not in rows: continue
            meta=json.loads(r.get('metadata_json') or '{}')
            rows[url]={**r,**rows.get(url,{}),'publisher_homepage':meta.get('publisher_homepage'),
                       'publisher_name':meta.get('publisher_name'),
                       'source_summary':r.get('summary_source') or r.get('source_summary'),
                       'publisher_url':meta.get('publisher_url'),'topics':json.loads(r.get('topics_json') or '[]'),
                       'priority':rows.get(url,{}).get('priority',100+len(rows))}
        db.close()
    # Reuse already verified publisher URLs, never reuse excerpt text as a full body.
    import gzip
    source=root/'data/research_texts.jsonl.gz'
    if source.exists():
        with gzip.open(source,'rt',encoding='utf-8') as f:
            for line in f:
                r=json.loads(line); key=r.get('canonical_url')
                if key:
                    key=clean_url(key)
                    if key in rows:
                        if r.get('publisher_url'): rows[key]['publisher_url']=r['publisher_url']
                        if r.get('source_text'): rows[key]['evidence_excerpt']=r['source_text']
    # Preserve existing raw evidence in the daily archive when no fresh DB row exists.
    archive=root/'data/news_archive.json'
    if archive.exists():
        archived=json.loads(archive.read_text('utf-8'))
        if isinstance(archived,dict):archived=archived.get('records',archived.get('articles',archived.get('items',[])))
        if isinstance(archived,list):
            for r in archived:
                if local_day(r.get('published_at_utc') or r.get('published_at'))!=day:continue
                url=r.get('canonical_url')
                if not url:continue
                url=clean_url(url)
                if url not in rows and int(r.get('relevance_score') or 0)>=65:
                    rows[url]={**r,'priority':100+len(rows),'source_summary':r.get('summary_source')}
                if url in rows and r.get('summary_source') and not rows[url].get('source_summary'):
                    rows[url]['source_summary']=r['summary_source']
    return sorted(rows.values(),key=lambda r:r['priority'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--day',default=day_now());p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path,default=Path('data/private_daily_fulltext/input.json'));a=p.parse_args()
    rows=prepare(a.root,a.day);atomic_json(a.output,rows)
    print(json.dumps({'day':a.day,'daily_candidates':len(rows),'input':str(a.output)}))

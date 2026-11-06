"""Quick inventory of durable bodies before annotation has caught up."""
import collections,gzip,json,re
import fulltext_pilot as p
from expansion_quality import eligible
base=p.ROOT/'data/private_global_expansion_20261106';out=p.ROOT/'analysis/global_expansion_20261106'
counts=collections.Counter();sources=collections.defaultdict(collections.Counter);years=collections.Counter();seen=set();urls=set()
files=list((base/'baseline_shards').glob('*.gz'))+list(base.glob('*.jsonl.gz'))+list((base/'targeted').glob('*.json'))+list((base/'historical').glob('*_verified.json'))
for file in files:
 if not file.exists():continue
 rows=(json.loads(s) for s in gzip.open(file,'rt',encoding='utf-8')) if file.suffix=='.gz' else [json.loads(file.read_text('utf-8'))]
 for d in rows:
  counts['input_records']+=1;norm=p.digest(re.sub(r'\s+',' ',d['source_text']).strip().casefold().encode());url=d['url'].rstrip('/')
  if norm in seen or url in urls:counts['duplicates']+=1;continue
  seen.add(norm);urls.add(url);old='document_key' in d;good=d['research_eligible'] if old else eligible(d)[0]
  if d.get('source_id') in ('THEDRIVEN','ELECTREK') and re.search(r'\breview\b|\btest drive\b|\bvideo\b|\bdeal\b',d['title'],re.I):good=False
  source=d['publisher'] if old else d['source'];date=d['published_date'] if old else d['date']
  counts['unique']+=1;counts['eligible']+=int(good);sources[source]['unique']+=1;sources[source]['eligible']+=int(good)
  if good:years[date[:4]]+=1
result={'at':p.stamp(),'scope':'durable bodies, before completed annotation snapshot','counts':dict(counts),'sources':{k:dict(v) for k,v in sources.items()},'years':dict(sorted(years.items()))}
p.dump(out/'acquisition_census.json',result);print(json.dumps({'at':result['at'],'counts':dict(counts),'years':result['years']},ensure_ascii=False))

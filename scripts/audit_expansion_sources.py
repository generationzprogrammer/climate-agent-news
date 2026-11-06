"""Publisher-page cross-check of API extraction, with inspectable comparisons."""
import concurrent.futures as cf,gzip,json,re,random,collections,difflib,time,argparse
from pathlib import Path
import fulltext_pilot as p
import bulk_fulltext as b
ROOT=p.ROOT;PRIVATE=ROOT/'data/private_global_expansion_20261106';OUT=ROOT/'analysis/global_expansion_20261106'
def main(args):
 groups=collections.defaultdict(list)
 for file in sorted(PRIVATE.glob('*.jsonl.gz')):groups[file.name.rsplit('_',1)[0]].append(file)
 selected=[];rng=random.Random(20261106)
 for source,files in groups.items():
  chosen=rng.sample(files,min(args.random_per_source,len(files))) if args.random_per_source else dict.fromkeys([files[0],files[len(files)//2],files[-1]])
  for file in chosen:
   rows=[json.loads(s) for s in gzip.open(file,'rt',encoding='utf-8')]
   good=[d for d in rows if d.get('research_eligible')]
   if good:selected.append(rng.choice(good) if args.random_per_source else good[len(good)//2])
 p.ACCEPT_ENCODING='gzip';p.TIMEOUT=25;fetcher=p.Fetcher();results=[]
 def audit(d):
  result={'id':d['id'],'source':d['source'],'url':d['url'],'api_text_sha256':d['text_sha256'],'published':d['date']}
  try:
   final,html,raw,_=fetcher.get(d['url'],b.timing());body,checks=p.extract(html,d['title'],final,compare_alternative=False)
   norm=lambda s:re.sub(r'\W+',' ',s).casefold().split()
   a=norm(d['source_text']);h=norm(body);aset={tuple(a[i:i+8]) for i in range(max(0,len(a)-7))};hset={tuple(h[i:i+8]) for i in range(max(0,len(h)-7))}
   overlap=len(aset & hset)/max(1,len(aset));ratio=len(body)/max(1,len(d['source_text']))
   result.update(status='agreement' if overlap>=.85 and .7<=ratio<=1.5 else 'manual_review',api_characters=len(d['source_text']),html_characters=len(body),api_shingles_in_html=round(overlap,4),length_ratio=round(ratio,4),html_text_sha256=p.digest(body.encode()),html_checks=checks)
   evidence=PRIVATE/'source_audit';evidence.mkdir(exist_ok=True)
   (evidence/(d['id']+'.html.gz')).write_bytes(gzip.compress(raw,mtime=0))
   p.dump(evidence/(d['id']+'.json'),{'result':result,'html_extracted_text':body})
  except Exception as e:result.update(status='unavailable_for_crosscheck',reason=getattr(e,'reason',type(e).__name__))
  return result
 with cf.ThreadPoolExecutor(max_workers=4) as pool:
  for result in pool.map(audit,selected):
   results.append(result);print(json.dumps({k:result.get(k) for k in ['source','status','api_shingles_in_html','length_ratio','reason']}),flush=True)
   p.dump(OUT/(args.output+'.json'),{'sampling':('seeded random page shards per publisher, one eligible article per selected shard; seed 20261106' if args.random_per_source else 'first/middle/latest available shard per publisher, middle eligible document, frozen at script start'),'samples':results,'not_a_random_label_accuracy_estimate':True})
 p.dump(OUT/(args.output+'_requests.json'),fetcher.requests)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--random-per-source',type=int,default=0);a.add_argument('--output',default='source_crosscheck');main(a.parse_args())

"""Label the small, verified historical/geographic supplement ahead of bulk queues."""
import collections,gzip,json
import fulltext_pilot as p
from label_global_expansion import annotate,ROOT,PRIVATE,OUT,CACHE
codehash=p.digest((ROOT/'src/climate_agent/governance_taxonomy_v2.py').read_bytes()+(ROOT/'scripts/expansion_quality.py').read_bytes()+(ROOT/'scripts/label_global_expansion.py').read_bytes())
manifest={}
for file in list((PRIVATE/'targeted').glob('*.json'))+list((PRIVATE/'historical').glob('*_verified.json')):
 raw=file.read_bytes();d=annotate(json.loads(raw));name=str(file.relative_to(ROOT));sha=p.digest(raw)
 dest=CACHE/(p.digest(name.encode())[:16]+'_'+sha[:12]+'_'+codehash[:8]+'.jsonl.gz')
 tmp=dest.with_suffix('.priority.tmp');tmp.write_bytes(gzip.compress((json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n').encode(),compresslevel=3,mtime=0));tmp.replace(dest)
 counts=lambda key:dict(collections.Counter(d['labels'][key])) if d['research_eligible'] else {}
 manifest[name]={'input_sha256':sha,'code_sha256':codehash,'file':dest.name,'records':1,'eligible':int(d['research_eligible']),'countries':counts('country_mentions'),'focal_countries':counts('country_focal_candidates'),'subcategories':counts('subcategory_mentions'),'focal_subcategories':counts('focal_subcategory_candidates'),'years':{str(d['year']):int(d['research_eligible'])}}
p.dump(OUT/'label_cache_manifest_priority.json',manifest)
print(json.dumps({'records':len(manifest),'eligible':sum(v['eligible'] for v in manifest.values())}))

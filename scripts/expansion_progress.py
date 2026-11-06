"""Read durable checkpoint counters, without counting incomplete temporary files."""
import collections,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/global_expansion_20261106'
def main():
 states={}
 for f in OUT.glob('*_state.json'):
  try:states[f.stem]=json.loads(f.read_text('utf-8'))
  except ValueError:pass
 counts=collections.Counter(); countries=collections.Counter(); topics=collections.Counter(); years=collections.Counter()
 entries={}
 for f in OUT.glob('label_cache_manifest_p*.json'):
  try:m=json.loads(f.read_text('utf-8'))
  except ValueError:continue
  entries.update(m)
 for v in entries.values():
   counts.update({k:v.get(k,0) for k in ['records','eligible']});countries.update(v.get('countries',{}));topics.update(v.get('subcategories',{}));years.update(v.get('years',{}))
 result={'labeled_pre_final_dedup':dict(counts),'countries':len(countries),'subtopics':len(topics),'collector_stage_accepted':sum(d.get('accepted',0) for d in states.values()),'collector_stage_review':sum(d.get('review',0) for d in states.values()),'source_checkpoints':len(states),'completed_sources':sum(bool(d.get('complete')) for d in states.values()),'failures':{n:d['last_failure'] for n,d in states.items() if d.get('last_failure')}}
 if '--detailed' in sys.argv:result.update(collection=states,years=dict(sorted(years.items())))
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()

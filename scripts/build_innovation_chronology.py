"""Materialise explicit editorial date reviews; never infer dates from URLs."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    review=json.loads((ROOT/'config/innovation_chronology_review.json').read_text(encoding='utf-8'))
    sources={}
    for path in sorted((ROOT/'config').glob('open_innovation_*.json')):
        data=json.loads(path.read_text(encoding='utf-8'))
        sources.update({s['url']:s['id'] for s in data.get('sources',[])})
    added, events=[],[]
    for entry in review['entries']:
        source_id=sources.get(entry['url'])
        if not source_id:
            source_id='s_history_'+hashlib.sha256(entry['url'].encode()).hexdigest()[:12]
            sources[entry['url']]=source_id
            added.append({'id':source_id,'url':entry['url'],'title':entry['title'],
              'publisher':entry['publisher'],'language':entry.get('language') or ('zh' if any('\u4e00'<=c<='\u9fff' for c in entry['publisher']) else 'en'),
              'published_date':entry['published_date'],'reviewed_at':review['reviewed_at'],
              'access':'public_metadata_and_paraphrase','source_role':entry.get('source_role','primary')})
        identifier=entry['case_id']+'|'+entry['date']+'|'+entry['kind']
        events.append({'id':'evt_'+hashlib.sha256(identifier.encode()).hexdigest()[:14],
          'case_id':entry['case_id'],'date':entry['date'],'date_precision':entry['precision'],
          'kind':entry['kind'],'origin_basis':entry['origin'],
          'description':{'zh':entry['zh'],'en':entry['en']},'source_ids':[source_id],
          'review_status':'reviewed','reviewed_at':review['reviewed_at'],
          'coding_basis':review['review_method']})
    result={'reviewed_at':review['reviewed_at'],'events':events,'sources':added}
    (ROOT/'config/innovation_chronology.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'events':len(events),'additional_sources':len(added)}))
if __name__=='__main__':main()

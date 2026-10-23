"""Add evidence-linked detail without overwriting directory or historical fields."""
import copy
import hashlib
import json
from pathlib import Path

def apply_case_details(book: dict, root: Path) -> None:
    path=root/'config/innovation_case_details.json'
    if not path.exists():return
    from .innovation_cases import safe_public_url
    config=json.loads(path.read_text(encoding='utf-8'))
    cases={c['id']:c for c in book['cases']}
    sources={s['url'].rstrip('/'):s for s in book['sources']}
    seen=set()
    prepared=[]
    for row in config['cases']:
        cid=row['case_id']
        if cid in seen or cid not in cases:raise ValueError('Invalid detail case identity')
        seen.add(cid)
        if not safe_public_url(row['url']):raise ValueError('Unsafe detail source')
        for key in ('title','summary'):
            if not all(isinstance(row[key].get(l),str) and row[key][l].strip() for l in ('zh','en')):raise ValueError('Missing bilingual detail')
        if not row.get('locator') or not row.get('publisher'):raise ValueError('Missing detail provenance')
        for fact in row['facts']:
            if fact.get('status') not in {'research_scope','reported_facility','registered_target','reported_result'} or not fact.get('locator'):raise ValueError('Invalid detail fact')
            if not all(fact.get(key,{}).get(l) for key in ('label','value') for l in ('zh','en')):raise ValueError('Missing bilingual fact')
        prepared.append(copy.deepcopy(row))
    for row in prepared:
        source=sources.get(row['url'].rstrip('/'))
        if source is None:
            source=dict(id='s_detail_'+hashlib.sha256(row['url'].encode()).hexdigest()[:16],
                        url=row['url'],title=row['source_title'],publisher=row['publisher'],language='en',
                        reviewed_at=config['version'])
            book['sources'].append(source);sources[row['url'].rstrip('/')]=source
        case=cases[row.pop('case_id')]
        row.update(source_id=source['id'],reviewed_at=config['version'],review_method=config['review_method'])
        for fact in row['facts']:fact['source_id']=source['id']
        case['case_detail']=row
        if not any(e.get('source_id')==source['id'] and 'case_detail' in e.get('supports',[]) for e in case['evidence']):
            case['evidence'].append(dict(source_id=source['id'],supports=['case_detail'],locator=row['locator']))
    book['reviewed_at']=max(book.get('reviewed_at',''),config['version'])

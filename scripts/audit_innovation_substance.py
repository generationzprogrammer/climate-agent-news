"""Reproducible, read-only semantic-density diagnostics; no synthetic scoring."""
import collections
import hashlib
import json
import re
import argparse
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis/innovation_quality_20261023'

def audit(raw=None):
    path = ROOT / 'static/data/innovation_cases.json'
    raw = path.read_bytes() if raw is None else raw
    book = json.loads(raw)
    cases = book['cases']
    counts = {}
    for field in ['summary', 'mechanism', 'observed', 'constraints', 'transfer']:
        values = [re.sub(r'\s+', '', c.get(field, {}).get('zh', '')) for c in cases]
        freq = collections.Counter(v for v in values if v)
        counts[field] = {'populated': sum(bool(v) for v in values),
                         'distinct': len(freq),
                         'rows_in_repeated_groups': sum(n for n in freq.values() if n > 1),
                         'largest_groups': [list(pair) for pair in freq.most_common(6)]}
    return dict(snapshot_sha256=hashlib.sha256(raw).hexdigest(),
                snapshot_updated_at=book.get('updated_at'), inspected_at=date.today().isoformat(),
                cases=len(cases), duplicate_ids=len(cases)-len({c['id'] for c in cases}),
                grains=dict(collections.Counter(c['research_annotation']['grain'] for c in cases)),
                cohorts=dict(collections.Counter(c['research_annotation']['cohort'] for c in cases)),
                registry_cases=sum(bool(c.get('registry_record')) for c in cases),
                single_citation_cases=sum(len(c.get('evidence', [])) == 1 for c in cases),
                unknown_origin_year=sum(c.get('timeline', {}).get('origin_year') is None for c in cases),
                fields=counts,
                interpretation='Exact repetition is a screening signal, not a count of invalid or duplicate cases. Shared programme rules must not be presented as case-level observations.')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT/'substance_audit_current.json')
    args=parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'fields'}, ensure_ascii=False))

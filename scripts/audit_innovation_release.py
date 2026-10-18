"""Offline integrity and reconciliation checks for an immutable research snapshot."""
import argparse,csv,hashlib,json
from collections import Counter
from pathlib import Path

def audit(folder):
    folder=Path(folder).resolve()
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        file=(folder/entry['path']).resolve()
        if folder not in file.parents:raise ValueError('Unsafe manifest path')
        assert file.stat().st_size==entry['bytes'],entry['path']
        assert hashlib.sha256(file.read_bytes()).hexdigest()==entry['sha256'],entry['path']
    quality=json.loads((folder/'quality_audit.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((folder/'quality_audit.json').read_bytes()).hexdigest()==manifest['quality_audit_sha256']
    book=json.loads((folder/'data/cases_nested.json').read_text(encoding='utf-8'))
    cases=book['cases'];sources=book['sources'];ids={c['id'] for c in cases};sids={s['id'] for s in sources}
    assert len(ids)==len(cases)==quality['cases']
    assert len(sids)==len(sources)==quality['sources']
    assert len({s['url'] for s in sources})==len(sources)
    assert dict(Counter(c['research_annotation']['grain'] for c in cases))==quality['grains']
    for case in cases:
        assert case['evidence'] and all(e['source_id'] in sids for e in case['evidence']),case['id']
        if case.get('registry_record',{}).get('designation_year'):
            assert case['timeline']['origin_year'] is None
    rows=list(csv.DictReader((folder/'data/cases.csv').read_text(encoding='utf-8-sig').splitlines()))
    assert {r['case_id'] for r in rows}==ids and len(rows)==len(cases)
    previous=folder.parent/'innovation_research_20261014_r2/data/cases_nested.json'
    if previous.exists():
        current={c['id']:c for c in cases}
        for old in json.loads(previous.read_text(encoding='utf-8'))['cases']:
            for key in ['title','summary','actors','mechanism','observed','evidence']:
                assert old.get(key)==current[old['id']].get(key),(old['id'],key)
    print(json.dumps({'status':'passed','release':manifest['release'],'cases':len(cases),'source_documents':len(sources),'files_verified':len(manifest['files']),'semantic_accuracy':'not_estimated'}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder')
    audit(parser.parse_args().folder)

"""Collect complete project records from cached, public ARPA-E index pages."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from fetch_us_innovation_evidence import CACHE, fetch

BASE = 'https://arpa-e.energy.gov/jsonapi/custom/index/project'


def parse_response(text):
    # Fail closed: an interrupted response never yields partial case facts.
    value = json.loads(text)
    if not isinstance(value.get('data'), list) or not value.get('meta', {}).get('count'):
        raise ValueError('Unexpected official index schema')
    return value


def complete_records(text):
    """Recover only fully decoded top-level nodes, never repair a partial node."""
    decoder = json.JSONDecoder()
    marker = text.find('"data":[')
    if marker < 0 or not text.lstrip().startswith('{"jsonapi":'):
        return []
    position, result = marker + len('"data":['), []
    while position < len(text):
        while position < len(text) and text[position].isspace():
            position += 1
        try:
            value, position = decoder.raw_decode(text, position)
        except ValueError:
            break
        if value.get('type') != 'node--project' or not value.get('attributes', {}).get('fields'):
            break
        result.append(value)
        if position >= len(text) or text[position] != ',':
            break
        position += 1
    return result


def recover_cached_complete_nodes():
    target = CACHE / 'projects.json'
    rows = {r['attributes']['drupal_internal__nid']:r for r in
            json.loads(target.read_text(encoding='utf-8'))} if target.exists() else {}
    recovered, partial_pages = 0, []
    for audit_file in CACHE.glob('*.audit.json'):
        audit = json.loads(audit_file.read_text(encoding='utf-8'))
        if '/custom/index/project' not in audit['url']:
            continue
        path = audit_file.with_name(audit_file.name.replace('.audit.json','.response'))
        text = path.read_text(encoding='utf-8')
        try:
            parsed = parse_response(text)['data']
            status = 'complete_page'
        except ValueError:
            parsed = complete_records(text)
            status = 'complete_nodes_only_from_interrupted_page'
            partial_pages.append({'url':audit['url'],'complete_nodes':len(parsed), 'sha256':audit['sha256']})
        for row in parsed:
            nid = row['attributes']['drupal_internal__nid']
            if nid not in rows:
                row['_snapshot'] = {k:audit[k] for k in ('url','sha256','fetched_at_utc')}
                row['_snapshot']['parse_basis'] = status
                rows[nid] = row
                recovered += 1
    target.write_text(json.dumps(list(rows.values()),ensure_ascii=False),encoding='utf-8')
    (CACHE/'recovery_audit.json').write_text(json.dumps({'recovered_complete_projects':recovered,'interrupted_pages':partial_pages},indent=2),encoding='utf-8')
    print(json.dumps({'recovered_complete_projects':recovered,'cached_projects':len(rows)}))


def collect(offset, count, size):
    target = CACHE / 'projects.json'
    rows = {r['attributes']['drupal_internal__nid']: r for r in
            json.loads(target.read_text(encoding='utf-8')) if target.exists()} if target.exists() else {}
    health_file = CACHE / 'collection_health.json'
    health = json.loads(health_file.read_text(encoding='utf-8')) if health_file.exists() else []
    for start in range(offset, offset + count, size):
        url = BASE + '?' + urlencode({'page[offset]': start, 'page[limit]': min(size, offset + count-start)})
        try:
            path = fetch(url)
            response = parse_response(path.read_text(encoding='utf-8'))
            audit = json.loads(path.with_suffix('.audit.json').read_text(encoding='utf-8'))
            for row in response['data']:
                row['_snapshot'] = {key: audit[key] for key in ('url', 'sha256', 'fetched_at_utc')}
                rows[row['attributes']['drupal_internal__nid']] = row
            target.write_text(json.dumps(list(rows.values()), ensure_ascii=False), encoding='utf-8')
            health.append({'url':url, 'status':'parsed', 'records':len(response['data']),
                           'checked_at_utc':datetime.now(timezone.utc).isoformat()})
            print(json.dumps({'offset': start, 'received': len(response['data']), 'cached_projects': len(rows)}), flush=True)
        except Exception as exc:
            health.append({'url':url, 'status':'failed', 'error':type(exc).__name__,
                           'checked_at_utc':datetime.now(timezone.utc).isoformat()})
            print(json.dumps({'offset': start, 'status': 'failed', 'error': type(exc).__name__}), flush=True)
            if isinstance(exc, PermissionError) or getattr(exc, 'code', None) in (401,403,429):
                break
        health_file.write_text(json.dumps(health,indent=2),encoding='utf-8')
    return rows


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--offset', type=int, default=300)
    p.add_argument('--count', type=int, default=600)
    p.add_argument('--size', type=int, default=5)
    p.add_argument('--recover-complete-records', action='store_true')
    args = p.parse_args()
    if args.recover_complete_records:
        recover_cached_complete_nodes()
    else:
        collect(args.offset, args.count, args.size)

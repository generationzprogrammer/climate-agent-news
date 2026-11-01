"""Read-only, reproducible profile for the 2026-11-01 GREEN expansion assessment."""
import argparse
import collections
import json
import sqlite3
import statistics
from pathlib import Path
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=root/'analysis/green_expansion_20261101/corpus_readiness.json')
args = parser.parse_args()
rows = [json.loads(line) for line in (root/'data/climate_text_corpus.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
archive = json.loads((root/'data/news_archive.json').read_text(encoding='utf-8'))['records']
domains = collections.Counter(urlsplit(r.get('canonical_url', '')).hostname for r in rows)
urls = collections.Counter(r.get('canonical_url') for r in rows)
c = sqlite3.connect((root/'data/climate.db').as_uri()+'?mode=ro', uri=True)
models = collections.Counter(); lengths=[]; basis=collections.Counter()
for (raw,) in c.execute('SELECT metadata_json FROM articles'):
    m = json.loads(raw or '{}')
    if m.get('translation_model'): models[m['translation_model']] += 1
    if m.get('summary_zh'): lengths.append(len(m['summary_zh']))
    basis[m.get('content_basis') or 'unrecorded'] += 1
counts = {t:c.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ['articles','historical_articles','official_documents','sources']}
c.close()
result = {'snapshot_date':'2026-11-01','corpus_records':len(rows),'archive_records':len(archive),
          'date_min':min(r['published_date'] for r in rows),'date_max':max(r['published_date'] for r in rows),
          'google_canonical_records':domains['news.google.com'],'google_canonical_share':round(domains['news.google.com']/len(rows),4),
          'exact_duplicate_url_excess':sum(n-1 for n in urls.values() if n>1),
          'country_codes_nonempty':sum(bool(r.get('country_codes')) for r in rows),
          'source_summary_nonempty':sum(bool(r.get('summary_source')) for r in rows),
          'metadata_only_flag_true':sum(r.get('quality_flags',{}).get('metadata_only') is True for r in rows),
          'translation_models':dict(models),'content_basis':dict(basis),
          'chinese_summary_median_chars':statistics.median(lengths) if lengths else None,
          'tables':counts,'note':'Content-basis labels describe extraction input, not storage rights or verified full text.'}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
print(json.dumps(result, ensure_ascii=True))

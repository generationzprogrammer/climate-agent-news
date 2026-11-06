"""Repartition checkpoint metadata after stopping label workers; preserve caches."""
import argparse, json, shutil
import fulltext_pilot as p
from label_global_expansion import OUT

parser = argparse.ArgumentParser(); parser.add_argument('--parts', type=int, required=True)
args = parser.parse_args()
if not 1 <= args.parts <= 16: raise SystemExit('parts must be 1..16')
backup = OUT / ('manifest_backup_' + p.stamp().replace(':', '-'))
backup.mkdir()
entries = {}
for file in sorted(OUT.glob('label_cache_manifest_p*.json')):
    entries.update(json.loads(file.read_text('utf-8')))
    shutil.copy2(file, backup / file.name)
for part in range(args.parts):
    selected = {k: v for k, v in entries.items() if int(p.digest(k.encode())[:8], 16) % args.parts == part}
    p.dump(OUT / f'label_cache_manifest_p{part}.json', selected)
print(json.dumps({'cached_inputs_preserved': len(entries), 'parts': args.parts, 'backup': str(backup)}))

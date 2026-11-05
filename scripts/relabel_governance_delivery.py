"""Reproduce tags from a delivered JSONL.gz, without acquisition assets."""
import argparse,gzip,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from climate_agent.governance_labels import label_text
ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('output');a=ap.parse_args()
if Path(a.output).exists():raise SystemExit('Choose a new output; existing files are not overwritten')
with gzip.open(a.input,'rt',encoding='utf-8') as src,gzip.open(a.output,'wt',encoding='utf-8') as dst:
    for line in src:
        r=json.loads(line)
        assert hashlib.sha256(r['source_text'].encode()).hexdigest()==r['text_sha256']
        labels=label_text(r['title'],r['source_text'])
        dst.write(json.dumps({'document_key':r['document_key'],'text_sha256':r['text_sha256'],'labels':labels},ensure_ascii=False)+'\n')

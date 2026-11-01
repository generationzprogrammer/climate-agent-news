"""Reproducible offline corpus validation; never prints credentials or contacts."""
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path
from climate_agent.research import load_jsonl,clean,substantive,words

parser=argparse.ArgumentParser();parser.add_argument('--samples',action='store_true');args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
rows=load_jsonl(root/'data/research_texts.jsonl')
errors=[]
for r in rows:
    if re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',json.dumps(r,ensure_ascii=False)):errors.append([r['text_id'],'email_not_redacted'])
    if r['text_sha256']!=hashlib.sha256(r['source_text'].encode()).hexdigest():errors.append([r['text_id'],'hash_mismatch'])
    if not substantive(r['source_text'],r['title_original']):errors.append([r['text_id'],'no_substantive_text'])
    if r['source_text']!=clean(r['source_text']):errors.append([r['text_id'],'not_clean'])
    for group in ['governance_themes','policy_tools','policy_stages']:
        for item in r.get(group,[]):
            if not 0<=item['start']<item['end']<=len(r['source_text']):errors.append([r['text_id'],'invalid_evidence_offset'])
print(json.dumps({'records':len(rows),'unique_text_ids':len({r['text_id'] for r in rows}),
                  'unique_urls':len({r['canonical_url'] for r in rows}),
                  'identical_text_excess':len(rows)-len({r['text_sha256'] for r in rows}),
                  'text_kinds':dict(collections.Counter(r['text_kind'] for r in rows)),
                  'errors':errors[:30],'error_count':len(errors)},ensure_ascii=True))
if args.samples:
    for kind in ['article_excerpt','source_excerpt','licensed_document_text']:
        sample=[r for r in rows if r['text_kind']==kind]
        for r in sample[::max(1,len(sample)//4)][:4]:
            print(json.dumps({'id':r['text_id'],'title':r['title_original'],'url':r.get('publisher_url'),
                              'text':r['source_text'][:380]},ensure_ascii=True))
if errors:raise SystemExit(1)

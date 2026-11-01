"""Explicit, bounded source-text backfill. Never calls a model API."""
import argparse
import json
from pathlib import Path
from climate_agent.db import Database
from climate_agent.research import collect_texts, write_research, freeze_release
from climate_agent.research_documents import update_documents

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
parser.add_argument('--fetch-limit',type=int,default=40)
parser.add_argument('--freeze',action='store_true')
parser.add_argument('--documents',action='store_true')
args=parser.parse_args()
if not 0<=args.fetch_limit<=200:parser.error('fetch-limit must be between 0 and 200')
db=Database(args.root/'data/climate.db')
status=collect_texts(args.root,db,fetch_limit=args.fetch_limit)
if args.documents:status['documents']=update_documents(args.root)
status['export']=write_research(args.root,db,args.root/'static/data')
if args.freeze:
    status['release']=freeze_release(args.root)
    status['export']=write_research(args.root,db,args.root/'static/data')
print(json.dumps(status,ensure_ascii=False),flush=True)

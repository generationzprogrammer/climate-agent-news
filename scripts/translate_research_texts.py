import argparse,json
from pathlib import Path
from climate_agent.research_translation import translate_corpus
parser=argparse.ArgumentParser();parser.add_argument('--max-requests',type=int,default=4);parser.add_argument('--workers',type=int,default=2)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
first=translate_corpus(root,max_requests=max(0,args.max_requests-20) if args.max_requests>30 else args.max_requests,workers=args.workers)
if args.max_requests>30 and first.get('pending_records') and not first.get('errors',{}).get('ModelBudgetExceeded') and not first.get('errors',{}).get('HTTPError'):
    first=translate_corpus(root,max_requests=20,workers=args.workers)
print(json.dumps(first,ensure_ascii=False),flush=True)

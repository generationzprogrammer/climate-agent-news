import argparse,json
from pathlib import Path
from climate_agent.research_archives import expand_archives
parser=argparse.ArgumentParser();parser.add_argument('--target-unique',type=int,default=3650);parser.add_argument('--max-pages',type=int,default=100)
args=parser.parse_args()
if not 1<=args.max_pages<=150:parser.error('max-pages must be 1..150')
print(json.dumps(expand_archives(Path(__file__).resolve().parents[1],target_unique=args.target_unique,max_pages=args.max_pages),ensure_ascii=False),flush=True)

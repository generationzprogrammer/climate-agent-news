"""Incrementally extract unpublished stance candidates under the shared free quota."""
import argparse
import json
from pathlib import Path
from climate_agent.stance_pilot import update_candidates

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-requests', type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(update_candidates(Path(__file__).resolve().parents[1], max_requests=args.max_requests)))

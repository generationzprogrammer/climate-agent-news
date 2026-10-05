"""Bounded, one-off HEAD checks of curated public evidence links; no page mirroring."""
import argparse
import concurrent.futures
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
book = json.loads((ROOT / "config/open_innovation_cases.json").read_text(encoding="utf-8"))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", action="append", help="Only check specified revised source IDs")
args = parser.parse_args()
checked_at = datetime.now(timezone.utc).isoformat()


def check(source):
    request = urllib.request.Request(source["url"], method="HEAD",
        headers={"User-Agent": "GruenInnovationCases/1.0 (public-link-check)", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return {"id": source["id"], "url": source["url"], "status": response.status, "resolved_url": response.url}
    except urllib.error.HTTPError as error:
        return {"id": source["id"], "url": source["url"], "status": error.code, "error": "http"}
    except Exception as error:
        return {"id": source["id"], "url": source["url"], "status": None, "error": type(error).__name__}


target = ROOT / "analysis/innovation_source_link_check.json"
prior = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
previous = {row["id"]: {**row, "checked_at": row.get("checked_at", prior.get("checked_at"))} for row in prior.get("sources", [])}
requested = [source for source in book["sources"] if not args.source or source["id"] in args.source]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    fresh = [{**row, "checked_at": checked_at} for row in pool.map(check, requested)]
previous.update({row["id"]: row for row in fresh})
results = [previous[source["id"]] for source in book["sources"] if source["id"] in previous]
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps({"checked_at": checked_at,
    "method": "one_HEAD_request_per_curated_URL_no_retries", "sources": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"sources": len(results), "reachable": sum(row["status"] == 200 for row in results),
    "review": [row for row in results if row["status"] != 200]}, ensure_ascii=False))

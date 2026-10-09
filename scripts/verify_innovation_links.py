"""Bounded, one-off HEAD checks of curated public evidence links; no page mirroring."""
import argparse
import concurrent.futures
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", action="append", help="Only check specified revised source IDs")
parser.add_argument("--casebook", type=Path, default=ROOT/"config/open_innovation_cases.json")
parser.add_argument("--output", type=Path, default=ROOT/"analysis/innovation_source_link_check.json")
parser.add_argument("--confirm-head-404", action="store_true",
                    help="Confirm HEAD 404 with one bounded GET; never retry 401/403/429")
args = parser.parse_args()
book = json.loads(args.casebook.read_text(encoding="utf-8"))
checked_at = datetime.now(timezone.utc).isoformat()
rate_lock = threading.Lock()
last_request = 0.0
stopped_hosts = set()


def check(source):
    global last_request
    host = urlparse(source["url"]).hostname
    with rate_lock:
        if host in stopped_hosts:
            return {"id": source["id"], "url": source["url"], "status": None, "error": "access_policy_stopped"}
        time.sleep(max(0,1-(time.monotonic()-last_request)))
        last_request=time.monotonic()
    request = urllib.request.Request(source["url"], method="HEAD",
        headers={"User-Agent": "GruenInnovationCases/1.0 (public-link-check)", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return {"id": source["id"], "url": source["url"], "status": response.status, "resolved_url": response.url}
    except urllib.error.HTTPError as error:
        if error.code == 404 and args.confirm_head_404:
            row = {"id": source["id"], "url": source["url"], "status": 404, "error": "http"}
            try:
                # Some university servers return 404 for HEAD but serve the page on GET.
                # Read only a bounded fragment; do not store or print page contents.
                get_request = urllib.request.Request(source["url"], headers=dict(request.header_items()))
                with rate_lock:
                    time.sleep(max(0,1-(time.monotonic()-last_request)))
                    last_request=time.monotonic()
                with urllib.request.urlopen(get_request, timeout=12) as response:
                    response.read(262144)
                    row.update(get_status=response.status, resolved_url=response.url,
                               confirmation_method="one_bounded_GET_after_HEAD_404")
            except urllib.error.HTTPError as confirm_error:
                row.update(get_status=confirm_error.code, get_error="http")
                if confirm_error.code in {401,403,429}:
                    with rate_lock:stopped_hosts.add(host)
            except Exception as confirm_error:
                row.update(get_status=None, get_error=type(confirm_error).__name__)
            return row
        if error.code in {401,403,429}:
            with rate_lock:
                stopped_hosts.add(host)
        return {"id": source["id"], "url": source["url"], "status": error.code, "error": "http"}
    except Exception as error:
        return {"id": source["id"], "url": source["url"], "status": None, "error": type(error).__name__}


target = args.output
prior = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
previous = {row["id"]: {**row, "checked_at": row.get("checked_at", prior.get("checked_at"))} for row in prior.get("sources", [])}
requested = [source for source in book["sources"] if not args.source or source["id"] in args.source]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    fresh = [{**row, "checked_at": checked_at} for row in pool.map(check, requested)]
previous.update({row["id"]: row for row in fresh})
results = [previous[source["id"]] for source in book["sources"] if source["id"] in previous]
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps({"checked_at": checked_at,
    "method": "one_HEAD_request_per_curated_URL_no_retries" +
        ("; opt-in bounded GET confirmation for HEAD 404 only" if args.confirm_head_404 else ""),
    "sources": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"sources": len(results), "reachable": sum(row["status"] == 200 or row.get("get_status") == 200 for row in results),
    "review": [row for row in results if row["status"] != 200 and row.get("get_status") != 200]}, ensure_ascii=False))

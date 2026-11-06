"""Revisit the SAME unresolved pilot articles; never substitute other news.

Private bodies and persistent URL mappings are separate from original data.
"""
from __future__ import annotations
import argparse
import collections
import concurrent.futures
import csv
import gzip
import hashlib
import json
import re
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import fulltext_pilot as pilot
from climate_agent.publisher_recovery import (
    VERSION, discover_publisher, identity, jats_text, normalized,
    scholarly_candidates, title_text,
)

ROOT = pilot.ROOT
OLD = ROOT / "analysis/fulltext_pilot_20261103"
OUT = ROOT / "analysis/fulltext_recovery_20261103"
PRIVATE = ROOT / "data/private_fulltext_recovery_20261103"


def prepare_catalog():
    cfg = json.loads((ROOT / "config/sources.master.json").read_text("utf-8"))
    homes = {normalized(s["name"]): s.get("homepage_url") for s in cfg}
    apis = json.loads((ROOT / "config/research_archives.json").read_text("utf-8"))["sources"]
    endpoints = {}
    for s in apis:
        homes[normalized(s["name"])] = s["homepage"]
        for h in s["allowed_hosts"]:
            endpoints[h] = s["endpoint"]
    for s in json.loads((ROOT/'config/publisher_recovery_sources.json').read_text('utf-8'))['sources']:
        for name in s['aliases']:
            homes[normalized(name)] = s['homepage']
    catalog = []
    for x in pilot.news_records(ROOT):
        if pilot.host(x["canonical_url"]) != "news.google.com":
            catalog.append({"url":x["canonical_url"],"title":x.get("title_original"),"source":x.get("source_name"),"date":x.get("published_at_utc") or x.get("published_at")})
    for x in pilot.load_lines(ROOT / "data/research_texts.jsonl.gz"):
        if x.get("text_kind") == "licensed_document_text":
            continue
        u = x.get("publisher_url") or x["canonical_url"]
        if pilot.host(u) != "news.google.com":
            catalog.append({"url":u,"title":x.get("title_original"),"source":x.get("source_name"),"date":x.get("published_at")})
    db = sqlite3.connect((ROOT / "data/climate.db").resolve().as_uri() + "?mode=ro", uri=True)
    for u, title, date, meta, source in db.execute("SELECT a.canonical_url,a.title_original,a.published_at_utc,a.metadata_json,s.name FROM articles a JOIN sources s USING(source_id)"):
        m = json.loads(meta or "{}")
        name = m.get("publisher_name") or source
        if m.get("publisher_homepage") and not pilot.host(m["publisher_homepage"]).endswith("google.com"):
            homes.setdefault(normalized(name), m["publisher_homepage"])
        if pilot.host(u) != "news.google.com":
            catalog.append({"url":u,"title":title,"source":name,"date":date})
    db.close()
    # Learn only publisher names with an observed direct URL, never guess a URL slug.
    for x in catalog:
        if x.get("source"):
            homes.setdefault(normalized(x["source"]), urlunsplit(("https", pilot.host(x["url"]), "/", "", "")))
    unique = {x["url"]:x for x in catalog}
    return homes, endpoints, list(unique.values())


def main(*, retry_failed=False):
    OUT.mkdir(parents=True,exist_ok=True)
    PRIVATE.mkdir(parents=True,exist_ok=True)
    pilot.PRIVATE = PRIVATE
    original_hashes = pilot.input_hashes()
    pilot.dump(OUT / "input_before.json", original_hashes)
    if (OUT/'summary.json').exists():
        prior_summary=json.loads((OUT/'summary.json').read_text('utf-8'))
        pilot.dump(OUT/'previous_summary.json',prior_summary)
        if not (OUT/'run_history.json').exists():
            pilot.dump(OUT/'run_history.json',[{'wall_seconds':prior_summary.get('wall_seconds_this_run',0),'network_requests':prior_summary.get('network_requests_this_run',0),'retry_failed':False,'note':'Initial run preserved before retry'}])
    original = pilot.load_lines(OLD / "attempts.jsonl")
    targets = [x for x in original if x["status"] == "publisher_url_unresolved"]
    pilot.dump(OUT / "same_failed_targets.json", targets)
    homes, endpoints, catalog = prepare_catalog()
    fetcher = pilot.Fetcher()
    cache = {}
    lock = threading.RLock()
    previous = pilot.load_lines(OUT / "attempts.jsonl")
    latest = {r['id']:r for r in previous}
    done = {r['id'] for r in latest.values() if not retry_failed or r.get('text_characters')}
    # Preserve access-denial circuit breakers across explicit same-day retries.
    for r in previous:
        for note in r.get('access_notes',[]):
            if note['status'] in ('http_401','http_403','http_429'):
                fetcher.stop_hosts[pilot.host(note['url'])]=note['status']
    results = list(latest.values())
    prior_ledger = {x['original_url']:x['candidate'] for x in pilot.load_lines(PRIVATE/'publisher_url_ledger.jsonl')}

    def work(original):
        row = {k:v for k,v in original.items() if k != "timing"}
        row.update(status="not_started", original_url=original["url"], resolver_version=VERSION, attempted_at=pilot.stamp())
        timings = {k:0.0 for k in ("dns_seconds","robots_seconds","network_seconds","rate_wait_seconds")}
        timings.update(request_count=0,response_bytes=0)
        notes = []
        began = time.perf_counter()
        def read(url):
            with lock:
                if url in cache:
                    return cache[url]
            try:
                _, _, data, _ = fetcher.get(url, timings)
            except pilot.StopFetch as e:
                notes.append({"url":url,"status":e.reason})
                data = b""
            with lock:
                cache[url] = data
            return data
        try:
            home = row.get("publisher_homepage")
            if not home or pilot.host(home).endswith("google.com"):
                home = homes.get(normalized(row.get("source") or ""))
            if not home and re.fullmatch(r"(?:[\w-]+\.)+[a-z]{2,}", row.get("source") or "", re.I):
                home = "https://" + row["source"].lower() + "/"
            row["publisher_homepage"] = home
            candidate = prior_ledger.get(original['url'])
            for x in catalog:
                if candidate:
                    break
                if normalized(x.get("source") or "") != normalized(row.get("source") or ""):
                    continue
                match = identity(row["title"], x.get("title"), publisher=row.get("source"), expected_date=row.get("date"),candidate_date=x.get("date"))
                if match:
                    candidate = {"publisher_url":x["url"],"route":"existing_publisher_title_date_index","identity":match,"source_date":x.get("date"),"source_page_title":x.get("title")}
                    break
            scholarly = row.get("source") in ("Nature","AGU Publications","Frontiers")
            if not candidate and scholarly:
                candidates = scholarly_candidates(row,read)
                candidates.sort(key=lambda x:bool(x.get("fulltext_xml_url")),reverse=True)
                candidate = candidates[0] if candidates else None
            if not candidate and home:
                candidates = discover_publisher(row,read,endpoint=endpoints.get(pilot.host(home)))
                candidate = candidates[0] if len(candidates) == 1 else None
                if len(candidates)>1:
                    row["status"]="ambiguous_multiple_identity_matches"
            row["resolution_seconds"] = time.perf_counter()-began
            if not candidate:
                if row["status"] == "not_started":
                    row["status"] = "publisher_url_unresolved" if home or scholarly else "publisher_homepage_unknown"
                return row
            row["candidate"] = candidate
            if candidate.get("fulltext_xml_url"):
                raw = read(candidate["fulltext_xml_url"])
                if not raw:
                    row["status"]="repository_download_failed"
                    return row
                t=time.perf_counter()
                text, checks = jats_text(raw,title_text(row["title"],row.get("source")))
                row.update(checks)
                row.update(fulltext_url=candidate["fulltext_xml_url"],publisher_url=candidate.get("publisher_url"),text_sha256=pilot.digest(text.encode()),text_characters=len(text),text_utf8_bytes=len(text.encode()),text_gzip_bytes=len(gzip.compress(text.encode(),mtime=0)),raw_response_bytes=len(raw),translated=False,rights_status="licensed_open_access_repository_copy",public_redistribution_allowed=False,manual_review="not_independently_human_reviewed")
                row["extract_seconds"] = time.perf_counter()-t
                (PRIVATE/"articles").mkdir(exist_ok=True)
                (PRIVATE/"raw").mkdir(exist_ok=True)
                (PRIVATE/"articles"/(row["id"]+".json")).write_bytes(pilot.jsonbytes({**row,"source_text":text}))
                (PRIVATE/"raw"/(row["id"]+".response.gz")).write_bytes(gzip.compress(raw,mtime=0))
            elif candidate.get("publisher_url"):
                target = {**row,"url":candidate["publisher_url"],"stratum":"direct_other","sample_group":"same_failed_target_recovery","aliases":[original["url"]]}
                # Only the previously registered 5 publishers use API body retrieval.
                # New/discovered APIs supply URL metadata; their page is fetched and
                # checked for registration/paywall restrictions before keeping text.
                if pilot.host(target["url"]) in endpoints and candidate.get('route')!='publisher_wordpress_all_types_search':
                    target.update(api_endpoint=endpoints[pilot.host(target["url"])],archive_post_id=candidate.get("archive_post_id"))
                result=pilot.perform(target,fetcher,{})
                row.update({k:v for k,v in result.items() if k not in ("url","original_url","candidate")})
                if row.get("text_characters"):
                    p=PRIVATE/"articles"/(row["id"]+".json")
                    doc=json.loads(p.read_text("utf-8"))
                    doc.update(original_url=original["url"],candidate=candidate,resolver_version=VERSION)
                    p.write_bytes(pilot.jsonbytes(doc))
            else:
                row["status"]="metadata_resolved_no_accessible_fulltext"
            return row
        except Exception as e:
            row["status"] = "recovery_"+(e.reason if isinstance(e,pilot.StopFetch) else type(e).__name__)
            return row
        finally:
            row["discovery_timing"] = timings
            row["access_notes"] = notes
            row["total_recovery_seconds"] = time.perf_counter()-began

    began=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(work,r) for r in targets if r["id"] not in done]
        with (OUT/"attempts.jsonl").open("a",encoding="utf-8") as f:
            for future in concurrent.futures.as_completed(futures):
                r=future.result(); latest[r['id']]=r;results=list(latest.values())
                f.write(json.dumps(r,ensure_ascii=False)+"\n");f.flush()
                if len(results)%10==0 and not retry_failed:
                    print(json.dumps({"completed":len(results),"resolved":sum(bool(x.get("candidate")) for x in results),"bodies":sum(bool(x.get("text_characters")) for x in results),"wall_seconds":round(time.perf_counter()-began,1)},ensure_ascii=False),flush=True)
    bodies=[]
    for p in sorted((PRIVATE/"articles").glob("*.json")):
        bodies.append(json.loads(p.read_text("utf-8")))
    full=b"".join(pilot.jsonbytes(d)+b"\n" for d in bodies)
    (PRIVATE/"fulltexts.jsonl.gz").write_bytes(gzip.compress(full,mtime=0))
    ledger=[{"id":r["id"],"original_url":r["original_url"],"title":r["title"],"source":r.get("source"),"date":r.get("date"),"candidate":r["candidate"],"status":r["status"],"resolver_version":VERSION} for r in results if r.get("candidate")]
    (PRIVATE/"publisher_url_ledger.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in ledger),"utf-8")
    old_requests=json.loads((OUT/'requests.json').read_text('utf-8')) if (OUT/'requests.json').exists() else []
    pilot.dump(OUT/"requests.json",old_requests+fetcher.requests)
    integrity={"unchanged":original_hashes==pilot.input_hashes(),"before":original_hashes,"after":pilot.input_hashes()}
    pilot.dump(OUT/"input_integrity.json",integrity)
    history=json.loads((OUT/'run_history.json').read_text('utf-8')) if (OUT/'run_history.json').exists() else []
    history.append({'finished_at':pilot.stamp(),'retry_failed':retry_failed,'wall_seconds':time.perf_counter()-began,'network_requests':len(fetcher.requests)})
    pilot.dump(OUT/'run_history.json',history)
    summary={"attempted_same_failed_targets":len(results),"resolved_original_identities":len(ledger),"bodies_saved":len(bodies),"candidate_complete":sum(x["status"]=="candidate_complete" for x in results),"statuses":dict(collections.Counter(x["status"] for x in results)),"wall_seconds_this_run":time.perf_counter()-began,"network_requests_this_run":len(fetcher.requests),"source_text_utf8_bytes":sum(x["text_utf8_bytes"] for x in results if x.get("text_utf8_bytes")),"jsonl_gzip_bytes":len(gzip.compress(full,mtime=0)),"original_data_unchanged":integrity["unchanged"],"translated":False,"model_requests":0,"scope":"Same 70 unresolved targets from the original fixed 100; no substitute articles; not a new full-population success-rate estimate."}
    pilot.dump(OUT/"summary.json",summary)
    cols=["id","source","title","date","status","text_characters","original_url","publisher_homepage","publisher_url","fulltext_url","resolution_seconds","total_recovery_seconds"]
    with (OUT/"attempts.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows({k:r.get(k) for k in cols} for r in results)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument('--retry-failed',action='store_true')
    args=parser.parse_args()
    main(retry_failed=args.retry_failed)

#!/usr/bin/env python3
# Copy of deploy/pipeline/grenn_daily_digest.py (branch cop31-redesign), used by .github/workflows/daily-fulltext.yml.
"""The public part of the daily full-text run (1116更新 · GREEN_daily_news_delivery_R3, 2026-11-17).

scripts/daily_fulltext_v2.py (the original project's code) keeps, in a private folder on this server, each day's
candidates with their original text, the complete Chinese translation and, for those it could not translate, an
evidence-backed 300—500 character Chinese summary (`summary_zh`, `summary_evidence`, `summary_basis`).

Decided with the user (2026-11-17): the long summaries are shown on the site, the full texts and translations are not
(publishers' copyright — "公开可访问不等于具有全文再发布授权"). So this writes `daily_digest.json` for the site: per
article only the long summary, what it rests on, and short quotes of the original passages it cites. Nothing else
leaves the private folder; `build` refuses to write a record carrying a full-text field.

  grenn_daily_digest.py build  --state <private folder> --out <site>/data/daily_digest.json [--days 3] [--dashboard <site>/data/dashboard.json]
  grenn_daily_digest.py status --state <private folder>        # the latest day's counts (no texts)
  grenn_daily_digest.py fetch  --repo <owner/name> --out <site>/data/daily_digest.json [--ref daily-digest] [--dashboard …]

Where the run happens (user, 2026-11-17, as with the Gemini summaries before): on GitHub, with the Bailian key kept in
the repository's secrets; its checkpoint (full texts and translations) stays encrypted there. After each run the workflow
.github/workflows/daily-fulltext.yml builds this same digest (the script is copied there as scripts/daily_digest_public.py)
and force-pushes it, alone, to the branch `daily-digest`. `fetch` takes it through api.github.com (the server reaches the
API, not raw.githubusercontent.com) and re-checks every item as if it were untrusted: the same fields, links only http(s),
lengths capped. With a key on this server (/srv/grenn/secrets/daily_fulltext.env) the run happens here instead (`build`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

QUOTE_MAX = 280     # characters of an original passage shown beside the summary
DAY_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.json")
BASIS = {"fulltext", "verified_excerpt", "partial_article", "publisher_feed"}
PRIVATE = ("source_text", "fulltext_zh", "display_text_zh", "evidence_excerpt", "partial_evidence", "body")


def clean_url(url) -> str:
    """The same key as daily_fulltext_v2.clean_url (lower-case host, no tracking parameters, no fragment); '' if not a link."""
    try:
        p = urlsplit(str(url or "").strip())
    except ValueError:
        return ""
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        return ""
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((p.scheme, p.netloc.lower(), p.path, urlencode(query), ""))


def clip(text: str, limit: int = QUOTE_MAX) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def public_item(record: dict) -> dict | None:
    """The summary of one record, or None when it has none that passed the run's checks."""
    summary, claims = record.get("summary_zh"), record.get("summary_evidence")
    if not isinstance(summary, str) or not summary.strip() or not isinstance(claims, list) or not claims:
        return None
    urls = []
    for key in ("canonical_url", "publisher_url", "source_url", "url"):
        url = clean_url(record.get(key))
        if url and url not in urls:
            urls.append(url)
    if not urls:
        return None
    quotes = []
    for claim in claims:
        quote = claim.get("evidence") if isinstance(claim, dict) else None
        if isinstance(quote, str) and quote.strip():
            quote = clip(quote)
            if quote not in quotes:
                quotes.append(quote)
    basis = record.get("summary_basis")
    return {"urls": urls, "day": record.get("day"), "title_original": clip(record.get("title_original") or record.get("title") or "", 300),
            "summary_zh": summary.strip(), "summary_basis": basis if basis in BASIS else "",
            "evidence": quotes[:8], "model": record.get("summary_model") or "", "at": record.get("summary_at") or ""}


def build(state: Path, days: int = 3) -> dict:
    files = sorted((p for p in state.glob("*.json") if DAY_FILE.fullmatch(p.name)), reverse=True)[:max(1, days)]
    items, seen = [], set()
    for path in files:  # newest day first: a later summary of the same article wins
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for record in records if isinstance(records, list) else []:
            item = public_item(record) if isinstance(record, dict) else None
            if item and not seen.intersection(item["urls"]):
                seen.update(item["urls"])
                items.append(item)
    for item in items:  # belt and braces: only the fields above, never a text field of the private store
        assert not set(item).intersection(PRIVATE), "private field in the public digest"
    return {"schema": "grenn-daily-digest/1", "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "days": [p.stem for p in files], "content": "long_summary_only",
            "note": "300—500字中文长摘要，依据原文自动生成并经程序核对证据与数字；不是全文，也不是人工审核",
            "items": items}


SUMMARY_MAX = 1200  # characters: the run asks for 300—500
FETCH_MAX = 5_000_000


def adopt(digest) -> dict:
    """A digest made elsewhere (the GitHub run), re-checked item by item: only the public fields, links only http(s),
    strings only, lengths capped. A file of another schema is refused whole."""
    if not isinstance(digest, dict) or digest.get("schema") != "grenn-daily-digest/1" or not isinstance(digest.get("items"), list):
        raise ValueError("not a grenn-daily-digest/1 file")
    text = lambda value, limit: clip(value, limit) if isinstance(value, str) else ""
    items, seen = [], set()
    for entry in digest["items"]:
        if not isinstance(entry, dict):
            continue
        urls = []
        for url in entry.get("urls") if isinstance(entry.get("urls"), list) else []:
            url = clean_url(url)
            if url and url not in urls:
                urls.append(url)
        summary = entry.get("summary_zh")
        if not urls or seen.intersection(urls) or not isinstance(summary, str) or not summary.strip() or len(summary) > SUMMARY_MAX:
            continue
        quotes = [clip(q) for q in (entry.get("evidence") if isinstance(entry.get("evidence"), list) else []) if isinstance(q, str) and q.strip()]
        day = entry.get("day") if isinstance(entry.get("day"), str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry["day"]) else None
        basis = entry.get("summary_basis")
        seen.update(urls)
        items.append({"urls": urls[:6], "day": day, "title_original": text(entry.get("title_original"), 300),
                      "summary_zh": summary.strip(), "summary_basis": basis if basis in BASIS else "",
                      "evidence": quotes[:8], "model": text(entry.get("model"), 80), "at": text(entry.get("at"), 40)})
    days = [d for d in digest.get("days", []) if isinstance(d, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)][:7]         if isinstance(digest.get("days"), list) else []
    made = digest.get("generated_at") if isinstance(digest.get("generated_at"), str) else ""
    return {"schema": "grenn-daily-digest/1", "generated_at": clip(made, 40), "days": days, "content": "long_summary_only",
            "note": "300—500字中文长摘要，依据原文自动生成并经程序核对证据与数字；不是全文，也不是人工审核",
            "source": "github-actions", "items": items}


def fetch(repo: str, ref: str = "daily-digest", path: str = "daily_digest.json") -> dict:
    """The digest the GitHub run pushed, through the contents API (public repository: no token)."""
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or not re.fullmatch(r"[\w./-]+", ref) or not re.fullmatch(r"[\w./-]+", path):
        raise ValueError("bad repository, ref or path")
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}",
                                 headers={"Accept": "application/vnd.github.raw", "User-Agent": "grenn-pipeline"})
    with urllib.request.urlopen(req, timeout=60) as response:
        body = response.read(FETCH_MAX + 1)
    if len(body) > FETCH_MAX:
        raise ValueError("digest too large")
    return adopt(json.loads(body.decode("utf-8")))


def status(state: Path) -> dict:
    files = sorted(state.glob("*.status.json"))
    if not files:
        return {"status": "no run yet", "state": str(state)}
    report = json.loads(files[-1].read_text(encoding="utf-8"))
    keep = ("day", "generated_at", "total", "statuses", "target", "ready_unique", "fulltext_ready_unique", "summary_ready_unique",
            "selected", "target_met", "shortfall", "pending_total", "failure_reasons", "summary_failure_reasons", "usage")
    return {k: report.get(k) for k in keep if k in report}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--state", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--days", type=int, default=3)
    b.add_argument("--dashboard", type=Path, help="dashboard.json to note the digest in (meta.daily_digest)")
    s = sub.add_parser("status")
    s.add_argument("--state", type=Path, required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--repo", required=True)
    f.add_argument("--ref", default="daily-digest")
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--dashboard", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "status":
        print(json.dumps(status(args.state), ensure_ascii=False, indent=1))
        return 0
    digest = fetch(args.repo, args.ref) if args.cmd == "fetch" else build(args.state, args.days)
    tmp = args.out.with_name(args.out.name + ".tmp")
    tmp.write_text(json.dumps(digest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(args.out)
    if args.dashboard:
        mark(args.dashboard, args.out.name, digest)
    print(json.dumps({"daily_digest": {"items": len(digest["items"]), "days": digest["days"]}}, ensure_ascii=False))
    return 0


def mark(dashboard: Path, name: str, digest: dict) -> None:
    """Note the digest in dashboard.json's meta, so the page asks for the file only where it exists (github.io serves the
    same page without it). Only `meta.daily_digest` is added; the rest of the file is written back as it was read."""
    data = json.loads(dashboard.read_text(encoding="utf-8"))
    data.setdefault("meta", {})["daily_digest"] = {"file": name, "items": len(digest["items"]), "generated_at": digest["generated_at"]}
    tmp = dashboard.with_name(dashboard.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")  # as export-web writes it
    tmp.replace(dashboard)


if __name__ == "__main__":
    sys.exit(main())

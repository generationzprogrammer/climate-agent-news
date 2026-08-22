from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from opencc import OpenCC


ROOT = Path(__file__).resolve().parents[1]
SIMPLIFIER = OpenCC("t2s")
MALFORMED_DASHED_LATIN = __import__("re").compile(r"(?:[A-Za-z0-9]-){3,}")


def _probe(url: str) -> dict:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "ClimateText-Lab/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return {"url": url, "status": response.status, "final_url": response.url, "ok": response.status < 400}
    except urllib.error.HTTPError as exc:
        return {"url": url, "status": exc.code, "final_url": exc.url, "ok": exc.code in {401, 403, 405, 429}}
    except Exception as exc:
        return {"url": url, "status": None, "error": type(exc).__name__, "ok": False}


def validate(check_urls: bool = False) -> dict:
    seed_reports = json.loads((ROOT / "config" / "energy_reports.seed.json").read_text(encoding="utf-8"))["reports"]
    bulk_path = ROOT / "config" / "energy_reports.bulk.json"
    bulk_reports = json.loads(bulk_path.read_text(encoding="utf-8"))["reports"] if bulk_path.exists() else []
    reports = seed_reports + bulk_reports
    catalogue = json.loads((ROOT / "config" / "energy_companies.json").read_text(encoding="utf-8"))["companies"]
    wikidata_path = ROOT / "config" / "energy_companies.wikidata.json"
    wikidata_companies = json.loads(wikidata_path.read_text(encoding="utf-8"))["companies"] if wikidata_path.exists() else []
    all_companies = catalogue + wikidata_companies
    profiles = json.loads((ROOT / "config" / "energy_company_profiles.json").read_text(encoding="utf-8"))["profiles"]
    issues = []
    urls = [row.get("report_url") for row in reports]
    duplicate_urls = [url for url, count in Counter(urls).items() if url and count > 1]
    if duplicate_urls:
        issues.append({"severity": "high", "code": "duplicate_report_url", "count": len(duplicate_urls), "values": duplicate_urls})
    required = ("title_original", "title_zh", "publisher", "country_or_region", "year", "report_url")
    for index, row in enumerate(reports):
        missing = [field for field in required if not row.get(field)]
        if missing:
            issues.append({"severity": "high", "code": "report_required_field", "row": index, "missing": missing})
        current_year = datetime.now(UTC).year
        if int(row.get("year") or 0) < current_year - 3 or int(row.get("year") or 0) > current_year:
            issues.append({"severity": "medium", "code": "report_year_outside_window", "row": index, "year": row.get("year")})
        if urlparse(str(row.get("report_url") or "")).scheme != "https":
            issues.append({"severity": "high", "code": "report_url_not_https", "row": index, "url": row.get("report_url")})
        if not any("\u4e00" <= char <= "\u9fff" for char in str(row.get("title_zh") or "")):
            issues.append({"severity": "high", "code": "report_chinese_title_missing", "row": index})
        if SIMPLIFIER.convert(str(row.get("title_zh") or "")) != str(row.get("title_zh") or "") or MALFORMED_DASHED_LATIN.search(str(row.get("title_zh") or "")):
            issues.append({"severity": "high", "code": "report_display_not_clean_simplified_chinese", "row": index})

    company_ids_all = [company.get("id") for company in all_companies]
    if len(company_ids_all) != len(set(company_ids_all)):
        issues.append({"severity": "high", "code": "duplicate_company_id"})
    company_required = ("id", "name_zh", "name_en", "type", "country", "business_zh", "aliases", "website")
    for index, company in enumerate(all_companies):
        missing = [field for field in company_required if not company.get(field)]
        if missing:
            issues.append({"severity": "high", "code": "company_required_field", "row": index, "missing": missing})
        name_zh = str(company.get("name_zh") or "")
        if sum("\u4e00" <= char <= "\u9fff" for char in name_zh) < 2 or SIMPLIFIER.convert(name_zh) != name_zh:
            issues.append({"severity": "high", "code": "company_display_not_clean_simplified_chinese", "row": index, "name_zh": name_zh})

    company_ids = {company["id"] for company in catalogue}
    for profile in profiles:
        if profile.get("company_id") not in company_ids:
            issues.append({"severity": "high", "code": "orphan_company_profile", "company_id": profile.get("company_id")})
        finance = profile.get("financials") or {}
        if finance and not finance.get("source_url"):
            issues.append({"severity": "high", "code": "financial_source_missing", "company_id": profile.get("company_id")})
        for metric_name in ("revenue", "profit"):
            metric = finance.get(metric_name)
            if metric is not None and (not metric.get("unit") or metric.get("value") is None):
                issues.append({"severity": "high", "code": "financial_metric_invalid", "company_id": profile.get("company_id"), "metric": metric_name})

    probes = []
    if check_urls:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(_probe, url): url for url in sorted(set(urls)) if url}
            for future in as_completed(futures):
                probes.append(future.result())
        broken = [row for row in probes if not row["ok"]]
        if broken:
            issues.append({"severity": "medium", "code": "report_url_probe_failed", "count": len(broken), "values": broken})

    return {
        "status": "passed" if not any(issue["severity"] == "high" for issue in issues) else "failed",
        "reports": len(reports),
        "bulk_reports": len(bulk_reports),
        "report_publishers": len({row["publisher"] for row in reports}),
        "report_countries_or_regions": len({row["country_or_region"] for row in reports}),
        "company_profiles": len(profiles),
        "company_profiles_with_financials": sum(bool(row.get("financials")) for row in profiles),
        "company_directory_records": len(all_companies),
        "wikidata_company_records": len(wikidata_companies),
        "url_checks": len(probes),
        "issues": issues,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-urls", action="store_true")
    args = parser.parse_args()
    result = validate(args.check_urls)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)

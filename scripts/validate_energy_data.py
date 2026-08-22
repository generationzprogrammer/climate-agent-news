from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


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
    reports = json.loads((ROOT / "config" / "energy_reports.seed.json").read_text(encoding="utf-8"))["reports"]
    catalogue = json.loads((ROOT / "config" / "energy_companies.json").read_text(encoding="utf-8"))["companies"]
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
        if int(row.get("year") or 0) < 2023 or int(row.get("year") or 0) > 2026:
            issues.append({"severity": "medium", "code": "report_year_outside_window", "row": index, "year": row.get("year")})
        if urlparse(str(row.get("report_url") or "")).scheme != "https":
            issues.append({"severity": "high", "code": "report_url_not_https", "row": index, "url": row.get("report_url")})

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
        "report_publishers": len({row["publisher"] for row in reports}),
        "report_countries_or_regions": len({row["country_or_region"] for row in reports}),
        "company_profiles": len(profiles),
        "company_profiles_with_financials": sum(bool(row.get("financials")) for row in profiles),
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

"""Bounded weekly official-statistics discovery; additive and fail-safe.

Numbers are admitted only by explicit label/unit rules. Annual and YTD series
are different metrics. Changed values enter review, never overwrite old data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from .article_content import extract_article_text
from .collector import fetch_resource

ROOT = Path(__file__).resolve().parents[2]
UA = "GruenEnergyMonitor/1.0 (+https://generationzprogrammer.github.io/climate-agent-news/)"
RULES = [
    ("population", "年末常住人口", "万人", r"年末(?:全市|全省)?常住人口(?:总量|总数)?(?:为|达到|达)?\s*([\d,.]+)\s*万人"),
    ("gdp_current", "地区生产总值", "亿元", r"(?:实现)?地区生产总值(?:为|达到|达)?\s*([\d,.]+)\s*亿元"),
    ("power_society", "全社会用电量", "亿千瓦时", r"全社会用电量(?:为|达到|达)?\s*([\d,.]+)\s*亿千瓦时"),
    ("nev_stock", "新能源汽车保有量", "万辆", r"新能源汽车保有量(?:为|达到|达)?\s*([\d,.]+)\s*万辆"),
    ("gas_supply", "天然气供气总量", "亿立方米", r"天然气供气(?:总量|量)(?:为|达到|达)?\s*([\d,.]+)\s*亿立方米"),
    ("metro_length", "轨道交通运营里程", "公里", r"轨道交通运营里程(?:为|达到|达)?\s*([\d,.]+)\s*公里"),
]


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.href = None; self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag == "a": self.href = dict(attrs).get("href"); self.parts = []
    def handle_data(self, data):
        if self.href: self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            self.links.append((self.href, "".join(self.parts).strip())); self.href = None


class StatText(HTMLParser):
    """Statistics often have short p/td cells which news extraction omits."""
    def __init__(self):
        super().__init__(); self.ignore=0; self.parts=[]
    def handle_starttag(self, tag, attrs):
        if tag in {"script","style","nav","footer"}: self.ignore+=1
    def handle_endtag(self, tag):
        if tag in {"script","style","nav","footer"}: self.ignore=max(0,self.ignore-1)
        if tag in {"p","td","tr"}: self.parts.append(" ")
    def handle_data(self, data):
        if not self.ignore: self.parts.append(data)


def parse_release(raw: str, source: dict, url: str) -> tuple[dict, list[dict]]:
    extracted = extract_article_text(raw, limit=100_000)
    title = extracted["title"]
    parser=StatText(); parser.feed(raw)
    text=re.sub(r"\s+"," "," ".join(parser.parts))
    year_match = re.search(r"(20\d{2})年", title)
    if not year_match or re.search("预算|规划", title):
        return {}, []
    year = int(year_match[1]); now = datetime.now(timezone.utc).date()
    monthly = re.search(r"20\d{2}年1[—－–-](\d{1,2})月",title)
    if monthly:
        if not 1<=int(monthly[1])<=12 or year>now.year: return {},[]
        period=f"{year}-{int(monthly[1]):02d}"
        rules=[("nev_output_ytd","新能源汽车累计产量","万辆",r"新能源汽车(?:产量)?\s*([\d,.]+)\s*万辆")]
        if "规模以上工业" not in title: return {},[]
        frequency="year_to_date"
    else:
        if "统计公报" not in title or re.search("月|季度|上半年",title) or year>=now.year: return {},[]
        period=str(year); rules=RULES; frequency="annual"
    published = extracted.get("published_at", "")
    if not published:
        meta = re.search(r'<meta[^>]+name=["\'](?:PubDate|publishdate|pubdate)["\'][^>]+content=["\']([^"\']+)', raw, re.I)
        published = meta[1] if meta else ""
    published = published[:10] if re.match(r"20\d{2}-\d{2}-\d{2}", published) else None
    sid = "weekly_" + hashlib.sha256(url.encode()).hexdigest()[:16]
    citation = {"id": sid, "region": source["region"], "year": year, "title": title,
                "publisher": source["publisher"], "url": url, "type": "官方统计公报", "published_at": published}
    observations = []
    for metric, label, unit, pattern in rules:
        matches = list(re.finditer(pattern, text))
        # Multiple values / retrospective paragraphs are deliberately withheld.
        if len(matches) != 1: continue
        match = matches[0]
        value = float(match[1].replace(",", ""))
        if value <= 0: continue
        excerpt = text[max(0, match.start()-35):match.end()+45]
        if re.search(r"20\d{2}年", excerpt) and str(year) not in excerpt: continue
        observations.append({"id": f"W-{sid}-{metric}", "region": source["region"], "year": year,
            "period":period,"frequency":frequency,
            "metric": metric, "label": label, "value": value, "unit": unit, "category": "宏观" if metric in {"population","gdp_current"} else "能源",
            "source_id": sid, "selected": True, "status": "官方年度统计" if frequency=="annual" else "官方月度累计统计", "locator": "网页具体指标段落",
            "excerpt": excerpt, "access_date": now.isoformat(), "published_at": published,
            "extraction_method": "explicit_label_unit_rule.v1", "notes": "年度统计公报口径；原文数值，未作插值" if frequency=="annual" else "当年1月至期末累计产量；规模以上工业口径，不能与全年保有量比较"})
    return citation, observations


def merge_updates(seed: dict, previous: dict, sources: list[dict], observations: list[dict]) -> dict:
    result = json.loads(json.dumps(previous))
    result.setdefault("sources", []); result.setdefault("observations", []); result.setdefault("review_queue", [])
    existing = seed.get("observations", []) + result["observations"]
    source_ids = {s["id"] for s in result["sources"]}
    for source in sources:
        if source["id"] not in source_ids: result["sources"].append(source); source_ids.add(source["id"])
    queued = {r["id"] for r in result["review_queue"]}
    for row in observations:
        same = [r for r in existing if all(r.get(k) == row.get(k) for k in ("region", "metric", "year", "unit")) and r.get("period",str(r["year"]))==row.get("period",str(row["year"]))]
        if any(r["value"] == row["value"] for r in same): continue
        if same:
            if row["id"] not in queued:
                result["review_queue"].append({**row, "reason": "conflicting_published_value", "existing_ids": [r["id"] for r in same]}); queued.add(row["id"])
        else:
            result["observations"].append(row); existing.append(row)
    return result


def refresh(root: Path = ROOT) -> dict:
    cfg = json.loads((root / "config/bth_energy_monitor.json").read_text(encoding="utf-8"))
    seed = json.loads((root / "config/bth_energy_evidence.json").read_text(encoding="utf-8"))
    path = root / "data/bth_energy_updates.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    new_sources, new_rows, releases, health = [], [], {}, []
    checked = datetime.now(timezone.utc).isoformat()
    for source in cfg["sources"]:
        blocked, robots, seen = set(), {}, set()
        def get(url):
            parts = urlsplit(url)
            if parts.scheme != "https" or parts.hostname not in source["hosts"] or parts.hostname in blocked:
                raise ValueError("unapproved_or_blocked_host")
            if parts.hostname not in robots:
                parser = urllib.robotparser.RobotFileParser()
                try:
                    response = fetch_resource(f"https://{parts.hostname}/robots.txt", timeout=8, retries=0, accept="text/plain", user_agent=UA)
                    parser.parse(response.payload.decode("utf-8", "replace").splitlines()); robots[parts.hostname] = parser
                except Exception as error:
                    cause = error.__cause__ or error
                    if "404" in str(cause): robots[parts.hostname] = True
                    else: blocked.add(parts.hostname); raise ValueError("robots_unavailable") from error
            policy = robots[parts.hostname]
            if policy is not True and not policy.can_fetch(UA, url): raise ValueError("robots_disallowed")
            time.sleep(0.7)
            try:
                response = fetch_resource(url, timeout=10, retries=0, max_bytes=2_000_000, accept="text/html", user_agent=UA)
            except Exception as error:
                if re.search(r"\b(?:401|403|429)\b", str(error)): blocked.add(parts.hostname)
                raise
            if urlsplit(response.final_url).hostname not in source["hosts"]: raise ValueError("unexpected_redirect")
            if response.content_type not in {"text/html", "application/xhtml+xml"}: raise ValueError("not_html")
            return response.payload.decode("utf-8", "replace")
        failures, count, attempts = 0, 0, 0
        candidates = [(url, "") for url in source["seeds"]]
        try:
            listing = get(source["list_url"]); parser = Links(); parser.feed(listing)
            candidates = [(urljoin(source["list_url"], href), title) for href, title in parser.links if re.search("统计公报|规模以上工业运行|能源生产|能源消费|用电量", title)] + candidates
        except Exception: failures += 1
        for url, title in candidates:
            if url in seen or attempts >= 4: continue
            seen.add(url)
            if urlsplit(url).hostname not in source["hosts"]: continue
            if urlsplit(url).hostname in blocked: continue
            attempts += 1
            try:
                raw = get(url)
                details = extract_article_text(raw, limit=6000)
                if not details["title"] or len(details["text"]) < 120: raise ValueError("empty_release")
                count += 1
                publication = details.get("published_at", "")[:10]
                if re.match(r"20\d{2}-\d{2}-\d{2}", publication):
                    releases[url] = {"region": source["region"], "title": details["title"], "url": url, "published_at": publication, "source": source["publisher"]}
                citation, rows = parse_release(raw, source, url)
                if citation: new_sources.append(citation); new_rows.extend(rows)
            except Exception: failures += 1
        health.append({"id": source["id"], "region": source["region"], "checked_at": checked, "attempted_articles": attempts, "successful_pages": count, "failed_pages": failures,
                       "status": "checked" if count else "unavailable", "blocked_hosts": sorted(blocked)})
    result = merge_updates(seed, previous, new_sources, new_rows)
    old_releases = {r["url"]: r for r in previous.get("releases", [])}; old_releases.update(releases)
    result.update({"schema_version": 1, "last_attempt_at": checked, "cadence": "weekly", "health": health,
                   "releases": sorted(old_releases.values(), key=lambda r: r["published_at"], reverse=True)[:60]})
    if any(h["successful_pages"] for h in health): result["last_successful_check_at"] = checked
    if len(result["observations"]) > len(previous.get("observations", [])): result["last_data_change_at"] = checked
    # Atomic replacement only of this additive supplement, never the seed archive.
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp"); temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"); temp.replace(path)
    return {"active_additions": len(result["observations"]), "review_candidates": len(result["review_queue"]), "sources_checked": len(health), "sources_available": sum(h["status"] == "checked" for h in health)}


if __name__ == "__main__":
    print(json.dumps(refresh(), ensure_ascii=False))

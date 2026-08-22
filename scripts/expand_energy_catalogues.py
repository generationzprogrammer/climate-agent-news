from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORLD_BANK_API = "https://search.worldbank.org/api/v3/wds"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = "ClimateAgentNews/1.0 (https://github.com/generationzprogrammer/climate-agent-news)"
TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-en-zh"

REPORT_TERMS = (
    "energy", "electricity", "power sector", "power system", "renewable", "solar", "wind",
    "battery", "storage", "hydrogen", "oil", "petroleum", "natural gas", "lng", "coal",
    "grid", "utility", "clean cooking", "critical mineral", "geothermal", "biofuel", "nuclear",
    "decarbon", "low-carbon", "green industr", "industrial emission", "energy transition",
)
REPORT_EXCLUDES = (
    "procurement plan", "resettlement plan", "environmental and social commitment",
    "implementation status", "implementation completion", "audit report", "loan agreement",
    "financing agreement", "disbursement", "request for expressions", "contract award",
    "minutes of negotiation", "project appraisal document", "project information document",
    "disclosable version of the isr", "audited financial statement", "project introduction",
    "frequently asked questions",
)
INDUSTRIES = {
    "Q2151621": "能源综合",
    "Q862571": "石油产业",
    "Q15765380": "天然气产业",
    "Q48767813": "可再生能源",
    "Q8024050": "风电",
    "Q2316331": "电力产业",
    "Q1778629": "煤炭产业",
    "Q99529212": "电池与储能",
    "Q192127": "光伏技术",
    "Q40015": "太阳能",
    "Q80638": "水电",
    "Q96107472": "水电产业",
    "Q4072210": "核能产业",
    "Q127343": "地热能",
    "Q271153": "生物燃料",
}
INACTIVE_TERMS = ("defunct", "former company", "dissolved", "bankrupt", "was an ", "ceased operations")


def fetch_json(url: str, *, timeout: int = 90, retries: int = 3) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            if attempt + 1 >= retries:
                raise
            time.sleep(3 * (attempt + 1))
    return {}


def text_value(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("cdata!") or value.get("value") or "").strip()
    if isinstance(value, list):
        return "; ".join(text_value(item) for item in value if text_value(item))
    return ""


def report_relevant(title: str) -> bool:
    lowered = title.lower()
    return any(term in lowered for term in REPORT_TERMS) and not any(term in lowered for term in REPORT_EXCLUDES)


def world_bank_reports(target: int) -> list[dict]:
    cutoff = (datetime.now(UTC).date() - timedelta(days=365 * 3)).isoformat()
    records: dict[str, dict] = {}
    stop = False
    for search_term in ("energy", "electricity", "renewable energy", "power sector", "battery storage", "hydrogen"):
        for offset in range(0, 3000, 1000):
            query = urllib.parse.urlencode({
            "format": "json", "qterm": search_term, "strdate": cutoff,
            "enddate": datetime.now(UTC).date().isoformat(), "docty_exact": "Report",
            "srt": "docdt", "order": "desc",
                "rows": 1000, "os": offset,
                "fl": "display_title,docdt,docty,count,abstracts,lang,repnme,url,txturl",
            })
            payload = fetch_json(f"{WORLD_BANK_API}?{query}")
            for raw in (payload.get("documents") or {}).values():
                title = text_value(raw.get("display_title"))
                if len(title) < 12 or not report_relevant(title):
                    continue
                language = text_value(raw.get("lang"))
                if language and "english" not in language.lower():
                    continue
                published = text_value(raw.get("docdt"))[:10]
                year_match = re.match(r"(20\d{2})", published)
                if not year_match:
                    continue
                guid = text_value(raw.get("guid")) or text_value(raw.get("id"))
                profile_url = text_value(raw.get("url"))
                if profile_url.startswith("http://"):
                    profile_url = "https://" + profile_url[7:]
                report_url = text_value(raw.get("pdfurl")) or profile_url
                if not report_url.startswith("https://"):
                    continue
                key = guid or re.sub(r"\W+", "", title.lower())
                country = text_value(raw.get("count")) or "国际组织"
                records[key] = {
                "report_id": f"wb_{guid or len(records)}",
                "title_original": title,
                "title_zh": "",
                "summary_zh": "",
                "abstract_original": text_value(raw.get("abstracts"))[:1600],
                "publisher": "世界银行",
                "publisher_type": "国际组织",
                "country_or_region": country,
                "year": int(year_match.group(1)),
                "published_at": published,
                "language": "English",
                "report_url": report_url,
                "source_url": profile_url or report_url,
                "discovery_method": "world_bank_documents_api_snapshot",
                "translation_method": "local_open_model",
                "source_tier": "official_metadata",
                "access_note_zh": "世界银行正式报告页面或全文",
                }
            if len(records) >= target * 1.25:
                stop = True
                break
            if offset + 1000 >= int(payload.get("total") or 0):
                break
        if stop:
            break
    return sorted(records.values(), key=lambda row: (row["published_at"], row["title_original"]), reverse=True)[:target]


def translate_titles(records: list[dict], *, batch_size: int = 20) -> list[dict]:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(TRANSLATION_MODEL)
    model = AutoModelForSeq2SeqLM.from_pretrained(TRANSLATION_MODEL)
    model.eval()
    for start in range(0, len(records), batch_size):
        batch = records[start:start + batch_size]
        texts = [">>cmn_Hans<< " + row["title_original"] for row in batch]
        encoded = tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=160)
        with torch.inference_mode():
            generated = model.generate(**encoded, max_new_tokens=160, num_beams=3)
        translated = tokenizer.batch_decode(generated, skip_special_tokens=True)
        for row, title in zip(batch, translated):
            title = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", title).strip()
            title = title.replace("世界银行集团", "世界银行")
            if re.search(r"[\u4e00-\u9fff]", title):
                row["title_zh"] = title
    return [row for row in records if row.get("title_zh")]


def binding_value(binding: dict, name: str) -> str:
    return str((binding.get(name) or {}).get("value") or "").strip()


def wikidata_industry_companies(industry_id: str, limit: int = 320) -> list[dict]:
    query = f'''SELECT DISTINCT ?company ?nameZh ?nameEn ?descZh ?descEn ?countryZh ?countryEn ?continentZh ?continentEn ?website WHERE {{
      ?company wdt:P452 wd:{industry_id}; wdt:P17 ?country; wdt:P856 ?website.
      MINUS {{ ?company wdt:P576 ?dissolved. }}
      ?company rdfs:label ?nameEn. FILTER(LANG(?nameEn) = "en")
      OPTIONAL {{ ?company rdfs:label ?nameZh. FILTER(LANG(?nameZh) = "zh") }}
      OPTIONAL {{ ?company schema:description ?descZh. FILTER(LANG(?descZh) = "zh") }}
      OPTIONAL {{ ?company schema:description ?descEn. FILTER(LANG(?descEn) = "en") }}
      OPTIONAL {{ ?country rdfs:label ?countryZh. FILTER(LANG(?countryZh) = "zh") }}
      OPTIONAL {{ ?country rdfs:label ?countryEn. FILTER(LANG(?countryEn) = "en") }}
      OPTIONAL {{ ?country wdt:P30 ?continent.
        OPTIONAL {{ ?continent rdfs:label ?continentZh. FILTER(LANG(?continentZh) = "zh") }}
        OPTIONAL {{ ?continent rdfs:label ?continentEn. FILTER(LANG(?continentEn) = "en") }}
      }}
    }} ORDER BY ?company LIMIT {limit}'''
    url = f"{WIKIDATA_SPARQL}?" + urllib.parse.urlencode({"format": "json", "query": query})
    payload = fetch_json(url, timeout=120)
    output = []
    for binding in payload.get("results", {}).get("bindings", []):
        company_uri = binding_value(binding, "company")
        qid = company_uri.rsplit("/", 1)[-1]
        name_en = binding_value(binding, "nameEn")
        name_zh = binding_value(binding, "nameZh") or name_en
        description_en = binding_value(binding, "descEn").lower()
        if not qid.startswith("Q") or not name_en or any(term in description_en for term in INACTIVE_TERMS):
            continue
        website = binding_value(binding, "website")
        if not website.startswith(("https://", "http://")):
            continue
        output.append({
            "id": f"wikidata_{qid}",
            "name_zh": name_zh,
            "name_en": name_en,
            "type": "energy_company",
            "country": binding_value(binding, "countryZh") or binding_value(binding, "countryEn") or "未标注",
            "continent": binding_value(binding, "continentZh") or binding_value(binding, "continentEn") or "未标注",
            "lon": None,
            "lat": None,
            "business_zh": [INDUSTRIES[industry_id]],
            "aliases": list(dict.fromkeys([name_zh, name_en])),
            "website": website,
            "overview_zh": binding_value(binding, "descZh"),
            "source_url": f"https://www.wikidata.org/wiki/{qid}",
            "profile_basis_zh": "Wikidata企业、国家、行业与官网结构化字段；未把国家中心点当作企业总部",
            "data_completeness_zh": "基础档案；财务、项目与技术字段仅在官方资料可核验时补充",
        })
    return output


def wikidata_companies(target: int) -> list[dict]:
    groups: list[deque] = []
    for industry_id in INDUSTRIES:
        try:
            rows = wikidata_industry_companies(industry_id)
        except Exception as exc:
            print(json.dumps({"wikidata_industry": industry_id, "status": "skipped", "error": type(exc).__name__}))
            continue
        if rows:
            groups.append(deque(rows))
        time.sleep(2)
    output: list[dict] = []
    seen_ids: set[str] = set()
    seen_websites: set[str] = set()
    while groups and len(output) < target:
        next_groups = []
        for group in groups:
            while group:
                row = group.popleft()
                host = urllib.parse.urlparse(row["website"]).netloc.lower().removeprefix("www.")
                if row["id"] in seen_ids or (host and host in seen_websites):
                    continue
                seen_ids.add(row["id"])
                if host:
                    seen_websites.add(host)
                output.append(row)
                break
            if group:
                next_groups.append(group)
            if len(output) >= target:
                break
        groups = next_groups
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports", type=int, default=850)
    parser.add_argument("--companies", type=int, default=1200)
    parser.add_argument("--skip-translation", action="store_true")
    parser.add_argument("--skip-reports", action="store_true")
    parser.add_argument("--skip-companies", action="store_true")
    args = parser.parse_args()

    report_path = ROOT / "config" / "energy_reports.bulk.json"
    if args.skip_reports:
        reports = json.loads(report_path.read_text(encoding="utf-8")).get("reports") or []
    else:
        reports = world_bank_reports(args.reports)
        if not args.skip_translation:
            reports = translate_titles(reports)
        report_payload = {
            "schema_version": "1.0",
            "generated_at": datetime.now(UTC).isoformat(),
            "source": "World Bank Documents & Reports API",
            "source_url": "https://documents.worldbank.org/en/publication/documents-reports/api",
            "translation_model": TRANSLATION_MODEL if not args.skip_translation else None,
            "reports": reports,
        }
        report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    company_path = ROOT / "config" / "energy_companies.wikidata.json"
    if args.skip_companies:
        companies = json.loads(company_path.read_text(encoding="utf-8")).get("companies") or []
    else:
        companies = wikidata_companies(args.companies)
        company_payload = {
            "schema_version": "1.0",
            "generated_at": datetime.now(UTC).isoformat(),
            "source": "Wikidata Query Service",
            "source_url": "https://query.wikidata.org/",
            "companies": companies,
        }
        company_path.write_text(json.dumps(company_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "ok", "reports": len(reports), "companies": len(companies),
        "report_path": str(report_path), "company_path": str(company_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

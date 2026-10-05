"""Publish an explicitly reviewed selection from official CORDIS public data.

No network, no new model calls. Personal contact, address and tax fields are not
copied. A reviewed title/focus register is required; drafts cannot self-publish.
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from climate_agent.innovation_metrics import profile_metrics

SECTORS = {
    "battery": {"zh": "电池与储能", "en": "Batteries and storage"},
    "grid": {"zh": "电网与能源社区", "en": "Grids and energy communities"},
    "heat": {"zh": "热能与地热", "en": "Heat and geothermal"},
    "hydrogen": {"zh": "氢能与合成燃料", "en": "Hydrogen and synthetic fuels"},
    "industry": {"zh": "产业脱碳与生物能源", "en": "Industrial decarbonisation and bioenergy"},
    "solar": {"zh": "太阳能技术", "en": "Solar technology"},
    "wind": {"zh": "风能与海洋能源", "en": "Wind and ocean energy"},
}
TYPES = {"PRC": {"zh": "企业", "en": "Company"}, "HES": {"zh": "高校", "en": "Higher education"},
         "REC": {"zh": "研究机构", "en": "Research organisation"},
         "PUB": {"zh": "公共机构", "en": "Public body"}, "OTH": {"zh": "其他机构", "en": "Other organisation"}}


def money(value):
    if not value:
        return None
    return float(str(value).replace(",", "."))


def main():
    data = ROOT / "tmp/innovation-import/HORIZON"
    raw = {r["id"]: r for r in json.loads((data / "energy_candidates.json").read_text(encoding="utf-8"))}
    register = {"projects": {}}
    for line in (ROOT / "config/innovation_project_review.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        pid, title, *focus = line.split("|")
        if pid in register["projects"]:
            raise ValueError("Duplicate reviewed ID: " + pid)
        register["projects"][pid] = {"status": "approved", "title_zh": title,
                                    "focus_zh": focus[0] if focus else title + "。"}
    codes = {r["alpha2"]: r for r in json.loads((ROOT / "config/country_codes.json").read_text(encoding="utf-8"))["countries"]}
    audit = json.loads((data / "download_audit.json").read_text(encoding="utf-8"))
    cases, sources = [], []
    for pid, review in register["projects"].items():
        if review.get("status") != "approved":
            continue
        row = raw[pid]
        sid = "s_cordis_" + pid
        participants = []
        for org in sorted(row["participants"], key=lambda o: (o["role"] != "coordinator", o["country"], o["name"])):
            country = {"EL": "GR", "UK": "GB"}.get(org["country"], org["country"])
            if country not in codes or org["activityType"] not in TYPES:
                raise ValueError("Unresolved country/actor type: " + pid)
            participants.append({"id": org["organisationID"], "name": org["name"], "country": country,
                                 "type": org["activityType"], "role": org["role"],
                                 "eu_contribution_eur": money(org["ecContribution"])})
        counts = Counter(o["type"] for o in participants)
        countries = sorted({o["country"] for o in participants})
        coordinators = [o for o in participants if o["role"] == "coordinator"]
        if len(coordinators) != 1 or not counts["PRC"] or not counts["HES"]+counts["REC"]:
            raise ValueError("Science-industry eligibility not met: " + pid)
        coordinator = coordinators[0]
        grant, cost = money(row["ecMaxContribution"]), money(row["totalCost"])
        project = {"official_id": pid, "acronym": row["acronym"], "programme": "Horizon Europe",
                   "action": "IA" if row["fundingScheme"].endswith("-IA") else "RIA",
                   "start_date": row["startDate"][:10], "end_date": row["endDate"][:10],
                   "register_status": row["status"], "source_updated_at": row["contentUpdateDate"],
                   "eu_grant_eur": grant, "total_cost_eur": cost,
                   "eu_grant_million": grant / 1_000_000 if grant is not None else None,
                   "country_count": len(countries), "participant_count": len(participants),
                   "company_count": counts["PRC"], "research_count": counts["HES"]+counts["REC"],
                   "actor_type_count": len(counts), "actor_types": dict(counts),
                   "coordinator_type": coordinator["type"], "coordinator_country": coordinator["country"],
                   "coordinator": coordinator["name"], "topic_code": row["topics"],
                   "funding_basis": "maximum_EU_contribution_not_actual_expenditure",
                   "evidence_stage": "registered_objectives_not_verified_outcomes"}
        # The reviewed technical focus replaces awkward literal MT headings.
        focus = review["focus_zh"]
        title = review["title_zh"]
        summary_zh = (focus + f" 联合体包括{len(countries)}个国家的{len(participants)}家机构，"
                      f"其中企业{counts['PRC']}家、高校及研究机构{counts['HES']+counts['REC']}家；"
                      f"欧盟最高资助额{grant/1e6:.2f}百万欧元。")
        summary_en = row["objective"][:650]
        actors_zh = (f"由{coordinator['name']}（{codes[coordinator['country']]['name_zh']}）协调。"
                     f"登记参与方共{len(participants)}家，来自{len(countries)}个国家；其中企业{counts['PRC']}家，"
                     f"高校{counts['HES']}家、研究机构{counts['REC']}家。")
        actors_en = (f"Coordinated by {coordinator['name']} ({coordinator['country']}). "
                     f"{len(participants)} registered participants in {len(countries)} countries: "
                     f"{counts['PRC']} companies, {counts['HES']} higher-education and {counts['REC']} research organisations.")
        action_zh = "创新行动" if project["action"] == "IA" else "研究与创新行动"
        mechanism_zh = (f"Horizon Europe{action_zh}。项目期为{project['start_date']}至{project['end_date']}；"
                        f"欧盟最高资助额为{grant/1e6:.2f}百万欧元，登记总成本为{cost/1e6:.2f}百万欧元。")
        mechanism_en = (f"Horizon Europe {project['action']}; {project['start_date']} to {project['end_date']}. "
                        f"Maximum EU contribution EUR {grant/1e6:.2f} million; registered total cost EUR {cost/1e6:.2f} million.")
        institutions = ["research"]
        # A data/standard/IP tag requires explicit project objective evidence,
        # not the mere fact that an EU grant has legal terms.
        obj = row["objective"].lower()
        for key, pattern in (("data", r"data sharing|data exchange|interoperab|data space|battery passport"),
                             ("standards", r"standardisation|standardization|certification|harmonisation"),
                             ("ip", r"intellectual property|patent|licensing")):
            if re.search(pattern, obj):
                institutions.append(key)
        modes = ["joint"]
        if re.search(r"demonstrat|pilot|test.?bed", obj):
            modes.append("testbed")
        if re.search(r"manufactur|industrial|scale.up|commercial", obj):
            modes.append("translation")
        facts = {"summary": {"zh": summary_zh, "en": summary_en},
                 "actors": {"zh": actors_zh, "en": actors_en},
                 "mechanism": {"zh": mechanism_zh, "en": mechanism_en},
                 "observed": {"zh": "官方登记技术目标：" + focus,
                              "en": "Registered technical objectives: " + row["title"]}}
        case = {"id": "oi_cordis_" + pid, "kind": "project", "title": {"zh": title, "en": row["title"]},
                "countries": countries, "scope": "bilateral" if len(countries)==2 else "multilateral",
                "sector": SECTORS[row["sector_key"]], "sector_key": row["sector_key"],
                "aliases": [row["title"], title.split("：", 1)[-1]],
                "challenges": ["factor", "adaptation"] + (["governance"] if len(institutions)>1 else []),
                "modes": modes, "institutions": institutions, "factors": ["knowledge", "capital", "market"],
                "start_year": int(row["startDate"][:4]), "end_year": int(row["endDate"][:4]),
                "review_status": "structured_verified", **facts,
                # Raw MT was reviewed and rejected for publication. Preserve the
                # original objective; only explicitly compiled Chinese is public.
                "objective_excerpt": {"en": row["objective"], "zh": focus}, "project": project, "participants": participants,
                "evidence": [{"source_id": sid, "supports": ["summary", "actors", "mechanism", "observed", "project", "participants", "objective_excerpt"]}],
                "profile": profile_metrics(project, sid),
                "editorial": {"title_and_focus": "reviewed_chinese_compilation", "objective_translation": "original_plus_reviewed_technical_focus",
                              "original_language": "en"}}
        cases.append(case)
        sources.append({"id": sid, "url": "https://cordis.europa.eu/project/id/" + pid,
                        "title": row["acronym"] + " — " + row["title"], "publisher": "European Commission · CORDIS",
                        "language": "en", "published_date": None, "reviewed_at": "2026-10-05",
                        "access": "official_open_data_metadata_and_paraphrase", "source_role": "primary",
                        "bulk_url": audit["url"], "snapshot_sha256": audit["sha256"],
                        "source_updated_at": row["contentUpdateDate"], "rights_url": "https://cordis.europa.eu/about/legal"})
    result = {"schema_version": "1.0", "reviewed_at": "2026-10-05", "cases": cases, "sources": sources,
              "sector_taxonomy": SECTORS, "participant_types": TYPES,
              "provenance": {**audit, "selection": "reviewed energy title and focus; company and research participants; at least two countries",
                             "input_rows": len(raw), "published_rows": len(cases)}}
    (ROOT / "config/open_innovation_projects.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"projects": len(cases), "sectors": dict(Counter(c["sector_key"] for c in cases)),
                      "countries": len({code for c in cases for code in c["countries"]})}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Inspect official energy-related projects, preserving project/participant grain."""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tmp/innovation-import/HORIZON"
SECTORS = {
    "hydrogen": r"hydrogen|electroly[sz]|fuel cell|ammonia|power.to.x|e.fuels|synthetic fuel",
    "battery": r"batter(?:y|ies)|energy storage|lithium|sodium.ion|thermal storage|supercapacitor",
    "solar": r"photovoltaic|solar|perovskite|pv module|pv cell",
    "wind": r"wind|wave energy|ocean energy|tidal|offshore renewable",
    "grid": r"electric(?:ity|al) (?:grid|system|network)|power (?:grid|system|network)|smart grid|microgrid|electricity market|energy communit|demand.response|vehicle.to.grid",
    "heat": r"geothermal|heat pump|district heat|waste heat|heat exchang|thermal energy|heating and cooling",
    "industry": r"carbon capture|co2 capture|carbon dioxide capture|decarboni[sz]|biofuel|biomethane|biogas|biorefin|renewable fuel|sustainable aviation fuel|green steel|industrial energy|energy efficien|energy.flexib|zero.energy|positive.energy|energy.positive|zero.emission|electric vehic|clean energy|renewable energy",
}


def read_rows(name):
    with (DATA / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=";"))


def candidates():
    participants = defaultdict(dict)
    for row in read_rows("organization.csv"):
        if row["role"] not in {"coordinator", "participant", "partner"}:
            continue
        key = row["organisationID"] or (row["name"], row["country"])
        participants[row["projectID"]][key] = row
    selected = []
    for row in read_rows("project.csv"):
        title = row["title"]
        if row["startDate"][:10] > "2026-10-05" or row["status"] == "TERMINATED":
            continue
        if row["fundingScheme"] not in {"HORIZON-RIA", "HORIZON-IA", "RIA", "IA"}:
            continue
        sector = next((key for key, pattern in SECTORS.items() if re.search(pattern, title, re.I)), None)
        if not sector or re.search(r"solar wind|space weather|heliophys|photosphere|cosmic|gamma ray", title, re.I):
            continue
        orgs = list(participants[row["id"]].values())
        types = Counter(o["activityType"] for o in orgs)
        countries = sorted({o["country"] for o in orgs})
        if not types["PRC"] or not (types["HES"] + types["REC"]) or len(countries) < 2:
            continue
        if len(row["objective"].strip()) < 100:
            continue
        selected.append({**row, "sector_key": sector, "participants": orgs,
                         "participant_types": dict(types), "country_codes": countries})
    return sorted(selected, key=lambda r: (r["sector_key"], r["startDate"], r["id"]))


if __name__ == "__main__":
    rows = candidates()
    DATA.joinpath("energy_candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Eligible", len(rows), "sectors", dict(Counter(r["sector_key"] for r in rows)))
    for row in rows:
        print(row["id"], row["sector_key"], row["acronym"], "|", row["title"])

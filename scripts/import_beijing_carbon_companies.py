"""Import the official 2024 Beijing carbon-market entity lists from DOCX files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def cell_text(cell: ET.Element) -> str:
    text = "".join(node.text or "" for node in cell.findall(".//w:t", NS))
    return re.sub(r"\s+", " ", text).strip()


def read_rows(path: Path, category: str) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    records = []
    for row in root.findall(".//w:tr", NS):
        cells = [cell_text(cell) for cell in row.findall("./w:tc", NS)]
        if len(cells) != 5 or not cells[0].isdigit():
            continue
        sequence, credit_code, name, district, industry = cells
        fingerprint = f"{category}|{credit_code}|{name}"
        records.append({
            "id": hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16],
            "category": category,
            "sequence": int(sequence),
            "credit_code": credit_code,
            "name_zh": name,
            "district_zh": district,
            "industry_zh": industry,
        })
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--general", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    companies = read_rows(args.key, "key_emitter") + read_rows(args.general, "general_reporting")
    companies.sort(key=lambda row: (row["category"] != "key_emitter", row["sequence"]))
    categories = Counter(row["category"] for row in companies)
    districts = Counter(row["district_zh"] for row in companies)
    industries = Counter(row["industry_zh"] for row in companies)
    payload = {
        "meta": {
            "dataset_name_zh": "全国碳市场重点排放单位概览与北京公开明细",
            "dataset_name_en": "National ETS Overview and Beijing Public Entity Register",
            "year": 2024,
            "published_at": "2024-08-06",
            "source_zh": "北京市生态环境局、北京市统计局",
            "source_en": "Beijing Municipal Ecology and Environment Bureau and Beijing Municipal Bureau of Statistics",
            "source_page": "https://sthjj.beijing.gov.cn/bjhrb/index/xxgk69/zfxxgk43/fdzdgknr2/325924085/543475291/index.html",
            "national_source_page": "https://www.mee.gov.cn/ywgz/ydqhbh/wsqtkz/202601/t20260101_1139528.shtml",
            "coverage_zh": "全国数据为生态环境部公布的2025年重点排放单位总量与行业分布；下方可逐家检索的1291条记录为北京地方碳市场2024年公开明细。全国企业级名录由各省级生态环境主管部门分别公布，平台不以北京名单代替全国名单。",
            "coverage_en": "National figures are the Ministry of Ecology and Environment's 2025 totals by sector. The 1,291 searchable entity-level records below are Beijing's 2024 local carbon-market register. Provincial authorities publish entity-level national ETS lists separately.",
            "definitions_zh": "重点碳排放单位为年度二氧化碳直接排放量达到5000吨的单位；一般报告单位为年度综合能源消费量达到2000吨标准煤、但未达到重点碳排放单位门槛的单位。",
            "definitions_en": "Key emitters report at least 5,000 tonnes of direct annual CO2 emissions. General reporting entities consume at least 2,000 tonnes of standard coal equivalent annually but remain below the key-emitter threshold.",
        },
        "statistics": {
            "total": len(companies),
            "key_emitters": categories["key_emitter"],
            "general_reporting": categories["general_reporting"],
            "districts": len(districts),
            "industries": len(industries),
        },
        "national_statistics": {
            "year": 2025,
            "total": 3378,
            "power": 2087,
            "steel": 232,
            "cement": 962,
            "aluminium": 97
        },
        "filters": {
            "districts": [name for name, _ in sorted(districts.items(), key=lambda item: (-item[1], item[0]))],
            "industries": [name for name, _ in sorted(industries.items(), key=lambda item: (-item[1], item[0]))],
        },
        "companies": companies,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["statistics"], ensure_ascii=False))


if __name__ == "__main__":
    main()

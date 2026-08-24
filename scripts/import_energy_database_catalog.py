from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import openpyxl


CHINESE_NAMES = {
    "IEA Energy Data Centre": "国际能源署能源数据中心",
    "JODI Oil & Gas": "JODI石油与天然气数据库",
    "Statistical Review of World Energy": "世界能源统计年鉴数据库",
    "EIA Open Data": "美国能源信息署开放数据",
    "UNSD Energy Statistics Database": "联合国能源统计数据库",
    "OPEC Annual Statistical Bulletin": "欧佩克年度统计公报数据库",
    "Eurostat Energy Database": "欧盟统计局能源数据库",
    "Materials Project Battery Explorer": "Materials Project电池探索器",
    "Battery Data Hub": "美国能源部电池数据中心",
    "Battery Archive": "电池档案数据库",
    "NASA Prognostics Data Repository": "NASA预测维护数据资源库",
    "CALCE Battery Data": "CALCE电池数据集",
    "NOMAD": "NOMAD材料数据平台",
    "NAATBatt Li-ion Battery Supply Chain Database": "NAATBatt锂离子电池供应链数据库",
    "ENTSO-E Transparency Platform": "欧洲输电运营商透明度平台",
    "IRENA Data": "国际可再生能源署数据平台",
    "Open Power System Data": "开放电力系统数据平台",
    "Open Energy Data Initiative": "开放能源数据计划",
    "ENERGYDATA.INFO": "世界银行能源数据平台",
    "Global Power Plant Database": "全球电厂数据库",
    "Renewables.ninja": "可再生能源逐小时模拟平台",
    "Power Reactor Information System（PRIS）": "动力堆信息系统",
    "Advanced Reactors Information System（ARIS）": "先进反应堆信息系统",
    "Research Reactor Database（RRDB）": "研究堆数据库",
    "EXFOR": "实验核反应数据库",
    "Fusion Evaluated Nuclear Data Library（FENDL）": "聚变评价核数据库",
    "JEFF Nuclear Data Library": "JEFF核数据库",
    "ALADDIN": "原子分子与等离子体相互作用数据库",
    "International Nuclear Information System（INIS）": "国际核信息系统",
    "IEA CCUS Projects Database": "国际能源署碳捕集利用与封存项目数据库",
    "CO₂RE Database": "全球碳捕集与封存设施数据库",
    "NATCARB": "美国碳封存图谱数据库",
    "NETL CCS Database": "美国国家能源技术实验室碳捕集与封存数据库",
    "CO₂DataShare": "二氧化碳封存数据共享平台",
    "CO₂ Storage Resource Catalogue": "二氧化碳封存资源目录",
    "European CO₂ Storage Database（CO2StoP）": "欧洲二氧化碳封存数据库",
}


def import_catalog(source: Path, output: Path) -> dict:
    workbook = openpyxl.load_workbook(source, data_only=True, read_only=True)
    sheet = workbook["Sheet2"]
    rows = list(sheet.iter_rows(values_only=True))
    headers = [str(value or "").strip() for value in rows[0]]
    expected = ["领域", "数据库名称", "数据库网址", "维护机构", "核心数据", "主要用途", "数据规模/覆盖范围", "时间跨度/更新情况"]
    if headers != expected:
        raise ValueError(f"unexpected columns: {headers}")
    records = []
    for values in rows[1:]:
        row = dict(zip(headers, values, strict=True))
        url = str(row["数据库网址"] or "").strip()
        name = str(row["数据库名称"] or "").strip()
        if not name or not url.startswith("https://"):
            continue
        records.append({
            "database_id": "energy_db_" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12],
            "record_type": "能源数据库",
            "domain": str(row["领域"] or "").strip(),
            "name_zh": CHINESE_NAMES.get(name, name),
            "name_original": name,
            "database_url": url,
            "maintainer": str(row["维护机构"] or "").strip(),
            "core_data": str(row["核心数据"] or "").strip(),
            "primary_use": str(row["主要用途"] or "").strip(),
            "coverage": str(row["数据规模/覆盖范围"] or "").strip(),
            "update_note": str(row["时间跨度/更新情况"] or "").strip(),
        })
    payload = {
        "schema_version": "1.0",
        "source_file": source.name,
        "imported_on": date.today().isoformat(),
        "databases": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the reviewed energy-database workbook into the website seed catalogue.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("config/energy_databases.seed.json"))
    args = parser.parse_args()
    payload = import_catalog(args.source, args.output)
    print(json.dumps({"output": str(args.output), "records": len(payload["databases"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()

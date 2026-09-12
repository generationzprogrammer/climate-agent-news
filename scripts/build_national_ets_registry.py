"""Build the searchable national ETS entity index from reviewed public tables.

The environment ministry delegates annual list publication to provincial
authorities.  This utility merges the consolidated 2019-2020 power list
already kept by the project with the 2024-2025 provincial expansion tables.
It never invents a current status for a historic power-sector record.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup


PROVINCES = (
    "北京市", "天津市", "河北省", "山西省", "内蒙古自治区", "辽宁省", "吉林省", "黑龙江省",
    "上海市", "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省", "河南省", "湖北省",
    "湖南省", "广东省", "广西壮族自治区", "海南省", "重庆市", "四川省", "贵州省", "云南省",
    "西藏自治区", "陕西省", "甘肃省", "青海省", "宁夏回族自治区", "新疆维吾尔自治区",
)


def clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", "", str(value)).strip("—-/／")


def province_from(title: str) -> str:
    aliases = {"内蒙古": "内蒙古自治区", "广西": "广西壮族自治区", "宁夏": "宁夏回族自治区",
               "新疆": "新疆维吾尔自治区", "西藏": "西藏自治区"}
    for name in PROVINCES:
        if name in title:
            return name
    for short, name in aliases.items():
        if short in title:
            return name
    return ""


def industry_from(values: list[str]) -> str:
    text = " ".join(values)
    if re.search(r"钢铁.{0,8}(压延|短流程|铸造)|非硅酸盐水泥", text):
        return ""
    if re.search(r"发电|热电|火力发电|4411|4412", text):
        return "发电"
    if re.search(r"钢铁|炼铁|炼钢|黑色金属|3110|3120", text):
        return "钢铁"
    if re.search(r"水泥|3011", text):
        return "水泥"
    if re.search(r"铝冶炼|电解铝|有色金属|3216", text):
        return "铝冶炼"
    return ""


def table_rows(table: pd.DataFrame, province: str, source_url: str, context: str) -> list[dict]:
    rows: list[dict] = []
    for raw in table.fillna("").astype(str).values.tolist():
        values = [clean(value) for value in raw]
        uscc_index = next((i for i, value in enumerate(values) if re.fullmatch(r"[0-9A-Z]{18}", value)), None)
        if uscc_index is None or uscc_index < 1:
            continue
        name = values[uscc_index - 1]
        if len(name) < 3 or "企业名称" in name or "单位名称" in name:
            continue
        industry = industry_from(values[uscc_index + 1:] + [context])
        if not industry:
            continue
        rows.append({
            "name": name,
            "province": province,
            "industry": industry,
            "industry_code": {"发电": "44", "钢铁": "31", "水泥": "30", "铝冶炼": "32"}[industry],
            "uscc": values[uscc_index],
            "registry_year": "2025",
            "source_url": source_url,
        })
    return rows


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    posts_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else root / ".tmp_registry_posts_20260912"
    output = root / "data" / "national_carbon_market_entities.json"
    current = json.loads(output.read_text(encoding="utf-8"))
    historic_power = [row for row in current["entities"] if row.get("industry") == "发电"]
    latest: dict[tuple[str, str], dict] = {}
    source_catalog: dict[str, str] = {}
    for path in sorted(posts_dir.glob("[0-9]*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        title = re.sub(r"<[^>]+>", "", payload.get("title", {}).get("rendered", ""))
        if "2025" not in title:
            continue
        province = province_from(title)
        if not province:
            continue
        source_url = str(payload.get("link") or "")
        source_catalog[province] = source_url
        soup = BeautifulSoup(payload["content"]["rendered"], "html.parser")
        for node in soup.find_all("table"):
            previous = node.find_previous(["p", "h2", "h3", "h4", "strong"])
            context = previous.get_text(" ", strip=True) if previous else title
            # Pages normally contain both annual tables.  A shared 2024/2025
            # heading is valid; a table explicitly labelled 2024 is not.
            if "2024" in context and "2025" not in context:
                continue
            try:
                table = pd.read_html(io.StringIO(str(node)), flavor="lxml")[0]
            except (ValueError, ImportError):
                continue
            for row in table_rows(table, province, source_url, context):
                latest[(row["uscc"], row["industry"])] = row

    # Preserve distinct, traceable historic power records; latest provincial
    # rows supersede only the same credit-code/industry key.
    merged: dict[tuple[str, str], dict] = {
        (row.get("uscc", ""), row.get("industry", "")): row for row in historic_power
    }
    merged.update(latest)
    entities = sorted(merged.values(), key=lambda row: (row["province"], row["industry"], row["name"]))
    counts = {name: sum(row["industry"] == name for row in entities) for name in ("发电", "钢铁", "水泥", "铝冶炼")}
    payload = {
        "metadata": {
            "title": "全国碳排放权交易市场重点排放单位名录",
            "record_count": len(entities),
            "registry_year": "2019-2020、2025",
            "latest_registry_year": "2025",
            "official_2025_total": 3378,
            "official_2025_sector_counts": {"发电": 2087, "钢铁": 232, "水泥": 962, "铝冶炼": 97},
            "source": "生态环境部及省级生态环境主管部门公开名录",
            "source_url": "https://www.mee.gov.cn/xxgk2018/xxgk/xxgk06/202504/t20250415_1114934.html",
            "industries": list(counts),
            "industry_counts": counts,
            "province_count": len({row["province"] for row in entities}),
            "source_catalog": [{"province": key, "url": value} for key, value in sorted(source_catalog.items())],
        },
        "entities": entities,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"records": len(entities), "latest_rows": len(latest), "counts": counts,
                      "provinces": payload["metadata"]["province_count"], "sources": len(source_catalog)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

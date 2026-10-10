"""Add individually reviewed provisions; preserve all existing target IDs."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "config/bth_targets.json"
config = json.loads(path.read_text(encoding="utf-8"))
rows = [
    ("bj_windsolar_2025", "北京市", "wind_solar_capacity", "太阳能与风电总装机", "Combined solar and wind capacity", "能源供给", "Energy supply", 2025, 280, "万千瓦", "ge", "达到280万千瓦", "2.8 million kW", "全市太阳能与风电合计装机，不含其他电源", "太阳能、风电总装机容量达到280万千瓦"),
    ("bj_greenimport_2025", "北京市", "imported_green_power", "市外调入绿色电力", "Imported green electricity", "能源结构", "Energy mix", 2025, 300, "亿千瓦时", "ge", "力争达到300亿千瓦时", "Aim for 30 billion kWh", "市外调入绿色电力总量，不等于市场化交易绿电电量；原方案目标", "市外调入绿色电力规模力争达到300亿千瓦时"),
    ("bj_reheat_2025", "北京市", "renewable_heating_area", "新能源和可再生能源供暖面积", "New and renewable energy heating area", "建筑", "Buildings", 2025, 14500, "万平方米", "approx", "达到1.45亿平方米左右", "About 145 million square metres", "新能源和可再生能源供暖面积；亿平方米换算为万平方米", "新能源和可再生能源供暖面积达到1.45亿平方米左右"),
    ("bj_reheatshare_2030", "北京市", "renewable_heating_share", "新能源和可再生能源供暖面积比重", "New and renewable energy heating share", "建筑", "Buildings", 2030, 15, "%", "approx", "约为15%", "About 15%", "供暖面积比重，不是供暖能源消费比重", "新能源和可再生能源供暖面积比重约为15%"),
    ("bj_retrofit_2025", "北京市", "public_building_retrofit_area", "公共建筑节能绿色化改造面积", "Public-building efficiency retrofit area", "建筑", "Buildings", 2025, 3000, "万平方米", "ge", "力争完成3000万平方米", "Aim for 30 million square metres", "十四五时期完成的公共建筑节能绿色化改造面积", "力争完成3000万平方米公共建筑节能绿色化改造"),
    ("bj_heatpump_2025", "北京市", "new_heatpump_heating_area", "新增热泵供暖应用建筑面积", "Additional heat-pump heating area", "建筑", "Buildings", 2025, 4500, "万平方米", "ge", "新增4500万平方米", "45 million additional square metres", "十四五时期新增面积，不是累计供暖存量", "新增热泵供暖应用建筑面积4500万平方米"),
    ("bj_travel_2025", "北京市", "central_city_green_travel_share", "中心城区绿色出行比例", "Central-city green travel share", "交通", "Transport", 2025, 76.5, "%", "ge", "达到76.5%", "76.5%", "中心城区出行，不是全市交通能源消费", "中心城区绿色出行比例达到76.5%"),
    ("bj_nevstock_2025", "北京市", "nev_stock", "新能源汽车累计保有量", "New-energy vehicle stock", "交通", "Transport", 2025, 200, "万辆", "ge", "力争达到200万辆", "Aim for 2 million vehicles", "全市新能源汽车保有量，不是新车销售占比", "新能源汽车累计保有量力争达到200万辆"),
    ("bj_waste_2025", "北京市", "municipal_waste_resource_share", "生活垃圾资源化利用率", "Municipal waste resource utilisation", "循环经济", "Circular economy", 2025, 80, "%", "ge", "提升至80%", "80%", "城市生活垃圾资源化利用率，不是无害化处理率", "生活垃圾资源化利用率提升至80%"),
    ("bj_waste_2030", "北京市", "municipal_waste_resource_share", "生活垃圾资源化利用率", "Municipal waste resource utilisation", "循环经济", "Circular economy", 2030, 80, "%", "ge", "保持在80%以上", "At least 80%", "城市生活垃圾资源化利用率，不是无害化处理率", "生活垃圾资源化利用率保持在80%以上"),
    ("tj_recapacity_2025", "天津市", "renewable_power_capacity", "可再生能源电力装机", "Renewable electricity capacity", "能源供给", "Energy supply", 2025, 800, "万千瓦", "gt", "超过800万千瓦", "More than 8 million kW", "全市投产可再生能源电力装机容量", "全市投产可再生能源电力装机容量超过800万千瓦"),
    ("tj_gas_2025", "天津市", "natural_gas_consumption", "天然气消费量", "Natural gas consumption", "能源结构", "Energy mix", 2025, 145, "亿立方米", "ge", "力争提高至145亿立方米", "Aim for 14.5 billion cubic metres", "全市天然气消费量，不等于供气量；不据此推定零碳", "全市天然气消费量力争提高至145亿立方米"),
    ("tj_storage_2025", "天津市", "new_storage_capacity", "新型储能装机容量", "New-type storage capacity", "能源供给", "Energy supply", 2025, 50, "万千瓦", "ge", "力争达到50万千瓦以上", "Aim for at least 500,000 kW", "新型储能，不包括抽水蓄能", "新型储能装机容量力争达到50万千瓦以上"),
    ("tj_response_2025", "天津市", "peak_demand_response_share", "尖峰负荷响应能力", "Peak demand response capability", "能源供给", "Energy supply", 2025, 5, "%", "ge", "具备5%以上响应能力", "At least 5% capability", "本市电网尖峰负荷响应能力占比，不是已发生的削峰电量", "本市电网基本具备5％以上的尖峰负荷响应能力"),
    ("tj_retrofit_2025", "天津市", "public_building_efficiency_retrofit_area", "公共建筑能效提升改造面积", "Public-building efficiency retrofit area", "建筑", "Buildings", 2025, 150, "万平方米", "ge", "150万平方米以上", "At least 1.5 million square metres", "十四五时期实施公共建筑能效提升改造面积", "实施公共建筑能效提升改造面积150万平方米以上"),
    ("tj_buildingre_2025", "天津市", "urban_building_renewable_substitution_share", "城镇建筑可再生能源替代率", "Renewable substitution in urban buildings", "建筑", "Buildings", 2025, 8, "%", "ge", "达到8%", "8%", "城镇建筑可再生能源替代率，不是全市能源消费比重", "城镇建筑可再生能源替代率达到8％"),
    ("tj_nevsales_2025", "天津市", "nev_new_sales_share", "新能源汽车新车销售占比", "New-energy vehicle share of new sales", "交通", "Transport", 2025, 25, "%", "approx", "达到25%左右", "About 25%", "新能源汽车新车销售量占汽车新车销售总量，不是保有量占比", "新能源汽车新车销售量达到汽车新车销售总量的25％左右"),
    ("tj_nevsales_2030", "天津市", "nev_new_sales_share", "新能源汽车新车销售占比", "New-energy vehicle share of new sales", "交通", "Transport", 2030, 50, "%", "approx", "达到50%左右", "About 50%", "新能源汽车新车销售量占汽车新车销售总量，不是保有量占比", "新能源汽车新车销售量达到汽车新车销售总量的50％左右"),
    ("tj_travel_2025", "天津市", "green_travel_share", "绿色出行比例", "Green travel share", "交通", "Transport", 2025, 75, "%", "ge", "达到75%以上", "At least 75%", "天津方案中的绿色出行比例；与北京中心城区口径不直接横向比较", "绿色出行比例达到75％以上"),
    ("tj_travel_2030", "天津市", "green_travel_share", "绿色出行比例", "Green travel share", "交通", "Transport", 2030, 80, "%", "approx", "达到80%左右", "About 80%", "天津方案中的绿色出行比例；与北京中心城区口径不直接横向比较", "绿色出行比例达到80％左右"),
]
keys = ["id","region","metric","title_zh","title_en","theme_zh","theme_en","year","value","unit","comparator","wording_zh","wording_en","scope","excerpt"]
existing = {r["id"] for r in config["targets"]}
for values in rows:
    row = dict(zip(keys, values))
    if row["id"] in existing: continue
    row.update({"source_id": "bj_peak" if row["region"] == "北京市" else "tj_peak",
                "reviewed_at": "2026-10-10", "locator": "正文对应专项行动的2025年或2030年目标条款",
                "strength": "近似目标" if row["comparator"] == "approx" else "力争目标" if "力争" in row["wording_zh"] else "明确目标"})
    config["targets"].append(row)
path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"before": len(existing), "after": len(config["targets"])}))

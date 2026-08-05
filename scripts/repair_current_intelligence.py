from __future__ import annotations

import json
from pathlib import Path

from climate_agent.archive import quality_result


ROOT = Path(__file__).resolve().parents[1]

PLACE = {
    "地中海地区": {"name_zh": "地中海地区", "lon": 18.0, "lat": 36.0},
    "安第斯地区": {"name_zh": "安第斯地区", "lon": -69.0, "lat": -20.0},
    "美国": {"name_zh": "美国", "lon": -100.0, "lat": 39.0},
    "欧洲": {"name_zh": "欧洲", "lon": 10.0, "lat": 51.0},
    "非洲": {"name_zh": "非洲", "lon": 22.0, "lat": 2.0},
    "法国": {"name_zh": "法国", "lon": 2.0, "lat": 46.0},
    "伊朗": {"name_zh": "伊朗", "lon": 53.0, "lat": 32.0},
    "沙特阿拉伯": {"name_zh": "沙特阿拉伯", "lon": 45.0, "lat": 24.0},
    "英国": {"name_zh": "英国", "lon": -2.0, "lat": 54.0},
}

FIXES = {
    "article_c9a6956b6ba6facb": {
        "title_zh": "《奥德赛》登上大银幕之际，地中海也在经历自己的史诗旅程",
        "summary_zh": "联合国环境规划署借影片《奥德赛》重返影院，介绍地中海当前面临的环境威胁，以及地中海行动计划正在采取的保护措施。",
        "theme_zh": "海洋生态保护", "topics": ["海洋生态保护", "环境治理"], "places": [PLACE["地中海地区"]],
    },
    "article_ff78f0fb97528ea2": {
        "title_zh": "生活在火山之巅的高海拔小鼠如何生存？研究揭示答案",
        "summary_zh": "研究发现，安第斯叶耳鼠通过生物适应机制，在低氧、常年低于冰点的火山高海拔环境中生存。",
        "theme_zh": "极端环境适应", "topics": ["极端环境适应", "生物多样性"], "places": [PLACE["安第斯地区"]],
    },
    "article_3d06fe0312c1d3f1": {
        "title_zh": "美国上诉法院阻止特朗普政府取消数十亿美元气候赠款",
        "summary_zh": "美国联邦上诉法院叫停特朗普政府取消数十亿美元气候赠款的决定。",
        "theme_zh": "气候资金诉讼", "topics": ["气候资金", "司法裁决"], "places": [PLACE["美国"]],
    },
    "article_9d36560bb109055b": {
        "title_zh": "欧洲河流正在干涸，连锁后果严重",
        "summary_zh": "多瑙河布达佩斯段水位降至41厘米，距2018年历史低点仅8厘米；罗马尼亚河段录得1996年以来最低水位，渡轮和粮食驳船运输被迫暂停。",
        "theme_zh": "欧洲干旱", "topics": ["干旱", "水资源", "航运"], "places": [PLACE["欧洲"]],
    },
    "article_12b76e7375a965f4": {
        "title_zh": "研究预测：气候变化将重塑非洲疟疾流行版图",
        "summary_zh": "研究预测气候变化将改变非洲疟疾的地理分布范围。",
        "theme_zh": "气候与健康", "topics": ["气候与健康", "疟疾风险"], "places": [PLACE["非洲"]],
    },
    "article_13ba664a39eb5819": {
        "title_zh": "法院裁定特朗普政府冻结200亿美元“绿色银行”资金不当",
        "summary_zh": "美国联邦上诉法院裁定，环境保护署终止200亿美元“绿色银行”融资的做法不当；案件可能继续提交联邦最高法院。",
        "theme_zh": "绿色融资诉讼", "topics": ["绿色融资", "司法裁决"], "numbers": ["200亿美元"], "places": [PLACE["美国"]],
    },
    "article_5da3e3fe9175f45b": {
        "title_zh": "法国录得1900年以来最热月份：2026年7月均温24.9℃，七成地区干旱",
        "summary_zh": "法国2026年7月平均气温达到24.9℃，成为1900年以来最热月份；报道同时称全国70%的地区受到干旱影响。",
        "theme_zh": "极端高温与干旱", "topics": ["极端高温", "干旱"], "numbers": ["24.9℃", "70%"], "places": [PLACE["法国"]],
    },
    "article_6be6139614763fad": {
        "title_zh": "《2026年全球可再生能源证书市场报告》：增长动力、主要趋势及2030年前预测",
        "summary_zh": "",
        "theme_zh": "可再生能源证书", "topics": ["可再生能源证书", "市场预测"], "numbers": ["2030年"], "places": [],
    },
    "article_d12bd87d287fb861": {
        "title_zh": "调查：战争与气候危机期间，主要石油公司获利930亿美元",
        "summary_zh": "八家大型石油公司在三个月内获利超过900亿美元；伊朗冲突推高能源价格，再次引发要求油气企业为环境损害出资并支持可再生能源转型的呼声。",
        "theme_zh": "石油利润与气候责任", "topics": ["石油天然气", "气候责任", "能源价格"], "numbers": ["930亿美元", "三个月"],
        "places": [PLACE["伊朗"], PLACE["沙特阿拉伯"], PLACE["英国"]],
    },
    "article_f276f2a85355a220": {
        "title_zh": "“错失恐惧”正在削弱气候外交吗？",
        "summary_zh": "文章指出，气候大会参会人数大幅扩张，但谈判群体规模并未同比增长；政界和企业代表增加可能挤压正式谈判工作的空间。",
        "theme_zh": "气候大会治理", "topics": ["气候外交", "大会治理"], "numbers": [], "places": [],
    },
}


def main() -> None:
    path = ROOT / "data" / "news_archive.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for record in payload.get("records", []):
        fix = FIXES.get(record.get("article_id"))
        if not fix:
            continue
        record.update(fix)
        record["translation_status"] = "human_reviewed"
        record["quality"] = quality_result(record)
        molecule = record.get("molecule") or {}
        molecule["topic_atoms"] = record.get("topics") or []
        molecule["number_atoms"] = record.get("numbers") or []
        molecule["geo_atoms"] = [place["name_zh"] for place in record.get("places") or []]
        record["molecule"] = molecule
        changed += 1
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"updated": changed, "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

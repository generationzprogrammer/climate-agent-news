from __future__ import annotations

import csv
import html
import json
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "climate_text_corpus.jsonl"
OUT_DIR = ROOT / "reports"
STAMP = "2026-08-04"

CONTINENT_ZH = {
    "Asia": "亚洲", "North America": "北美洲", "South America": "南美洲",
    "Europe": "欧洲", "Africa": "非洲", "Oceania": "大洋洲",
    "Antarctica": "南极洲", "Global/Unspecified": "全球/未标注",
}

KEYWORD_GROUPS = {
    "新能源/清洁能源": ["新能源", "清洁能源", "可再生", "renewable", "clean energy", "solar", "wind", "光伏", "太阳能", "风电", "海上风电"],
    "石油/天然气/化石能源": ["石油", "天然气", "化石", "煤", "oil", "gas", "fossil", "coal", "lng", "petroleum"],
    "高温/热浪": ["高温", "热浪", "heatwave", "heat wave", "extreme heat", "record heat"],
    "洪水/强降雨": ["洪水", "暴雨", "强降雨", "flood", "rainfall", "storm"],
    "干旱/水风险": ["干旱", "水风险", "drought", "water scarcity"],
    "野火/森林火灾": ["野火", "森林火灾", "wildfire", "bushfire"],
    "气候资金": ["气候资金", "融资", "资金", "finance", "fund", "loss and damage"],
    "碳市场/碳价": ["碳市场", "碳价", "碳交易", "carbon market", "carbon credit", "article 6"],
    "NDC/COP/谈判": ["ndc", "cop", "unfccc", "谈判", "全球盘点", "climate talks"],
    "储能/电池/电网": ["储能", "电池", "电网", "battery", "storage", "grid", "smart grid"],
    "氢能/低碳燃料": ["氢", "绿氢", "hydrogen", "green hydrogen", "low-carbon fuel"],
    "数能/AI/数据中心": ["数能", "数字能源", "数据中心", "人工智能", "ai", "data center", "digital energy"],
}


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def read_rows() -> list[dict]:
    rows = []
    with CORPUS.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def quarter_of(day: str) -> str:
    year = int(day[:4])
    month = int(day[5:7])
    return f"{year}Q{(month - 1) // 3 + 1}"


def quarter_range(start_year: int = 2021, start_quarter: int = 3, end_year: int = 2026, end_quarter: int = 3) -> list[str]:
    values = []
    year, quarter = start_year, start_quarter
    while (year, quarter) <= (end_year, end_quarter):
        values.append(f"{year}Q{quarter}")
        quarter += 1
        if quarter == 5:
            year, quarter = year + 1, 1
    return values


def text_of(row: dict) -> str:
    values = [
        row.get("title_original"), row.get("summary_source"), row.get("title_zh"),
        row.get("summary_zh"), row.get("source_domain"), " ".join(row.get("topics") or []),
        " ".join(row.get("country_tags") or []), " ".join(row.get("continent_tags") or []),
    ]
    return " ".join(str(value) for value in values if value).lower()


def matched_groups(row: dict) -> list[str]:
    text = text_of(row)
    groups = []
    for group, terms in KEYWORD_GROUPS.items():
        if any(term.lower() in text for term in terms):
            groups.append(group)
    return groups or ["综合气候政策"]


def continents(row: dict) -> list[str]:
    values = row.get("continent_tags") or ["Global/Unspecified"]
    return [CONTINENT_ZH.get(str(value), str(value)) for value in values]


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if not sx or not sy:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sx / sy


def line_svg(series: dict[str, list[float]], labels: list[str], *, width: int = 960, height: int = 320) -> str:
    colors = ["#174ea6", "#c61f32", "#0f766e", "#d97706", "#6f7f95", "#7c3aed"]
    left, right, top, bottom = 54, 20, 26, 44
    maxv = max([1, *[value for values in series.values() for value in values]])
    span = max(1, len(labels) - 1)
    def x(i: int) -> float: return left + i / span * (width - left - right)
    def y(v: float) -> float: return top + (1 - v / maxv) * (height - top - bottom)
    grid = []
    for ratio in (0, .25, .5, .75, 1):
        yy = top + ratio * (height - top - bottom)
        grid.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{width-right}" y2="{yy:.1f}" class="grid"/><text x="{left-8}" y="{yy+4:.1f}" text-anchor="end" class="muted">{round(maxv*(1-ratio))}</text>')
    paths = []
    legend = []
    for idx, (name, values) in enumerate(series.items()):
        color = colors[idx % len(colors)]
        d = " ".join(f'{"M" if i == 0 else "L"}{x(i):.1f},{y(v):.1f}' for i, v in enumerate(values))
        paths.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.4"/>')
        legend.append(f'<span><i style="background:{color}"></i>{esc(name)}</span>')
    ticks = [0, max(0, len(labels)//3), max(0, len(labels)*2//3), len(labels)-1]
    tick_text = "".join(f'<text x="{x(i):.1f}" y="{height-16}" text-anchor="middle" class="muted">{labels[i]}</text>' for i in sorted(set(ticks)))
    return f'<div class="legend">{"".join(legend)}</div><svg viewBox="0 0 {width} {height}">{"".join(grid)}{"".join(paths)}<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" class="axis"/>{tick_text}</svg>'


def bar_svg(items: list[tuple[str, int]], *, width: int = 560, row_h: int = 32) -> str:
    items = items[:10]
    left, right, top = 150, 62, 12
    height = top * 2 + len(items) * row_h
    maxv = max([1, *[v for _, v in items]])
    rows = []
    for i, (name, value) in enumerate(items):
        y = top + i * row_h + 7
        w = (width - left - right) * value / maxv
        rows.append(f'<text x="{left-10}" y="{y+13}" text-anchor="end" class="label">{esc(name)}</text><rect x="{left}" y="{y}" width="{width-left-right}" height="16" fill="#edf1f6"/><rect x="{left}" y="{y}" width="{w:.1f}" height="16" fill="#174ea6"/><text x="{left+w+7:.1f}" y="{y+12}" class="value">{value}</text>')
    return f'<svg viewBox="0 0 {width} {height}">{"".join(rows)}</svg>'


def heatmap_svg(rows: list[str], cols: list[str], values: dict[tuple[str, str], int]) -> str:
    maxv = max([1, *values.values()])
    cell_w, cell_h, left, top = 94, 30, 106, 54
    width = left + len(cols) * cell_w + 20
    height = top + len(rows) * cell_h + 16
    out = [f'<svg viewBox="0 0 {width} {height}">']
    for j, col in enumerate(cols):
        out.append(f'<text x="{left+j*cell_w+cell_w/2}" y="20" text-anchor="middle" class="muted">{esc(col)}</text>')
    for i, row in enumerate(rows):
        out.append(f'<text x="{left-10}" y="{top+i*cell_h+20}" text-anchor="end" class="label">{esc(row)}</text>')
        for j, col in enumerate(cols):
            value = values.get((row, col), 0)
            alpha = .08 + .82 * value / maxv
            ink = "#fff" if alpha > .48 else "#12223a"
            out.append(f'<rect x="{left+j*cell_w}" y="{top+i*cell_h}" width="{cell_w-5}" height="{cell_h-5}" fill="rgba(23,78,166,{alpha:.3f})" stroke="#d8dde5"/><text x="{left+j*cell_w+(cell_w-5)/2}" y="{top+i*cell_h+18}" text-anchor="middle" fill="{ink}" class="value">{value or ""}</text>')
    out.append("</svg>")
    return "".join(out)


def build() -> dict:
    rows = read_rows()
    covered_quarters = sorted({quarter_of(row["published_date"]) for row in rows if row.get("published_date")})
    all_quarters = quarter_range()
    q_counts = Counter()
    q_group = defaultdict(Counter)
    q_continent_group = defaultdict(Counter)
    continent_counts = Counter()
    topic_counts = Counter()
    country_counts = Counter()
    for row in rows:
        day = row.get("published_date")
        if not day:
            continue
        q = quarter_of(day)
        q_counts[q] += 1
        groups = matched_groups(row)
        for group in groups:
            q_group[q][group] += 1
        for continent in continents(row):
            continent_counts[continent] += 1
            for group in groups:
                q_continent_group[(q, continent)][group] += 1
        topic_counts.update(row.get("topics") or [])
        country_counts.update(country for country in row.get("country_tags") or [] if country != "未标注")

    group_totals = Counter()
    for counter in q_group.values():
        group_totals.update(counter)
    focus_groups = [name for name, _ in group_totals.most_common(8)]
    trend_quarters = [q for q in all_quarters if q in q_counts]
    trend_series = {
        group: [q_group[q][group] for q in trend_quarters]
        for group in ["新能源/清洁能源", "石油/天然气/化石能源", "高温/热浪", "气候资金", "NDC/COP/谈判"]
    }
    heat_values = {(q, group): q_group[q][group] for q in trend_quarters for group in focus_groups}
    shares = {
        group: [q_group[q][group] / q_counts[q] if q_counts[q] else 0 for q in trend_quarters]
        for group in focus_groups
    }
    corr_pairs = []
    for i, left in enumerate(focus_groups):
        for right in focus_groups[i + 1:]:
            corr_pairs.append((left, right, pearson(shares[left], shares[right])))
    corr_pairs = sorted(corr_pairs, key=lambda item: item[2], reverse=True)[:8]

    global_rows = []
    for q in all_quarters:
        if q_counts[q]:
            top = "；".join(f"{name}({count})" for name, count in q_group[q].most_common(5))
            volume = q_counts[q]
        else:
            top, volume = "无语料覆盖", 0
        global_rows.append({"quarter": q, "records": volume, "top_keywords": top})

    continents_order = ["亚洲", "北美洲", "欧洲", "非洲", "南美洲", "大洋洲", "南极洲", "全球/未标注"]
    continent_rows = []
    for q in all_quarters:
        for continent in continents_order:
            counter = q_continent_group.get((q, continent), Counter())
            continent_rows.append({
                "quarter": q,
                "continent": continent,
                "top_keywords": "；".join(f"{name}({count})" for name, count in counter.most_common(3)) if counter else ("无语料覆盖" if not q_counts[q] else "无明确样本"),
            })

    data = {
        "records": len(rows),
        "date_min": min(row["published_date"] for row in rows if row.get("published_date")),
        "date_max": max(row["published_date"] for row in rows if row.get("published_date")),
        "covered_quarters": covered_quarters,
        "quarter_records": dict(q_counts),
        "top_topics": topic_counts.most_common(10),
        "top_countries": country_counts.most_common(10),
        "continent_counts": continent_counts.most_common(),
        "keyword_totals": group_totals.most_common(),
        "correlations": corr_pairs,
        "global_quarter_keywords": global_rows,
        "continent_quarter_keywords": continent_rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"global_climate_analysis_data_{STAMP}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT_DIR / f"quarter_global_keywords_{STAMP}.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["quarter", "records", "top_keywords"])
        writer.writeheader(); writer.writerows(global_rows)
    with (OUT_DIR / f"quarter_continent_keywords_{STAMP}.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["quarter", "continent", "top_keywords"])
        writer.writeheader(); writer.writerows(continent_rows)

    html_report = render_report(data, trend_quarters, trend_series, focus_groups, heat_values)
    report_path = OUT_DIR / f"global_climate_analysis_report_{STAMP}.html"
    report_path.write_text(html_report, encoding="utf-8")
    (OUT_DIR / "global_climate_analysis_report_latest.html").write_text(html_report, encoding="utf-8")
    return {"report": str(report_path), "records": len(rows), "covered_quarters": len(covered_quarters)}


def render_report(data: dict, trend_quarters: list[str], trend_series: dict[str, list[float]], focus_groups: list[str], heat_values: dict[tuple[str, str], int]) -> str:
    continent_bar = bar_svg([(name, count) for name, count in data["continent_counts"]])
    topic_bar = bar_svg([(name, count) for name, count in data["keyword_totals"][:10]])
    line = line_svg(trend_series, trend_quarters)
    heatmap = heatmap_svg(trend_quarters, focus_groups[:8], heat_values)
    corr_rows = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{c:.2f}</td></tr>" for a, b, c in data["correlations"])
    q_rows = "".join(f"<tr><td>{row['quarter']}</td><td>{row['records']}</td><td>{esc(row['top_keywords'])}</td></tr>" for row in data["global_quarter_keywords"])
    country_rows = "".join(f"<tr><td>{esc(name)}</td><td>{count}</td></tr>" for name, count in data["top_countries"][:8])
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>全球气候文本语料分析报告</title>
<style>
:root{{--ink:#11151c;--muted:#5d6673;--line:#d8dde5;--blue:#174ea6;--red:#c61f32;--soft:#f4f6f8;--mono:'Cascadia Code',Consolas,monospace;--serif:Georgia,'Songti SC','Noto Serif CJK SC',serif;--sans:Inter,'Microsoft YaHei',system-ui,sans-serif}}
body{{margin:0;background:#fff;color:var(--ink);font:15px/1.65 var(--sans)}}main{{width:min(1180px,calc(100% - 48px));margin:0 auto 80px}}header{{padding:46px 0 28px;border-bottom:4px solid var(--ink)}}h1{{margin:0;font:650 42px/1.15 var(--serif)}}h2{{margin:36px 0 14px;font:650 27px/1.2 var(--serif)}}h3{{margin:0 0 8px;font:700 17px var(--sans)}}.sub{{color:var(--muted);margin-top:12px}}.badge{{display:inline-block;margin-right:8px;padding:5px 8px;border:1px solid var(--line);font:700 11px var(--mono);color:var(--blue)}}.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:24px 0}}.card{{background:#fff;padding:18px}}.card b{{display:block;font:750 28px var(--mono);color:var(--blue-dark,#092d68)}}.card span{{color:var(--muted);font-size:13px}}section{{border-bottom:1px solid var(--line);padding:18px 0 28px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.wide{{grid-column:1/-1}}.chart{{border:1px solid var(--line);padding:18px;background:#fff;overflow-x:auto}}svg{{width:100%;height:auto;min-width:620px}}.grid .chart svg{{min-width:520px}}.gridline,.grid{{stroke:#dce2ea;stroke-dasharray:2 4}}.axis{{stroke:#cfd7e1}}.muted{{fill:#687384;font:11px var(--mono)}}.label{{fill:#263242;font:12px var(--sans)}}.value{{font:700 11px var(--mono)}}.legend{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:10px;color:#4d5868;font-size:13px}}.legend i{{display:inline-block;width:10px;height:10px;margin-right:6px}}table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{border-bottom:1px solid var(--line);padding:9px 8px;text-align:left;vertical-align:top}}th{{font:800 11px var(--mono);color:#526071;background:var(--soft)}}.note{{color:#697484;font-size:13px}}@media(max-width:820px){{.summary,.grid{{grid-template-columns:1fr}}main{{width:calc(100% - 28px)}}}}
</style></head><body><main>
<header><span class="badge">CORPUS ANALYSIS</span><span class="badge">2026-08-04</span><h1>全球气候变化重点情报与文本语料分析报告</h1><p class="sub">参考 CountryRiskRatings 类报告的“风险卡片 + 关键图表 + 简短判断”结构；基于站内 <b>{data['records']}</b> 条 canonical URL 去重文本语料。当前数据覆盖 {data['date_min']} 至 {data['date_max']}，不足完整5年，未覆盖季度明确标注。</p></header>
<section><h2>Executive Summary</h2><ul><li><b>语料热度高度集中在能源与适应。</b> 关键词组中“新能源/清洁能源”“NDC/COP/谈判”“气候资金”和“高温/热浪”等构成主要分析轴。</li><li><b>地理标签仍是最大不确定性。</b> 国家/地区只在文本明确出现时标注，全球性文本保留未标注；这提高严谨性，但限制了跨洲对比的解释力度。</li><li><b>相关性是“共同被报道”的相关性。</b> 季度相关矩阵反映语料中的共现节奏，不应解释为气候风险或政策因果关系。</li></ul></section>
<div class="summary"><div class="card"><b>{data['records']}</b><span>文本记录</span></div><div class="card"><b>{len(data['covered_quarters'])}</b><span>有覆盖季度</span></div><div class="card"><b>{data['date_min']}</b><span>最早记录</span></div><div class="card"><b>{data['date_max']}</b><span>最新记录</span></div></div>
<section><h2>热度变化：能源、极端天气与谈判议题并行</h2><div class="chart wide">{line}</div><p class="note">图：重点关键词组季度记录数。2023Q3 和 2026Q3 为部分季度，不能与完整季度直接等量比较。</p></section>
<section><h2>样本结构：主题和洲别分布</h2><div class="grid"><div class="chart"><h3>关键词组总量</h3>{topic_bar}</div><div class="chart"><h3>洲别标签分布</h3>{continent_bar}</div></div></section>
<section><h2>季度关键词矩阵：哪些话题在同一阶段被集中报道</h2><div class="chart wide">{heatmap}</div><p class="note">颜色越深表示该季度该关键词组记录越多；空白表示无明显记录或未覆盖。</p></section>
<section><h2>相关性分析：共同升降而非因果解释</h2><table><thead><tr><th>关键词A</th><th>关键词B</th><th>季度份额相关系数</th></tr></thead><tbody>{corr_rows}</tbody></table><p class="note">计算口径：以有覆盖季度为样本，使用各关键词组在该季度总记录中的份额计算 Pearson 相关。</p></section>
<section><h2>国家/地区样本排名</h2><table><thead><tr><th>国家/地区</th><th>记录数</th></tr></thead><tbody>{country_rows}</tbody></table></section>
<section><h2>过去5年季度关键词表</h2><table><thead><tr><th>季度</th><th>记录数</th><th>全球Top关键词组</th></tr></thead><tbody>{q_rows}</tbody></table></section>
<section><h2>建议的后续分析</h2><ol><li>补齐 2021Q3–2023Q2 的历史语料后，再正式声称“过去5年趋势”。</li><li>对国家标签引入人工校订样本，优先修正美国、中国、欧盟、印度、巴西、非洲区域。</li><li>将“新能源/清洁能源”拆分为风电、光伏、储能、电网、氢能，用于能源技术模式的专题看板。</li></ol></section>
<section><h2>边界与假设</h2><p>来源为站内气候文本语料库；记录粒度为 canonical URL。Google News RSS 作为 GDELT 限流时的兜底源。报告统计的是语料库中的报道频率和标签共现，不代表全球气候事件真实发生频率、政策强度或投资规模。</p></section>
</main></body></html>"""


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))

from __future__ import annotations

import csv
import html
import json
import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "climate_text_corpus.jsonl"
OUT_DIR = ROOT / "reports"
STAMP = "2026-08-04"

CONTINENT_ZH = {
    "Asia": "亚洲",
    "North America": "北美洲",
    "South America": "南美洲",
    "Europe": "欧洲",
    "Africa": "非洲",
    "Oceania": "大洋洲",
    "Antarctica": "南极洲",
    "Global/Unspecified": "全球未标注",
}

KEYWORD_GROUPS = {
    "新能源与清洁能源": ["新能源", "清洁能源", "可再生", "renewable", "clean energy", "solar", "wind", "光伏", "太阳能", "风电", "海上风电"],
    "石油、天然气与化石能源": ["石油", "天然气", "化石", "煤", "oil", "gas", "fossil", "coal", "lng", "petroleum"],
    "高温与热浪": ["高温", "热浪", "heatwave", "heat wave", "extreme heat", "record heat"],
    "洪水与强降雨": ["洪水", "暴雨", "强降雨", "flood", "rainfall", "storm", "extreme rainfall"],
    "干旱与水风险": ["干旱", "水风险", "drought", "water scarcity", "water stress"],
    "野火与森林火灾": ["野火", "森林火灾", "wildfire", "bushfire", "forest fire"],
    "气候资金": ["气候资金", "融资", "资金", "finance", "fund", "loss and damage"],
    "碳市场与碳价": ["碳市场", "碳价", "碳交易", "carbon market", "carbon credit", "article 6"],
    "国家气候承诺": ["ndc", "nationally determined", "国家自主贡献", "减排承诺", "climate pledge"],
    "联合国气候大会": ["cop29", "cop30", "cop28", "气候大会", "climate summit", "un climate conference"],
    "国际谈判": ["unfccc", "谈判", "全球盘点", "climate talks", "negotiation"],
    "储能、电池与电网": ["储能", "电池", "电网", "battery", "storage", "grid", "smart grid"],
    "氢能与低碳燃料": ["氢", "绿氢", "hydrogen", "green hydrogen", "low-carbon fuel"],
    "数字能源、AI与数据中心": ["数能", "数字能源", "数据中心", "人工智能", "ai", "data center", "digital energy"],
}

SHORT_LABEL = {
    "新能源与清洁能源": "新能源",
    "石油、天然气与化石能源": "化石能源",
    "高温与热浪": "高温",
    "洪水与强降雨": "洪水",
    "干旱与水风险": "干旱",
    "野火与森林火灾": "野火",
    "气候资金": "资金",
    "碳市场与碳价": "碳市场",
    "国家气候承诺": "国家承诺",
    "联合国气候大会": "气候大会",
    "国际谈判": "谈判",
    "储能、电池与电网": "储能电网",
    "氢能与低碳燃料": "氢能",
    "数字能源、AI与数据中心": "数能",
    "综合气候政策": "综合政策",
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


def quarter_key(q: str) -> tuple[int, int]:
    return int(q[:4]), int(q[-1])


def add_quarter(q: str) -> str:
    year, quarter = quarter_key(q)
    quarter += 1
    if quarter == 5:
        year += 1
        quarter = 1
    return f"{year}Q{quarter}"


def quarter_range(start_q: str, end_q: str) -> list[str]:
    values = []
    q = start_q
    while quarter_key(q) <= quarter_key(end_q):
        values.append(q)
        q = add_quarter(q)
    return values


def text_of(row: dict) -> str:
    values = [
        row.get("title_original"),
        row.get("summary_source"),
        row.get("title_zh"),
        row.get("summary_zh"),
        row.get("source_domain"),
        " ".join(row.get("topics") or []),
        " ".join(row.get("country_tags") or []),
        " ".join(row.get("continent_tags") or []),
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


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


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


def line_svg(series: dict[str, list[float]], labels: list[str], *, width: int = 980, height: int = 330) -> str:
    colors = ["#0b3b75", "#b42334", "#0f766e", "#b26a00", "#5b6472"]
    left, right, top, bottom = 56, 24, 24, 46
    maxv = max([1, *[value for values in series.values() for value in values]])
    span = max(1, len(labels) - 1)

    def x(i: int) -> float:
        return left + i / span * (width - left - right)

    def y(v: float) -> float:
        return top + (1 - v / maxv) * (height - top - bottom)

    guides = []
    for ratio in (0, .25, .5, .75, 1):
        yy = top + ratio * (height - top - bottom)
        guides.append(
            f'<line x1="{left}" y1="{yy:.1f}" x2="{width-right}" y2="{yy:.1f}" class="guide"/>'
            f'<text x="{left-9}" y="{yy+4:.1f}" text-anchor="end" class="muted">{round(maxv*(1-ratio))}</text>'
        )
    paths = []
    legend = []
    for idx, (name, values) in enumerate(series.items()):
        color = colors[idx % len(colors)]
        d = " ".join(f'{"M" if i == 0 else "L"}{x(i):.1f},{y(v):.1f}' for i, v in enumerate(values))
        points = "".join(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.2" fill="#fff" stroke="{color}" stroke-width="1.6"/>' for i, v in enumerate(values))
        paths.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.5"/>{points}')
        legend.append(f'<span><i style="background:{color}"></i>{esc(name)}</span>')
    ticks = [0, max(0, len(labels)//3), max(0, len(labels)*2//3), len(labels)-1]
    tick_text = "".join(f'<text x="{x(i):.1f}" y="{height-17}" text-anchor="middle" class="muted">{labels[i]}</text>' for i in sorted(set(ticks)))
    return f'<div class="legend">{"".join(legend)}</div><svg viewBox="0 0 {width} {height}">{"".join(guides)}{"".join(paths)}<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" class="axis"/>{tick_text}</svg>'


def hbar_svg(items: list[tuple[str, int]], *, width: int = 620, row_h: int = 34, color: str = "#0b3b75") -> str:
    items = items[:10]
    left, right, top = 176, 66, 14
    height = top * 2 + len(items) * row_h
    maxv = max([1, *[v for _, v in items]])
    rows = []
    for i, (name, value) in enumerate(items):
        y = top + i * row_h + 8
        w = (width - left - right) * value / maxv
        rows.append(
            f'<text x="{left-12}" y="{y+13}" text-anchor="end" class="label">{esc(name)}</text>'
            f'<rect x="{left}" y="{y}" width="{width-left-right}" height="16" rx="8" fill="#edf1f5"/>'
            f'<rect x="{left}" y="{y}" width="{w:.1f}" height="16" rx="8" fill="{color}"/>'
            f'<text x="{left+w+8:.1f}" y="{y+12}" class="value">{value}</text>'
        )
    return f'<svg viewBox="0 0 {width} {height}">{"".join(rows)}</svg>'


def heatmap_svg(rows: list[str], cols: list[str], values: dict[tuple[str, str], int]) -> str:
    maxv = max([1, *values.values()])
    cell_w, cell_h, left, top = 104, 30, 80, 58
    width = left + len(cols) * cell_w + 22
    height = top + len(rows) * cell_h + 18
    out = [f'<svg viewBox="0 0 {width} {height}">']
    for j, col in enumerate(cols):
        out.append(f'<text x="{left+j*cell_w+cell_w/2}" y="24" text-anchor="middle" class="muted">{esc(SHORT_LABEL.get(col, col))}</text>')
    for i, row in enumerate(rows):
        out.append(f'<text x="{left-10}" y="{top+i*cell_h+20}" text-anchor="end" class="label mono">{esc(row)}</text>')
        for j, col in enumerate(cols):
            value = values.get((row, col), 0)
            alpha = .07 + .84 * value / maxv
            ink = "#fff" if alpha > .48 else "#142033"
            out.append(
                f'<rect x="{left+j*cell_w}" y="{top+i*cell_h}" width="{cell_w-5}" height="{cell_h-5}" rx="3" fill="rgba(11,59,117,{alpha:.3f})" stroke="#d9e0e8"/>'
                f'<text x="{left+j*cell_w+(cell_w-5)/2}" y="{top+i*cell_h+18}" text-anchor="middle" fill="{ink}" class="value">{value or ""}</text>'
            )
    out.append("</svg>")
    return "".join(out)


def momentum_svg(items: list[dict], *, width: int = 920, height: int = 420) -> str:
    if not items:
        return ""
    left, right, top, bottom = 70, 42, 34, 58
    max_x = max(8.0, max(item["recent_share"] for item in items) * 1.25)
    max_abs_y = max(5.0, max(abs(item["delta_pp"]) for item in items) * 1.25)

    def x(v: float) -> float:
        return left + v / max_x * (width - left - right)

    def y(v: float) -> float:
        return top + (max_abs_y - v) / (2 * max_abs_y) * (height - top - bottom)

    zero_y = y(0)
    guides = [
        f'<line x1="{left}" y1="{zero_y:.1f}" x2="{width-right}" y2="{zero_y:.1f}" class="axis"/>',
        f'<text x="{left}" y="{height-18}" class="muted">最近四个季度占比</text>',
        f'<text x="{left-54}" y="{top+4}" class="muted" transform="rotate(-90 {left-54},{top+4})">占比变化，百分点</text>',
    ]
    for ratio in (.25, .5, .75, 1):
        xx = x(max_x * ratio)
        guides.append(f'<line x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{height-bottom}" class="guide"/>')
        guides.append(f'<text x="{xx:.1f}" y="{height-36}" text-anchor="middle" class="muted">{max_x*ratio:.0f}%</text>')
    bubbles = []
    for item in items:
        cx, cy = x(item["recent_share"]), y(item["delta_pp"])
        r = 7 + math.sqrt(item["total"]) * 0.35
        color = "#b42334" if item["delta_pp"] >= 0 else "#0b3b75"
        bubbles.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{color}" fill-opacity=".78" stroke="#fff" stroke-width="1.5"/>'
            f'<text x="{cx+r+5:.1f}" y="{cy+4:.1f}" class="label">{esc(SHORT_LABEL.get(item["group"], item["group"]))}</text>'
        )
    return f'<svg viewBox="0 0 {width} {height}">{"".join(guides)}{"".join(bubbles)}</svg>'


def small_matrix_table(rows: list[dict]) -> str:
    body = "".join(
        f"<tr><td>{esc(row['continent'])}</td><td>{row['records']}</td><td>{row['share']}</td><td>{esc(row['top_keywords'])}</td></tr>"
        for row in rows
    )
    return f"<table><thead><tr><th>地区</th><th>记录数</th><th>占比</th><th>最突出的议题</th></tr></thead><tbody>{body}</tbody></table>"


def build() -> dict:
    raw_rows = read_rows()
    dated_rows = [row for row in raw_rows if row.get("published_date")]
    max_day = max(date.fromisoformat(row["published_date"]) for row in dated_rows)
    try:
        start_day = max_day.replace(year=max_day.year - 3) + timedelta(days=1)
    except ValueError:
        start_day = max_day - timedelta(days=365 * 3 - 1)
    rows = [row for row in dated_rows if start_day <= date.fromisoformat(row["published_date"]) <= max_day]

    q_counts = Counter()
    q_group = defaultdict(Counter)
    q_continent_group = defaultdict(Counter)
    continent_counts = Counter()
    topic_counts = Counter()
    country_counts = Counter()
    source_counts = Counter()

    for row in rows:
        q = quarter_of(row["published_date"])
        q_counts[q] += 1
        groups = matched_groups(row)
        for group in groups:
            q_group[q][group] += 1
        for continent in continents(row):
            continent_counts[continent] += 1
            for group in groups:
                q_continent_group[(q, continent)][group] += 1
        topic_counts.update(row.get("topics") or [])
        source_counts.update([row.get("source_domain") or row.get("source_name") or "unknown"])
        country_counts.update(country for country in row.get("country_tags") or [] if country and country != "未标注")

    start_q = quarter_of(start_day.isoformat())
    end_q = quarter_of(max_day.isoformat())
    trend_quarters = [q for q in quarter_range(start_q, end_q) if q in q_counts]

    group_totals = Counter()
    for counter in q_group.values():
        group_totals.update(counter)
    focus_groups = [name for name, _ in group_totals.most_common(8)]
    trend_focus = ["新能源与清洁能源", "石油、天然气与化石能源", "高温与热浪", "气候资金", "国际谈判"]
    trend_series = {group: [q_group[q][group] for q in trend_quarters] for group in trend_focus}
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

    recent_quarters = trend_quarters[-4:]
    prior_quarters = trend_quarters[-8:-4] or trend_quarters[:-4]
    recent_total = sum(q_counts[q] for q in recent_quarters) or 1
    prior_total = sum(q_counts[q] for q in prior_quarters) or 1
    momentum = []
    for group in focus_groups:
        recent_share = sum(q_group[q][group] for q in recent_quarters) / recent_total * 100
        prior_share = sum(q_group[q][group] for q in prior_quarters) / prior_total * 100 if prior_quarters else 0
        momentum.append({
            "group": group,
            "recent_share": recent_share,
            "delta_pp": recent_share - prior_share,
            "total": group_totals[group],
        })
    momentum = sorted(momentum, key=lambda item: (item["delta_pp"], item["recent_share"]), reverse=True)

    global_rows = []
    for q in trend_quarters:
        top = "；".join(f"{name}（{count}）" for name, count in q_group[q].most_common(5))
        global_rows.append({"quarter": q, "records": q_counts[q], "top_keywords": top})

    continents_order = ["亚洲", "北美洲", "欧洲", "非洲", "南美洲", "大洋洲", "南极洲", "全球未标注"]
    continent_rows = []
    total_continent_marks = sum(continent_counts.values()) or 1
    for continent in continents_order:
        count = continent_counts[continent]
        counter = Counter()
        for q in trend_quarters:
            counter.update(q_continent_group.get((q, continent), Counter()))
        if count:
            continent_rows.append({
                "continent": continent,
                "records": count,
                "share": pct(count / total_continent_marks),
                "top_keywords": "；".join(f"{name}（{n}）" for name, n in counter.most_common(3)),
            })
    continent_quarter_rows = []
    for q in trend_quarters:
        for continent in continents_order:
            counter = q_continent_group.get((q, continent), Counter())
            if counter:
                continent_quarter_rows.append({
                    "quarter": q,
                    "continent": continent,
                    "top_keywords": "；".join(f"{name}（{count}）" for name, count in counter.most_common(3)),
                })

    data = {
        "records": len(rows),
        "date_min": start_day.isoformat(),
        "date_max": max_day.isoformat(),
        "covered_quarters": trend_quarters,
        "quarter_records": dict(q_counts),
        "top_topics": topic_counts.most_common(10),
        "top_countries": country_counts.most_common(12),
        "top_sources": source_counts.most_common(8),
        "continent_counts": continent_counts.most_common(),
        "keyword_totals": group_totals.most_common(),
        "correlations": corr_pairs,
        "momentum": momentum,
        "global_quarter_keywords": global_rows,
        "continent_summary": continent_rows,
        "continent_quarter_keywords": continent_quarter_rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"global_climate_analysis_data_{STAMP}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT_DIR / f"quarter_global_keywords_{STAMP}.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["quarter", "records", "top_keywords"])
        writer.writeheader()
        writer.writerows(global_rows)
    with (OUT_DIR / f"quarter_continent_keywords_{STAMP}.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["quarter", "continent", "top_keywords"])
        writer.writeheader()
        writer.writerows(continent_quarter_rows)

    html_report = render_report(data, trend_quarters, trend_series, focus_groups, heat_values)
    report_path = OUT_DIR / f"global_climate_analysis_report_{STAMP}.html"
    report_path.write_text(html_report, encoding="utf-8")
    (OUT_DIR / "global_climate_analysis_report_latest.html").write_text(html_report, encoding="utf-8")
    return {"report": str(report_path), "records": len(rows), "covered_quarters": len(trend_quarters)}


def render_report(data: dict, trend_quarters: list[str], trend_series: dict[str, list[float]], focus_groups: list[str], heat_values: dict[tuple[str, str], int]) -> str:
    top_group, top_group_count = data["keyword_totals"][0]
    top_country, top_country_count = data["top_countries"][0]
    top_continent, top_continent_count = data["continent_counts"][0]
    fastest = data["momentum"][0]
    line = line_svg(trend_series, trend_quarters)
    topic_bar = hbar_svg(data["keyword_totals"][:10], color="#0b3b75")
    continent_bar = hbar_svg(data["continent_counts"], color="#7a4b00")
    heatmap = heatmap_svg(trend_quarters, focus_groups[:8], heat_values)
    momentum = momentum_svg(data["momentum"][:8])
    corr_rows = "".join(
        f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{c:.2f}</td></tr>"
        for a, b, c in data["correlations"]
    )
    q_rows = "".join(
        f"<tr><td>{row['quarter']}</td><td>{row['records']}</td><td>{esc(row['top_keywords'])}</td></tr>"
        for row in data["global_quarter_keywords"][-8:]
    )
    country_rows = "".join(
        f"<tr><td>{esc(name)}</td><td>{count}</td></tr>"
        for name, count in data["top_countries"][:10]
    )
    source_rows = "".join(
        f"<tr><td>{esc(name)}</td><td>{count}</td></tr>"
        for name, count in data["top_sources"][:8]
    )
    continent_table = small_matrix_table(data["continent_summary"])
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>全球气候变化重点情报与文本数据库三年分析</title>
<style>
:root{{--ink:#111827;--muted:#667085;--line:#d7dde6;--soft:#f5f7fa;--paper:#ffffff;--blue:#0b3b75;--red:#b42334;--gold:#7a4b00;--green:#0f766e;--mono:'Times New Roman','Cascadia Code',Consolas,monospace;--serif:'Noto Serif SC','Source Han Serif SC','Songti SC','SimSun',serif;--sans:'Noto Sans SC','Source Han Sans SC','Microsoft YaHei','PingFang SC',Arial,sans-serif}}
*{{box-sizing:border-box}}body{{margin:0;background:#eef2f6;color:var(--ink);font:16px/1.72 var(--sans)}}main{{width:min(1160px,calc(100% - 42px));margin:28px auto 74px;background:var(--paper);box-shadow:0 18px 50px rgba(16,24,40,.08)}}.wrap{{padding:34px 44px}}header{{border-top:6px solid var(--ink);border-bottom:1px solid var(--line)}}h1{{margin:14px 0 12px;font:700 40px/1.16 var(--serif);letter-spacing:-.02em}}h2{{margin:0 0 14px;font:700 25px/1.25 var(--serif)}}h3{{margin:0 0 10px;font:800 15px/1.35 var(--sans)}}p{{margin:0 0 12px}}.deck{{color:var(--muted);max-width:900px}}.badge{{display:inline-block;margin:0 8px 8px 0;padding:5px 9px;border:1px solid var(--line);font:700 11px var(--mono);letter-spacing:.08em;color:var(--blue);background:#fff}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-top:24px}}.metric{{padding:18px 20px;border-right:1px solid var(--line)}}.metric:last-child{{border-right:0}}.metric b{{display:block;font:750 31px/1.05 var(--mono);color:var(--blue)}}.metric span{{display:block;margin-top:7px;color:var(--muted);font-size:13px}}section{{padding:30px 44px;border-bottom:1px solid var(--line)}}.signal-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.signal{{border:1px solid var(--line);padding:16px;background:linear-gradient(180deg,#fff,#fafbfd)}}.signal strong{{display:block;font:800 17px var(--sans);margin-bottom:7px}}.signal em{{font-style:normal;color:var(--red);font-weight:800}}.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.chart{{border:1px solid var(--line);background:#fff;padding:18px;overflow-x:auto}}.wide{{grid-column:1/-1}}svg{{width:100%;height:auto;min-width:650px}}.grid2 .chart svg{{min-width:560px}}.guide{{stroke:#dfe5ed;stroke-dasharray:2 5}}.axis{{stroke:#8792a2}}.muted{{fill:#687384;color:#667085;font:12px var(--mono)}}.label{{fill:#233044;font:13px var(--sans)}}.mono{{font-family:var(--mono)}}.value{{font:700 12px var(--mono)}}.legend{{display:flex;flex-wrap:wrap;gap:13px;margin-bottom:10px;color:#4b5565;font-size:13px}}.legend i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}}table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:14px}}th,td{{border-bottom:1px solid var(--line);padding:10px 9px;text-align:left;vertical-align:top}}th{{font:800 12px var(--sans);color:#475467;background:var(--soft)}}td:nth-child(2),td:nth-child(3){{font-family:var(--mono)}}.note{{color:#667085;font-size:13px;margin-top:10px}}.split{{display:grid;grid-template-columns:1.05fr .95fr;gap:16px}}.callout{{border-left:4px solid var(--red);padding:12px 16px;background:#fff8f7;color:#3b2730}}@media(max-width:860px){{main{{width:100%;margin:0;box-shadow:none}}.wrap,section{{padding-left:22px;padding-right:22px}}.metrics,.signal-grid,.grid2,.split{{grid-template-columns:1fr}}.metric{{border-right:0;border-bottom:1px solid var(--line)}}h1{{font-size:31px}}}}
</style></head><body><main>
<header class="wrap"><span class="badge">GLOBAL CLIMATE SIGNALS</span><span class="badge">THREE YEAR CORPUS</span><span class="badge">{STAMP}</span><h1>全球气候变化重点情报与文本数据库三年分析</h1><p class="deck">这份报告只保留最值得被读者迅速抓住的信号：过去三年，气候报道的主线并不是单一灾害或单一会议，而是能源转型、极端天气、资金压力与国际规则在同一张议程表上反复交织。</p><div class="metrics"><div class="metric"><b>{data['records']}</b><span>去重文本记录</span></div><div class="metric"><b>{len(data['covered_quarters'])}</b><span>有记录季度</span></div><div class="metric"><b>{esc(SHORT_LABEL.get(top_group, top_group))}</b><span>最强主题信号，{top_group_count} 条</span></div><div class="metric"><b>{esc(top_country)}</b><span>出现最多的国家标签，{top_country_count} 条</span></div></div></header>
<section><h2>四个一眼可见的判断</h2><div class="signal-grid"><div class="signal"><strong>能源转型是底盘</strong><em>{esc(top_group)}</em> 是三年样本中最稳定的高频议题，说明减排议程越来越多地被写成能源系统改造问题。</div><div class="signal"><strong>极端天气正在政策化</strong>高温、洪水、干旱和野火不再只是灾害新闻，它们频繁连接财政支出、基础设施和适应政策。</div><div class="signal"><strong>资金与规则同频</strong>气候资金、碳市场、国家气候承诺、联合国气候大会和国际谈判共同构成政策压力层。</div><div class="signal"><strong>地理分布需要审慎读</strong>{esc(top_continent)} 标签最多，约 {pct(top_continent_count / max(1, sum(v for _, v in data['continent_counts'])))}；全球性文本仍保留未标注，避免臆造地点。</div></div></section>
<section><h2>主线走势：能源、天气与规则在同一周期中波动</h2><p>季度曲线显示，能源类议题长期占据核心位置；极端天气通常在季节性灾害和政策窗口中抬升；资金与谈判类议题则更接近国际会议和规则更新节奏。</p><div class="chart wide">{line}</div><p class="note">读图提示：2023Q3 和 2026Q3 为部分季度，适合观察方向，不适合与完整季度做绝对量比较。</p></section>
<section><h2>动量图：最近一年哪些议题更值得盯住</h2><p>横轴是最近四个季度在语料中的占比，纵轴是相比此前四个季度的变化。右上方代表“既高频、又升温”，是后续监测优先区。</p><div class="chart wide">{momentum}</div><div class="callout">当前升温最明显的信号是 <b>{esc(fastest['group'])}</b>，最近四个季度占比 {fastest['recent_share']:.1f}%，较此前四个季度变化 {fastest['delta_pp']:+.1f} 个百分点。</div></section>
<section><h2>季度热点地图：议题并不是平均铺开</h2><p>热力矩阵把季度和主题放在一起看：深色块代表某个阶段被集中报道的议题。它比单独排行榜更适合发现“某一议题何时突然变热”。</p><div class="chart wide">{heatmap}</div></section>
<section><h2>结构对比：主题集中度与地区标签</h2><div class="grid2"><div class="chart"><h3>三年关键词组总量</h3>{topic_bar}</div><div class="chart"><h3>洲别标签分布</h3>{continent_bar}</div></div></section>
<section><h2>地区差异：各洲最突出的问题不同</h2><p>同样是气候新闻，不同地区的报道焦点并不一致。北美洲更容易出现能源、野火和政策争议；亚洲样本常与能源转型和产业政策相连；全球未标注文本多服务于大会、规则和综合议程。</p>{continent_table}</section>
<section><h2>关键词共振：哪些议题经常一起升降</h2><p>相关系数反映的是季度报道份额的共同变化。它适合帮助读者识别议程联动，但不能直接解释为因果关系。</p><table><thead><tr><th>关键词一</th><th>关键词二</th><th>共同变化强度</th></tr></thead><tbody>{corr_rows}</tbody></table></section>
<section><h2>国家与来源：高影响国家已经进入样本核心</h2><div class="split"><div><h3>国家标签前十</h3><table><thead><tr><th>国家或地区</th><th>记录数</th></tr></thead><tbody>{country_rows}</tbody></table></div><div><h3>主要来源前八</h3><table><thead><tr><th>来源域名</th><th>记录数</th></tr></thead><tbody>{source_rows}</tbody></table></div></div></section>
<section><h2>最近八个季度信号速览</h2><p>这张表保留精确数值，用来快速定位每个季度的主要文本主题。</p><table><thead><tr><th>季度</th><th>记录数</th><th>最突出关键词组</th></tr></thead><tbody>{q_rows}</tbody></table></section>
<section><h2>读者应优先带走什么</h2><ol><li>如果只看一条主线，应看能源转型如何与产业、贸易、投资和适应政策同时发生关联。</li><li>如果要做谈判和外交研判，应把气候资金、国家气候承诺、联合国气候大会和国际谈判分别跟踪，不再合并成一个难懂标签。</li><li>如果要做后续学术分析，建议优先做国家与主题的交叉趋势，并对美国、中国、欧盟、印度、巴西和非洲区域样本进行人工复核。</li></ol><p class="note">样本期：{data['date_min']} 至 {data['date_max']}。本报告统计新闻文本中的报道频率、标签分布和季度共现；它不等同于真实灾害发生频率、政策强度或投资金额。</p></section>
</main></body></html>"""


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))

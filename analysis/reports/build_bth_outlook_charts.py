"""Generate reproducible figures and an evidence summary for BTH policy reports.

The charts describe the composition and timing of the collected policy corpus.
They do not score or rank real-world transition performance.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "data" / "bth_policy_archive.json"
OUT = Path(__file__).resolve().parent
FIGURES = OUT / "figures"
WINDOW_START = "2023-09-23"
PROVINCES = ("北京市", "天津市", "河北省")
COLORS = {"北京市": "#22577A", "天津市": "#2A9D8F", "河北省": "#E76F51"}
TOPICS = (
    "综合绿色转型", "碳目标与核算", "碳市场与绿色金融", "能源转型", "工业绿色化",
    "绿色建筑", "绿色交通", "循环经济", "减污降碳协同", "生态环境治理",
)


def load_records() -> list[dict]:
    payload = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    return [r for r in payload["records"] if r.get("published_at", "") >= WINDOW_START]


def setup_style() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"],
        "axes.unicode_minus": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#A8B3BD",
        "axes.labelcolor": "#263238",
        "xtick.color": "#52606D",
        "ytick.color": "#52606D",
        "text.color": "#1F2933",
        "axes.titleweight": "bold",
        "axes.titlepad": 14,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def quarter(value: str) -> str:
    year, month = int(value[:4]), int(value[5:7])
    return f"{year} Q{(month - 1) // 3 + 1}"


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(FIGURES / name, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def figure_quarterly(records: list[dict]) -> None:
    quarters = sorted({quarter(r["published_at"]) for r in records})
    values = {p: Counter(quarter(r["published_at"]) for r in records if r.get("province") == p) for p in PROVINCES}
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    x = np.arange(len(quarters))
    for p in PROVINCES:
        y = [values[p][q] for q in quarters]
        ax.plot(x, y, color=COLORS[p], linewidth=2.1, marker="o", markersize=4.5, label=p)
    ax.set_xticks(x, quarters, rotation=35, ha="right")
    ax.set_ylabel("收录政策数（条）")
    ax.set_title("政策发布节奏：季度收录量")
    ax.grid(axis="y", color="#E5E9ED", linewidth=0.8)
    ax.legend(frameon=False, ncol=3, loc="upper left")
    ax.text(0, -0.28, "注：数量反映政策发布与公开页面可得性，不代表绿色转型绩效。", transform=ax.transAxes, fontsize=8.5, color="#52606D")
    save(fig, "figure_01_quarterly.png")


def figure_topic_heatmap(records: list[dict]) -> None:
    matrix = np.zeros((len(TOPICS), len(PROVINCES)))
    for j, p in enumerate(PROVINCES):
        subset = [r for r in records if r.get("province") == p]
        denominator = max(1, len(subset))
        counts = Counter(k for r in subset for k in set(r.get("keywords", [])))
        for i, topic in enumerate(TOPICS):
            matrix[i, j] = counts[topic] * 100 / denominator
    fig, ax = plt.subplots(figsize=(7.7, 6.0))
    image = ax.imshow(matrix, cmap=mpl.colors.LinearSegmentedColormap.from_list("policy", ["#F4F7F8", "#8CC9C1", "#176B68"]), aspect="auto")
    ax.set_xticks(range(len(PROVINCES)), PROVINCES)
    ax.set_yticks(range(len(TOPICS)), TOPICS)
    ax.set_title("政策议题组合：各地收录政策中的议题占比")
    for i in range(len(TOPICS)):
        for j in range(len(PROVINCES)):
            ax.text(j, i, f"{matrix[i, j]:.0f}%", ha="center", va="center", fontsize=8.5,
                    color="white" if matrix[i, j] > 32 else "#263238")
    cbar = fig.colorbar(image, ax=ax, fraction=0.045, pad=0.04)
    cbar.set_label("占本地收录政策比例（%）")
    ax.text(0, -0.10, "注：一项政策可对应多个议题，因此各列合计可超过100%。", transform=ax.transAxes, fontsize=8.5, color="#52606D")
    save(fig, "figure_02_topic_heatmap.png")


def figure_instruments(records: list[dict]) -> None:
    top_types = [name for name, _ in Counter(r.get("policy_type") or "其他" for r in records).most_common(7)]
    fig, axes = plt.subplots(1, 3, figsize=(11.0, 4.5), sharey=True)
    for ax, p in zip(axes, PROVINCES):
        subset = [r for r in records if r.get("province") == p]
        counts = Counter(r.get("policy_type") or "其他" for r in subset)
        values = [counts[t] for t in top_types]
        ax.barh(top_types[::-1], values[::-1], color=COLORS[p], alpha=0.9)
        ax.set_title(p)
        ax.grid(axis="x", color="#E5E9ED", linewidth=0.8)
        for i, value in enumerate(values[::-1]):
            ax.text(value + max(values + [1]) * 0.025, i, str(value), va="center", fontsize=8)
    fig.suptitle("政策工具形态：主要文种构成", fontsize=13, fontweight="bold", y=1.02)
    fig.text(0.5, -0.01, "注：文种由政策标题识别，用于观察政策工具形态，不评价政策强度。", ha="center", fontsize=8.5, color="#52606D")
    save(fig, "figure_03_instruments.png")


def figure_coverage(records: list[dict]) -> None:
    regions = defaultdict(Counter)
    for r in records:
        if r.get("province") in PROVINCES:
            regions[r["province"]][r.get("region") or r["province"]] += 1
    rows = []
    for p in PROVINCES:
        for region, count in regions[p].most_common(8):
            rows.append((p, region, count))
    labels = [f"{region}" for _, region, _ in rows][::-1]
    values = [count for _, _, count in rows][::-1]
    colors = [COLORS[p] for p, _, _ in rows][::-1]
    fig, ax = plt.subplots(figsize=(9.6, 7.0))
    ax.barh(labels, values, color=colors)
    ax.set_xlabel("收录政策数（条）")
    ax.set_title("区域覆盖：各地收录量较高的行政单元")
    ax.grid(axis="x", color="#E5E9ED", linewidth=0.8)
    for i, value in enumerate(values):
        ax.text(value + max(values) * 0.01, i, str(value), va="center", fontsize=8)
    handles = [mpl.patches.Patch(color=COLORS[p], label=p) for p in PROVINCES]
    ax.legend(handles=handles, frameon=False, ncol=3, loc="lower right")
    ax.text(0, -0.09, "注：仅显示各地收录量前8位行政单元；收录量受公开目录结构影响。", transform=ax.transAxes, fontsize=8.5, color="#52606D")
    save(fig, "figure_04_coverage.png")


def build_summary(records: list[dict]) -> None:
    topics = Counter(k for r in records for k in set(r.get("keywords", [])))
    region_counts = Counter((r.get("province"), r.get("region")) for r in records)
    summary = {
        "generated_at": date.today().isoformat(),
        "window_start": WINDOW_START,
        "window_end": max(r["published_at"] for r in records),
        "records": len(records),
        "unique_urls": len({r.get("url") for r in records}),
        "sources": len({r.get("source") for r in records}),
        "official_domains": len({r.get("official_domain") for r in records}),
        "regions": len({r.get("region") for r in records}),
        "province_counts": dict(Counter(r.get("province") for r in records)),
        "topic_counts": dict(topics.most_common()),
        "region_counts": [{"province": p, "region": reg, "count": n} for (p, reg), n in region_counts.most_common()],
        "quarter_counts": {
            p: dict(sorted(Counter(quarter(r["published_at"]) for r in records if r.get("province") == p).items()))
            for p in PROVINCES
        },
        "representative_records": {
            p: [
                {k: r.get(k) for k in ("published_at", "title", "source", "region", "keywords", "url")}
                for r in sorted((x for x in records if x.get("province") == p), key=lambda x: x["published_at"], reverse=True)[:20]
            ] for p in PROVINCES
        },
    }
    (OUT / "bth_evidence_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    setup_style()
    records = load_records()
    figure_quarterly(records)
    figure_topic_heatmap(records)
    figure_instruments(records)
    figure_coverage(records)
    build_summary(records)
    print(json.dumps({"records": len(records), "figures": 4, "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

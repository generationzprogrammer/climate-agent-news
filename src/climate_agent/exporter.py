from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from .archive import DEFAULT_ARCHIVE_LIMIT, update_archive, validate_public_payload
from .briefing import apply_archive_windows, dashboard_payload, publishable_intelligence, render_markdown, render_weekly_markdown, weekly_report_payload
from .company_intelligence import write_company_intelligence
from .corpus_update import merge_archive_into_corpus
from .corpus_analytics import write_corpus_analytics, write_energy_corpus_analytics
from .db import Database
from .energy_view import write_energy_view
from .energy_reports import write_energy_report_database
from .pdf_brief import write_daily_brief_pdf, write_weekly_report_pdf
from .site_metrics import write_site_metrics
from .taxonomy import public_taxonomy


def _inject_cloudflare_beacon(index_path: Path, token: str) -> bool:
    """Inject only Cloudflare's public site token; never an API credential."""
    token = (token or "").strip()
    if not token:
        return False
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", token):
        raise ValueError("invalid Cloudflare Web Analytics site token format")
    html = index_path.read_text(encoding="utf-8")
    marker = "https://static.cloudflareinsights.com/beacon.min.js"
    if marker not in html:
        beacon = (
            "  <script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
            f"data-cf-beacon='{{\"token\":\"{token}\"}}'></script>\n"
        )
        html = html.replace("</body>", f"{beacon}</body>")
        index_path.write_text(html, encoding="utf-8")
    return True


def export_static_site(
    db: Database,
    static_dir: Path,
    output_dir: Path,
    *,
    archive_path: Path | None = None,
    archive_limit: int = DEFAULT_ARCHIVE_LIMIT,
) -> dict:
    """Create a host-independent static snapshot; no Python server is required."""
    payload = dashboard_payload(db)
    archive_path = archive_path or db.path.parent / "news_archive.json"
    archive = update_archive(archive_path, publishable_intelligence(db), limit=archive_limit)
    payload = apply_archive_windows(payload, archive)
    payload["archive"] = {
        "dataset_name": archive["dataset_name"],
        "updated_at": archive["updated_at"],
        "total": archive["total"],
        "limit": archive["limit"],
        "statistics": archive["statistics"],
    }
    payload["metrics"]["archive_total"] = archive["total"]
    payload["meta"]["dataset_version"] = archive["updated_at"]
    errors = validate_public_payload(payload, archive)
    if errors:
        raise ValueError("public quality gate failed: " + ", ".join(errors[:10]))
    data_dir = static_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    dashboard_path = data_dir / "dashboard.json"
    dashboard_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "news_archive.json").write_text(
        json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (data_dir / "taxonomy.json").write_text(
        json.dumps(public_taxonomy(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (data_dir / "daily_brief.md").write_text(render_markdown(payload), encoding="utf-8")
    pdf_path = write_daily_brief_pdf(payload, data_dir / "daily_brief.pdf")
    weekly_report = weekly_report_payload(archive)
    (data_dir / "weekly_report.json").write_text(json.dumps(weekly_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "weekly_report.md").write_text(render_weekly_markdown(weekly_report), encoding="utf-8")
    weekly_pdf_path = write_weekly_report_pdf(weekly_report, data_dir / "weekly_report.pdf")
    (data_dir / "subscription.json").write_text(json.dumps({
        "endpoint": os.getenv("CLIMATE_SUBSCRIBE_ENDPOINT", ""),
        "unsubscribe_endpoint": os.getenv("CLIMATE_UNSUBSCRIBE_ENDPOINT", ""),
        "contact_email": os.getenv("CLIMATE_PUBLIC_CONTACT_EMAIL", "yuan-yh21@mails.tsinghua.edu.cn"),
        "privacy_note": "订阅邮箱不写入公开源码或Git历史；请使用表单端点或GitHub Secrets保存订阅列表。",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    team = {
        "updated_at": "2026-08-16",
        "members": [
            {
                "name": "宋伟泽",
                "role": "清华大学低碳能源实验室，数据平台研究主任，助理教授（研究系列）",
                "email": "songwz@tsinghua.edu.cn",
                "research": "低碳转型情景推演理论与方法；环境系统与智能决策；零碳园区治理与政策创新；城市空间环境绩效量化评估。",
            },
            {
                "name": "袁誉杭",
                "role": "清华大学化学工程系在读博士",
                "email": "yuan-yh21@mails.tsinghua.edu.cn",
                "research": "锂电池电解液与人工智能交叉领域。",
            },
        ],
    }
    (data_dir / "team.json").write_text(json.dumps(team, ensure_ascii=False, indent=2), encoding="utf-8")
    energy_view = write_energy_view(payload, archive, data_dir, limit=archive_limit)
    company_intelligence = write_company_intelligence(
        energy_view["archive"], data_dir / "energy_companies.json"
    )
    energy_reports = write_energy_report_database(
        energy_view["archive"], db.path.parent / "energy_reports.json", data_dir / "energy_reports.json"
    )
    corpus_path = db.path.parent / "climate_text_corpus.jsonl"
    manifest_path = db.path.parent / "climate_text_corpus.manifest.json"
    corpus_merge = merge_archive_into_corpus(
        corpus_path, manifest_path, archive, limit=archive_limit
    )
    analytics = None
    if corpus_path.exists():
        analytics = write_corpus_analytics(corpus_path, data_dir / "corpus_analytics.json", manifest_path)
        write_energy_corpus_analytics(corpus_path, data_dir / "energy_corpus_analytics.json", manifest_path)
    site_metrics = write_site_metrics(corpus_path, db.path.parent / "visitor_history.json", data_dir / "site_metrics.json")
    for history_name in ("climate_text_corpus.jsonl", "climate_text_corpus.manifest.json"):
        history_path = db.path.parent / history_name
        if history_path.exists():
            shutil.copy2(history_path, data_dir / history_name)
    reports_dir = db.path.parent.parent / "reports"
    for report_name in (
        "global_climate_analysis_report_latest.html",
        "global_climate_analysis_data_2026-08-04.json",
        "quarter_global_keywords_2026-08-04.csv",
        "quarter_continent_keywords_2026-08-04.csv",
    ):
        report_path = reports_dir / report_name
        if report_path.exists():
            shutil.copy2(report_path, data_dir / report_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(static_dir, output_dir, dirs_exist_ok=True)
    analytics_beacon = _inject_cloudflare_beacon(
        output_dir / "index.html",
        os.getenv("CLOUDFLARE_WEB_ANALYTICS_SITE_TOKEN", ""),
    )
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    return {
        "output": str(output_dir),
        "dashboard": str(dashboard_path),
        "articles": len(payload.get("intelligence", [])),
        "map_markers": len(payload.get("map_events", [])),
        "week_map_markers": len(payload.get("map_events_week", [])),
        "phrases": len(payload.get("phrases", [])),
        "pdf": str(pdf_path),
        "weekly_pdf": str(weekly_pdf_path),
        "archive_total": archive["total"],
        "archive_added": archive["statistics"]["added"],
        "energy_archive_total": energy_view["archive"].get("total", 0),
        "energy_companies": company_intelligence["statistics"].get("companies", 0),
        "company_intelligence": company_intelligence["statistics"].get("intelligence", 0),
        "energy_reports": energy_reports["statistics"].get("reports", 0),
        "corpus_added": corpus_merge.get("added", 0),
        "corpus_analytics_records": (analytics or {}).get("records", 0),
        "site_metrics_points": len(site_metrics.get("archive_cumulative", [])),
        "analytics_beacon": analytics_beacon,
        "quality_gate": "passed",
        "generated_at": payload["meta"]["generated_at"],
    }

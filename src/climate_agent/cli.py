from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .archive import DEFAULT_ARCHIVE_LIMIT, load_archive, validate_public_payload
from .briefing import dashboard_payload, save_brief
from .collector import fetch_feed, parse_feed
from .db import Database
from .delivery import build_push_message
from .editorial import apply_editorial_overrides
from .exporter import export_static_site
from .official_data import import_curated_unfccc, import_ndcs
from .providers import OpenAICompatibleModel, publish_email, publish_file, publish_wecom
from .sync import P0_SOURCE_IDS, sync_p0
from .translation import translate_pending
from .web import serve


ROOT = Path(__file__).resolve().parents[2]


def bootstrap(db: Database) -> tuple[int, int]:
    db.initialize()
    source_count = db.import_sources(ROOT / "config" / "sources.master.json")
    event_count = db.seed_events(ROOT / "data" / "demo_events.json")
    import_curated_unfccc(db, ROOT / "config")
    apply_editorial_overrides(db, ROOT / "config" / "editorial_overrides.json")
    return source_count, event_count


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="国际气候谈判情报台")
    cli.add_argument("--db", type=Path, default=ROOT / "data" / "climate.db")
    sub = cli.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="初始化 SQLite 并导入来源清单与演示事件")
    run = sub.add_parser("serve", help="启动本地可视化界面")
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8765)
    brief = sub.add_parser("brief", help="生成并保存 Markdown 简报")
    brief.add_argument("--output", type=Path, default=ROOT / "outputs" / "daily_brief.md")
    collect = sub.add_parser("collect", help="试运行一个已配置的 RSS/Atom 来源")
    collect.add_argument("source_id")
    collect.add_argument("--limit", type=int, default=10)
    sync = sub.add_parser("sync", help="同步 8 个 P0 RSS/API，并导入 UNFCCC/NDC 档案")
    sync.add_argument("--skip-news", action="store_true", help="不抓取 8 个 P0 新闻入口")
    sync.add_argument("--skip-ndc", action="store_true", help="不更新 NDC 版本档案")
    sync.add_argument("--cutoff-year", type=int, help="NDC 最早提交年份，默认当前年份减 10")
    sync.add_argument("--source", action="append", choices=P0_SOURCE_IDS, help="只重试指定 P0 来源，可重复使用")
    translate = sub.add_parser("translate", help="使用已配置模型编译最近新闻的中文标题与摘要")
    translate.add_argument("--limit", type=int, default=20)
    export = sub.add_parser("export-web", help="导出无需 Python 服务的静态网站")
    export.add_argument("--output", type=Path, default=ROOT / "dist")
    export.add_argument("--archive-limit", type=int, default=int(os.getenv("CLIMATE_ARCHIVE_LIMIT", str(DEFAULT_ARCHIVE_LIMIT))))
    validate = sub.add_parser("validate-publish", help="校验待发布网站的中文质量、链接与档案上限")
    validate.add_argument("--site", type=Path, default=ROOT / "dist")
    deliver = sub.add_parser("deliver", help="预览或投递每日中文情报提醒")
    deliver.add_argument("--channel", choices=("preview", "auto", "wecom", "email", "all"), default="preview")
    deliver.add_argument("--public-url", default=os.getenv("CLIMATE_PUBLIC_URL", ""))
    deliver.add_argument("--recipient", action="append", help="邮件收件人，可重复使用；未提供时读取 CLIMATE_MAIL_TO")
    deliver.add_argument("--max-items", type=int, default=3)
    deliver.add_argument("--output", type=Path, help="同时保存推送文本")
    deliver.add_argument("--snapshot", type=Path, help="读取已通过门禁的 dashboard.json，而不是重新查询数据库")
    return cli


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    db = Database(args.db)
    sources, events = bootstrap(db)
    if args.command == "init":
        print(json.dumps({"status": "ok", "sources": sources, "demo_events": events, "database": str(args.db)}, ensure_ascii=False))
    elif args.command == "serve":
        serve(db, ROOT / "static", args.host, args.port)
    elif args.command == "brief":
        brief = save_brief(db, dashboard_payload(db))
        output = publish_file(brief["markdown"], args.output)
        print(json.dumps({"status": "ok", "brief_id": brief["brief_id"], "version": brief["version"], "output": str(output)}, ensure_ascii=False))
    elif args.command == "collect":
        rows = db.rows("SELECT * FROM sources WHERE source_id=?", (args.source_id,))
        if not rows:
            raise SystemExit(f"unknown source_id: {args.source_id}")
        source = rows[0]
        if not source["machine_url"] or "{" in source["machine_url"]:
            raise SystemExit(f"source {args.source_id} has no directly callable feed URL")
        payload = fetch_feed(source["machine_url"])
        language = json.loads(source["languages_json"])[0] if json.loads(source["languages_json"]) else None
        articles = parse_feed(payload, args.source_id, language)
        print(json.dumps([article.to_dict() for article in articles[: args.limit]], ensure_ascii=False, indent=2))
    elif args.command == "sync":
        result = {"status": "ok", "official": import_curated_unfccc(db, ROOT / "config")}
        if not args.skip_news:
            result["p0"] = sync_p0(db, tuple(args.source) if args.source else P0_SOURCE_IDS)
            if result["p0"]["status"] != "ok":
                result["status"] = "partial"
        if not args.skip_ndc:
            try:
                result["ndc"] = import_ndcs(db, cutoff_year=args.cutoff_year)
            except Exception as exc:
                result["ndc"] = {"status": "failed", "error": str(exc)}
                result["status"] = "partial"
        result["editorial"] = apply_editorial_overrides(db, ROOT / "config" / "editorial_overrides.json")
        if all(os.getenv(name) for name in ("CLIMATE_MODEL_BASE_URL", "CLIMATE_MODEL_API_KEY", "CLIMATE_MODEL_NAME")):
            try:
                result["translation"] = translate_pending(db, OpenAICompatibleModel.from_env(), limit=20)
            except Exception as exc:
                result["translation"] = {"status": "failed", "error": str(exc)}
        result["web_export"] = export_static_site(
            db,
            ROOT / "static",
            ROOT / "dist",
            archive_limit=int(os.getenv("CLIMATE_ARCHIVE_LIMIT", str(DEFAULT_ARCHIVE_LIMIT))),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "translate":
        result = translate_pending(db, OpenAICompatibleModel.from_env(), limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "export-web":
        result = export_static_site(db, ROOT / "static", args.output, archive_limit=args.archive_limit)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False, indent=2))
    elif args.command == "validate-publish":
        dashboard_path = args.site / "data" / "dashboard.json"
        archive_path = args.site / "data" / "news_archive.json"
        dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
        archive = load_archive(archive_path)
        errors = validate_public_payload(dashboard, archive)
        if errors:
            print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False, indent=2))
            return 1
        print(json.dumps({
            "status": "passed",
            "archive_total": archive.get("total", 0),
            "intelligence": len(dashboard.get("intelligence", [])),
            "generated_at": dashboard.get("meta", {}).get("generated_at"),
        }, ensure_ascii=False, indent=2))
    elif args.command == "deliver":
        payload = (
            json.loads(args.snapshot.read_text(encoding="utf-8"))
            if args.snapshot else dashboard_payload(db)
        )
        message = build_push_message(payload, args.public_url, max_items=args.max_items)
        if args.output:
            publish_file(message, args.output)
        if args.channel == "preview":
            print(message)
            return 0
        sent: list[str] = []
        wecom_url = os.getenv("CLIMATE_WECOM_WEBHOOK_URL", "")
        recipients = args.recipient or [
            item.strip() for item in os.getenv("CLIMATE_MAIL_TO", "").split(",") if item.strip()
        ]
        wants_wecom = args.channel in {"wecom", "all"} or (args.channel == "auto" and bool(wecom_url))
        wants_email = args.channel in {"email", "all"} or (args.channel == "auto" and bool(recipients))
        if wants_wecom:
            if not wecom_url:
                raise SystemExit("缺少 CLIMATE_WECOM_WEBHOOK_URL")
            publish_wecom(message, wecom_url)
            sent.append("wecom")
        if wants_email:
            if not recipients:
                raise SystemExit("缺少 --recipient 或 CLIMATE_MAIL_TO")
            for recipient in recipients:
                publish_email(message, recipient, subject=f"国际气候谈判情报｜{payload['meta']['date']}")
            sent.append(f"email:{len(recipients)}")
        print(json.dumps({"status": "sent" if sent else "skipped", "channels": sent}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

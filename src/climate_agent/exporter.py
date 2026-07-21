from __future__ import annotations

import json
import shutil
from pathlib import Path

from .archive import DEFAULT_ARCHIVE_LIMIT, update_archive, validate_public_payload
from .briefing import dashboard_payload, publishable_intelligence, render_markdown
from .db import Database


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
    (data_dir / "daily_brief.md").write_text(render_markdown(payload), encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(static_dir, output_dir, dirs_exist_ok=True)
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    return {
        "output": str(output_dir),
        "dashboard": str(dashboard_path),
        "articles": len(payload.get("intelligence", [])),
        "map_markers": len(payload.get("map_events", [])),
        "phrases": len(payload.get("phrases", [])),
        "archive_total": archive["total"],
        "archive_added": archive["statistics"]["added"],
        "quality_gate": "passed",
        "generated_at": payload["meta"]["generated_at"],
    }

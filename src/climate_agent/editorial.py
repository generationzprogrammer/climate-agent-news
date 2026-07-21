from __future__ import annotations

import json
from pathlib import Path

from .db import Database


def apply_editorial_overrides(db: Database, path: Path) -> dict[str, int]:
    """Apply reviewed Chinese copy without overwriting source metadata."""
    if not path.exists():
        return {"configured": 0, "applied": 0, "missing": 0}
    items = json.loads(path.read_text(encoding="utf-8"))
    applied = 0
    with db.connect() as conn:
        for item in items:
            row = conn.execute(
                "SELECT metadata_json FROM articles WHERE article_id=?",
                (item["article_id"],),
            ).fetchone()
            if not row:
                continue
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except json.JSONDecodeError:
                metadata = {}
            metadata.update({
                "summary_zh": item["summary_zh"],
                "theme_zh": item["theme_zh"],
                "importance_zh": item["importance_zh"],
                "poster_phrase": item["poster_phrase"],
                "places": item.get("places", []),
                "translation_status": "human_reviewed",
            })
            conn.execute(
                "UPDATE articles SET title_zh=?, metadata_json=? WHERE article_id=?",
                (item["title_zh"], json.dumps(metadata, ensure_ascii=False), item["article_id"]),
            )
            applied += 1
    return {"configured": len(items), "applied": applied, "missing": len(items) - applied}

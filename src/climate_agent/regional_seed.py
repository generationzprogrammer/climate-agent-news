from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from .db import Database


SOURCE_HOSTS = {
    "CHN003": ("mee.gov.cn",),
    "CHN006": ("gov.cn",),
    "CHN007": ("nea.gov.cn",),
    "CHN008": ("scio.gov.cn",),
    "OFF014": ("science.nasa.gov",),
    "INT020": ("grist.org",),
}


def _allowed_url(source_id: str, value: str) -> bool:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        host == domain or host.endswith(f".{domain}") for domain in SOURCE_HOSTS.get(source_id, ())
    )


def import_regional_seed(db: Database, path: Path) -> dict[str, int]:
    """Import a small, human-reviewed regional catch-up set idempotently."""
    if not path.exists():
        return {"configured": 0, "accepted": 0, "rejected": 0, "new": 0, "updated": 0}
    items = json.loads(path.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    valid_rows = []
    for item in items:
        source_id = item.get("source_id", "")
        url = item.get("canonical_url", "")
        try:
            published = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=UTC)
        except (KeyError, TypeError, ValueError):
            continue
        if not _allowed_url(source_id, url) or published.year < 2016 or published > now + timedelta(days=1):
            continue
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        content_hash = hashlib.sha256(
            f"{item['title_original']}\n{item['summary_zh']}".encode("utf-8")
        ).hexdigest()
        valid_rows.append({
            "article_id": f"curated_{digest[:16]}",
            "source_id": source_id,
            "source_url": url,
            "canonical_url": url,
            "title_original": item["title_original"],
            "title_zh": item["title_zh"],
            "summary_source": None,
            "published_at_utc": published.astimezone(UTC).isoformat(),
            "language": item.get("language", "zh"),
            "rights_status": "metadata_only",
            "content_hash": content_hash,
            "fetched_at": now.isoformat(),
            "relevance_score": item.get("relevance_score", 82),
            "topics": item.get("topics", []),
            "numbers": item.get("numbers", []),
            "metadata": {
                "summary_zh": item["summary_zh"],
                "theme_zh": item["theme_zh"],
                "importance_zh": item["importance_zh"],
                "poster_phrase": item["poster_phrase"],
                "places": item.get("places", []),
                "translation_status": "human_reviewed",
                "fact_status": item.get("fact_status", "source_claim_unverified"),
                "regional_seed": "2026-07-29-human-reviewed",
            },
        })
    result = db.upsert_articles(valid_rows)
    return {
        "configured": len(items),
        "accepted": len(valid_rows),
        "rejected": len(items) - len(valid_rows),
        "new": result["new"],
        "updated": result["updated"],
    }

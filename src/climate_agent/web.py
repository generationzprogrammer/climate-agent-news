from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .briefing import dashboard_payload, save_brief
from .db import Database


class AppHandler(BaseHTTPRequestHandler):
    db: Database
    static_dir: Path
    server_version = "ClimateBriefingRoom/0.1"

    def log_message(self, fmt: str, *args) -> None:
        print(json.dumps({"level": "info", "component": "web", "message": fmt % args}, ensure_ascii=False))

    def _send_json(self, payload: dict | list, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_static(self, relative: str) -> None:
        relative = relative or "index.html"
        candidate = (self.static_dir / relative).resolve()
        if self.static_dir.resolve() not in candidate.parents and candidate != self.static_dir.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not candidate.is_file():
            candidate = self.static_dir / "index.html"
        data = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/api/dashboard":
            self._send_json(dashboard_payload(self.db))
        elif path == "/api/sources":
            rows = self.db.rows("""
                SELECT s.*,f.status AS fetch_status,f.finished_at AS last_fetched_at,
                       f.items_seen AS last_items_seen,f.error_message AS fetch_error
                FROM sources s LEFT JOIN fetch_runs f ON f.run_id=(
                  SELECT f2.run_id FROM fetch_runs f2 WHERE f2.source_id=s.source_id
                  ORDER BY f2.finished_at DESC LIMIT 1
                )
                ORDER BY s.enabled DESC,s.authority DESC,s.name
            """)
            for row in rows:
                row["languages"] = json.loads(row.pop("languages_json"))
                row["enabled"] = bool(row["enabled"])
            self._send_json(rows)
        elif path == "/api/articles":
            self._send_json(dashboard_payload(self.db)["intelligence"])
        elif path == "/api/documents":
            self._send_json(dashboard_payload(self.db)["official"])
        elif path == "/api/quality":
            self._send_json({
                "source_health": dashboard_payload(self.db)["source_health"],
                "recent_runs": self.db.rows("SELECT * FROM fetch_runs ORDER BY finished_at DESC LIMIT 40"),
            })
        elif path == "/api/briefs/latest":
            rows = self.db.rows("SELECT * FROM briefs ORDER BY created_at DESC LIMIT 1")
            self._send_json(rows[0] if rows else {})
        elif path.startswith("/api/"):
            self._send_json({"error": "not found"}, 404)
        else:
            self._send_static(path.lstrip("/"))

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/api/briefs/generate":
            brief = save_brief(self.db, dashboard_payload(self.db))
            self._send_json(brief, 201)
        else:
            self._send_json({"error": "not found"}, 404)


def serve(db: Database, static_dir: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    handler = type("ConfiguredAppHandler", (AppHandler,), {"db": db, "static_dir": static_dir})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Climate Briefing Room: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

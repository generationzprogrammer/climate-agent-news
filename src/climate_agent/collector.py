from __future__ import annotations

import email.utils
import hashlib
import html
import http.client
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Iterable

from .pipeline import normalize_url, stable_id


USER_AGENT = "ClimateBriefingRoom/0.1 (+local research; contact configured by operator)"


@dataclass(slots=True)
class FetchResponse:
    payload: bytes
    status: int
    content_type: str
    final_url: str

    @property
    def size(self) -> int:
        return len(self.payload)


@dataclass(slots=True)
class NormalizedArticle:
    article_id: str
    source_id: str
    source_url: str
    canonical_url: str
    title: str
    published_at_raw: str | None
    published_at_utc: str | None
    summary_from_source: str | None
    language: str | None
    content_hash: str
    rights_status: str = "metadata_only"
    extraction_method: str = "rss"
    parser_version: str = "rss.v1"

    def to_dict(self) -> dict:
        return asdict(self)


def _text(node: ET.Element, names: Iterable[str]) -> str | None:
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return " ".join(child.text.split())
    return None


def _date_to_utc(value: str | None) -> str | None:
    if not value:
        return None
    html_datetime = re.search(r'datetime=["\']([^"\']+)', value)
    if html_datetime:
        value = html_datetime.group(1)
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat()
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(UTC).isoformat()
        except ValueError:
            return None


def _plain_text(value: str | None, limit: int = 1200) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", html.unescape(value))
    text = " ".join(text.split())
    return text[:limit] or None


def parse_feed(payload: bytes, source_id: str, language: str | None = None) -> list[NormalizedArticle]:
    recovered = False
    try:
        root = ET.fromstring(payload)
        nodes = root.findall(".//item")
        if not nodes:
            nodes = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    except ET.ParseError:
        nodes = []
        rss_start = payload.find(b"<rss")
        rss_open_end = payload.find(b">", rss_start) if rss_start >= 0 else -1
        rss_open = payload[rss_start:rss_open_end + 1] if rss_open_end > rss_start else b"<rss>"
        for fragment in re.findall(rb"<item\b.*?</item>", payload, flags=re.DOTALL):
            try:
                wrapper = ET.fromstring(rss_open + b"<channel>" + fragment + b"</channel></rss>")
                node = wrapper.find(".//item")
                if node is not None:
                    nodes.append(node)
            except ET.ParseError:
                continue
        if not nodes:
            raise
        recovered = True
    articles: list[NormalizedArticle] = []
    for node in nodes:
        title = _text(node, ["title", "{http://www.w3.org/2005/Atom}title"])
        link = _text(node, ["link", "path"])
        if not link:
            atom_link = node.find("{http://www.w3.org/2005/Atom}link")
            link = atom_link.get("href") if atom_link is not None else None
        if not title or not link:
            continue
        canonical = normalize_url(link)
        raw_date = _text(node, [
            "pubDate", "created", "{http://purl.org/dc/elements/1.1/}date",
            "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated",
        ])
        summary = _plain_text(_text(node, [
            "description", "field_synopsis", "{http://www.w3.org/2005/Atom}summary", "field_body",
        ]))
        digest = hashlib.sha256(f"{title}\n{summary or ''}".encode("utf-8")).hexdigest()
        articles.append(NormalizedArticle(
            article_id=stable_id("article", canonical), source_id=source_id, source_url=link,
            canonical_url=canonical, title=title, published_at_raw=raw_date,
            published_at_utc=_date_to_utc(raw_date), summary_from_source=summary,
            language=language, content_hash=digest,
            parser_version="rss.recovered.v1" if recovered else "rss.v1",
        ))
    return articles


def parse_gdelt(payload: bytes, source_id: str = "API001") -> list[NormalizedArticle]:
    data = json.loads(payload.decode("utf-8-sig"))
    articles: list[NormalizedArticle] = []
    for item in data.get("articles", []):
        title, link = item.get("title"), item.get("url")
        if not title or not link or not link.startswith(("http://", "https://")):
            continue
        canonical = normalize_url(link)
        raw_date = item.get("seendate")
        parsed_date = None
        if raw_date:
            try:
                parsed_date = datetime.strptime(raw_date, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC).isoformat()
            except ValueError:
                parsed_date = _date_to_utc(raw_date)
        digest = hashlib.sha256(f"{title}\n{item.get('domain', '')}".encode("utf-8")).hexdigest()
        articles.append(NormalizedArticle(
            article_id=stable_id("article", canonical), source_id=source_id,
            source_url=link, canonical_url=canonical, title=title,
            published_at_raw=raw_date, published_at_utc=parsed_date,
            summary_from_source=None, language=item.get("language"),
            content_hash=digest, extraction_method="gdelt_doc_api",
            parser_version="gdelt.v1",
        ))
    return articles


def fetch_resource(
    url: str,
    *,
    timeout: int = 20,
    max_bytes: int = 3_000_000,
    retries: int = 2,
    accept: str = "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, application/json;q=0.8",
) -> FetchResponse:
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Encoding": "identity",
        "Connection": "close",
    })
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content_length = int(response.headers.get("Content-Length") or 0)
                if content_length > max_bytes:
                    raise ValueError(f"response too large: {content_length} bytes")
                try:
                    payload = response.read(max_bytes + 1)
                except http.client.IncompleteRead as exc:
                    raise http.client.IncompleteRead(exc.partial, exc.expected)
                if len(payload) > max_bytes:
                    raise ValueError(f"response exceeded {max_bytes} bytes")
                return FetchResponse(
                    payload=payload,
                    status=getattr(response, "status", 200),
                    content_type=response.headers.get_content_type(),
                    final_url=response.geturl(),
                )
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in {401, 403, 404} or attempt >= retries:
                break
            retry_after = exc.headers.get("Retry-After")
            delay = min(float(retry_after), 8.0) if retry_after and retry_after.isdigit() else 0.8 * (2**attempt)
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError, ValueError, http.client.HTTPException) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.5 * (2**attempt))
    raise RuntimeError(f"resource fetch failed after {retries + 1} attempts: {last_error}")


def fetch_feed(url: str, *, timeout: int = 15, max_bytes: int = 3_000_000, retries: int = 2) -> bytes:
    return fetch_resource(url, timeout=timeout, max_bytes=max_bytes, retries=retries).payload

from __future__ import annotations

import ipaddress
import json
import re
import urllib.error
import urllib.request
import urllib.robotparser
from functools import lru_cache
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit


USER_AGENT = "ClimateText-Lab/1.0 (+https://generationzprogrammer.github.io/climate-agent-news/)"
MAX_RESPONSE_BYTES = 1_000_000
MAX_EXCERPT_CHARS = 4_200
METADATA_ONLY_HOSTS = (
    "news.google.com",
    "reuters.com",
    "apnews.com",
    "politico.com",
    "politico.eu",
)


def _clean_text(value: str) -> str:
    value = unescape(value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return value


class _ArticleParser(HTMLParser):
    _ignored = {"script", "style", "nav", "header", "footer", "form", "noscript", "svg", "aside"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ignore_depth = 0
        self.article_depth = 0
        self.paragraph_depth = 0
        self.paragraph_parts: list[str] = []
        self.article_paragraphs: list[str] = []
        self.page_paragraphs: list[str] = []
        self.descriptions: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = {str(key).lower(): value or "" for key, value in attrs}
        if tag in self._ignored:
            self.ignore_depth += 1
        if tag == "article":
            self.article_depth += 1
        if tag == "meta":
            key = (attr.get("name") or attr.get("property") or "").lower()
            if key in {"description", "og:description", "twitter:description"}:
                text = _clean_text(attr.get("content", ""))
                if text:
                    self.descriptions.append(text)
        if tag == "p" and not self.ignore_depth:
            self.paragraph_depth += 1
            self.paragraph_parts = []

    def handle_data(self, data: str) -> None:
        if self.paragraph_depth and not self.ignore_depth:
            self.paragraph_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "p" and self.paragraph_depth:
            text = _clean_text(" ".join(self.paragraph_parts))
            if len(text) >= 45:
                self.page_paragraphs.append(text)
                if self.article_depth:
                    self.article_paragraphs.append(text)
            self.paragraph_depth = max(0, self.paragraph_depth - 1)
            self.paragraph_parts = []
        if tag == "article" and self.article_depth:
            self.article_depth -= 1
        if tag in self._ignored and self.ignore_depth:
            self.ignore_depth -= 1


def extract_article_text(html: str, *, limit: int = MAX_EXCERPT_CHARS) -> dict:
    """Extract a short, in-memory evidence excerpt without retaining article HTML."""
    parser = _ArticleParser()
    parser.feed(html)
    body_match = re.search(r'"articleBody"\s*:\s*("(?:\\.|[^"\\])*")', html, re.IGNORECASE)
    article_body = ""
    if body_match:
        try:
            article_body = _clean_text(json.loads(body_match.group(1)))
        except (json.JSONDecodeError, TypeError):
            article_body = ""
    candidates = []
    if article_body:
        candidates.append(("jsonld_article_body", article_body))
    if parser.article_paragraphs:
        candidates.append(("article_paragraphs", " ".join(parser.article_paragraphs)))
    if parser.page_paragraphs:
        candidates.append(("page_paragraphs", " ".join(parser.page_paragraphs)))
    if parser.descriptions:
        candidates.append(("page_description", parser.descriptions[0]))
    if not candidates:
        return {"text": "", "basis": "none"}
    basis, text = max(candidates, key=lambda pair: len(pair[1]))
    return {"text": text[:limit].strip(), "basis": basis}


@lru_cache(maxsize=64)
def _robots_parser(scheme: str, netloc: str) -> urllib.robotparser.RobotFileParser | bool:
    robots_url = f"{scheme}://{netloc}/robots.txt"
    request = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            parser.parse(response.read(256_000).decode("utf-8", errors="replace").splitlines())
        return parser
    except urllib.error.HTTPError as exc:
        return exc.code == 404
    except (OSError, urllib.error.URLError):
        return True


def _robots_allows(scheme: str, netloc: str, target_url: str) -> bool:
    policy = _robots_parser(scheme, netloc)
    return policy if isinstance(policy, bool) else policy.can_fetch(USER_AGENT, target_url)


@lru_cache(maxsize=128)
def fetch_article_text(url: str) -> dict:
    """Fetch one public article page with size, timeout and robots safeguards."""
    parts = urlsplit(url or "")
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return {"text": "", "basis": "invalid_url"}
    hostname = (parts.hostname or "").lower()
    if any(hostname == host or hostname.endswith(f".{host}") for host in METADATA_ONLY_HOSTS):
        return {"text": "", "basis": "metadata_only_source"}
    if hostname == "localhost" or hostname.endswith((".local", ".internal")):
        return {"text": "", "basis": "non_public_host"}
    try:
        address = ipaddress.ip_address(hostname)
        if not address.is_global:
            return {"text": "", "basis": "non_public_host"}
    except ValueError:
        pass
    if not _robots_allows(parts.scheme, parts.netloc, url):
        return {"text": "", "basis": "robots_disallowed"}
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9",
            "Accept-Language": "en,zh-CN;q=0.8,zh;q=0.7",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            content_type = (response.headers.get_content_type() or "").lower()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                return {"text": "", "basis": "unsupported_content_type"}
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                return {"text": "", "basis": "response_too_large"}
            charset = response.headers.get_content_charset() or "utf-8"
            html = data.decode(charset, errors="replace")
    except (OSError, UnicodeError, urllib.error.URLError):
        return {"text": "", "basis": "fetch_failed"}
    return extract_article_text(html)

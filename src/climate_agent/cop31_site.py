"""Publish the hand-built COP31 entry page over the same daily data and shared UI.

Until 2026-10-27 this module generated static/cop31/index.html from the main
site's index.html on every export. The 2026-10 redesign replaced that page
with a hand-built one (static/cop31/index.html plus cop31.css/cop31.js,
motion-kit.js, intel.*, countries.*, globe.js), so regenerating it would
overwrite the redesign. The page is now kept as is: this step only removes
markup that belongs to the offline preview package and checks that the
element contracts app.js and the daily data rely on are still present.
"""
import re
from pathlib import Path

from bs4 import BeautifulSoup

# Preview-package markup: a CSP that blocks the subscription service and a
# script that disables downloads and external requests. Never published.
PREVIEW_ONLY = (
    re.compile(r'^[ \t]*<meta http-equiv="Content-Security-Policy"[^\n]*\n?', re.M),
    re.compile(r'^[ \t]*<script src="preview-mode\.js"></script>[ \t]*\n?', re.M),
)
# Sections app.js renders into, plus the subscription contract.
REQUIRED_IDS = (
    "map", "today", "chinaCarbon", "singapore", "analytics", "assistant", "database",
    "subscribeOpen", "subscribeForm", "subscribeLanguage", "teamList",
)


def write_cop31_entry(static_dir: Path) -> Path:
    path = static_dir / "cop31" / "index.html"
    if not path.exists():
        raise FileNotFoundError(f"COP31 entry page missing: {path}")
    html = path.read_text(encoding="utf-8")
    published = html
    for pattern in PREVIEW_ONLY:
        published = pattern.sub("", published)
    soup = BeautifulSoup(published, "html.parser")
    problems = []
    if soup.body is None or soup.body.get("data-edition") != "cop31":
        problems.append('body[data-edition="cop31"]')
    if soup.base is None or soup.base.get("href") != "../":
        problems.append('<base href="../">')
    problems += [f"#{name}" for name in REQUIRED_IDS if soup.find(id=name) is None]
    if not soup.select_one('script[src*="app.js"]'):
        problems.append("app.js")
    if problems:
        raise ValueError("COP31 entry page is missing: " + ", ".join(problems))
    if published != html:
        path.write_text(published, encoding="utf-8")
    return path

#!/usr/bin/env python3
"""每日气候通讯 — the Chinese daily brief PDF of zerocarbonx.cn (2026-11-05).

Layout copied from the team's template 1223-0120-中文-讲话收集-ICCSD-杨秀精简.docx (user: fonts, sizes and format
strictly as that file, output PDF, title 每日气候通讯; readers: climate negotiation delegations):
  A4, 1-inch margins. First section, no page number: the logo top right (the template's box: 1.69 in from the left
  margin, 4.37 × 0.52 in), the title (bold 24 pt, first-line indent 2 characters), the date (bold 14 pt small caps,
  0.25 pt tracking, centred, a 0.5 pt rule under it), then 目录 (bold 20 pt, centred) and one entry per story (bold
  10.5 pt, #333333, 6 pt before, dot leader to the page number). Body section on a new page, page numbers from 1
  (10.5 pt, centred in the footer): per story a heading 「YYYY.MM.DD【来源】标题」 (bold 18 pt, #333333, 12 pt
  before / 14.4 pt after), body text in FangSong 16 pt (三号), line spacing 1.15, first-line indent 2 characters,
  justified; sub-headings bold 16 pt; the source as 「(来源: …」 and the link in 12 pt, no indent.
Fonts as the template (user 2026-11-05: 字体务必改成方正仿宋_GB2312): FangSong_GB2312 for everything (Normal and the
styles based on it set it for both East Asian and ASCII text), except the 目录 entries, whose ASCII text is Times New
Roman (TOC1) — bold there is the real Times New Roman Bold. FangSong_GB2312 has one weight: bold is drawn as Word
does, fill + thin stroke. Characters outside GB2312 fall back to STSong-Light. Without the FangSong_GB2312 file the
script fails (sync-data.sh then keeps the original brief); without Times New Roman Bold the 目录 uses FangSong_GB2312.
Input: the dashboard.json the site mirrors from the original project (its `intelligence` stories: Chinese title,
summary, why it matters, source, time, link).
Usage: grenn_brief.py DASHBOARD.json OUT.pdf [--logo PNG] [--font FangSong_GB2312.ttf] [--latin-bold timesbd.ttf]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, KeepTogether, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer
from reportlab.lib import textsplit as _textsplit
from reportlab.platypus import paragraph as _paragraph

# Chinese line-breaking (避头): reportlab's list lacks the full-width marks; they hang in the margin as in Word.
# Both copies: single-run paragraphs break in textsplit.wordSplit, mixed-font ones in paragraph.cjkFragSplit.
for _module in (_textsplit, _paragraph):
    _module.ALL_CANNOT_START += "，；：！？、。”’》〉）」』】…·％"

BEIJING = timezone(timedelta(hours=8))
INCH = 72.0
MARGIN = 1 * INCH
FONT, FALLBACK, LATIN_BOLD = "FangSong_GB2312", "STSong-Light", "TimesNewRoman-Bold"
INK = colors.HexColor("#333333")
TITLE = "每日气候通讯"
ABOUT = ("关于 GREEN：格润（GREEN）气候治理智能平台由清华大学气候变化与可持续发展研究院建设，2023 年 12 月在迪拜 COP28 中国角发布，"
         "2025 年 11 月在巴西贝伦 COP30 中国角发布 GREEN 1.0 版。平台以数字技术促进气候信息互联互通、数据开放共享与智能辅助决策，"
         "服务气候谈判与全球气候治理研究。更多内容见 https://zerocarbonx.cn")
DEFAULT_FONT = Path("/srv/grenn/app/fonts/FangSong_GB2312.ttf")
DEFAULT_LATIN_BOLD = Path("/srv/grenn/app/fonts/timesbd.ttf")
DEFAULT_LOGO = Path("/srv/grenn/current/assets/green-logo-mark.png")


def styles() -> dict:
    base = dict(fontName=FONT, wordWrap="CJK", textColor=colors.black)
    return {
        "title": ParagraphStyle("title", **base, fontSize=24, leading=24 * 1.15, firstLineIndent=32, alignment=TA_LEFT),
        "date": ParagraphStyle("date", **base, fontSize=14, leading=14 * 1.15, alignment=TA_CENTER),
        "toc_title": ParagraphStyle("toc_title", **{**base, "textColor": colors.black}, fontSize=20, leading=20 * 1.15,
                                    alignment=TA_CENTER, spaceBefore=6),
        "heading": ParagraphStyle("heading", **{**base, "textColor": INK}, fontSize=18, leading=18 * 1.15, spaceBefore=12,
                                  spaceAfter=14.4, alignment=TA_LEFT),
        "body": ParagraphStyle("body", **base, fontSize=16, leading=16 * 1.15, firstLineIndent=32, alignment=TA_JUSTIFY),
        "sub": ParagraphStyle("sub", **base, fontSize=16, leading=16 * 1.15, firstLineIndent=32, alignment=TA_JUSTIFY),
        "source": ParagraphStyle("source", **base, fontSize=12, leading=12 * 1.15, alignment=TA_LEFT),
        "about": ParagraphStyle("about", **{**base, "textColor": INK}, fontSize=10.5, leading=10.5 * 1.45, alignment=TA_JUSTIFY),
    }


_cmap: set = set()
_latin: list = []  # [True] once Times New Roman Bold is registered


def markup(text: str) -> str:
    """Escape for Paragraph; characters the FangSong font lacks fall back to STSong-Light."""
    out, run, fallback = [], [], False
    for ch in str(text or ""):
        miss = ch.strip() != "" and ord(ch) not in _cmap
        if miss != fallback and run:
            chunk = escape("".join(run))
            out.append(f'<font name="{FALLBACK}">{chunk}</font>' if fallback else chunk)
            run = []
        fallback = miss
        run.append(ch)
    if run:
        chunk = escape("".join(run))
        out.append(f'<font name="{FALLBACK}">{chunk}</font>' if fallback else chunk)
    return "".join(out)


def embolden(size: float) -> float:
    """Stroke width of the simulated bold: the outline widened by 1/24 em, as Word / FreeType embolden one-weight fonts."""
    return size / 24


class Bold(Flowable):
    """A flowable drawn with fill + stroke (text render mode 2): bold for a single-weight font."""

    def __init__(self, inner: Flowable, color=colors.black, width: float | None = None):
        super().__init__()
        self.inner, self.color = inner, color
        self.width = width if width is not None else embolden(getattr(getattr(inner, "style", None), "fontSize", 12))

    def wrap(self, aw, ah):
        self.w, self.h = self.inner.wrap(aw, ah)
        return self.w, self.h

    def split(self, aw, ah):
        return [Bold(part, self.color, self.width) for part in self.inner.split(aw, ah)]

    def getSpaceBefore(self):
        return self.inner.getSpaceBefore()

    def getSpaceAfter(self):
        return self.inner.getSpaceAfter()

    def draw(self):
        canv = self.canv
        canv.saveState()
        canv.setStrokeColor(self.color)
        canv._code.append(f"2 Tr {self.width:.2f} w")
        self.inner.drawOn(canv, 0, 0)
        canv.restoreState()


class Rule(Flowable):
    """The template's paragraph bottom border under the date: a 0.5 pt line, 1 pt below the text."""

    def wrap(self, aw, ah):
        self.width = aw
        return aw, 1.5

    def draw(self):
        self.canv.setLineWidth(0.5)
        self.canv.line(0, 0.5, self.width, 0.5)


class Logo(Flowable):
    """GREEN's mark and name in the template's logo box (1.69 in from the left margin, 4.37 × 0.52 in)."""

    def __init__(self, mark: Path | None):
        super().__init__()
        self.mark = mark if mark and mark.is_file() else None

    def wrap(self, aw, ah):
        return aw, 0.52 * INCH + 0.21 * INCH

    def draw(self):
        c, h = self.canv, 0.52 * INCH
        x = 1.69 * INCH
        if self.mark:
            c.drawImage(str(self.mark), x, 0, width=h, height=h, mask="auto")
        tx = x + h + 8
        c.setFillColor(colors.HexColor("#1f6f43"))
        c.setFont(FONT, 19)
        c.saveState()
        c.setStrokeColor(colors.HexColor("#1f6f43"))
        c._code.append(f"2 Tr {embolden(19):.2f} w")
        c.drawString(tx, h * 0.46, "格润气候治理")
        c.restoreState()
        c.setFillColor(colors.HexColor("#3f556c"))
        c.setFont(FONT, 9)
        c.drawString(tx, h * 0.08, "GREEN 2026 · climate governance")


class TocLine(Flowable):
    """One 目录 entry (TOC1: bold 10.5 pt, #333333, 6 pt before): the title wrapping on the left, a dot leader and the
    body page number on the right. Set by hand so that ASCII runs use Times New Roman Bold (a real bold face) while
    the FangSong_GB2312 runs get the stroked bold."""

    SIZE, SPACE_BEFORE = 10.5, 6

    def __init__(self, text: str, page: int | None):
        super().__init__()
        self.text, self.number = text, (str(page) if page else "")
        self.leading = self.SIZE * 1.15

    @staticmethod
    def font_of(token: str) -> tuple[str, bool]:
        if _latin and token.isascii():
            return LATIN_BOLD, False
        if all(ord(ch) in _cmap for ch in token if ch.strip()):
            return FONT, True
        return FALLBACK, True

    def wrap(self, aw, ah):
        self.aw = aw
        size = self.SIZE
        self.num_font = self.font_of("0")[0]
        self.num_w = pdfmetrics.stringWidth(self.number or "00", self.num_font, size)
        limit = aw - self.num_w - 18
        lines, line, width = [], [], 0.0
        # ASCII words stay whole (Word breaks Latin text at spaces), every other character is a break opportunity
        for token in re.findall(r"[!-~]+| |.", self.text):
            font, stroked = self.font_of(token)
            w = pdfmetrics.stringWidth(token, font, size)
            if line and width + w > limit and token != " ":
                lines.append(line)
                line, width = [], 0.0
            if not line and token == " ":
                continue
            line.append((token, font, stroked, w))
            width += w
        if line:
            lines.append(line)
        self.lines = lines or [[]]
        self.h = len(self.lines) * self.leading
        return aw, self.h

    def getSpaceBefore(self):
        return self.SPACE_BEFORE

    def _run(self, x, y, text, font, stroked):
        t = self.canv.beginText(x, y)
        t.setFont(font, self.SIZE)
        t.setTextRenderMode(2 if stroked else 0)
        t.textOut(text)
        self.canv.drawText(t)

    def draw(self):
        c, size = self.canv, self.SIZE
        c.saveState()
        c.setFont(FONT, size)  # text objects open with the canvas font
        c.setFillColor(INK)
        c.setStrokeColor(INK)
        c.setLineWidth(embolden(size))
        x = 0.0
        for i, line in enumerate(self.lines):
            y = self.h - (i + 1) * self.leading + (self.leading - size) + size * 0.18
            x = 0.0
            for token, font, stroked, w in line:
                self._run(x, y, token, font, stroked)
                x += w
        dot_font, dot_stroked = self.font_of(".")
        dot = pdfmetrics.stringWidth(".", dot_font, size)
        num_x = self.aw - self.num_w
        lead = x + 3
        while lead + dot < num_x - 3:
            self._run(lead, y, ".", dot_font, dot_stroked)
            lead += dot * 1.6
        if self.number:
            self._run(num_x, y, self.number, self.num_font, self.num_font != LATIN_BOLD)
        c.restoreState()


class Brief(BaseDocTemplate):
    def __init__(self, path, **kw):
        super().__init__(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN,
                         bottomMargin=MARGIN, title=TITLE, author="GREEN 格润气候治理", **kw)
        frame = Frame(MARGIN, MARGIN, A4[0] - 2 * MARGIN, A4[1] - 2 * MARGIN, id="text", leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0)
        self.body_start = None
        self.heading_pages = {}
        self.addPageTemplates([
            PageTemplate("front", [frame]),
            PageTemplate("body", [frame], onPage=self.number_page),
        ])

    def number_page(self, canv, doc):
        if self.body_start is None:
            self.body_start = canv.getPageNumber()
        canv.saveState()
        canv.setFont(FONT, 10.5)
        canv.drawCentredString(A4[0] / 2, 40, str(canv.getPageNumber() - self.body_start + 1))
        canv.restoreState()

    def afterFlowable(self, flowable):
        key = getattr(flowable, "story_key", None)
        if key is not None and self.body_start is not None:
            self.heading_pages[key] = self.canv.getPageNumber() - self.body_start + 1


def _list(value):
    if isinstance(value, list):
        return value
    try:
        out = ast.literal_eval(value) if value else []
        return out if isinstance(out, list) else []
    except (ValueError, SyntaxError):
        return []


def stories(dashboard: dict) -> list:
    out = []
    for item in dashboard.get("intelligence") or []:
        title = (item.get("title_zh") or item.get("title_original") or "").strip()
        if not title:
            continue
        try:
            when = datetime.fromisoformat(str(item.get("published_at")).replace("Z", "+00:00")).astimezone(BEIJING)
            day = when.strftime("%Y.%m.%d")
        except ValueError:
            day = (dashboard.get("meta") or {}).get("date", "").replace("-", ".")
        places = [p.get("name_zh") for p in _list(item.get("places")) if isinstance(p, dict) and p.get("name_zh")]
        out.append({"heading": f"{day}【{(item.get('source_name') or '来源待核').strip()}】{title}",
                    "summary": (item.get("summary_zh") or "").strip(), "why": (item.get("why_zh") or "").strip(),
                    "theme": (item.get("theme_zh") or "").strip(), "places": places,
                    "source": (item.get("source_name") or "").strip(), "url": (item.get("canonical_url") or "").strip()})
    return out


def build_story(data: list, toc_pages: dict | None, logo: Path | None, date_text: str) -> list:
    st = styles()
    story = [Logo(logo), Spacer(1, 18 * 1.15 * 2),
             Bold(Paragraph(markup(TITLE), st["title"])),
             Bold(Paragraph(markup(date_text), st["date"])), Rule(), Spacer(1, 18),
             Bold(Paragraph(markup("目录"), st["toc_title"])), Spacer(1, 4)]
    for index, s in enumerate(data):
        story.append(TocLine(s["heading"], (toc_pages or {}).get(index)))
    story += [NextPageTemplate("body"), PageBreak()]
    for index, s in enumerate(data):
        heading = Bold(Paragraph(markup(s["heading"]), st["heading"]), INK)
        heading.story_key = index
        story.append(heading)
        for part in [p.strip() for p in re.split(r"\n{2,}|\r?\n", s["summary"]) if p.strip()]:
            story.append(Paragraph(markup(part), st["body"]))
        if s["why"]:
            story.append(Bold(Paragraph(markup("关注要点"), st["sub"])))
            story.append(Paragraph(markup(s["why"]), st["body"]))
        facts = []
        if s["theme"]:
            facts.append(f"主题：{s['theme']}")
        if s["places"]:
            facts.append(f"涉及国家与地区：{'、'.join(dict.fromkeys(s['places']))}")
        if facts:
            story.append(Paragraph(markup("；".join(facts) + "。"), st["body"]))
        story.append(Paragraph(markup(f"(来源: {s['source'] or '来源待核'}"), st["source"]))
        if s["url"].startswith(("http://", "https://")):
            shown = s["url"] if len(s["url"]) <= 86 else s["url"][:84] + "…"  # aggregator links run for lines
            story.append(Paragraph(f'<link href="{escape(s["url"])}">{markup(shown)}</link>', st["source"]))
    story.append(KeepTogether([Spacer(1, 22), Rule(), Spacer(1, 8), Paragraph(markup(ABOUT), st["about"])]))
    return story


def render(dashboard_path: Path, out: Path, *, font: Path, logo: Path | None, latin_bold: Path | None = None) -> dict:
    if not font.is_file():
        raise SystemExit(f"FangSong_GB2312 font not found: {font}")
    pdfmetrics.registerFont(TTFont(FONT, str(font)))
    if latin_bold and latin_bold.is_file() and not _latin:
        pdfmetrics.registerFont(TTFont(LATIN_BOLD, str(latin_bold)))
        _latin.append(True)
    pdfmetrics.registerFont(UnicodeCIDFont(FALLBACK))
    _cmap.update(pdfmetrics.getFont(FONT).face.charToGlyph.keys())
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    data = stories(dashboard)
    if not data:
        raise SystemExit("no stories in the dashboard")
    meta = dashboard.get("meta") or {}
    day = meta.get("latest_news_date") or meta.get("date") or datetime.now(BEIJING).date().isoformat()
    y, m, d = day[:10].split("-")
    date_text = f"{y}年{m}月{d}日"
    # two passes: the first finds the body page of every story, the second prints them in the 目录
    probe = Brief(out.with_suffix(".probe.pdf"))
    probe.build(build_story(data, None, logo, date_text))
    pages = dict(probe.heading_pages)
    out.with_suffix(".probe.pdf").unlink(missing_ok=True)
    tmp = out.with_suffix(".tmp.pdf")
    doc = Brief(tmp)
    doc.build(build_story(data, pages, logo, date_text))
    tmp.replace(out)
    return {"stories": len(data), "date": day, "pages": max(pages.values(), default=0), "file": str(out)}


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("dashboard", type=Path)
    cli.add_argument("out", type=Path)
    cli.add_argument("--font", type=Path, default=DEFAULT_FONT)
    cli.add_argument("--logo", type=Path, default=DEFAULT_LOGO)
    cli.add_argument("--latin-bold", type=Path, default=DEFAULT_LATIN_BOLD)
    args = cli.parse_args(argv)
    print(json.dumps(render(args.dashboard, args.out, font=args.font, logo=args.logo, latin_bold=args.latin_bold),
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

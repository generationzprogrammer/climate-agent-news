from __future__ import annotations

from pathlib import Path
from textwrap import wrap


PAGE_WIDTH = 595
PAGE_HEIGHT = 842


def _pdf_cjk_text(value: str) -> str:
    return "<" + value.encode("utf-16-be").hex().upper() + ">"


def _pdf_latin_text(value: str) -> str:
    return "<" + value.encode("cp1252", errors="replace").hex().upper() + ">"


def _font_for_character(character: str) -> str:
    try:
        character.encode("cp1252")
    except UnicodeEncodeError:
        return "F0"
    return "F1"


def _font_runs(value: str) -> list[tuple[str, str]]:
    """Split mixed Chinese/Latin text so English and digits are not CJK-width."""
    runs: list[tuple[str, str]] = []
    for character in value:
        font = _font_for_character(character)
        if runs and runs[-1][0] == font:
            runs[-1] = (font, runs[-1][1] + character)
        else:
            runs.append((font, character))
    return runs


def _wrap_text(value: str, width: int) -> list[str]:
    clean = " ".join(str(value or "").split())
    return wrap(clean, width=width, break_long_words=True, replace_whitespace=False) or [""]


def _brief_lines(payload: dict) -> list[tuple[str, int, int]]:
    meta = payload.get("meta", {})
    lines: list[tuple[str, int, int]] = [
        ("国际气候情报今日简报", 22, 30),
        (f"发布日期：{meta.get('date', '时间待核')}（北京时间）", 11, 20),
        ("仅收录最近一个有有效记录的自然日；重要数字与立场请回到原文复核。", 10, 28),
    ]
    for index, item in enumerate(payload.get("intelligence", []), 1):
        theme = item.get("theme_zh") or "气候动态"
        title = item.get("title_zh") or item.get("title_original") or "未命名情报"
        summary = item.get("summary_zh") or "概要待补充。"
        source = item.get("source_name") or "来源待核"
        published = item.get("published_at") or "时间待核"
        why = item.get("why_zh") or "请结合原文判断其政策含义。"
        url = item.get("canonical_url") or ""
        lines.append((f"{index:02d}  [{theme}] {title}", 14, 18))
        lines.extend((part, 10, 14) for part in _wrap_text(summary, 48))
        lines.extend((part, 9, 13) for part in _wrap_text(f"来源：{source}｜{published}", 64))
        lines.extend((part, 9, 13) for part in _wrap_text(f"关注理由：{why}", 60))
        if url:
            lines.extend((part, 8, 12) for part in _wrap_text(f"原文：{url}", 78))
        lines.append(("", 8, 10))
    if not payload.get("intelligence"):
        lines.append(("今日暂无通过质量门槛的新情报。", 12, 20))
    lines.extend([
        ("数据边界", 13, 18),
        ("新闻标题与中文摘要不等于独立事实核验；涉及数字、承诺和立场时，请通过原文链接复核。", 9, 13),
    ])
    return lines


def _page_stream(lines: list[tuple[str, int, int]]) -> bytes:
    commands = ["BT", "/F0 10 Tf", "1 0 0 1 48 796 Tm"]
    current_font = "F0"
    current_size = 10
    for text, size, leading in lines:
        commands.append(f"0 -{leading} Td")
        for font, run in _font_runs(text):
            if font != current_font or size != current_size:
                commands.append(f"/{font} {size} Tf")
                current_font = font
                current_size = size
            encoded = _pdf_latin_text(run) if font == "F1" else _pdf_cjk_text(run)
            commands.append(f"{encoded} Tj")
    commands.append("ET")
    return "\n".join(commands).encode("ascii")


def write_daily_brief_pdf(payload: dict, path: Path) -> Path:
    """Write a dependency-free, searchable Chinese PDF using a standard CJK font."""
    pages: list[list[tuple[str, int, int]]] = []
    page: list[tuple[str, int, int]] = []
    used = 0
    for line in _brief_lines(payload):
        height = line[2]
        if page and used + height > 720:
            pages.append(page)
            page = []
            used = 0
        page.append(line)
        used += height
    if page:
        pages.append(page)

    objects: list[bytes] = []

    def add_object(content: bytes) -> int:
        objects.append(content)
        return len(objects)

    catalog_id = add_object(b"")
    pages_id = add_object(b"")
    font_id = add_object(b"")
    latin_font_id = add_object(b"")
    cid_font_id = add_object(b"")
    descriptor_id = add_object(
        b"<< /Type /FontDescriptor /FontName /STSong-Light /Flags 6 "
        b"/FontBBox [-25 -254 1000 880] /ItalicAngle 0 /Ascent 880 "
        b"/Descent -120 /CapHeight 880 /StemV 80 >>"
    )
    page_ids: list[int] = []
    for page_lines in pages:
        stream = _page_stream(page_lines)
        stream_id = add_object(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
        )
        page_id = add_object(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F0 {font_id} 0 R /F1 {latin_font_id} 0 R >> >> "
            f"/Contents {stream_id} 0 R >>".encode("ascii")
        )
        page_ids.append(page_id)

    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii")
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")
    objects[font_id - 1] = (
        f"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H "
        f"/DescendantFonts [{cid_font_id} 0 R] >>"
    ).encode("ascii")
    # Times-Roman is the portable PDF Base-14 Times face. It has conventional
    # Latin/digit metrics and is reader-compatible with Times New Roman.
    objects[latin_font_id - 1] = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>"
    )
    objects[cid_font_id - 1] = (
        f"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
        f"/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> "
        f"/FontDescriptor {descriptor_id} 0 R /DW 1000 >>"
    ).encode("ascii")

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, content in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(content)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(output)
    return path

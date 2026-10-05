"""Print the verified native HTML, then verify and render every PDF page."""
from pathlib import Path
import json
import subprocess
import tempfile
import sys
import fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "analysis/reports/open_innovation"
HTML = FOLDER / "科产融合全球开放创新生态研究报告.html"
PDF = FOLDER / "科产融合全球开放创新生态研究报告.pdf"
CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
if not json.loads((FOLDER / "verification_receipt.json").read_text(encoding="utf-8"))["ok"]:
    raise SystemExit("Verified HTML required")
if "--verify-only" not in sys.argv:
    with tempfile.TemporaryDirectory(prefix="innovation-print-") as profile:
        subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--no-first-run",
                        "--no-default-browser-check", "--no-pdf-header-footer", "--virtual-time-budget=8000",
                        "--user-data-dir=" + profile, "--print-to-pdf=" + str(PDF), HTML.as_uri()],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, check=True)
doc = fitz.open(PDF)
texts = [page.get_text() for page in doc]
assert doc.page_count > 0 and PDF.stat().st_size > 10000
assert all(len(text.strip()) > 40 for text in texts), "Blank or nearly blank PDF page"
all_text = "\n".join(texts)
assert "科产融合" in all_text and "图1" in all_text and "图3" in all_text
assert all(word not in all_text for word in ("snapshot status", "manifest path", "Open options", "Refresh", "file:///"))
preview = ROOT / "tmp/innovation-report-pdf"
preview.mkdir(parents=True, exist_ok=True)
tiles = []
for i, page in enumerate(doc):
    pix = page.get_pixmap(matrix=fitz.Matrix(1.15, 1.15), alpha=False)
    pix.save(str(preview / f"page-{i+1:02d}.png"))
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    im.thumbnail((360, 510))
    tile = Image.new("RGB", (380, 550), "#e9e9e9")
    tile.paste(im, ((380-im.width)//2, 25))
    ImageDraw.Draw(tile).text((12, 5), str(i+1), fill="black")
    tiles.append(tile)
for batch in range(0, len(tiles), 6):
    subset = tiles[batch:batch+6]
    sheet = Image.new("RGB", (380*3, 550*((len(subset)+2)//3)), "white")
    for i, tile in enumerate(subset): sheet.paste(tile, ((i%3)*380, (i//3)*550))
    sheet.save(preview / f"sheet-{batch//6+1}.png")
result = {"pages": doc.page_count, "bytes": PDF.stat().st_size,
          "characters": sum(map(len, texts)), "rendered_all_pages": True,
          "searchable_text": True, "empty_pages": 0}
(FOLDER / "pdf_checks.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
print(json.dumps(result))

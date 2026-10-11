"""Render three documents with native Word when bundled LibreOffice is absent."""
from pathlib import Path
import json
import subprocess
import win32com.client
from pypdf import PdfReader
from PIL import Image, ImageOps, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'analysis/reports/platform_publication_20261011'
QA=ROOT/'tmp/platform-publication-qa'
POPPLER=Path('C:/Users/10906/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe')
app=win32com.client.DispatchEx('Word.Application')
app.Visible=False
app.DisplayAlerts=0
results=[]
try:
    for index, path in enumerate(sorted(FOLDER.glob('*.docx'))):
        dest=QA/f'document-{index+1}';dest.mkdir(parents=True,exist_ok=True)
        document=None
        try:
            document=app.Documents.Open(str(path),ReadOnly=True,AddToRecentFiles=False)
            document.Repaginate()
            pdf=dest/'render.pdf'
            document.ExportAsFixedFormat(str(pdf),17)
        finally:
            if document is not None:document.Close(False)
        reader=PdfReader(pdf)
        texts=[page.extract_text() for page in reader.pages]
        assert all(len(text.strip())>50 for text in texts), 'Unexpected blank page'
        assert all('\ufffd' not in text for text in texts), 'Replacement glyph'
        subprocess.run([str(POPPLER),'-r','110','-png',str(pdf),str(dest/'page')],check=True,timeout=60)
        images=[Image.open(p).convert('RGB') for p in sorted(dest.glob('page-*.png'))]
        thumbs=[]
        for number, image in enumerate(images,1):
            thumb=ImageOps.contain(image,(510,690))
            tile=Image.new('RGB',(530,725),'#e9eaec');tile.paste(thumb,((530-thumb.width)//2,25))
            ImageDraw.Draw(tile).text((14,6),f'{index+1} / {number}',fill='black')
            thumbs.append(tile)
        sheet=Image.new('RGB',(530*min(2,len(thumbs)),725*((len(thumbs)+1)//2)), 'white')
        for pos,tile in enumerate(thumbs):sheet.paste(tile,((pos%2)*530,(pos//2)*725))
        sheet.save(dest/'contact-sheet.png')
        results.append({'file':path.name,'pages':len(reader.pages),'characters':[len(text) for text in texts],'renderer':'Microsoft Word','rendered_pages':len(images)})
finally:app.Quit()
(QA/'render-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False))

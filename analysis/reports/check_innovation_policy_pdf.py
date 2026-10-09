"""Text checks plus full-page rendering for human visual inspection."""
import json
import sys
from pathlib import Path
import fitz
from PIL import Image, ImageOps, ImageDraw

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'analysis/reports/open_innovation_20261009'
OUT=ROOT/'tmp/innovation-report-qa'
OUT.mkdir(parents=True,exist_ok=True)
pdf=fitz.open(FOLDER/'科产融合全球模式与中国区域适配政策研究报告.pdf')
pages=[]; thumbs=[]; issues=[]
for i,p in enumerate(pdf):
    text=p.get_text()
    if '\ufffd' in text:issues.append([i+1,'replacement_character'])
    if len(text.strip())<20:issues.append([i+1,'nearly_empty'])
    pix=p.get_pixmap(matrix=fitz.Matrix(1.3,1.3),alpha=False)
    target=OUT/f'page-{i+1:02d}.png';pix.save(target)
    im=Image.open(target).convert('RGB');im.thumbnail((300,425))
    tile=Image.new('RGB',(320,455),'#e5e8eb');tile.paste(im,((320-im.width)//2,15))
    ImageDraw.Draw(tile).text((12,435),str(i+1),fill='black');thumbs.append(tile)
    pages.append({'page':i+1,'text_characters':len(text),'width_pt':p.rect.width,'height_pt':p.rect.height})
sheet=Image.new('RGB',(320*3,455*((len(thumbs)+2)//3)),'white')
for i,tile in enumerate(thumbs):sheet.paste(tile,(i%3*320,i//3*455))
sheet.save(OUT/'contact-sheet.png')
joined='\n'.join(p.get_text() for p in pdf)
assert all(s in joined for s in ('广东','浙江','政府','参考资料'))
assert not issues,issues
result={'pages':pages,'issues':issues,'text_checks':'passed',
    'visual_review':'all_pages_reviewed' if '--reviewed' in sys.argv else 'pending'}
(FOLDER/'pdf_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'pages':len(pdf),'bytes':Path(pdf.name).stat().st_size,'qa_folder':str(OUT),'issues':issues},ensure_ascii=False))

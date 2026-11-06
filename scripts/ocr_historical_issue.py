"""Local OCR with boxes/confidence; source scan retained, never guessed text."""
import json
import numpy as np
import pymupdf
from rapidocr_onnxruntime import RapidOCR
import fulltext_pilot as p

dest=p.ROOT/'data/private_global_expansion_20261106/historical/airclim_june_1992'
pdf=pymupdf.open(dest/'source.pdf');engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1)
allpages=[]
for i,page in enumerate(pdf):
 output=dest/f'ocr_page_{i+1:02d}.json'
 if output.exists():allpages.append(json.loads(output.read_text('utf-8')));continue
 pix=page.get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False)
 img=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3)
 result,elapsed=engine(img)
 items=[{'box':box,'text':text,'confidence':float(conf)} for box,text,conf in (result or [])]
 obj={'page':i+1,'width':pix.width,'height':pix.height,'items':items,'elapsed':elapsed,'source_pdf_sha256':p.digest((dest/'source.pdf').read_bytes())}
 p.dump(output,obj);allpages.append(obj);print(json.dumps({'page':i+1,'lines':len(items),'mean_confidence':sum(x['confidence'] for x in items)/max(1,len(items))}),flush=True)
p.dump(dest/'ocr_all_pages.json',allpages)

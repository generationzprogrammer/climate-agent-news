"""English OCR for a verifiable 1992 article; retain all geometry and scores."""
import hashlib,json,urllib.request
import numpy as np
import pymupdf
from rapidocr_onnxruntime import RapidOCR
import fulltext_pilot as p
dest=p.ROOT/'data/private_global_expansion_20261106/historical/airclim_june_1992'
model=dest/'en_PP-OCRv3_rec_infer.onnx'
url='https://huggingface.co/spaces/RapidAI/RapidOCR/resolve/main/models/text_rec/en_PP-OCRv3_rec_infer.onnx'
if not model.exists():
 with urllib.request.urlopen(url,timeout=45) as response:raw=response.read(30_000_000)
 if len(raw)<1_000_000:raise ValueError('unexpected model size')
 model.write_bytes(raw)
p.dump(dest/'english_model_provenance.json',{'url':url,'sha256':hashlib.sha256(model.read_bytes()).hexdigest()})
engine=RapidOCR(rec_model_path=str(model),rec_img_shape=[3,48,320],intra_op_num_threads=2,inter_op_num_threads=1)
pdf=pymupdf.open(dest/'source.pdf');page=pdf[13]
pix=page.get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False)
img=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3)
result,elapsed=engine(img)
p.dump(dest/'ocr_page_14_english.json',{'page':14,'width':pix.width,'height':pix.height,'items':[{'box':box,'text':text,'confidence':float(conf)} for box,text,conf in result],'elapsed':elapsed})
print('English OCR page 14 saved',flush=True)

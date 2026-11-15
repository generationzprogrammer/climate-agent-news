"""Read-only smoke check of the deployed bilingual thematic briefings."""
import io,json,urllib.request
from pypdf import PdfReader
BASE='https://generationzprogrammer.github.io/climate-agent-news/data/'
results={}
for name in ('dashboard.json','daily_brief.pdf','daily_brief_en.pdf','weekly_report.pdf','weekly_report_en.pdf'):
    request=urllib.request.Request(BASE+name,headers={'User-Agent':'GREEN-release-check/1.0','Cache-Control':'no-cache'})
    with urllib.request.urlopen(request,timeout=40) as response:
        raw=response.read();record={'status':response.status,'bytes':len(raw)}
    if name.endswith('.json'):
        payload=json.loads(raw);items=payload.get('intelligence',[])
        record.update(date=payload.get('meta',{}).get('date'),articles=len(items),summary_lengths=[len(x.get('summary_zh') or '') for x in items])
    else:
        pdf=PdfReader(io.BytesIO(raw));text='\n'.join(p.extract_text() or '' for p in pdf.pages)
        record.update(pages=len(pdf.pages),characters=len(text),thematic_sections=any(x in text for x in ('国际谈判与履约','Negotiations and implementation','Energy and industrial transition','能源与产业转型')))
    results[name]=record
print(json.dumps(results,ensure_ascii=False,indent=2))

"""Offline regression checks and actual cached briefing layout previews."""
import importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
OUT=ROOT/'analysis/governance_release_checks_20261105'
OUT.mkdir(parents=True,exist_ok=True)
tempdir=ROOT/'tmp/governance_tests';tempdir.mkdir(parents=True,exist_ok=True)
tempfile.tempdir=str(tempdir)
suite=unittest.TestSuite()
for pattern in ['test_governance_labels.py','test_country_evidence.py','test_english_brief.py','test_core.py','test_research.py','test_weekly_subscribers.py']:
    suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=pattern))
result=unittest.TextTestRunner(verbosity=1).run(suite)
(OUT/'tests.json').write_text(json.dumps({'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful()}),encoding='utf-8')
from climate_agent.pdf_brief import write_daily_brief_pdf,write_weekly_report_pdf
from climate_agent.briefing import weekly_report_payload,render_markdown,render_weekly_markdown
paths=[ROOT/'static/data/dashboard.json',ROOT/'.publish-climate-agent-news/static/data/dashboard.json']
path=next((p for p in paths if p.exists()),None)
if path:
    daily=json.loads(path.read_text('utf-8'))
    archive=ROOT/'data/news_archive.json'
    weekly=weekly_report_payload(json.loads(archive.read_text('utf-8')))
    for language in ('zh','en'):
        write_daily_brief_pdf(daily,OUT/f'daily_{language}.pdf',language=language)
        write_weekly_report_pdf(weekly,OUT/f'weekly_{language}.pdf',language=language)
    (OUT/'daily.md').write_text(render_markdown(daily),encoding='utf-8')
    (OUT/'weekly.md').write_text(render_weekly_markdown(weekly),encoding='utf-8')
    report={'preview_source':str(path.relative_to(ROOT)),'preview_date':daily.get('meta',{}).get('date'),'daily_articles':len(daily.get('intelligence',[])),'weekly_articles':len(weekly.get('highlights',[])),'summaries':'existing stored summaries, no new model call in offline preview'}
    if importlib.util.find_spec('fitz'):
        import fitz
        for p in OUT.glob('*.pdf'):
            doc=fitz.open(p);report[p.name]={'pages':len(doc),'characters':sum(len(pg.get_text()) for pg in doc)}
            for i,pg in enumerate(doc):
                if i==0 or i==len(doc)-1:pg.get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(str(OUT/f'{p.stem}_{i+1}.png'))
            doc.close()
    (OUT/'preview_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'tests':result.testsRun,'passed':result.wasSuccessful(),'preview':str(OUT)},ensure_ascii=False))
sys.exit(0 if result.wasSuccessful() else 1)

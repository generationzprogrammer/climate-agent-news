"""Check a finished export, add portable replay tools, and seal the ZIP."""
import collections,csv,gzip,hashlib,json,shutil,sqlite3,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/governance_handover_20261105_final'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
db=sqlite3.connect('file:'+str(OUT/'governance.sqlite').replace('\\','/')+'?mode=ro',uri=True)
db.row_factory=sqlite3.Row
m=json.loads((OUT/'manifest.json').read_text('utf-8'))
total=db.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
assert total==27159,(total,'unexpected input count')
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
# Round-trip an independently selected deterministic audit set.
samples=db.execute('SELECT * FROM articles ORDER BY text_sha256 LIMIT 200').fetchall()
checked=0
for row in samples:
    assert hashlib.sha256(row['source_text'].encode()).hexdigest()==row['text_sha256']
    for e in db.execute('SELECT * FROM evidence WHERE document_key=?',(row['document_key'],)):
        assert row[e['field']][e['start']:e['end']]==e['quote'];checked+=1
counts=dict(db.execute('SELECT primary_topic,COUNT(*) FROM articles WHERE research_eligible=1 GROUP BY primary_topic').fetchall())
with (OUT/'primary_topic_year.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['year','primary_topic','articles','denominator_articles','share'])
    denominators=dict(db.execute('SELECT year,COUNT(*) FROM articles WHERE research_eligible=1 GROUP BY year'))
    for year,topic,n in db.execute('SELECT year,primary_topic,COUNT(*) FROM articles WHERE research_eligible=1 GROUP BY year,primary_topic ORDER BY year,primary_topic'):
        w.writerow([year,topic,n,denominators[year],n/denominators[year]])
sources=db.execute('SELECT publisher,COUNT(*) n FROM articles WHERE research_eligible=1 GROUP BY publisher ORDER BY n DESC LIMIT 5').fetchall()
dates=db.execute('SELECT MIN(published_date),MAX(published_date) FROM articles WHERE research_eligible=1').fetchone()
timeline=json.loads((OUT/'policy_timeline.json').read_text('utf-8'))
missing=[r['event_id'] for r in timeline if not r.get('source_url') or not r.get('date') or not r.get('evidence_quote')]
for row in timeline:
    row['timeline_eligible']=row['event_id'] not in missing
    row['missing_fields']=[k for k in ('source_url','date','evidence_quote') if not row.get(k)]
(OUT/'policy_timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'policy_timeline_ready.json').write_text(json.dumps([r for r in timeline if r['timeline_eligible']],ensure_ascii=False,indent=2),encoding='utf-8')
m['policy_timeline_ready_events']=len(timeline)-len(missing)
m['policy_timeline_incomplete_events']=len(missing)
(OUT/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
audit={'articles':total,'eligible':m['counts']['research_eligible'],'audit_documents':len(samples),'checked_evidence_spans':checked,'topic_distribution':counts,'largest_publishers':[dict(r) for r in sources],'eligible_publication_range':list(dates),'timeline_missing_source_date_or_quote':missing,'inputs_unchanged':m['inputs_unchanged'],'human_semantic_accuracy':'not_estimated'}
(OUT/'final_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
db.close()
for name in ('query_governance_example.py','relabel_governance_delivery.py','finalize_governance_handover.py','build_governance_handover.py'):
    shutil.copy2(ROOT/'scripts'/name,OUT/'reproducibility/scripts'/name)
doc=OUT/'交接说明与数据字典.txt'
text=doc.read_text('utf-8')
text=text.split('\n七、无需采集环境的复核命令')[0]
text+='\n七、无需采集环境的复核命令\n解压后运行：python reproducibility/scripts/query_governance_example.py governance.sqlite\n重新生成标签：python reproducibility/scripts/relabel_governance_delivery.py original_recovery_labeled_fulltexts.jsonl.gz labels_replayed.jsonl.gz\n以上仅依赖Python标准库和包内代码，不联网、不调用模型。重新标注全部文本会占用一定时间；可直接使用已生成的SQLite与CSV。\n'
text+='\n补充表primary_topic_year.csv使用互斥主议题计数，各年度占比加总为100%（包含unclassified），可直接用于堆积面积图。未分类不得直接删去后仍沿用原分母。政策时间线含87条既有来源记录；当前与全文库的精确URL关联为0条，因此尚不能据此声称已建立新闻与政策事件的关联。\n'
text+=f'其中{len(missing)}条缺少日期、链接或原句之一，保留记录并标明缺项，不进入时间线图。policy_timeline_ready.json仅包含字段齐备的{len(timeline)-len(missing)}条候选记录，仍需核对原始文件。\n'
doc.write_text(text,encoding='utf-8')
(OUT/'checksums.json').write_text(json.dumps({str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='checksums.json'},ensure_ascii=False,indent=2),encoding='utf-8')
archive=OUT.parent/(OUT.name+'_交接包.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():z.write(p,str(p.relative_to(OUT)))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
receipt={'file':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive),'github_fulltext_uploaded':False,'github_reason':'repository privacy change deferred by owner','audit':audit}
(OUT.parent/'governance_handover_20261105_delivery_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False))

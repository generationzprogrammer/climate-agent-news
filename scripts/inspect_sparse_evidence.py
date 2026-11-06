"""Print a bounded source-context sample for the least frequent country labels."""
import argparse,json,sqlite3
import fulltext_pilot as p
parser=argparse.ArgumentParser();parser.add_argument('--snapshot',required=True);args=parser.parse_args()
db=sqlite3.connect(p.ROOT/'analysis/global_expansion_20261106'/args.snapshot/'climate_governance.sqlite')
rows=db.execute("SELECT l.label,count(*) FROM labels l JOIN articles a USING(article_id) WHERE a.eligible=1 AND l.dimension='country' GROUP BY l.label ORDER BY count(*) LIMIT 12").fetchall()
for code,count in rows:
    example=db.execute("SELECT a.title,e.quote,e.field,e.start,a.source_text FROM articles a JOIN evidence e USING(article_id) WHERE a.eligible=1 AND e.dimension='country' AND e.label=? ORDER BY CASE WHEN e.field='title' THEN 0 ELSE 1 END,e.start LIMIT 1",(code,)).fetchone()
    title,quote,field,start,body=example
    text=title if field=='title' else body
    print(json.dumps({'country':code,'articles':count,'title':title,'quote':quote,'context':text[max(0,start-80):start+180]},ensure_ascii=False))

"""Recompute a topic/year count directly from the delivered SQLite, offline."""
import argparse,csv,sqlite3,sys
ap=argparse.ArgumentParser();ap.add_argument('database');args=ap.parse_args()
db=sqlite3.connect('file:'+args.database.replace('\\','/')+'?mode=ro',uri=True)
rows=db.execute('''SELECT a.year,l.label_id,COUNT(DISTINCT a.document_key) AS articles
FROM articles a JOIN labels l USING(document_key)
WHERE a.research_eligible=1 AND l.label_type='topic'
GROUP BY a.year,l.label_id ORDER BY a.year,l.label_id''')
w=csv.writer(sys.stdout);w.writerow(['year','topic','articles']);w.writerows(rows)
db.close()

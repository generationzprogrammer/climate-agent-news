"""Inspect dated official 1990s press releases, without assuming modern markup."""
import gzip,json
from bs4 import BeautifulSoup
import fulltext_pilot as p
import bulk_fulltext as b
urls=['https://unfccc.int/cop3/fccc/info/pr7-96b.html','https://unfccc.int/cop3/fccc/info/pr7-96a.html','https://unfccc.int/cop3/fccc/info/indust.htm']
dest=p.ROOT/'data/private_global_expansion_20261106/historical/early_unfccc';dest.mkdir(exist_ok=True)
f=p.Fetcher();p.ACCEPT_ENCODING='gzip';p.TIMEOUT=25
for url in urls:
 try:
  final,html,raw,_=f.get(url,b.timing());s=BeautifulSoup(html,'lxml');name=url.rsplit('/',1)[-1]
  (dest/(name+'.gz')).write_bytes(gzip.compress(raw,mtime=0))
  p.dump(dest/(name+'.probe.json'),{'url':final,'sha256':p.digest(raw),'acquired_at':p.stamp(),'headings':[(x.name,x.get_text(' ',strip=True)) for x in s.select('h1,h2,h3,title')],'first_text':s.get_text(' ',strip=True)[:1600],'last_text':s.get_text(' ',strip=True)[-700:],'links':[(x.get_text(' ',strip=True),x.get('href')) for x in s.select('a[href]')]})
  print(json.dumps({'url':url,'headings':[(x.name,x.get_text(' ',strip=True)) for x in s.select('h1,h2,h3,title')],'first':s.get_text(' ',strip=True)[:750]},ensure_ascii=False),flush=True)
 except Exception as e:print(json.dumps({'url':url,'error':getattr(e,'reason',type(e).__name__)}),flush=True)
p.dump(dest/'requests.json',f.requests)

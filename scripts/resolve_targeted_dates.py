"""Resolve dates from already downloaded visible source text, not guessed dates."""
import gzip,json,re
from datetime import datetime
from bs4 import BeautifulSoup
import fulltext_pilot as p
from expansion_quality import eligible
root=p.ROOT/'data/private_global_expansion_20261106'
for file in (root/'targeted').glob('*.json'):
 d=json.loads(file.read_text('utf-8'))
 if d['date']!='unknown':continue
 soup=BeautifulSoup(gzip.decompress(file.with_suffix('.html.gz').read_bytes()),'lxml')
 plain=soup.get_text(' ',strip=True)
 # Observed news templates put their visible date immediately after headline.
 if p.host(d['url']) in ('www.gov.je','bonairegov.com'):
  index=plain.rfind(d['title']);tail=plain[index+len(d['title']):index+len(d['title'])+180]
  m=re.search(r'\b(\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (20\d{2})\b',tail)
  if m:
   d['date']=datetime.strptime(m.group(),'%d %B %Y').date().isoformat();d['date_precision']='day';d['source_date_evidence']={'quote':m.group(),'field':'raw_visible_HTML','basis':'visible_date_immediately_after_headline'}
   d['quality_flags']=[x for x in d['quality_flags'] if x!='source_publication_date_unresolved'];d['research_eligible']=not d['quality_flags'];p.dump(file,d);print(d['url'],d['date']);continue
 # Preserve undated non-news supplementary material outside temporal corpus.
 target=root/'targeted_undated';target.mkdir(exist_ok=True)
 file.replace(target/file.name);file.with_suffix('.html.gz').replace(target/file.with_suffix('.html.gz').name)
 print('undated_supplement',d['url'])

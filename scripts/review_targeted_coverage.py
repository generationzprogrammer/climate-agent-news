"""Explicit source-backed adjudications, preserving raw source and prior record."""
import gzip,json,re,shutil
from bs4 import BeautifulSoup
import fulltext_pilot as p
base=p.ROOT/'data/private_global_expansion_20261106';audit=base/'targeted_review_before';audit.mkdir(exist_ok=True)
ids=['target_87555ae849486cfb6eaf65ec','target_be425b3e5bd49827bc93c0d8','target_c87c02db9b99951d4443e2fa','target_2b07a6adbb24161fd71ff368']
for ident in ids:
 file=base/'targeted'/(ident+'.json')
 if not file.exists():file=base/'targeted_undated'/(ident+'.json')
 d=json.loads(file.read_text('utf-8'));htmlfile=file.with_suffix('.html.gz');soup=BeautifulSoup(gzip.decompress(htmlfile.read_bytes()),'lxml');heads=[x.get_text(' ',strip=True) for x in soup.select('h1')]
 if not (audit/file.name).exists():shutil.copy2(file,audit/file.name)
 flags=list(d['quality_flags']);evidence={'reviewer':'assistant_source_adjudication_not_independent_annotation','source_html_sha256':p.digest(gzip.decompress(htmlfile.read_bytes()))}
 if ident.endswith('2b07a6adbb24161fd71ff368'):
  title='Early ice retreat and anomalous CO2 sink in the South Atlantic in austral summer 2022'
  assert title in heads and '02 May 2025 '+title in soup.get_text(' ',strip=True)
  d.update(title=title,date='2025-05-02',date_precision='day')
  evidence.update(date_quote='02 May 2025 '+title,headline_selector='h1 exact full article title',terminal_basis='Complete scientific-news prose followed by figure captions, references and author/contact attribution; all 14 source blocks preserved')
  assert d['source_block_coverage']==1 and d['last_block_present']
  flags=[x for x in flags if x not in ['last_block_needs_review','source_publication_date_unresolved']]
 else:
  assert d['title'] in heads and d.get('title_match') is True
  evidence.update(headline_quote=d['title'],headline_selector='h1 exact match',identity_basis='direct official article URL, source H1 matches requested title; no recovered-URL identity inference required')
  flags=[x for x in flags if x!='strict_title_identity_needs_review']
 d.update(quality_flags=flags,completeness_flags=flags,research_eligible=not flags,source_adjudication=evidence)
 out=base/'targeted'/file.name;p.dump(out,d)
 if htmlfile.parent!=out.parent:shutil.copy2(htmlfile,out.with_suffix('.html.gz'))
 print(json.dumps({'id':ident,'eligible':d['research_eligible'],'date':d['date']}))

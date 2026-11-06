"""Documented post-label checks and conservative contextual alias enrichment."""
import re
from urllib.parse import urlsplit
VERSION='post-label-validation-20261106-v1'
ALIASES={'PS':r'\bPalestin(?:e|ian)\b|巴勒斯坦','PN':r'\bPitcairn\b','AX':r'\bÅland\b|\bAland Islands\b','KN':r'\bSaint Kitts and Nevis\b|\bSt\.? Kitts (?:and|&) Nevis\b'}
def enrich(doc):
 tags=doc['labels'];added=[]
 aliases=dict(ALIASES)
 if (urlsplit(doc.get('url','')).hostname or '').removeprefix('www.')=='gov.je':aliases['JE']=r'(?<!New )\bJersey\b'
 for field in ['title','source_text']:
  text=doc[field]
  for code,pattern in aliases.items():
   matches=list(re.finditer(pattern,text,re.I))[:3]
   if not matches:continue
   tags['country_mentions']=sorted(set(tags['country_mentions'])|{code})
   for m in matches:
    e={'label_type':'country','label_id':code,'field':field,'start':m.start(),'end':m.end(),'quote':m.group(),'method':'explicit_alias_postvalidation'}
    tags['evidence'].append(e);added.append(e)
    if field=='title' or m.start()<1500:tags['country_focal_candidates']=sorted(set(tags['country_focal_candidates'])|{code})
  if 'G02.06' not in tags['subcategory_mentions']:
   for m in re.finditer(r'policy coherence|policy consistency|政策一致性|政策协同',text,re.I):
    start=max(text.rfind('\n\n',0,m.start()),0);end=text.find('\n\n',m.end());end=len(text) if end<0 else end
    context=text[start:end]
    if not re.search(r'climate|net.zero|decarbon|气候|碳中和',context,re.I):continue
    e={'label_type':'subcategory','label_id':'G02.06','field':field,'start':m.start(),'end':m.end(),'quote':m.group(),'method':'policy_coherence_with_climate_anchor_in_same_paragraph'}
    tags['evidence'].append(e);added.append(e);tags['subcategory_mentions']=sorted(set(tags['subcategory_mentions'])|{'G02.06'});tags['category_mentions']=sorted(set(tags['category_mentions'])|{'G02'});tags['scores']['G02.06']=8 if field=='title' else 2
    if field=='title':tags['focal_subcategory_candidates']=sorted(set(tags['focal_subcategory_candidates'])|{'G02.06'})
    if tags['primary_subcategory'] is None:tags.update(primary_subcategory='G02.06',primary_category='G02')
    break
 doc['post_label_enrichment']={'version':VERSION,'additional_evidence_spans':len(added)}
 return doc

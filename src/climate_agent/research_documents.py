"""Explicitly licensed official documents, separate from news excerpts."""
import json
import time
import urllib.request
from pathlib import Path
from datetime import UTC,datetime,timedelta
from bs4 import BeautifulSoup
from .article_content import USER_AGENT, _robots_allows
from .research import load_jsonl, save_jsonl, persist_texts, make_text_record, clean, stamp


def update_documents(root):
    root=Path(root);config=root/'config/research_documents.json'
    if not config.exists():return {'requested':0,'saved':0,'errors':[]}
    texts_path=root/'data/research_texts.jsonl';texts={r['canonical_url']:r for r in load_jsonl(texts_path)}
    versions_path=root/'data/research_document_versions.jsonl';versions=load_jsonl(versions_path)
    keys={(r['canonical_url'],r['text_sha256']) for r in versions}
    count=saved=0;errors=[]
    for document in json.loads(config.read_text(encoding='utf-8'))['documents']:
        url=document['url'];existing=texts.get(url)
        if existing and existing.get('collected_at','')>(datetime.now(UTC)-timedelta(days=7)).isoformat():
            key=(url,existing['text_sha256'])
            if key not in keys:versions.append(existing);keys.add(key)
            continue
        if not url.startswith('https://www.gov.uk/government/publications/') or document.get('licence')!='OGL-3.0':continue
        count+=1
        try:
            if not _robots_allows('https','www.gov.uk',url):errors.append({'id':document['document_id'],'status':'robots_disallowed'});continue
            request=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'text/html'})
            with urllib.request.urlopen(request,timeout=15) as response:
                content=response.read(2_000_001)
            if len(content)>2_000_000:raise ValueError('document_too_large')
            soup=BeautifulSoup(content,'html.parser')
            if 'Open Government Licence' not in soup.get_text():raise ValueError('licence_not_found')
            main=soup.select_one('main')
            if not main:raise ValueError('main_text_not_found')
            for node in main.select('nav,aside,form,script,style,figure,img'):node.decompose()
            text=clean(main.get_text(' ',strip=True))
            if len(text)<3000:raise ValueError('document_text_too_short')
            row={'record_id':document['document_id'],'canonical_url':url,'title_original':document['title_en'],
                 'title_en':document['title_en'],'title_zh':document['title_zh'],'source_name':'UK Government',
                 'source_id':'RESEARCH-UK-GOV','source_type':'official_policy_document','language':'en',
                 'published_at':document['published_at'],
                 'country_codes':[{'alpha2':'GB','alpha3':'GBR','name_zh':'英国','name_en':'United Kingdom'}]}
            record=make_text_record(row,text,'licensed_document_text',basis='official_html_main_text')
            record.update({'document_family':document['family'],'document_country':'GB','version_label':document['version_label'],
                           'target_year':document['target_year'],'rights_status':document['licence'],
                           'licence_url':document['licence_url'],'rights_evidence':document['rights_evidence'],
                           'text_transformations':['HTML main-content extraction','whitespace normalization','contact email redaction']})
            texts[url]=record;saved+=1
            key=(url,record['text_sha256'])
            if key not in keys:versions.append(record);keys.add(key)
        except Exception as exc:errors.append({'id':document['document_id'],'status':type(exc).__name__})
        time.sleep(2)
    persist_texts(texts_path,sorted(texts.values(),key=lambda r:r.get('published_at') or '',reverse=True))
    save_jsonl(versions_path,versions)
    return {'requested':count,'saved':saved,'errors':errors}

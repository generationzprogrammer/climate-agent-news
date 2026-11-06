"""Add reproducible research lineage to delivered bodies without rewriting them.

Offsets are Unicode character offsets into source_text, end-exclusive. This is
evidence addressing, not automated factual/stance annotation or semantic dedup.
"""
import collections
import gzip
import hashlib
import importlib.metadata
import itertools
import json
import re
import sys
import unicodedata
from datetime import datetime,timezone
import bulk_fulltext as b
import collect_public_fulltext_library as n
import fulltext_pilot as p

def normalized_hash(text):
    text=re.sub(r'\s+',' ',unicodedata.normalize('NFKC',text)).strip().casefold()
    return p.digest(text.encode('utf-8'))

def paragraph_spans(text):
    out=[]; cursor=0
    boundaries=((m.start(),m.end()) for m in re.finditer(r'\n[^\S\n]*\n',text))
    for boundary,next_cursor in itertools.chain(boundaries,[(len(text),len(text))]):
        part=text[cursor:boundary]
        start=cursor+len(part)-len(part.lstrip())
        end=cursor+len(part.rstrip())
        if start<end:
            out.append({'start':start,'end':end,'sha256':p.digest(text[start:end].encode('utf-8'))})
        cursor=next_cursor
    return out

def utc_date(doc):
    value=doc.get('source_published_at_utc') or doc.get('date')
    if not value: return None
    try:
        dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if dt.tzinfo is None: return None
        return dt.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
    except ValueError: return None

def record(doc,cohort,original_ids):
    text=doc['source_text']; rawsha=p.digest(text.encode())
    if rawsha!=doc['text_sha256']: raise ValueError('Body checksum mismatch')
    relevant,tags=n.relevance(doc.get('page_title') or doc['title'],text)
    strict=doc.get('delivery_class')=='candidate_full_article' and relevant and len(text)>=800
    return {'schema_version':'green-fulltext-evidence-1.0','cohort':cohort,'document_id':doc['id'],'text_sha256':rawsha,'normalized_text_sha256':normalized_hash(text),'source_record_ids':original_ids.get(rawsha,[]) if cohort=='original_recovery' else [],'title':doc['title'],'publisher_headline':doc.get('page_title'),'publisher':doc['source'],'publisher_url':doc.get('publisher_url') or doc['url'],'published_at_raw':doc.get('source_published_at') or doc.get('date'),'published_at_utc':utc_date(doc),'acquired_at':doc.get('acquired_at') or doc.get('fetched_at') or doc.get('finished_at'),'language_declared':doc.get('language','und'),'language_independently_verified':False,'text_characters':len(text),'text_utf8_bytes':len(text.encode()),'paragraph_spans':paragraph_spans(text),'source_dom_coverage':doc.get('source_block_coverage'),'quality_flags':doc.get('quality_flags',[]),'candidate_full_article':doc.get('delivery_class')=='candidate_full_article','domain_relevance_pass':relevant,'topic_tags':tags['topic_tags'],'relevance_evidence':tags['relevance_evidence'],'primary_research_candidate':strict,'extraction_method':doc.get('extraction_method'),'pipeline_version':doc.get('pipeline_version'),'raw_asset':doc.get('raw_batch_path') or str((b.PRIVATE/'raw'/f"{doc['id']}.response.gz").relative_to(p.ROOT)),'raw_asset_sha256':doc.get('raw_batch_sha256'),'public_redistribution_allowed':False}

def main():
    # A bounded acquisition orchestrator can predate a dictionary update.
    # Index with the current saved rules, recording their final code digest.
    import importlib
    importlib.reload(n)
    dest=n.OUT/'research'; dest.mkdir(exist_ok=True)
    original_ids=collections.defaultdict(list)
    for r in json.loads((b.PRIVATE/'original_to_document.json').read_text('utf-8')):
        original_ids[r['sha256']].append(r['target_id'])
    groups=collections.defaultdict(list); counts=collections.Counter(); samples=collections.defaultdict(list)
    by_source=collections.defaultdict(collections.Counter); by_year=collections.defaultdict(collections.Counter)
    for cohort,path in [('original_recovery',b.PRIVATE/'fulltexts.jsonl.gz'),('new_library',n.PRIVATE/'new_fulltexts.jsonl.gz')]:
        outpath=dest/(cohort+'_evidence_index.jsonl.gz')
        bodypath=dest/(cohort+'_primary_candidates.jsonl.gz')
        with gzip.open(path,'rt',encoding='utf-8') as source,gzip.open(outpath,'wb') as idx,gzip.open(bodypath,'wb') as body:
            for line in source:
                doc=json.loads(line); r=record(doc,cohort,original_ids)
                # Ingestion labels such as GDELT are not publishers. Use the
                # retrieved original host for publisher grouping, retaining
                # the source label separately without inventing a legal name.
                r['source_label']=r['publisher']
                r['publisher_domain']=p.host(r['publisher_url']).removeprefix('www.')
                r['publisher']=r['publisher_domain']
                r['processing_version']=doc.get('processing_version')
                r['offline_revision']=doc.get('offline_revision')
                r['completion_review']=doc.get('completion_review')
                r['followup_review']=doc.get('followup_review')
                r['original_record_date_raw']=doc.get('date')
                r['publisher_page_date_raw']=(doc.get('resolved_identity') or {}).get('source_date')
                r['publication_date_basis']='publisher_api_field' if doc.get('source_published_at') else 'original_database_timestamp'
                idx.write(p.jsonbytes(r)+b'\n'); counts[cohort]+=1
                if counts[cohort]%1000==0: print(json.dumps({'indexing':cohort,'records':counts[cohort]}),flush=True)
                groups[r['normalized_text_sha256']].append({'cohort':cohort,'document_id':r['document_id'],'text_sha256':r['text_sha256']})
                by_source[cohort][r['publisher']]+=1; by_year[cohort][str(r['published_at_raw'])[:4]]+=1
                counts[cohort+'_missing_utc']+=r['published_at_utc'] is None
                if r['primary_research_candidate']:
                    body.write(p.jsonbytes(doc)+b'\n'); counts[cohort+'_primary_candidates']+=1
                sample={k:r[k] for k in ('cohort','document_id','publisher_url','title','text_characters','quality_flags','text_sha256','primary_research_candidate')}
                key=(cohort,r['publisher']); samples[key].append(sample)
                samples[key]=sorted(samples[key],key=lambda x:x['text_sha256'])[:3]
    n.state_write(dest/'normalized_duplicate_groups.json',{k:v for k,v in groups.items() if len(v)>1})
    n.state_write(dest/'review_sample.json',[x for group in samples.values() for x in group])
    versions={}
    for name in ('trafilatura','beautifulsoup4','lxml','charset-normalizer','certifi'):
        try: versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name]='not_installed'
    codefiles=['scripts/fulltext_pilot.py','scripts/bulk_fulltext.py','scripts/collect_public_fulltext_library.py','scripts/build_fulltext_research_index.py','scripts/audit_fulltext_delivery.py','src/climate_agent/publisher_recovery.py']
    manifest={'generated_at':p.stamp(),'counts':dict(counts),'combined_normalized_unique_bodies':len(groups),'normalized_duplicate_groups':sum(len(v)>1 for v in groups.values()),'by_source':{k:dict(v) for k,v in by_source.items()},'by_year':{k:dict(sorted(v.items())) for k,v in by_year.items()},'python_version':sys.version.split()[0],'dependencies':versions,'code_sha256':{f:p.digest((p.ROOT/f).read_bytes()) for f in codefiles},'inputs_sha256':{str(path.relative_to(p.ROOT)):p.digest(path.read_bytes()) for path in (b.PRIVATE/'fulltexts.jsonl.gz',n.PRIVATE/'new_fulltexts.jsonl.gz')},'checks':['Raw source_text checksums verified','Paragraph offsets reference Unicode code points, not bytes','Original corpus IDs mapped by fulltext hash','No LLM-generated or translated body','UTC unknown remains null; local time is not silently converted'],'limitations':['Primary candidates pass automatic checks, not independent human verification.','Normalized duplicates do not establish absence of near duplicates or syndicated paraphrases.','Source selection and language screening limit representativeness.']}
    for filename in ('scripts/repair_fulltext_interstitials.py','scripts/benchmark_fulltext_replay.py','scripts/check_fulltext_research_delivery.py','scripts/fulltext_review_rules.py','scripts/review_original_fulltexts.py','scripts/benchmark_original_followup.py','scripts/run_original_followup_final_stages.py','scripts/summarize_fulltext_followup.py'):
        manifest['code_sha256'][filename]=p.digest((p.ROOT/filename).read_bytes())
    manifest['code_digest_scope']='Final delivery working copy; early runs did not freeze executable source hashes. Do not treat this as per-record historic execution proof.'
    manifest['request_log_limitation']='An early interrupted run lacks a complete HTTP ledger; complete-run totals are not whole-task exact costs.'
    manifest['raw_asset_path_convention']='Raw acquisition records may contain Windows separators; replace backslashes with forward slashes when replaying on another OS.'
    manifest['publisher_definition']='Evidence-index publisher and by_source groups use the retrieved publisher hostname; source_label preserves the input/feed label, which may be an aggregator. No corporate ownership equivalence is inferred.'
    n.state_write(dest/'research_manifest.json',manifest)
    print(json.dumps({'counts':dict(counts),'combined_normalized_unique_bodies':len(groups)},ensure_ascii=False),flush=True)

if __name__=='__main__': main()

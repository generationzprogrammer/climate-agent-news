"""Deterministic relational research release and structural validation."""
from collections import Counter
import csv
import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/os.environ.get('INNOVATION_RESEARCH_OUTPUT','analysis/innovation_research_20261014')
ARCHIVE_NAME=os.environ.get('INNOVATION_RESEARCH_ARCHIVE','科产融合研究数据_20261014.zip')
def write_json(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def table(name,rows,fields=None):
    fields=fields or list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/'data'/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--refresh',action='store_true',help='Replace a preparation snapshot explicitly; use a new release directory after publication.');args=ap.parse_args()
    source_hash=hashlib.sha256((ROOT/'static/data/innovation_cases.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    old_manifest=OUT/'manifest.json'
    if old_manifest.exists() and json.loads(old_manifest.read_text(encoding='utf-8'))['source_sha256']!=source_hash and not args.refresh:
        raise SystemExit('Frozen snapshot differs: use --refresh only during preparation; published releases require a new version and output directory.')
    (OUT/'data').mkdir(parents=True,exist_ok=True)
    b=json.loads((ROOT/'static/data/innovation_cases.json').read_text(encoding='utf-8'));r=b['research'];cases=b['cases'];sources=b['sources'];sourceids={s['id'] for s in sources}
    assert len({c['id'] for c in cases})==len(cases)
    assert len(sourceids)==len(sources)
    assert len({s['url'] for s in sources})==len(sources)
    case_rows=[];evidence=[];countries=[];factors=[];participants=[];memberships=[]
    fields=['title','summary','actors','mechanism','observed','constraints','transfer']
    for c in cases:
        a=c['research_annotation'];t=c['timeline']
        row={'case_id':c['id'],'grain':a['grain'],'source_cohort':a['cohort'],'primary_model':a['primary_model'],'focus_country':a.get('country'),'continent':a['continent'],'economy':a['economy'],'province':a.get('province'),'city':a.get('city'),'origin_year':t['origin_year'],'origin_basis':t['origin_basis'],'origin_period':t['origin_period'],'origin_decade':t['origin_decade'],'legacy_start_year':t['legacy_start_year'],'end_year':c.get('end_year'),'review_status':c['review_status']}
        for field in fields:
            for language in ('zh','en'):row[field+'_'+language]=c.get(field,{}).get(language)
        row['observation_basis']='registered_project_objectives' if c.get('project') else ('official_registry_unit' if c.get('registry_record') else 'official_institutional_account')
        row['primary_model_basis']='programme_rule' if c.get('project') or c.get('registry_record') else 'editorial_mechanism_code'
        case_rows.append(row)
        for ref in c['evidence']:
            assert ref['source_id'] in sourceids
            for field in ref.get('supports',[]):evidence.append({'case_id':c['id'],'source_id':ref['source_id'],'supported_field':field,'support_type':'editorial_field_link_not_independent_entailment_test'})
        for code in c['countries']:countries.append({'case_id':c['id'],'country_alpha2':code,'is_focus_country':code==a.get('country')})
        for factor in c['factors']:factors.append({'case_id':c['id'],'factor':factor,'coding_type':'registry_rule' if c.get('project') or c.get('registry_record') else 'editorial_structural_code'})
        for item in c.get('participants',[]):participants.append({'case_id':c['id'],**item})
        for org in c['organization_participant_tags']:memberships.append({'case_id':c['id'],'group_id':org,'scope':'documented_participant_country','as_of':'2026-10-14'})
        for org in c['organization_tags']:memberships.append({'case_id':c['id'],'group_id':org,'scope':'focus_country','as_of':'2026-10-14'})
    table('cases.csv',case_rows);table('sources.csv',sources);table('case_sources.csv',evidence);table('case_countries.csv',countries);table('case_factors.csv',factors);table('participants.csv',participants,fields=list(dict.fromkeys(k for row in participants for k in row)) or ['case_id','name','country','type','role'])
    table('chronology.csv',r['chronology']);table('country_group_associations.csv',memberships);table('temporal_counts.csv',r['temporal']);table('factor_pairs.csv',r['factor_pairs'])
    write_json(OUT/'data/taxonomy.json',{'taxonomy':b['taxonomy'],'sector_taxonomy':b['sector_taxonomy'],'archetypes':b['analysis']['archetypes'],'period_labels':r['period_labels'],'organizations':r['organizations'],'participant_types':b['participant_types'],'profile_axes':b['profile_axes']})
    write_json(OUT/'data/cases_nested.json',b)
    registry_rows=[{'case_id':c['id'],'registry':c['registry_record']['registry'],'source_record_key':c['registry_record']['key'],'original_name':c['registry_record']['name'],'record_json':c['registry_record']} for c in cases if c.get('registry_record')]
    if registry_rows:table('registry_records.csv',registry_rows)
    for name in ['innovation_registry_update.json','innovation_registry_history.json']:
        file=ROOT/'data'/name
        if file.exists():write_json(OUT/'data'/name,json.loads(file.read_text(encoding='utf-8')))
    if r.get('review_diagnostics'):
        write_json(OUT/'data/review_diagnostics.json',r['review_diagnostics'])
        review_path=ROOT/'config/innovation_peer_evidence.json'
        if review_path.exists():write_json(OUT/'data/review_evidence.json',json.loads(review_path.read_text(encoding='utf-8')))
    grains=Counter(c['research_annotation']['grain'] for c in cases)
    summary={'version':r['version'],'as_of':r['as_of'],'cases':len(cases),'sources':len(sources),'country_tags':len({code for c in cases for code in c['countries']}),'focus_countries':len({c['research_annotation'].get('country') for c in cases if c['research_annotation'].get('country')}),'grains':dict(grains),'source_cohorts':r['source_strata'],'dated_cases':r['dated_cases'],'china_cases':r['china_cases'],'dated_china_cases':r['dated_china_cases'],'chronology_events':len(r['chronology']),'chronology_cases':len({e['case_id'] for e in r['chronology']}),'origin_year_range':[min(c['timeline']['origin_year'] for c in cases if c['timeline']['origin_year'] is not None),max(c['timeline']['origin_year'] for c in cases if c['timeline']['origin_year'] is not None)],'source_mode_uncertainty_reduction':r['source_mode_uncertainty_reduction'],'platform_models':dict(Counter(c['research_annotation']['primary_model'] for c in cases if c['research_annotation']['grain']=='platform')),'project_models':dict(Counter(c['research_annotation']['primary_model'] for c in cases if c['research_annotation']['grain']=='project')),'checks':{'case_ids_unique':True,'source_ids_unique':True,'source_urls_unique':True,'case_source_foreign_keys_valid':True,'unknown_dates_retained':sum(c['timeline']['origin_year'] is None for c in cases),'previous_754_case_facts':'verified by test_original_facts_preserved','independent_semantic_validation':'not_performed','temporal_review':'single editorial review of cited official statements; not independently rated'},'field_completeness':{f:sum(all(c.get(f,{}).get(l) for l in ('zh','en')) for c in cases) for f in fields}}
    summary['interpretive_notes']=sum(bool(c.get('constraints')) and bool(c.get('transfer')) for c in cases)
    summary['review_diagnostics']=r.get('review_diagnostics',{}).get('audit',{})
    summary['checks']['temporal_review']='AI-assisted editorial reading of official statements; no independent human rater'
    write_json(OUT/'quality_audit.json',summary)
    manifest={'release':r['version'],'generated_from':'static/data/innovation_cases.json','source_sha256':hashlib.sha256((ROOT/'static/data/innovation_cases.json').read_bytes()).hexdigest(),'encoding':'UTF-8; CSV UTF-8 with BOM','missing_values':'empty CSV values or JSON null denote unknown or not coded, never zero','licensing':'Compilation and third-party source rights require separate review before repository deposit. Source webpages are not redistributed as full text.','semantic_validation':'No independent inter-rater reliability or semantic accuracy estimate is claimed.','files':[]}
    dictionary=OUT/'data_dictionary.csv'
    manifest['source_sha256']=source_hash
    manifest['source_hash_normalization']='CRLF converted to LF; no other JSON transformation'
    if dictionary.exists():(OUT/'data/data_dictionary.csv').write_bytes(dictionary.read_bytes())
    if dictionary.exists():
        definitions={}
        for entry in csv.DictReader(dictionary.read_text(encoding='utf-8').splitlines()):
            if None in entry:raise ValueError('Malformed data dictionary')
            for field in entry['field'].split(' and '):definitions[(entry['table'],field)]=entry
        schema={}
        for path in sorted((OUT/'data').glob('*.csv')):
            if path.stem=='data_dictionary':continue
            fields=next(csv.reader(path.read_text(encoding='utf-8-sig').splitlines()))
            missing=[f for f in fields if (path.stem,f) not in definitions]
            if missing:raise ValueError('Undocumented fields '+path.stem+':'+str(missing))
            schema[path.name]={'columns':{f:{k:v for k,v in definitions[(path.stem,f)].items() if k not in ('table','field')} for f in fields}}
        write_json(OUT/'data/schema.json',schema)
    manifest['code_hash_normalization']='CRLF converted to LF; no other source transformation'
    manifest['code_files']=[{'path':name,'sha256':hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()} for name in ['src/climate_agent/innovation_cases.py','src/climate_agent/innovation_research.py','src/climate_agent/innovation_analysis.py','src/climate_agent/innovation_review.py','scripts/build_innovation_chronology.py','scripts/build_innovation_history_cases.py','scripts/build_innovation_peer_review.py','scripts/build_innovation_research_release.py','scripts/build_innovation_figures.py','scripts/collect_innovation_registries.py','scripts/extract_innovation_registry_candidates.py','scripts/update_innovation_registries.py','scripts/build_innovation_live_figures.py']]
    manifest['quality_audit_sha256']=hashlib.sha256((OUT/'quality_audit.json').read_bytes()).hexdigest()
    for path in sorted((OUT/'data').iterdir()):manifest['files'].append({'path':'data/'+path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    write_json(OUT/'manifest.json',manifest)
    with zipfile.ZipFile(OUT/ARCHIVE_NAME,'w',zipfile.ZIP_DEFLATED) as z:
        for path in [*sorted((OUT/'data').iterdir()),OUT/'manifest.json',OUT/'quality_audit.json']:z.write(path,path.relative_to(OUT))
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()

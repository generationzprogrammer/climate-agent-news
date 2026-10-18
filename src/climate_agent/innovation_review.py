"""Reviewer diagnostics at explicit record and acquisition strata.

Intervals below are deterministic sensitivity ranges, not sampling uncertainty.
Absence of a tag is never interpreted as observed absence of a resource.
"""
from collections import Counter
from difflib import SequenceMatcher
from itertools import combinations
import math
import re
import unicodedata

def normalized_title(value):
    return re.sub(r'[^\w]+',' ',unicodedata.normalize('NFKC',value).casefold()).strip()

def diagnostic_tables(book):
    cases=book['cases']; source_map={s['id']:s for s in book['sources']}
    quality=[]
    for dimension in ('grain','cohort','continent'):
        for group in sorted({c['research_annotation'][dimension] for c in cases}):
            subset=[c for c in cases if c['research_annotation'][dimension]==group]
            known=sum(c['timeline']['origin_year'] is not None for c in subset)
            multiple=sum(len({e['source_id'] for e in c['evidence']})>=2 for c in subset)
            multi_publisher=sum(len({source_map[e['source_id']]['publisher'] for e in c['evidence']})>=2 for c in subset)
            quality.append({'dimension':dimension,'group':group,'cases':len(subset),
                'supported_origins':known,'origin_coverage':known/len(subset),
                'multiple_source_cases':multiple,'multiple_publisher_cases':multi_publisher,
                'interpretive_notes':sum(bool(c.get('constraints')) and bool(c.get('transfer')) for c in subset),
                'chronology_cases':sum(bool(c['timeline']['events']) for c in subset)})
    sensitivities=[]
    for grain in ('all','platform','project'):
        base=[c for c in cases if grain=='all' or c['research_annotation']['grain']==grain]
        source_cohorts=sorted({c['research_annotation']['cohort'] for c in base})
        for omitted in [None,*source_cohorts]:
            subset=[c for c in base if c['research_annotation']['cohort']!=omitted]
            counts=Counter(c['research_annotation']['primary_model'] for c in subset)
            for model in book['analysis']['archetypes']:
                n=counts[model['id']]
                sensitivities.append({'grain':grain,'omitted_cohort':omitted or 'none','model':model['id'],
                    'count':n,'denominator':len(subset),'share':n/len(subset) if subset else None})
    factor_sensitivity=[]
    platforms=[c for c in cases if c['research_annotation']['grain']=='platform']
    platform_cohorts=sorted({c['research_annotation']['cohort'] for c in platforms})
    for first,second in combinations(book['taxonomy']['factors'],2):
        rows=[]
        for omitted in [None,*platform_cohorts]:
            subset=[c for c in platforms if c['research_annotation']['cohort']!=omitted]
            both=[c for c in subset if first in c['factors'] and second in c['factors']]
            union=sum(first in c['factors'] or second in c['factors'] for c in subset)
            na=sum(first in c['factors'] for c in subset);nb=sum(second in c['factors'] for c in subset)
            j=len(both)/union if union else None
            rows.append({'omitted_cohort':omitted or 'none','jaccard':j,'count':len(both),
                'denominator':len(subset),'union':union,'first_count':na,'second_count':nb,
                'lift':len(both)*len(subset)/(na*nb) if na and nb else None})
        values=[x['jaccard'] for x in rows[1:] if x['jaccard'] is not None]
        factor_sensitivity.append({'first':first,'second':second,**{k:v for k,v in rows[0].items() if k!='omitted_cohort'},
            'leave_one_cohort_out_min':min(values) if values else None,
            'leave_one_cohort_out_max':max(values) if values else None,
            'range_type':'deterministic_acquisition_sensitivity_not_confidence_interval',
            'source_cohort_results':rows,'case_ids':[c['id'] for c in platforms if first in c['factors'] and second in c['factors']]})
    titles=Counter(normalized_title(c['title']['en']) for c in cases)
    project_keys=Counter((c['research_annotation']['cohort'],c['project'].get('official_id'))
        for c in cases if c.get('project') and c['project'].get('official_id'))
    near=[]
    for first,second in combinations(platforms,2):
        if first['research_annotation'].get('country')!=second['research_annotation'].get('country'):continue
        # Programme suffixes are not entity identity; compare the original unit names.
        a=normalized_title(first.get('registry_record',{}).get('name') or first['title']['en'])
        b=normalized_title(second.get('registry_record',{}).get('name') or second['title']['en'])
        if abs(len(a)-len(b))>max(len(a),len(b))*.25:continue
        if a and b and SequenceMatcher(None,a,b).ratio()>=.88:
            near.append({'first':first['id'],'second':second['id'],'status':'candidate_not_automatically_merged'})
    history=book['research']['chronology']
    institutions_with_origins=sum(c['timeline']['origin_year'] is not None for c in platforms)
    one_source=sum(len({e['source_id'] for e in c['evidence']})==1 for c in cases)
    source_documents={e['source_id'] for c in cases for e in c['evidence']}
    all_linked=source_documents|{sid for e in history for sid in e['source_ids']}|{sid for p in book['analysis']['profiles'] for sid in p['source_ids']}
    audit={'case_count':len(cases),'platform_count':len(platforms),'project_count':len(cases)-len(platforms),
        'single_source_cases':one_source,'single_source_fraction':one_source/len(cases),
        'case_evidence_source_records':len(source_documents),
        'sources_not_linked_to_case_event_or_profile':sorted(set(source_map)-all_linked),
        'source_record_count':len(source_map),'distinct_source_domains':len({__import__('urllib.parse',fromlist=['urlparse']).urlparse(s['url']).netloc.lower() for s in source_map.values()}),
        'supported_institutional_origins':institutions_with_origins,
        'institutional_origin_coverage':institutions_with_origins/len(platforms),
        'duplicate_normalized_titles':[k for k,n in titles.items() if n>1],
        'duplicate_official_project_keys':[list(k) for k,n in project_keys.items() if n>1],
        'near_duplicate_candidates':near,'independent_semantic_validation':'not_performed',
        'review_agent':'AI-assisted editorial review; not an independent human reviewer',
        'historical_model_coding':'current_case_archetype_not_reconstructed_event_level_mechanism',
        'resource_absence_semantics':'not_coded_does_not_mean_absent',
        'outcome_variables':'not_harmonised; no causal or performance inference'}
    return {'quality':quality,'model_sensitivity':sensitivities,'factor_sensitivity':factor_sensitivity,'audit':audit}

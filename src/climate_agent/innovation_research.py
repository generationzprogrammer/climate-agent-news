"""Versioned research annotations without rewriting reviewed case facts.

Origin cohorts, dated observations and contemporary country-group membership
are deliberately separate. None measures innovation performance or causality.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
import copy
import json
import math
from pathlib import Path

PLAN_NAMES = {6:'六五',7:'七五',8:'八五',9:'九五',10:'十五',11:'十一五',12:'十二五',13:'十三五',14:'十四五',15:'十五五'}


def decade(year):
    return f'{year // 10 * 10}s' if isinstance(year, int) and not isinstance(year, bool) else None


def china_plan(year):
    if not isinstance(year, int) or isinstance(year, bool):
        return None
    if year < 1981:
        return 'pre_1981'
    number = (year - 1981) // 5 + 6
    return f'cn_fyp_{number}' if number in PLAN_NAMES else None


def period_labels(years):
    labels = {'undated':{'zh':'时间未核验','en':'Undated'}}
    for year in sorted(years):
        start = year // 10 * 10
        labels[f'{start}s'] = {'zh':f'{start}年代','en':f'{start}s'}
    labels['pre_1981'] = {'zh':'六五以前','en':'Before the sixth plan'}
    for number, name in PLAN_NAMES.items():
        start = 1981 + (number - 6) * 5
        labels[f'cn_fyp_{number}'] = {'zh':f'{name}（{start}—{start+4}）','en':f'{number}th five-year plan ({start}–{start+4})'}
    return labels


def entropy(values):
    total = len(values)
    return -sum((n/total)*math.log2(n/total) for n in Counter(values).values()) if total else 0.0


def period_sort(period):
    if period == 'undated':
        return 9999
    if period == 'pre_1981':
        return 0
    return 1981 + (int(period.rsplit('_',1)[1])-6)*5 if period.startswith('cn_fyp_') else int(period[:-1])


def annotate_research(book, config, chronology, *, as_of):
    """Add source-grounded editorial annotations; return the chronology."""
    byid = {c['id']:c for c in book['cases']}
    source_ids = {s['id'] for s in book['sources']}
    known_events, event_ids = defaultdict(list), set()
    for item in chronology.get('events', []):
        event = copy.deepcopy(item)
        cid = event['case_id']
        if cid not in byid or event['id'] in event_ids:
            raise ValueError('innovation_chronology_identity:'+event['id'])
        event_ids.add(event['id'])
        value = event['date']
        precision = event['date_precision']
        if precision not in {'year','month','day'} or len(value) != {'year':4,'month':7,'day':10}[precision]:
            raise ValueError('innovation_chronology_precision:'+event['id'])
        try:
            parsed = date.fromisoformat(value + {'year':'-01-01','month':'-01','day':''}[precision])
        except ValueError as error:
            raise ValueError('innovation_chronology_date:'+event['id']) from error
        if parsed > as_of or not event.get('source_ids') or not set(event['source_ids']) <= source_ids:
            raise ValueError('innovation_chronology_evidence:'+event['id'])
        if event.get('review_status') != 'reviewed' or not all(event.get('description',{}).get(l) for l in ('zh','en')):
            raise ValueError('innovation_chronology_review:'+event['id'])
        if event['kind'] not in {'establishment','launch','expansion','institutional_change','demonstration','documented_activity'}:
            raise ValueError('innovation_chronology_kind:'+event['id'])
        event['year'] = parsed.year
        event['decade'] = decade(parsed.year)
        event['china_plan'] = china_plan(parsed.year) if byid[cid]['research_annotation'].get('country') == 'CN' else None
        known_events[cid].append(event)
    flattened = []
    for case in book['cases']:
        cid, annotation = case['id'], case['research_annotation']
        events = sorted(known_events[cid], key=lambda e:(e['date'],e['id']))
        starts = [e for e in events if e.get('origin_basis')]
        if len(starts) > 1:
            raise ValueError('multiple_innovation_origins:'+cid)
        year = case.get('start_year')
        year_sources = [e['source_id'] for e in case['evidence'] if 'start_year' in e.get('supports',[])]
        if case.get('project'):
            year_sources = [case['evidence'][0]['source_id']]
        if starts:
            if year is not None and year != starts[0]['year']:
                raise ValueError('innovation_origin_conflict:'+cid)
            year, year_sources = starts[0]['year'], starts[0]['source_ids']
            basis = 'reviewed_chronology'
        else:
            basis = 'reviewed_register_start' if case.get('project') else 'legacy_reviewed_start'
        if year is not None and (not isinstance(year,int) or isinstance(year,bool) or year < 1800 or year > as_of.year):
            raise ValueError('innovation_origin_year:'+cid)
        # Legacy dates remain visible, but dates with no field-level source or
        # register support are excluded from the strict temporal research view.
        verified_year = year if year_sources else None
        is_china = annotation.get('country') == 'CN'
        memberships = [o['id'] for o in config['organizations'] if annotation.get('country') in o['country_members']]
        any_memberships = [o['id'] for o in config['organizations'] if set(case['countries']) & set(o['country_members'])]
        case['timeline'] = {'origin_year':verified_year,'legacy_start_year':case.get('start_year'),
          'origin_basis':basis if verified_year is not None else 'not_verified',
          'origin_source_ids':year_sources,'origin_decade':decade(verified_year),
          'origin_china_plan':china_plan(verified_year) if is_china else None,
          'origin_period':(china_plan(verified_year) if is_china else decade(verified_year)) or 'undated',
          'events':events,'activity_periods':sorted({(e['china_plan'] if is_china else e['decade']) for e in events}),
          'country_group_basis':'documented_focus_country', 'interpretation':'origin_cohort_not_period_activity'}
        case['organization_tags'] = memberships
        case['organization_participant_tags'] = any_memberships
        case['organization_basis'] = 'current_country_membership_not_organisation_sponsorship'
        flattened.extend(events)
    return flattened


def temporal_rows(cases, events, labels):
    rows = []
    for grain in ('platform','project'):
        base = [c for c in cases if c['research_annotation']['grain'] == grain]
        for scope in ('global_decades','china_plans'):
            subset = [c for c in base if scope != 'china_plans' or c['research_annotation'].get('country') == 'CN']
            field = 'origin_decade' if scope == 'global_decades' else 'origin_china_plan'
            groups = defaultdict(list)
            for c in subset:
                groups[c['timeline'][field] or 'undated'].append(c)
            for period, members in sorted(groups.items(),key=lambda p:period_sort(p[0])):
                models = Counter(c['research_annotation']['primary_model'] for c in members)
                rows.append({'grain':grain,'scope':scope,'basis':'origin','period':period,
                  'label':labels[period],'count':len(members),'denominator':len(subset),
                  'models':dict(models),'case_ids':[c['id'] for c in members],
                  'source_cohorts':dict(Counter(c['research_annotation']['cohort'] for c in members))})
            ids = {c['id'] for c in subset}
            event_groups = defaultdict(list)
            for event in events:
                if event['case_id'] in ids:
                    period = event['decade'] if scope == 'global_decades' else event['china_plan']
                    event_groups[period].append(event)
            for period, members in sorted(event_groups.items(),key=lambda p:period_sort(p[0])):
                case_ids = sorted({e['case_id'] for e in members})
                rows.append({'grain':grain,'scope':scope,'basis':'activity','period':period,'label':labels[period],
                  'count':len(case_ids),'events':len(members),'denominator':len(subset),'case_ids':case_ids,
                  'models':dict(Counter(next(c for c in subset if c['id']==cid)['research_annotation']['primary_model'] for cid in case_ids)),
                  'event_ids':[e['id'] for e in members]})
    return rows


def factor_pairs(cases, taxonomy):
    rows = []
    for grain in ('platform','project'):
        subset = [c for c in cases if c['research_annotation']['grain'] == grain]
        totals = Counter(f for c in subset for f in set(c['factors']))
        for first, second in combinations(taxonomy['factors'],2):
            support = [c for c in subset if first in c['factors'] and second in c['factors']]
            n, total = len(support), len(subset)
            union = totals[first] + totals[second] - n
            rows.append({'grain':grain,'first':first,'second':second,'count':n,'denominator':total,
              'first_count':totals[first],'second_count':totals[second],
              'jaccard':n/union if union else None,
              'lift':n*total/(totals[first]*totals[second]) if totals[first] and totals[second] else None,
              'source_cohorts':dict(Counter(c['research_annotation']['cohort'] for c in support)),
              'case_ids':[c['id'] for c in support]})
    return rows


def build_research(book, root, *, as_of):
    path = root / 'config/innovation_research_framework.json'
    if not path.exists():
        return
    config = json.loads(path.read_text(encoding='utf-8'))
    as_of = max(as_of, date.fromisoformat(config['reviewed_at']))
    history_path = root / 'config/innovation_chronology.json'
    history = json.loads(history_path.read_text(encoding='utf-8')) if history_path.exists() else {'events':[],'sources':[]}
    existing = {s['id']:s for s in book['sources']}
    urls = {s['url']:s['id'] for s in book['sources']}
    for source in history.get('sources',[]):
        if source['id'] in existing:
            if source != existing[source['id']]:
                raise ValueError('innovation_history_source_conflict:'+source['id'])
        elif source['url'] in urls:
            raise ValueError('innovation_history_duplicate_url:'+source['id'])
        else:
            book['sources'].append(source)
            existing[source['id']] = source
            urls[source['url']] = source['id']
    events = annotate_research(book, config, history, as_of=as_of)
    years = {e['year'] for e in events} | {c['timeline']['origin_year'] for c in book['cases'] if c['timeline']['origin_year'] is not None}
    labels = period_labels(years)
    cases = book['cases']
    cohorts = []
    for cohort in sorted({c['research_annotation']['cohort'] for c in cases}):
        subset = [c for c in cases if c['research_annotation']['cohort'] == cohort]
        cohorts.append({'cohort':cohort,'count':len(subset),
          'dated':sum(c['timeline']['origin_year'] is not None for c in subset),
          'models':dict(Counter(c['research_annotation']['primary_model'] for c in subset))})
    total_entropy = entropy([c['research_annotation']['primary_model'] for c in cases])
    conditional_entropy = sum(row['count']/len(cases)*entropy([c['research_annotation']['primary_model'] for c in cases if c['research_annotation']['cohort']==row['cohort']]) for row in cohorts)
    organizations = []
    for organization in config['organizations']:
        row = copy.deepcopy(organization)
        row['focus_case_ids'] = [c['id'] for c in cases if row['id'] in c['organization_tags']]
        row['participant_case_ids'] = [c['id'] for c in cases if row['id'] in c['organization_participant_tags']]
        organizations.append(row)
    book['research'] = {'version':config['version'],'as_of':as_of.isoformat(),
      'literature':config['literature'],'model_tradeoffs':config['model_tradeoffs'],
      'organizations':organizations,'period_labels':labels,'chronology':events,
      'temporal':temporal_rows(cases,events,labels),'factor_pairs':factor_pairs(cases,book['taxonomy']),
      'source_strata':cohorts,'mode_entropy_bits':total_entropy,
      'mode_entropy_given_source_bits':conditional_entropy,
      'source_mode_uncertainty_reduction':1-conditional_entropy/total_entropy if total_entropy else None,
      'dated_cases':sum(c['timeline']['origin_year'] is not None for c in cases),
      'china_cases':sum(c['research_annotation'].get('country')=='CN' for c in cases),
      'dated_china_cases':sum(c['research_annotation'].get('country')=='CN' and c['timeline']['origin_year'] is not None for c in cases),
      'limitations':{'zh':'起始阶段描述本库收录案例的设立时间，活动阶段只计有日期证据的实践。两者均非历史普查。组织筛选采用2026年10月核验的现行成员国口径，组间可重叠，不表示组织主办。要素共现仅为描述性关联。',
        'en':'Origin cohorts describe establishment dates in this catalogue; activity cohorts require dated evidence. Neither is a historical census. Group filters use contemporary country membership verified in October 2026, overlap, and do not imply sponsorship. Factor co-occurrence is descriptive.'}}
    watch_path=root/'data/innovation_watch.json'
    watch=json.loads(watch_path.read_text(encoding='utf-8')) if watch_path.exists() else {}
    book['research']['update_policy']={'cadence':'weekly_source_watch_daily_chart_rebuild','last_watch':watch.get('updated_at'),'pending_candidates':len(watch.get('candidates',[])),'persistent_news_observations':len(watch.get('observations',[])),'promotion':'editorial_review_required','model_api_calls':0}
    from .innovation_review import diagnostic_tables
    book['research']['review_diagnostics'] = diagnostic_tables(book)
    book['reviewed_at'] = max(book['reviewed_at'],config['reviewed_at'],history.get('reviewed_at',''))

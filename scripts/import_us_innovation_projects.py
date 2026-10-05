"""Import only explicitly compiled US research-industry project reviews."""
import collections
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from select_us_innovation_projects import CACHE, ROOT

sys.path.insert(0, str(ROOT / 'src'))
from climate_agent.innovation_metrics import profile_metrics

SECTORS = {
    'nuclear': {'zh': '核裂变与核聚变', 'en': 'Fission and fusion'},
    'transport': {'zh': '交通动力与电气化', 'en': 'Transport and electrification'},
    'digital': {'zh': '数字能源与计算能效', 'en': 'Digital energy and computing efficiency'},
}
TYPES = {'University': 'HES', 'Private Company': 'PRC', 'National Laboratory': 'REC',
         'Government Laboratory': 'REC', 'Non-Profit': 'OTH'}


def iso(value):
    if not value:
        return None
    for pattern in ('%b %d %Y','%Y-%m-%d'):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            pass
    raise ValueError('Unexpected official project date')


def read_reviews(path):
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        fields = [x.strip() for x in line.split('|')]
        if len(fields) != 4 or fields[0] in result:
            raise ValueError('Each review needs unique ID, Chinese title, focus and interface')
        nid, title, focus, interface = fields
        if not all(re.search(r'[\u4e00-\u9fff]', x) for x in (title, focus, interface)):
            raise ValueError('Chinese technical compilation required: ' + nid)
        if len(focus) < 45 or len(interface) < 15:
            raise ValueError('Insufficient substantive compilation: ' + nid)
        result[nid] = (title, focus, interface)
    return result


def build():
    rows = json.loads((CACHE / 'candidates.json').read_text(encoding='utf-8'))
    candidates = {r['id']: r for r in rows}
    reviews = read_reviews(ROOT / 'config/innovation_us_review.txt')
    prior = json.loads((ROOT / 'config/open_innovation_projects.json').read_text(encoding='utf-8'))
    sectors = {**prior['sector_taxonomy'], **SECTORS}
    exclusions = json.loads((ROOT/'config/innovation_us_exclusions.json').read_text(encoding='utf-8'))
    omitted = {(r['official_node'],r['partner_label_sha256']) for r in exclusions['public_partner_omissions']}
    sector_review = json.loads((ROOT/'config/innovation_us_sector_review.json').read_text(encoding='utf-8'))['overrides']
    if set(reviews).intersection(r['official_node'] for r in exclusions['excluded_candidates']):
        raise ValueError('Excluded candidate must not be published')
    cases, sources = [], []
    for nid, (title, focus, interface) in reviews.items():
        r = candidates[nid]
        r['sector'] = sector_review.get(nid,r['sector'])
        sid = 's_arpae_' + nid
        source = {'id': sid, 'url': r['url'], 'title': r['title'], 'publisher': 'U.S. Department of Energy · ARPA-E',
                  'language': 'en', 'reviewed_at': '2026-10-05', 'published_date': iso(r['date']),
                  'access': 'official_project_metadata_and_chinese_compilation', 'source_role': 'primary',
                  'snapshot_url': r['snapshot']['url'], 'snapshot_sha256': r['snapshot']['sha256'],
                  'fetched_at_utc': r['snapshot']['fetched_at_utc'],
                  'snapshot_parse_basis': r['snapshot'].get('parse_basis','complete_page'),
                  'rights_url': 'https://www.energy.gov/web-policies', 'parser_version': 'arpae-project-1.0'}
        start, end = iso(r['start']), iso(r['end'])
        amount = float(str(r['award']).replace(',', '')) if r['award'] else None
        participants = [{'id': 'arpae_'+nid+'_lead', 'name': r['lead'], 'country': 'US',
                         'type': TYPES[r['lead_type']], 'role': 'coordinator'}]
        names = {r['lead'].casefold()}
        for partner in r['partners']:
            if partner.casefold() in names or (nid,hashlib.sha256(partner.encode()).hexdigest()) in omitted:
                continue
            names.add(partner.casefold())
            # Public partners are named, but country/type/completeness are not registered.
            participants.append({'id': 'arpae_'+nid+'_'+hashlib.sha256(partner.encode()).hexdigest()[:12],
                                 'name': partner, 'country': None, 'type': None, 'role': 'participant'})
        program = ', '.join(r['programs'])
        actors_zh = r['lead'] + '；合作单位：' + '、'.join(p['name'] for p in participants[1:]) + '。'
        original_excerpt = r['description'][:600].rsplit(' ', 1)[0] + '…'
        project = {'source_type': 'ARPAE', 'official_id': 'ARPA-E node '+nid, 'acronym': None,
                   'programme': 'ARPA-E · '+program, 'action': program,
                   'start_date': start, 'end_date': end, 'register_status': r['status'],
                   'award_usd': amount, 'funding_basis': 'listed_ARPAE_award_not_actual_expenditure',
                   'coordinator_name': r['lead'], 'coordinator_country': 'US', 'coordinator_type': TYPES[r['lead_type']],
                   'lead_state': r['state'], 'participant_count': None, 'country_count': None,
                   'company_count': None, 'research_count': None, 'actor_type_count': None,
                   'participant_list_basis': 'public_named_partners_not_guaranteed_complete'}
        case = {'id': 'oi_arpae_'+nid, 'kind': 'project', 'title': {'zh': title, 'en': r['title']},
                'countries': ['US'], 'scope': 'national', 'sector_key': r['sector'], 'sector': sectors[r['sector']],
                'aliases': [r['title'], title], 'challenges': ['factor', 'adaptation'],
                'modes': ['translation'], 'institutions': ['research'], 'factors': ['knowledge','capital','market'],
                'start_year': int(start[:4]) if start else None, 'end_year': int(end[:4]) if end else None,
                'review_status': 'structured_verified', 'summary': {'zh': focus, 'en': original_excerpt},
                'actors': {'zh': actors_zh, 'en': r['lead']+'; named partners: '+'; '.join(p['name'] for p in participants[1:])},
                'mechanism': {'zh': interface, 'en': 'ARPA-E '+program+' research collaboration led by '+r['lead']+' with the named partners.'},
                'observed': {'zh': 'ARPA-E项目 '+nid+'，'+program+'计划。'+
                             ('登记资助'+f'{amount:,.0f}'+'美元；' if amount is not None else '')+
                             ('项目期'+start+'至'+end+'；' if start and end else '')+
                             '官网状态为'+('进行中。' if r['status']=='Active' else '历史项目。'),
                             'en': 'ARPA-E project '+nid+', '+program+'. '+
                             ('Listed award: USD '+f'{amount:,.0f}'+'. ' if amount is not None else '')+
                             'Technical objectives are not achieved performance or commercial output.'},
                'project': project, 'participants': participants, 'profile': profile_metrics(project, sid),
                'evidence': [{'source_id': sid, 'supports': ['summary','actors','mechanism','observed','project','participants']}],
                'editorial': {'title_and_focus': 'reviewed_chinese_compilation', 'original_language': 'en',
                              'country_basis': 'official_US_lead_state_not_inferred_partner_countries'}}
        cases.append(case)
        sources.append(source)
    payload = {'schema_version':'1.0', 'reviewed_at':'2026-10-05', 'cases':cases,'sources':sources,
               'sector_taxonomy': SECTORS, 'provenance': {'ARPAE': {
                   'source': 'https://arpa-e.energy.gov/programs-and-initiatives/search-all-projects',
                   'retrieval': 'official_public_site_JSON_API_cached_complete_pages',
                   'grain': 'one_official_project_node', 'eligibility': 'US lead; named research-industry interface; technical task; Active or Alumni',
                   'review_register': 'config/innovation_us_review.txt', 'countries': 'US lead affiliation; unverified partner country null',
                   'profile_policy': 'no comparable complete participant census or EUR grant; no score imputation',
                   'raw_contact_data': 'not_published', 'new_model_api_calls':0}}}
    (ROOT/'config/open_innovation_us_projects.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'imported':len(cases),'sectors':dict(collections.Counter(r['sector_key'] for r in cases))}))


if __name__ == '__main__':
    build()

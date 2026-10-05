"""Conservative candidate selection; publication still requires Chinese review."""
import argparse
import collections
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'tmp/us-innovation'


def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', str(value or '')))).strip()


def classify(title, description):
    rules = [
        ('heat', r'\bthermal batter|geothermal|datacenter|data.center|\bcooling\b'),
        ('battery', r'batter|electrolyte|energy storage|supercapacitor'),
        ('hydrogen', r'hydrogen|fuel.cell|ammonia|electroly[sz]|electrofuel'),
        ('nuclear', r'\bnuclear\b|\bfusion\b|\bfission\b|reactor.*(molten|salt|neutron)|tokamak'),
        ('solar', r'solar|photovoltaic'),
        ('wind', r'\bwind\b|hydrokinetic|wave.energy|ocean.energy|tidal'),
        ('grid', r'electric.*grid|microgrid|power.electronic|power.system|transformer|transmission|distribution'),
        ('heat', r'heat|thermal|cooling|refrigerat|geothermal|air.condition'),
        ('transport', r'engine|vehicle|transportation|motor|aviation|aircraft'),
        ('industry', r'carbon|biofuel|biomass|manufactur|methane|cement|steel|critical.mineral|rare.earth|metall|alumin|energy|electric')
    ]
    for text in (title.lower(), description.lower()):
        for key, pattern in rules:
            if re.search(pattern, text):
                return key
    return None


def candidates(rows):
    accepted, excluded, seen = [], collections.Counter(), set()
    known_company = {clean(o['attributes']['title']).casefold() for row in rows
                     for o in row.get('attributes', {}).get('fields', {}).get('organization', [])
                     if any(t['name'] == 'Private Company' for t in o.get('fields', {}).get('type', []))}
    for row in rows:
        a = row.get('attributes', {})
        f = a.get('fields', {})
        title = clean(a.get('title'))
        norm = re.sub(r'[^a-z0-9]', '', title.casefold())
        lead = f.get('organization') or []
        partners = [clean(p.get('value')) for p in f.get('partner_organizations', []) if clean(p.get('value'))]
        description = clean(f.get('project_description'))
        types = [t['name'] for x in lead for t in x.get('fields', {}).get('type', [])]
        # Require a named industrial and research interface, not just an award.
        lead_research = any(t in ('University', 'National Laboratory', 'Federally Funded Research and Development Center') for t in types)
        lead_company = 'Private Company' in types
        research_pattern = r'university|college|institut|laborator|polytechnic|Georgia Tech|Research Foundation|Alliance for Sustainable Energy|\bNREL\b|\bORNL\b|\bPNNL\b|\bMIT\b|\bANL\b|\bLBNL\b'
        partner_research = any(re.search(research_pattern, x, re.I) for x in partners)
        partner_company = any(not re.search(research_pattern, x, re.I) and (
            x.casefold() in known_company or re.search(r'\b(inc|llc|corp|corporation|company|ltd|limited|gmbh)\b|\b(General Electric|Ford|Siemens|Boeing|Chevron|Schlumberger|Honeywell|Cummins|Caterpillar|Bosch|ABB|Shell|3M)\b', x, re.I)) for x in partners)
        sector = classify(title, description)
        reason = ('duplicate_title' if norm in seen else
                  'no_named_science_industry_interface' if not ((lead_research and partner_company) or (lead_company and partner_research)) else
                  'no_us_location' if f.get('state') not in {'AL','AK','AZ','AR','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY'} else
                  'selected_only' if f.get('status') not in ('Active', 'Alumni') else
                  'insufficient_technical_evidence' if len(description) < 180 else
                  'not_energy' if not sector else None)
        if reason:
            excluded[reason] += 1
            continue
        seen.add(norm)
        accepted.append({'id': str(a['drupal_internal__nid']), 'title': title, 'sector': sector,
                         'lead': clean(lead[0]['attributes']['title']), 'lead_type': types[0],
                         'partners': list(dict.fromkeys(partners)), 'description': description,
                         'state': f['state'], 'status': f['status'], 'date': f.get('release_date'),
                         'start': f.get('term_start'), 'end': f.get('term_end'), 'award': f.get('award'),
                         'programs': [x['attributes']['title'] for x in f.get('related_programs', [])],
                         'url': 'https://arpa-e.energy.gov' + a['urls'][0], 'snapshot': row['_snapshot']})
    return accepted, dict(excluded)


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--inspect', action='store_true')
    args = cli.parse_args()
    rows = json.loads((CACHE / 'projects.json').read_text(encoding='utf-8'))
    accepted, excluded = candidates(rows)
    (CACHE / 'candidates.json').write_text(json.dumps(accepted, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'fetched': len(rows), 'eligible': len(accepted), 'excluded': excluded,
                      'sectors': dict(collections.Counter(x['sector'] for x in accepted)),
                      'lead_types': dict(collections.Counter(x['lead_type'] for x in accepted))}, ensure_ascii=False))
    if args.inspect:
        for x in accepted:
            print(x['id'] + ' | ' + x['title'] + ' | ' + x['lead'] + ' + ' + '; '.join(x['partners']) + ' | ' + x['description'][:700])

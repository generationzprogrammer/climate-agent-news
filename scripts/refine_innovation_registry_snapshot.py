"""One-time reproducible refinement of the initial official-directory admission."""
import csv,json
from update_innovation_registries import ROOT,CACHE,OUT,source,build_case,identity

def main():
    layer=json.loads(OUT.read_text(encoding='utf-8'))
    rows=json.loads((CACHE/'candidates.json').read_text(encoding='utf-8'))
    practices=json.loads((ROOT/'config/innovation_registry_practices.json').read_text(encoding='utf-8'))
    for r in csv.DictReader((ROOT/'config/innovation_registry_china.tsv').read_text(encoding='utf-8').splitlines(),delimiter='\t'):
        key='china_moe_first_list' if r['batch']=='1' else 'china_moe_second_list'
        if r['name'] in practices:r.update(practice=practices[r['name']]['zh'],practice_en=practices[r['name']]['en'])
        rows.append(dict(r,key=identity(key,r['name']),registry=key,country='CN'))
    bykey={r['key']:r for r in rows};translations=json.loads((ROOT/'config/innovation_registry_translations.json').read_text(encoding='utf-8'))
    for old in layer['cases']:
        revised=build_case(bykey[old['registry_record']['key']],translations)
        # Preserve programme and practice citations resolved during admission.
        revised['evidence']=old['evidence'];old.clear();old.update(revised)
    layer['sources']=[source(s['id'].removeprefix('s_registry_')) for s in layer['sources']]
    OUT.write_text(json.dumps(layer,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()

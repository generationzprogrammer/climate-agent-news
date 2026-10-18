"""Incremental official-register admission, with conservative evidence and no deletions.

The programme unit is a case, not its parent university or funding agency.
Raw pages are private; only whitelisted organisational metadata are published.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,sys
from collections import Counter
from datetime import datetime,timezone,date
from pathlib import Path
from urllib.parse import urlsplit
from collect_innovation_registries import ROOT,CACHE,SOURCES,collect
from extract_innovation_registry_candidates import nsf,embrapii,australia,africa,japan,identity

OUT=ROOT/'config/open_innovation_registries.json'
TODAY=date.today().isoformat()
PROGRAMMES={'nsf_iucrc':'nsf_programme','embrapii_export':'embrapii_programme','australia_crcp':'au_programme','jst_coinext':'jst_programme','africa_ace':'ace_programme'}
LABELS={'nsf_iucrc':('美国国家科学基金会产学合作研究中心','US National Science Foundation IUCRC'),
 'nsf_programme':('NSF产学合作研究中心运行机制','NSF IUCRC university participation and operating model'),
 'embrapii_programme':('EMBRAPII合作与资助规则','EMBRAPII cooperation and funding rules'),
 'au_programme':('澳大利亚CRC-P项目合作与资助条件','Australian CRC-P eligibility and funding rules'),
 'jst_programme':('JST共创平台计划概要','JST COI-NEXT programme outline'),
 'ace_programme':('非洲卓越中心影响计划说明','ACE Impact programme and industry partnerships'),
 'china_moe_experience':('教育部首批技术转移基地典型经验','MOE technology-transfer base practices'),
 'embrapii_export':('巴西工业研究与创新公司认证单元','EMBRAPII accredited research units'),
 'australia_crcp':('澳大利亚合作研究中心项目计划','Australian CRC-P grants'),
 'africa_ace':('非洲卓越中心影响计划','Africa Centres of Excellence Impact'),
 'africa_ace2':('东部与南部非洲卓越中心产业计划','Eastern and Southern Africa ACE II industry centres'),
 'jst_coinext':('日本科学技术振兴机构共创平台计划','JST COI-NEXT'),
 'china_moe_first_list':('教育部首批高校科技成果转化和技术转移基地','MOE first technology-transfer base designation'),
 'china_moe_second_list':('教育部第二批高校科技成果转化和技术转移基地','MOE second technology-transfer base designation')}
SECTORS={
 'digital':('数字技术与智能系统','Digital and intelligent systems'),
 'materials':('新材料与工程验证','Materials and engineering validation'),
 'manufacturing':('先进制造','Advanced manufacturing'),
 'biomanufacturing':('生物制造与食品工程','Biomanufacturing and food engineering'),
 'energy_systems':('能源系统与碳中和','Energy systems and carbon neutrality'),
 'applied_innovation':('应用技术与产业创新','Applied research and industrial innovation'),
 'environment':('环境与资源工程','Environment and resource engineering'),
 'health':('医疗技术与药物开发','Medical technologies and drug development')}
def bilingual(zh,en):return {'zh':zh,'en':en}
def norm(x):return re.sub(r'[^\w]','',x.casefold())
def register_date(value):
    if '/' in value:return datetime.strptime(value,'%d/%m/%Y').date()
    day,month,year=value.split();month=month[:3]
    return datetime.strptime(day+' '+month+' '+year,'%d %b %Y').date()
def sector(r):
    # Primary technical focus, not every word in an organisation's name.
    t=' '.join(r.get('focus',[])) or r['name'];t=t.casefold()
    groups=[('energy_systems','energ|solar|battery|batteries|hydrogen|carbon|power|petrol|óleo|eletroqu|電池|エネルギー|カーボン|電力'),('environment','water|waste|sustainab|environ|recycl|mining|minera|florest|環境|循環|流域|海洋|資源'),('health','health|medic|drug|fármac|saúde|biomol|健康|医療|生命'),('biomanufacturing','bio|agro|agri|food|aliment|crop|plant|畜|和牛|バイオ|養殖'),('digital','comput|information|communication|software|intelig|digital|IoT|sensing|sensori|quantum|量子|AI|データ'),('materials','material|nano|poly|polímero|aço|ligas'),('manufacturing','manufact|manufat|automation|robót|mecân|potência|powertrain|mobil|industrial')]
    return next((k for k,p in groups if re.search(p,t,re.I)),'applied_innovation')
def source(key):
    a=json.loads((CACHE/(key+'.audit.json')).read_text(encoding='utf-8'))
    label=LABELS.get(key,(key,key))[1]
    publisher=next((v for p,v in [('nsf','US National Science Foundation'),('embrapii','EMBRAPII'),('australia','Australian Government'),('au_','Australian Government'),('jst','Japan Science and Technology Agency'),('africa_ace2','IUCEA'),('africa_ace','Association of African Universities'),('ace_','Association of African Universities'),('china','Ministry of Education of China')] if key.startswith(p)),label)
    return dict(id='s_registry_'+key,title=label,publisher=publisher,url=SOURCES[key],language={'embrapii_export':'pt','embrapii_programme':'pt','jst_coinext':'ja','jst_programme':'ja','africa_ace':'en/fr'}.get(key,'zh' if key.startswith('china') else 'en'),reviewed_at=a['fetched_at_utc'][:10],retrieved_at=a['fetched_at_utc'],content_sha256=a['sha256'],robots_status=a['robots_status'])

def build_case(r,translations):
    key=r['registry'];sid='s_registry_'+key;kind=sector(r);zhfocus,enfocus=SECTORS[kind]
    name=r['name'];label=LABELS[key];loc=r.get('location','');hosts=r.get('institutions',[])
    tr=translations.get(r['key'],{});title_zh=tr.get('title_zh') or name
    c=dict(id='oi_reg_'+r['key'],title=bilingual(title_zh,name),countries=[r['country']],scope='national',sector=bilingual(zhfocus,enfocus),sector_key=kind,
        aliases=[name if len(name)>=5 else label[1]+' '+name],challenges=['factor','adaptation'],modes=['joint'],institutions=['research'],factors=['knowledge','market'],start_year=None,end_year=None,review_status='structured_verified',
        evidence=[dict(source_id=sid,supports=['summary','actors','mechanism','observed'],locator=r['name'])],
        research_annotation=dict(primary_model='consortium',country=r['country'],cohort=key,basis='official_registry_and_programme_rule',reviewed_at=TODAY,interpretation_fields=['constraints','transfer','primary_model']),
        registry_record={k:v for k,v in r.items() if k not in ['description','members','institutions']},
        constraints=bilingual('名录提供组织、技术任务或资助事实，不作为项目效果的独立评价。','Directory facts establish organisational arrangements or registered tasks, not independently evaluated effects.'),
        transfer=bilingual('比较合作主体的职责、技术验证条件与企业参与方式，再判断本地是否具备相同实施条件。','Compare actor responsibilities, technical validation requirements and industry involvement before considering transfer.'))
    if key=='nsf_iucrc':
        focus_labels={'Information, Communication and Computing':'信息通信与计算','Energy and Environment':'能源与环境','Advanced Materials':'先进材料','Advanced Manufacturing':'先进制造','Advanced Electronics':'先进电子','Sensing and Information Systems':'传感与信息系统','Biotechnology':'生物技术','Health and Safety':'健康与安全','System Design and Simulation':'系统设计与仿真','Civil Infrastructure Systems':'土木基础设施'}
        focus='、'.join(focus_labels.get(x,x) for x in r['focus']);members=r['members'];c['start_year']=r['year']
        if r['year']:c['evidence'][0]['supports'].append('start_year')
        c['summary']=bilingual(f'{name}由'+ '、'.join(hosts)+f'参与，研究覆盖{zhfocus}。名录登记的具体方向为{focus}。',f'{name} links '+', '.join(hosts)+'. Listed research areas are '+', '.join(r['focus'])+'.')
        c['actors']=bilingual('高校：'+'；'.join(hosts)+'。名录成员：'+('；'.join(members) if members else '该页未列出成员名称')+'。','Universities: '+'; '.join(hosts)+'. Directory members: '+('; '.join(members) if members else 'not listed on the directory page')+'.')
        c['mechanism']=bilingual('通过NSF产学合作研究中心组织竞争前研究，产业成员参与研究方向选择；各中心的高校和成员名单单独记录。','The NSF IUCRC programme organises precompetitive research with industrial members involved in research direction; universities and members are recorded separately for each centre.')
        c['observed']=bilingual((f'名录所列成立年份为{r["year"]}年；' if r['year'] else '')+f'合作高校{len(hosts)}所，名录列示成员{len(members)}个。'+('该中心在名录中标记为已完成。' if r['status']=='completed' else ''),f'The directory lists {len(hosts)} universities and {len(members)} members'+(f', established in {r["year"]}' if r['year'] else '')+f'. Directory status: {r["status"]}.')
        c['registry_record']['member_names']=members;c['registry_record']['universities']=hosts
    elif key=='embrapii_export':
        c['parent_id']='oi_embrapii';c['research_annotation']['primary_model']='intermediary';c['modes']=['translation']
        title_zh=tr.get('title_zh') or f'{name}——{tr.get("focus_zh",zhfocus)}技术单元';c['title']['zh']=title_zh
        focus=tr.get('focus_zh') or zhfocus
        c['summary']=bilingual(f'{name}位于巴西{loc}，是EMBRAPII认证的{focus}研究单元。企业可围绕这一专长与该单元对接研发；其资格与技术领域在官方名录中逐项列明。',f'{name}, based in {loc}, is an EMBRAPII unit for {r["focus"][0]}. Technical lines: {r["activities"] or r["focus"][0]}.')
        c['actors']=bilingual(f'实施单元：{name}；名录中的机构类型为{r["institution_type"]}。',f'Unit: {name}; directory institution type: {r["institution_type"]}.')
        c['mechanism']=bilingual('企业围绕自身技术问题与认证单元协商研发项目，EMBRAPII网络提供应用研发的合作渠道。','Firms negotiate applied R&D projects with accredited units within the EMBRAPII cooperation framework.')
        c['observed']=bilingual(f'官方名录明确列出{loc}的{r["focus"][0]}技术资质及工作方向。',f'The official directory documents the technical competence {r["focus"][0]} and its operating location {loc}.')
    elif key=='australia_crcp':
        dates=re.findall(r'\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}',r['period']);years=re.findall(r'\b20\d{2}\b',r['period'])
        if len(years)!=2 or len(hosts)<2 or len(r['description'])<60:raise ValueError('incomplete_project')
        if len(dates)!=2:raise ValueError('missing_project_dates')
        start,end=map(register_date,dates)
        if start>date.today() or end<start:raise ValueError('invalid_project_period')
        c.update(start_year=int(years[0]),end_year=int(years[1]))
        c['project']={'source_type':'AU_CRCP','coordinator_country':'AU','registered_grant_aud':float(re.sub(r'[^\d.]','',r['grant'])),'registered_project_value_aud':float(re.sub(r'[^\d.]','',r['project_value'])),'start_date_text':dates[0] if dates else None,'end_date_text':dates[1] if len(dates)>1 else None,'funding_basis':'announced_grant_not_actual_expenditure'}
        c['project'].update(start_date=start.isoformat(),end_date=end.isoformat())
        c['summary']=bilingual(tr.get('summary_zh') or f'{hosts[0]}与'+ '、'.join(hosts[1:])+f'合作推进“{title_zh}”。登记项目期为{r["period"]}，获批资助{r["grant"]}澳元。',r['description'])
        c['actors']=bilingual('项目合作方：'+'；'.join(hosts)+'。','Project partners: '+'; '.join(hosts)+'.')
        c['mechanism']=bilingual('企业牵头的合作研发项目通过CRC-P获得配套资助，与高校或研究机构共同完成具体技术任务。','An industry-led collaborative R&D project receives CRC-P co-funding and involves research partners in a defined technical task.')
        c['observed']=bilingual(f'{r["round"]}获选项目；登记资助{r["grant"]}澳元，项目总价值{r["project_value"]}澳元；实施期{r["period"]}。以上为登记预算和计划。',f'Selected in {r["round"]}; grant AUD {r["grant"]}, total project value AUD {r["project_value"]}; {r["period"]}. These are registered budgets and plans.')
        c['registry_record']['objective_original']=r['description'];c['registry_record']['partners']=hosts
    elif key.startswith('africa'):
        c['research_annotation']['primary_model']='capacity';c['modes']=['incubation','joint'];c['factors']=['knowledge','talent']
        c['summary']=bilingual(tr.get('summary_zh') or f'{title_zh}通过非洲卓越中心计划开展{zhfocus}相关研究与专业人才培养。对应的实施机构与研究方向见官方登记：{r["description"]}。',r['description'])
        c['actors']=bilingual('中心与依托机构：'+r['description']+'。','Centre and host: '+r['description'])
        c['mechanism']=bilingual('以大学为依托，将研究生培养、应用研究和区域产业技能需求结合；此处记录的是能力建设单元，不等同于已完成的技术商业化项目。','University-based capacity building links postgraduate training, applied research and regional skills demand; the recorded unit is not a completed commercialisation project.')
        c['observed']=bilingual('区域项目官方名录列明该中心及其技术方向：'+title_zh+'。','The regional programme directory identifies this centre and its technical remit: '+name+'.')
    elif key=='jst_coinext':
        c['summary']=bilingual(f'{hosts[0]}承担“{title_zh}”，在JST共创平台计划下组织围绕这一目标的研究与合作。',f'{hosts[0]} hosts {name} under the JST COI-NEXT co-creation programme.')
        c['actors']=bilingual('代表机构：'+hosts[0]+'；项目管理机构：日本科学技术振兴机构。','Lead institution: '+hosts[0]+'. Programme agency: Japan Science and Technology Agency.')
        c['mechanism']=bilingual('大学等代表机构与合作主体共同提出社会愿景，并将研究开发与共创平台建设结合。','The lead institution and collaborators connect a shared societal vision with R&D and development of a co-creation platform.')
        c['observed']=bilingual('JST项目表列出代表机构，并提供该平台的专属概要文件。','JST identifies the lead institution and links a platform-specific overview document.')
    elif key.startswith('china_moe'):
        c['research_annotation'].update(primary_model='intermediary',province='CN-'+r['province'],city=r['city']);c['modes']=['translation'];c['institutions']=['research','ip']
        c['title']=bilingual(name+'科技成果转化和技术转移基地',tr.get('name_en',name)+' technology-transfer base')
        year=2019 if r['batch']=='1' else 2020
        c['summary']=bilingual(f'{name}被教育部认定为第'+('一' if r['batch']=='1' else '二')+f'批高校科技成果转化和技术转移基地，承担科研成果向产业应用转化的组织职能。'+r.get('practice',''),f'{name} was designated by the Ministry of Education as a technology-transfer base in {year}, connecting university research with industrial application.'+r.get('practice_en',''))
        c['actors']=bilingual('依托高校：'+name+'；认定部门：教育部。','Host university: '+name+'; designating authority: Ministry of Education.')
        c['mechanism']=bilingual(r.get('practice') or '以高校技术转移基地为组织载体，开展科技成果转化和技术转移。',r.get('practice_en') or 'A university technology-transfer base organises transfer and application of research outputs.')
        c['observed']=bilingual(f'{year}年教育部认定文件将{name}列为依托高校；认定日期不作为大学或转移机构成立日期。',f'The {year} designation names {name} as host. The designation date is not an institutional founding date.')
        c['registry_record']['designation_year']=year
    else:raise ValueError('unsupported_registry')
    if tr.get('summary_zh'):c['summary']['zh']=tr['summary_zh']
    return c

def load_candidates(refresh=False):
    groups=[('nsf_iucrc',['nsf_iucrc'],nsf),('embrapii_export',['embrapii_export'],embrapii),('australia_crcp',['australia_crcp'],australia),('africa',['africa_ace','africa_ace2'],africa),('jst_coinext',['jst_coinext'],japan)]
    rows=[];health=[]
    for label,keys,parse in groups:
        try:
            programme_keys=list(dict.fromkeys(PROGRAMMES[k] for k in keys if k in PROGRAMMES))
            audits=[collect(k,SOURCES[k],refresh) for k in keys+programme_keys];batch=parse()
            if len(batch)<5:raise ValueError('unexpected_directory_shrink')
            rows.extend(batch);health.append({'registry':label,'status':'ok','candidates':len(batch),'sources':audits})
        except Exception as exc:health.append({'registry':label,'status':'failed','error':type(exc).__name__+':'+str(exc)[:120]})
    return rows,health

def run(initial=False,refresh=False,max_add=36,per_country=12):
    rows,health=load_candidates(refresh)
    translation_path=ROOT/'config/innovation_registry_translations.json'
    translations=json.loads(translation_path.read_text(encoding='utf-8')) if translation_path.exists() else {}
    if initial:
        practices=json.loads((ROOT/'config/innovation_registry_practices.json').read_text(encoding='utf-8'))
        for r in csv.DictReader((ROOT/'config/innovation_registry_china.tsv').read_text(encoding='utf-8').splitlines(),delimiter='\t'):
            key='china_moe_first_list' if r['batch']=='1' else 'china_moe_second_list'
            if r['name'] in practices:r.update(practice=practices[r['name']]['zh'],practice_en=practices[r['name']]['en'])
            rows.append(dict(r,key=identity(key,r['name']),registry=key,country='CN'))
    book=json.loads((ROOT/'static/data/innovation_cases.json').read_text(encoding='utf-8'))
    existing=json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {'cases':[],'sources':[]}
    ids={c['id'] for c in book['cases']}|{c['id'] for c in existing['cases']}
    titles={norm(c['title']['en']) for c in book['cases']}
    known_registry_urls={c.get('registry_record',{}).get('url') for c in book['cases']+existing['cases'] if c.get('registry_record',{}).get('url')}
    countries=Counter(c.get('research_annotation',{}).get('country') for c in book['cases'])
    decisions=[];admitted=Counter();new_sources={};new=[]
    # Deterministic balancing: underrepresented focus countries first, then source identity.
    rows.sort(key=lambda r:(countries[r['country']],r['registry'],r['key']))
    for r in rows:
        cid='oi_reg_'+r['key'];reason=None
        if cid in ids:reason='already_present'
        elif r.get('url') and r['url'] in known_registry_urls:reason='same_official_record_review_name_change'
        elif r['registry']=='embrapii_export' and r['name']=='CNPEM':reason='same_institution_already_present_oi_cnpem'
        elif norm(r['name']) in titles:reason='duplicate_title'
        elif r['registry']=='africa_ace' and re.search(r'pedagogy|education|learning|population health|reproductive|infectious|transmissibles|maladies|medicine|sante|santé|medicament|toxicolog|maladies|cell biology|genetic|drug|engineering, \(CoE',r['name'],re.I):reason='outside_documented_industry_scope'
        elif r['registry']=='australia_crcp' and not any(w in r['name'].lower() for w in ['energy','battery','batteries','hydrogen','solar','carbon','recycl','manufactur','mineral','mining','electric','steel','water','wind','bioenergy','copper','nickel','alumina']):reason='outside_selected_technical_scope'
        limit=60 if initial and r['country']=='AU' else (10000 if initial else per_country)
        if not reason and (len(new)>=max_add or admitted[r['country']]>=limit):reason='eligible_backlog_capacity_limit'
        if not reason:
            try:
                c=build_case(r,translations)
                if c.get('start_year') and c['start_year']>date.today().year:raise ValueError('future_start')
                key=r['registry'];s=source(key)
                extra_keys=[PROGRAMMES[key]] if key in PROGRAMMES else []
                if r.get('practice'):extra_keys.append('china_moe_experience')
                for extra_key in extra_keys:
                    # Missing programme evidence blocks admission, rather than inventing a mechanism.
                    extra=source(extra_key);new_sources[extra['id']]=extra
                    c['evidence'].append({'source_id':extra['id'],'supports':['mechanism']+(['summary'] if r.get('practice') else []),'locator':r['name'] if r.get('practice') else 'Programme rules'})
                new.append(c);new_sources[s['id']]=s;ids.add(cid);titles.add(norm(c['title']['en']));admitted[r['country']]+=1;reason='admitted'
            except (ValueError,KeyError,TypeError) as exc:reason='rejected_'+str(exc)[:100]
        decisions.append({'candidate_key':r['key'],'registry':r['registry'],'country':r['country'],'decision':reason})
    existing['cases'].extend(new)
    # Existing source URLs keep their stable IDs; never duplicate source rows.
    old_urls={s['url']:s['id'] for s in book['sources'] if s['id'] not in {x['id'] for x in existing['sources']}}
    for sid,s in list(new_sources.items()):
        if s['url'] in old_urls:
            for c in new:
                for ref in c['evidence']:
                    if ref['source_id']==sid:ref['source_id']=old_urls[s['url']]
            del new_sources[sid]
    source_map={s['id']:s for s in existing['sources']};source_map.update(new_sources)
    existing.update(schema_version='1.0',sources=list(source_map.values()),reviewed_at=TODAY,sector_taxonomy={k:bilingual(*v) for k,v in SECTORS.items()})
    OUT.write_text(json.dumps(existing,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    audit={'checked_at':datetime.now(timezone.utc).isoformat(),'added':len(new),'added_by_country':dict(admitted),'total_registry_cases':len(existing['cases']),'candidate_decisions':dict(Counter(x['decision'] for x in decisions)),
       'selection':{'max_add':max_add,'per_country':per_country,'initial':initial,'order':'ascending previously recorded focus-country count, registry, stable key','scope':'STEM industry cooperation; CRC-P energy, resources, manufacturing and environment; Africa non-clinical applied centres'},'health':health,'decisions':decisions,'added_case_ids':[c['id'] for c in new]}
    (ROOT/'data/innovation_registry_update.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    history_path=ROOT/'data/innovation_registry_history.json';history=json.loads(history_path.read_text(encoding='utf-8')) if history_path.exists() else []
    history.append({k:audit[k] for k in ['checked_at','added','added_by_country','total_registry_cases','added_case_ids']});history_path.write_text(json.dumps(history,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:audit[k] for k in ['added','added_by_country','total_registry_cases','candidate_decisions']},ensure_ascii=False))
    if not any(h['status']=='ok' for h in health):raise RuntimeError('All registries unavailable; previous cases preserved')
    return audit

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--initial',action='store_true');p.add_argument('--refresh',action='store_true');p.add_argument('--max-add',type=int,default=36);p.add_argument('--per-country',type=int,default=12);a=p.parse_args();run(a.initial,a.refresh,a.max_add,a.per_country)

"""Targeted, additive institutional evidence following the 2026-10-14 review.

This is an AI-assisted editorial source review, not independent human validation.
Existing facts and the first research release are never overwritten.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAY = '2026-10-14'
METHOD = 'AI-assisted reading of named official pages; no independent rater'

def pair(zh, en):
    return {'zh': zh, 'en': en}

def main():
    cases, sources, entries, ledger = [], [], [], []
    source_by_url = {}
    for path in sorted((ROOT/'config').glob('open_innovation_*.json')):
        if path.name == 'open_innovation_peer_review.json':
            continue
        source_by_url.update({s['url']: s['id'] for s in json.loads(path.read_text(encoding='utf-8')).get('sources', [])})
    old_review = json.loads((ROOT/'config/innovation_chronology_review.json').read_text(encoding='utf-8'))

    def source(url, title, publisher, language='en', published=None):
        sid = source_by_url.get(url)
        if not sid:
            sid = 's_peer_' + hashlib.sha256(url.encode()).hexdigest()[:12]
            sources.append({'id':sid,'url':url,'title':title,'publisher':publisher,
                'language':language,'published_date':published,'reviewed_at':DAY,
                'access':'public_metadata_and_paraphrase','source_role':'primary',
                'review_method':METHOD})
            source_by_url[url] = sid
        return sid

    def event(cid, when, kind, origin, zh, en, url, publisher, title, anchor, published=None):
        entries.append({'case_id':cid,'date':when,'precision':{4:'year',7:'month',10:'day'}[len(when)],
            'kind':kind,'origin':origin,'zh':zh,'en':en,'url':url,'publisher':publisher,
            'title':title,'published_date':published,'language':'zh' if any('\u4e00'<=x<='\u9fff' for x in publisher) else 'en'})
        ledger.append({'case_id':cid,'field':'origin_year' if origin else 'dated_activity',
            'value':when,'source_id':source_by_url[url],'source_url':url,
            'source_locator':anchor,'review_method':METHOD,'reviewed_at':DAY,
            'access_basis':'indexed_official_excerpt_direct_fetch_unavailable' if cid=='oi_zju_shaoxing' else 'official_page_or_indexed_official_text',
            'independent_validation':False})

    def add(key, zh, en, country, year, model, modes, factors, url, publisher, summary, actors, mechanism, observed, anchor, second=None):
        sid = source(url, en+' official evidence', publisher)
        refs = [{'source_id':sid,'supports':['summary','actors','mechanism','observed','start_year']}]
        if second:
            other = source(*second)
            refs.append({'source_id':other,'supports':['actors','mechanism']})
        cases.append({'id':'oi_'+key,'title':pair(zh,en),'countries':[country],'scope':'national',
            'sector':pair('应用技术与产业创新','Applied research and industrial innovation'),
            'sector_key':'applied_innovation','aliases':[zh,en],
            'challenges':['factor','adaptation'],'modes':modes,'institutions':['research'],
            'factors':factors,'start_year':year,'end_year':None,'review_status':'reviewed','reviewed_at':DAY,
            'summary':pair(*summary),'actors':pair(*actors),'mechanism':pair(*mechanism),'observed':pair(*observed),
            'evidence':refs,'research_annotation':{'primary_model':model,'country':country,
                'cohort':'peer_review','basis':'AI_assisted_official_source_review'}})
        event('oi_'+key,str(year),'establishment',True,zh+'于'+str(year)+'年设立。',
            en+' was established in '+str(year)+'.',url,publisher,en,anchor)

    add('imec_review','比利时imec竞争前联合研发','imec precompetitive semiconductor collaboration','BE',1984,'consortium',
        ['joint','testbed','translation'],['knowledge','infrastructure','market'],
        'https://www.imec-int.com/en/about-imec/history','imec',
        ('imec于1984年在鲁汶成立，通过共享研发设施组织芯片制造商、设计企业和设备材料供应商开展竞争前研究。',
         'Founded in Leuven in 1984, imec organises precompetitive semiconductor research using shared facilities.'),
        ('imec研究团队及半导体产业链企业。','Imec researchers and semiconductor value-chain companies.'),
        ('合作企业共同分担复杂研发的成本和风险，结合联合研究、双边合作与技术转移。',
         'Industry partners share R&D costs and risks through collaborative research and technology transfer.'),
        ('官方历程记录其从半导体研发扩展到能源等应用，并于2019年参与共建OnePlanet研究中心。',
         'Its history records expansion into application domains and co-founding OnePlanet in 2019.'),
        'History sections on foundation, precompetitive research and OnePlanet')
    add('cea_leti_review','法国CEA-Leti产业研发与中试','CEA-Leti industrial research and pilot facilities','FR',1967,'pilot',
        ['testbed','joint','translation'],['knowledge','infrastructure','market'],
        'https://www.cea.fr/cea-tech/leti/english/Pages/Leti/About-Leti/mission-organization.aspx','CEA-Leti',
        ('CEA-Leti于1967年设立，面向企业提供微纳技术研究、原型开发及中试验证。',
         'Established in 1967, CEA-Leti supports company research, prototyping and pilot validation in micro- and nanotechnologies.'),
        ('CEA-Leti与不同规模的产业合作企业。','CEA-Leti and industrial partners of different sizes.'),
        ('合作企业使用预工业化设施与工程研究能力，推动概念验证向规模化制造衔接。',
         'Partners access pre-industrial infrastructure and engineering expertise to link proof of concept with manufacturing.'),
        ('官网列出洁净室、表征及试验平台和技术转移服务；设施能力不等于每个项目已完成产业化。',
         'The institutional profile lists cleanrooms, characterisation platforms and technology-transfer services.'),
        'Who are we and advanced technology platforms')
    add('sri_review','美国SRI合同研发与技术商业化','SRI contract research and commercialisation','US',1946,'intermediary',
        ['joint','translation'],['knowledge','talent','market'],
        'https://www.sri.com/about-us/','SRI',
        ('SRI于1946年由斯坦福大学创办，1970年成为独立非营利研发机构，为政府和企业提供研究及商业化服务。',
         'Founded by Stanford in 1946 and independent since 1970, SRI serves government and commercial R&D clients.'),
        ('SRI研究团队、委托企业和公共部门。','SRI researchers, commercial customers and public clients.'),
        ('将合同研究与技术商业化结合，研发和商业化收入用于继续建设研究能力。',
         'Contract R&D and commercialisation revenue supports further research capability.'),
        ('官方介绍记载2023年并入PARC，并说明其面向商业应用的技术转化职责。',
         'The official account records the 2023 acquisition of PARC and a commercial-application mission.'),
        'From ideas to applications')
    add('vtt_review','芬兰VTT应用研究与企业合作','VTT applied research and industrial collaboration','FI',1942,'intermediary',
        ['joint','testbed','translation'],['knowledge','infrastructure','market'],
        'https://www.vttresearch.com/en/about-us/vtts-history-bunker-stoves-printed-intelligence','VTT',
        ('VTT于1942年成立，连接应用研究与产业技术开发，并向企业提供合作研发、试验和技术转移服务。',
         'VTT was founded in 1942 and links applied research with industrial technology development.'),
        ('VTT、企业及研究资助机构。','VTT, companies and research funders.'),
        ('共同资助研究项目，并通过中试设施和知识产权许可支持技术应用。',
         'Co-funded research, piloting and licensing support industrial applications.'),
        ('官方历史与合作说明分别提供成立证据和企业合作方式，不把当前服务追溯为1942年即已存在。',
         'Separate history and partnership pages document foundation and current services; current services are not backdated.'),
        'History opening foundation paragraph',
        second=('https://www.vttresearch.com/en/about-us/how-partner-us','How to partner with VTT','VTT'))
    add('hvm_review','英国高价值制造Catapult协同中试网络','High Value Manufacturing Catapult industrial piloting network','GB',2011,'pilot',
        ['testbed','network','translation'],['knowledge','infrastructure','talent','market'],
        'https://hvm.catapult.org.uk/who-we-are/our-history/','High Value Manufacturing Catapult',
        ('英国高价值制造Catapult于2011年整合七个创新中心的能力，连接工业研究、技术验证和制造应用。',
         'Established in 2011, HVM Catapult combined seven innovation centres for industrial research and manufacturing application.'),
        ('Innovate UK、制造创新中心、企业和学术机构。','Innovate UK, manufacturing centres, companies and academic partners.'),
        ('通过共享研发和工程设施组织制造技术验证，并配置专业训练和产业协作。',
         'Shared research and engineering facilities support validation, training and industrial collaboration.'),
        ('官方历程记录2014年能源创新中心启用、2018年与制造研究机构组织英国制造论坛。',
         'The history records a 2014 energy innovation centre and a manufacturing forum in 2018.'),
        'History entries 2011, 2014 and 2018')
    add('yissum_review','以色列Yissum大学技术许可','Yissum university technology licensing','IL',1964,'intermediary',
        ['translation','incubation'],['knowledge','capital','market'],
        'https://www.yissum.co.il/about-us/','Yissum',
        ('Yissum于1964年设立，将希伯来大学研究与企业、创业者及投资者连接，提供技术许可与商业化服务。',
         'Founded in 1964, Yissum connects Hebrew University research with industry, entrepreneurs and investors.'),
        ('希伯来大学研究人员、Yissum、产业合作方和投资者。','Hebrew University researchers, Yissum, industrial partners and investors.'),
        ('以大学技术转移机构作为交易接口，组织许可、合作和创业支持。',
         'A university technology-transfer organisation coordinates licensing, partnerships and venture support.'),
        ('官网确认成立年份与许可商业化职责，未据此推断单项许可的商业回报。',
         'The official profile confirms foundation and commercialisation functions, not returns from individual licences.'),
        'About Us foundation and researcher industry investor paragraphs')
    add('america_makes_review','美国增材制造公私合作研发','America Makes additive-manufacturing public-private research','US',2012,'consortium',
        ['joint','testbed'],['knowledge','capital','infrastructure','talent','market'],
        'https://www.nist.gov/news-events/news/2012/08/obama-administration-announces-new-public-private-partnership-support','NIST',
        ('2012年设立的美国增材制造创新机构前身NAMII，通过公私合作汇集企业、研究型大学、社区学院及行业组织。',
         'NAMII, the predecessor of America Makes, began in 2012 as an additive-manufacturing public-private consortium.'),
        ('NCDMM牵头，企业、大学、社区学院和非营利机构参与。','NCDMM leads with companies, universities, community colleges and nonprofit organisations.'),
        ('联邦资金与成员配套资金共同支持研发基础，将研究、企业生产需求和技能培养结合。',
         'Federal and member co-funding connects research, production needs and workforce skills.'),
        ('NIST当年公告说明合作结构和初始资助承诺；承诺资金不作为实际支出。',
         'The 2012 NIST announcement describes governance and initial commitments, not actual expenditure.'),
        '2012 announcement and consortium description')
    add('nsf_iucrc_review','美国NSF产学合作研究中心机制','NSF Industry-University Cooperative Research Centers programme','US',1973,'consortium',
        ['joint','network','translation'],['knowledge','capital','talent','market'],
        'https://www.nsf.gov/funding/opportunities/iucrc-industry-university-cooperative-research-centers-program/5501/nsf13-594/solicitation','NSF',
        ('NSF产学合作研究中心计划始于1973年，通过长期产学政合作组织共同感兴趣的研究及技术转移。',
         'The NSF IUCRC programme began in 1973 to support long-term industry-university-government research partnerships.'),
        ('NSF、高校、企业成员和合作研究中心。','NSF, universities, industry members and cooperative research centres.'),
        ('在持续合作框架下整合企业需求、大学研究及科研教育，支持研究基础设施与技术转移。',
         'Long-term partnerships combine industrial needs, academic research, research infrastructure and technology transfer.'),
        ('2013年官方征集指南确认1973年起始与计划机制；本条为计划层记录，不代表每个中心均有相同成效。',
         'The 2013 solicitation documents the origin and programme mechanism, not uniform outcomes across centres.'),
        'NSF 13-594 introduction and programme description')

    origin_reviews = [
        ('oi_scici','2012','华南协同创新研究院于2012年底挂牌成立。','SCICI was established in late 2012.',
         'https://www.scici.cn/about.aspx?AboutCateId=65','华南协同创新研究院','研究院简介','简介首段'),
        ('oi_tsinghua_hebei','2002-08-12','河北清华发展研究院于2002年8月12日在廊坊成立。','The Hebei Tsinghua institute was established in Langfang on 12 August 2002.',
         'https://www.tsinghua.edu.cn/info/2014/78202.htm','清华大学','河北清华发展研究院成立','正文首段与2002年8月14日发布日'),
        ('oi_zju_shaoxing','2022-01-21','浙江大学绍兴研究院于2022年1月21日揭牌成立。','The Zhejiang University Shaoxing institute was inaugurated on 21 January 2022.',
         'https://shaoxing.zju.edu.cn/index.php?a=lists&c=index&catid=19&m=content','浙江大学绍兴研究院','研究院简介','机构简介首段'),
        ('oi_gdut_cnc','2013','广工大数控装备协同创新研究院于2013年注册成立。','The GDUT CNC institute was registered in 2013.',
         'https://yjs.gdut.edu.cn/info/1246/3978.htm','广东工业大学','佛山市南海区广工大数控装备协同创新研究院简介','简介首段'),
        ('oi_stanford_otl','1970','斯坦福大学技术许可办公室于1970年正式设立。','Stanford OTL was formally established in 1970.',
         'https://otl.stanford.edu/news/otls-first-50-years-executive-roundtable','Stanford University','OTL First 50 Years','Pilot made permanent in 1970'),
        ('oi_embrapii','2013','EMBRAPII于2013年设立，连接企业与技术研究机构。','EMBRAPII was established in 2013 to connect firms and technological research institutions.',
         'https://embrapii.org.br/sobre-a-embrapii/','EMBRAPII','Sobre a Embrapii','About Embrapii foundation paragraph'),
        ('oi_fundacion_chile','1976','智利基金会于1976年设立。','Fundación Chile was established in 1976.',
         'https://fch.cl/nosotros/sobre-nosotros/','Fundación Chile','Sobre Nosotros','Primera década'),
        ('oi_kirdi','1979','KIRDI根据1979年科学技术法设立。','KIRDI was established under the 1979 Science and Technology Act.',
         'https://www.kirdi.go.ke/index.php/background-information','KIRDI','Background Information','History paragraph on the 1979 Act'),
        ('oi_bitri','2012','博茨瓦纳技术研究与创新研究院于2012年设立。','BITRI was established in 2012.',
         'https://bitri.co.bw/about-us/','BITRI','About Us','Our Journey 2012'),
        ('oi_epecentre','2002','EPECentre于2002年由坎特伯雷大学与电力行业共同设立。','EPECentre was established jointly by the University of Canterbury and the electricity industry in 2002.',
         'https://www.canterbury.ac.nz/research/about-uc-research/research-groups-and-centres/electric-power-engineering-centre/about-epecentre','University of Canterbury','About EPECentre','About EPECentre opening paragraph'),
        ('oi_anff','2007','澳大利亚国家微纳加工设施网络于2007年设立。','ANFF was established in 2007 under NCRIS.',
         'https://anff.org.au/governance-and-management/','ANFF','Governance and Management','Opening foundation paragraph'),
        ('oi_embrapa_open','1973-04-26','巴西农业研究公司于1973年4月26日正式设立运行。','Embrapa was inaugurated on 26 April 1973.',
         'https://www.embrapa.br/en/50-anos/linha-do-tempo','Embrapa','Timeline','1973 installation event'),
        ('oi_agrosavia','1993','AGROSAVIA前身CORPOICA于1993年设立，2018年更名。','CORPOICA was established in 1993 and renamed AGROSAVIA in 2018.',
         'https://www.agrosavia.co/noticias/corpoica-se-transforma-ahora-es-agrosavia','AGROSAVIA','Corpoica se transforma ahora es AGROSAVIA','2018 account of the 1993 foundation')]
    for cid,when,zh,en,url,publisher,title,anchor in origin_reviews:
        language='zh' if any('\u4e00'<=x<='\u9fff' for x in publisher) else ('pt' if publisher in ('Embrapa','EMBRAPII') else 'es' if publisher in ('Fundación Chile','AGROSAVIA') else 'en')
        source(url,title,publisher,language)
        event(cid,when,'establishment',True,zh,en,url,publisher,title,anchor)
    for cid,when,kind,zh,en,url,publisher,anchor in [
        ('oi_sri_review','1970','institutional_change','SRI成为独立非营利研究机构。','SRI became an independent nonprofit institute.','https://www.sri.com/about-us/','SRI','From ideas to applications'),
        ('oi_sri_review','2023','expansion','SRI并入PARC。','SRI acquired PARC.','https://www.sri.com/about-us/','SRI','From ideas to applications'),
        ('oi_imec_review','2019','expansion','imec参与共建OnePlanet研究中心。','Imec co-founded OnePlanet Research Center.','https://www.imec-int.com/en/about-imec/history','imec','From semiconductors to smart applications'),
        ('oi_hvm_review','2014','expansion','WMG能源创新中心启用。','WMG Energy Innovation Centre opened.','https://hvm.catapult.org.uk/who-we-are/our-history/','High Value Manufacturing Catapult','2014 milestone')]:
        event(cid,when,kind,False,zh,en,url,publisher,anchor,anchor)
    old_keys={(e['case_id'],e['date'],e['kind']) for e in old_review['entries']}
    old_review['entries'].extend(e for e in entries if (e['case_id'],e['date'],e['kind']) not in old_keys)
    old_review['review_method']=METHOD
    for path,value in [
        ('config/open_innovation_peer_review.json',{'reviewed_at':DAY,'review_method':METHOD,'cases':cases,'sources':sources}),
        ('config/innovation_chronology_review.json',old_review),
        ('config/innovation_peer_evidence.json',{'version':'2026.10.14-r2','review_method':METHOD,'claims':ledger})]:
        (ROOT/path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'added_cases':len(cases),'added_sources':len(sources),'reviewed_claims':len(ledger)}))

if __name__=='__main__':
    main()

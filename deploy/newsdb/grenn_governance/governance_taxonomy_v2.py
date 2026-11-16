"""14/83 research taxonomy. Evidence offsets are Unicode, end-exclusive.

Labels are lexical candidates, not verified positions or causal relationships.
Nine extensions were authorized by the user on 2026-11-06. This is a research
classification, not an official UNFCCC taxonomy. Original source text is immutable.
"""
import re
from collections import defaultdict
from .governance_labels import label_text as legacy_labels
from .taxonomy import country_index

VERSION='governance-14x83-20261106-v2'
PARENTS=[
 ('G01','全球气候治理机制与国际谈判','Global Climate Governance'),
 ('G02','气候目标、承诺与履约','Climate Targets and Commitments'),
 ('G03','温室气体减排与能源转型','Mitigation and Energy Transition'),
 ('G04','气候适应与韧性建设','Adaptation and Resilience'),
 ('G05','气候损失与损害','Loss and Damage'),
 ('G06','气候资金与绿色金融','Climate Finance'),
 ('G07','碳市场与市场合作机制','Carbon Markets and Cooperation'),
 ('G08','气候技术创新与能力建设','Technology and Capacity Building'),
 ('G09','气候透明度、核算与科学评估','Transparency and Assessment'),
 ('G10','气候公平、正义与公正转型','Equity, Justice and Just Transition'),
 ('G11','气候外交、国际政治经济与贸易','Climate Diplomacy and Trade'),
 ('G12','自然生态、土地利用与粮食系统','Nature, Land and Food Systems'),
 ('G13','多元主体、地方行动与社会治理','Non-State Actors and Society'),
 ('G14','气候风险、健康与新兴治理议题','Climate Risks and Emerging Issues'),
]
# code | Chinese | English | explicit lexical evidence; broader contexts can be
# retained as review candidates but must not be silently asserted as focal topics.
ROWS=r'''
G01.01|国际气候条约与法律制度|Climate treaties and legal regimes|UNFCCC|Kyoto Protocol|Paris Agreement|气候公约|京都议定书|巴黎协定
G01.02|COP、CMA、CMP会议与决议|COP CMA CMP meetings and decisions|\bCOP\s*\d{1,2}\b|\bCMA\s*\d|\bCMP\s*\d|Conference of the Parties|缔约方大会|气候大会决议
G01.03|国际谈判进程与集团立场|Negotiations and negotiating positions|climate negotiations?|climate talks|negotiating bloc|negotiating group|气候谈判|谈判立场|谈判集团
G01.04|全球气候治理机构与改革|Climate institutions and reform|UNFCCC secretariat|reform.{0,40}climate governance|climate governance.{0,40}reform|气候治理改革|气候公约秘书处
G01.05|国际合作倡议与伙伴关系|International initiatives and partnerships|climate partnership|climate cooperation|climate alliance|international climate initiative|气候伙伴关系|气候合作|气候联盟
G01.06|全球气候治理体系演进|Evolution of climate governance|history of climate negotiations|evolution of.{0,30}climate governance|post.Kyoto|post.Paris|气候治理体系|气候谈判历程
G02.01|全球温控与长期气候目标|Global temperature and long-term goals|1\.5\s*(?:°|degrees?|C\b)|well below 2|global net.zero|temperature goal|温控目标|全球净零
G02.02|国家自主贡献|Nationally determined contributions|nationally determined contributions?|\bNDCs?\b|国家自主贡献|自主贡献更新
G02.03|长期低排放发展战略|Long-term low-emission strategies|LT.LEDS|long.term low.emission|net.zero strateg|carbon neutrality strateg|长期低排放|碳中和战略
G02.04|全球盘点|Global stocktake|global stocktake|全球盘点
G02.05|国家履约进展与行动差距|Implementation progress and gaps|emissions? gap|implementation gap|off track.{0,40}(?:climate|emission)|climate target.{0,30}(?:miss|progress)|排放差距|履约进展|减排缺口
G02.06|气候目标协同与政策一致性|Policy coherence and target synergies|climate policy coherence|climate policy consistency|climate.{0,30}policy conflict|气候政策一致性|气候目标协同|气候政策冲突
G03.01|化石能源转型与退出|Fossil fuel transition and phase-out|fossil fuels?|coal phase.out|coal.fired|oil and gas|化石能源|化石燃料|煤电|煤炭退出|bahan bakar fosil|batu ?bara|combustibles f[oó]siles
G03.02|可再生能源发展|Renewable energy deployment|renewable(?: energy| power|s\b)|solar (?:power|energy|panel|farm)|wind (?:power|energy|farm|turbine)|可再生能源|光伏|风电|energ[ií]a renovable|energi terbarukan|energi surya
G03.03|能源效率与终端电气化|Efficiency and end-use electrification|energy efficiency|energy.efficient|electrification|heat pumps?|能效|能源效率|终端电气化|节能
G03.04|工业低碳转型|Industrial decarbonization|green steel|low.carbon (?:steel|cement|industr)|industrial decarboni|工业减碳|工业低碳|绿色钢铁|水泥减排
G03.05|交通运输低碳转型|Low-carbon transport|electric vehicles?|\bEVs\b|transport decarboni|sustainable aviation fuel|shipping emissions|电动汽车|交通减排|绿色航运|航空减排
G03.06|非二氧化碳温室气体减排|Non-CO2 mitigation|methane|nitrous oxide|hydrofluorocarbon|\bHFCs\b|甲烷|氧化亚氮|含氟温室气体
G03.07|CCUS与碳移除|CCUS and carbon removal|carbon capture|carbon removal|direct air capture|\bCCUS\b|碳捕集|碳移除|直接空气捕集
G03.08|绿色氢能与新型能源系统|Green hydrogen and energy systems|green hydrogen|energy storage|battery storage|electricity grid|smart grid|绿氢|储能|智能电网|新型电力系统
G04.01|全球适应目标|Global goal on adaptation|global goal on adaptation|全球适应目标|UAE Framework for Global Climate Resilience
G04.02|国家适应计划与政策|Adaptation plans and policies|national adaptation plan|adaptation strateg|adaptation polic|国家适应计划|适应气候变化战略
G04.03|气候灾害预警与风险管理|Early warning and risk management|early warning|disaster risk reduction|disaster preparedness|早期预警|灾害预警|防灾减灾
G04.04|城市与基础设施气候韧性|Urban and infrastructure resilience|resilient infrastructure|climate.resilient cit|urban resilience|flood defen[cs]e|城市韧性|基础设施韧性|防洪工程
G04.05|水资源与生态系统适应|Water and ecosystem adaptation|water security|water scarcity|ecosystem.based adaptation|水安全|水资源适应|生态系统适应
G04.06|农业与社区适应|Agriculture and community adaptation|climate.resilient agricultur|community.based adaptation|drought.resistant crop|农业适应|社区适应|抗旱作物
G05.01|损失与损害国际治理机制|Loss and damage governance|Warsaw International Mechanism|Santiago Network|loss and damage.{0,40}(?:mechanism|negotiat)|华沙国际机制|圣地亚哥网络|损失与损害机制
G05.02|损失与损害基金|Loss and damage fund|loss and damage fund|fund for responding to loss|loss.and.damage fund|损失与损害基金|损失和损害基金
G05.03|极端事件经济损失|Economic losses from extremes|(?:flood|storm|hurricane|cyclone|wildfire).{0,60}(?:damage|loss|cost)|(?:damage|loss|cost).{0,60}(?:flood|hurricane|cyclone|wildfire)|灾害损失|气候经济损失
G05.04|非经济损失与损害|Non-economic loss and damage|non.economic loss|cultural heritage.{0,50}climate|非经济损失|气候.{0,20}文化遗产
G05.05|气候灾害援助与恢复|Climate disaster aid and recovery|disaster recovery|climate disaster relief|post.disaster reconstruction|灾后恢复|灾后重建|气候灾害援助
G06.01|国际气候资金目标与承诺|Climate finance goals and pledges|NCQG|new collective quantified goal|climate finance goal|climate finance pledge|气候资金目标|气候资金承诺
G06.02|多边气候基金|Multilateral climate funds|Green Climate Fund|Global Environment Facility|Adaptation Fund|绿色气候基金|全球环境基金|适应基金
G06.03|减缓与适应资金配置|Mitigation and adaptation allocation|adaptation financ|mitigation financ|climate finance flow|适应融资|减缓资金|气候资金流向
G06.04|多边开发银行与发展融资|Development banks and finance|multilateral development bank|concessional financ|development bank.{0,40}climate|多边开发银行|优惠贷款|开发融资
G06.05|私人气候投融资|Private climate investment|green bonds?|transition financ|private climate financ|climate investment|绿色债券|转型金融|气候投融资
G06.06|气候债务与金融公平|Climate debt and finance equity|climate debt|debt.for.climate|debt.for.nature|climate finance.{0,40}grants|气候债务|债务置换|气候赠款
G06.07|金融体系与气候风险|Financial climate risk|climate.related financial|climate financial risk|climate stress test|气候金融风险|气候压力测试|气候风险披露
G07.01|巴黎协定第6.2条合作|Article 6.2 cooperation|Article\s*6\.2|\bITMOs?\b|internationally transferred mitigation|第6\.2条|国际转让减缓成果
G07.02|巴黎协定第6.4条机制|Article 6.4 mechanism|Article\s*6\.4|Paris Agreement Crediting Mechanism|第6\.4条|巴黎协定碳信用机制
G07.03|第6.8条非市场合作|Article 6.8 non-market cooperation|Article\s*6\.8|non.market approaches|第6\.8条|非市场方法|非市场合作
G07.04|国内碳排放交易体系|Domestic emissions trading|emissions? trading|\bEU ETS\b|carbon allowance|碳排放权交易|排放交易体系|碳配额
G07.05|自愿碳市场与碳信用|Voluntary carbon markets|voluntary carbon|carbon credits?|carbon offsets?|自愿碳市场|碳信用|碳抵消
G07.06|碳市场完整性与核算|Carbon market integrity|corresponding adjustment|double counting|carbon.{0,40}additionality|carbon.{0,40}permanence|对应调整|双重计算|碳市场完整性|额外性
G08.01|气候技术研发与突破|Climate technology R&D|clean.tech.{0,30}(?:breakthrough|research|demonstration)|climate technolog.{0,30}(?:research|innovation)|气候技术研发|清洁技术突破|低碳技术研发
G08.02|国际技术转让与扩散|Technology transfer and diffusion|technology transfer|technology diffusion|技术转让|技术扩散|技术转移
G08.03|气候技术机制与平台|Climate technology mechanisms|Climate Technology Centre|\bCTCN\b|Technology Executive Committee|气候技术中心|技术执行委员会
G08.04|能力建设与人才培养|Capacity building and training|capacity.building|climate training|climate capacity|能力建设|气候培训|气候人才
G08.05|人工智能与数字气候治理|AI and digital climate governance|artificial intelligence.{0,80}climate|climate.{0,80}artificial intelligence|AI.{0,25}climate|digital climate|数字气候|人工智能.{0,20}气候|气候.{0,20}人工智能
G08.06|气候创新生态与产业化|Climate innovation ecosystems|climate.tech startup|climate innovation|clean.tech commerciali|气候创新|气候科技初创|低碳技术产业化
G09.01|强化透明度框架|Enhanced transparency framework|enhanced transparency framework|biennial transparency report|强化透明度框架|两年期透明度报告
G09.02|温室气体清单与排放数据|GHG inventories and emissions data|emissions? inventor|greenhouse gas inventor|emission factors?|排放清单|温室气体清单|排放因子
G09.03|MRV与碳核算标准|MRV and carbon accounting|\bMRV\b|carbon accounting|monitoring.{0,20}reporting.{0,20}verification|碳核算|监测.{0,5}报告.{0,5}核查
G09.04|气候科学与IPCC评估|Climate science and IPCC|\bIPCC\b|climate science|climate assessment|气候科学|气候评估|政府间气候变化专门委员会
G09.05|气候政策效果评估|Climate policy evaluation|climate policy.{0,35}(?:effectiveness|evaluation|impact)|(?:evaluation|effectiveness).{0,35}climate polic|气候政策评估|气候政策效果
G09.06|气候数据基础设施与开放科学|Climate data and open science|climate data|climate database|climate model|climate remote sensing|气候数据|气候模型|气候遥感
G10.01|气候公平与历史责任|Equity and historical responsibility|climate justice|historical emissions|common but differentiated|CBDR|气候公平|历史排放|共同但有区别
G10.02|公正转型政策与机制|Just transition policies|just transition|公正转型
G10.03|就业、劳工与社会保障|Jobs labour and social protection|green jobs|energy transition.{0,40}workers|coal workers|绿色就业|煤炭工人|转型.{0,15}社会保障
G10.04|弱势群体与气候权利|Vulnerable groups and climate rights|climate rights|climate.{0,40}(?:gender|indigenous|youth)|(?:gender|indigenous|youth).{0,40}climate|气候权利|气候.{0,15}弱势群体
G10.05|发展权、能源可及性与贫困|Development energy access and poverty|energy poverty|energy access|right to development|能源贫困|能源可及|发展权
G11.01|大国气候外交与双边关系|Major-power climate diplomacy|climate diplomacy|bilateral climate|US.China.{0,40}climate|China.US.{0,40}climate|气候外交|中美气候|中欧气候
G11.02|气候谈判联盟与南北关系|Negotiating alliances and North-South relations|\bG77\b|\bAOSIS\b|Alliance of Small Island States|Like.Minded Developing Countries|小岛屿国家联盟|七十七国集团
G11.03|气候贸易政策与碳边境措施|Climate trade and border measures|\bCBAM\b|carbon border|carbon tariff|碳边境|碳关税|绿色贸易
G11.04|绿色产业竞争与供应链|Green industrial competition and supply chains|clean.energy supply chain|critical minerals|clean.tech industrial|green industrial polic|关键矿产|清洁能源供应链|绿色产业政策
G11.05|气候安全与地缘政治|Climate security and geopolitics|climate security|energy security|climate geopolitic|气候安全|能源安全|气候地缘政治
G12.01|森林保护与REDD+|Forests and REDD+|deforestation|reforestation|\bREDD\+?|forest carbon|毁林|森林碳|植树造林|deforestaci[oó]n|deforestasi
G12.02|土地利用与自然碳汇|Land use and natural carbon sinks|\bLULUCF\b|soil carbon|carbon sinks?|land.use emissions|土壤碳|碳汇|土地利用排放
G12.03|生物多样性与自然解决方案|Biodiversity and nature-based solutions|nature.based solutions|biodiversity.{0,50}climate|climate.{0,50}biodiversity|基于自然的解决方案|生物多样性.{0,20}气候
G12.04|海洋生态与蓝碳|Ocean ecosystems and blue carbon|blue carbon|ocean acidification|mangrove.{0,40}carbon|蓝碳|海洋酸化|红树林.{0,15}碳
G12.05|农业减排与可持续粮食系统|Agricultural mitigation and food systems|food system.{0,40}emission|agricultural emissions|livestock methane|sustainable food system|农业减排|粮食系统|畜牧业甲烷
G12.06|生态保护与气候协同治理|Integrated nature-climate governance|nature.climate nexus|climate.biodiversity nexus|Kunming.Montreal|Rio conventions|生态.{0,15}气候协同|里约三公约|昆明.蒙特利尔
G13.01|城市与地方政府气候行动|Cities and local climate action|\bC40\b|ICLEI|mayors.{0,30}climate|municipal climate|local climate action|城市气候行动|地方气候行动
G13.02|企业气候承诺与行动|Corporate climate commitments|corporate net.zero|corporate climate|company.{0,30}net.zero|企业净零|企业气候|企业减排
G13.03|金融机构与投资者气候行动|Financial institutions and investors|investor climate|net.zero banking|net.zero asset|GFANZ|金融机构.{0,20}气候|净零银行|投资者气候
G13.04|社会组织、公众与青年参与|Civil society and youth participation|climate protest|climate activism|Fridays for Future|climate movement|气候抗议|气候行动主义|气候公众参与|青年气候
G13.05|气候教育、传播与信息完整性|Education communication and information integrity|climate education|climate communication|climate misinformation|climate disinformation|climate denial|气候教育|气候传播|气候虚假信息|气候否认
G14.01|气候变化与公共健康|Climate and public health|climate.{0,40}health|heat.related (?:death|illness)|climate.{0,30}disease|气候.{0,15}健康|热相关死亡
G14.02|气候迁移、流离失所与人类安全|Climate migration and displacement|climate migra|climate refugees?|climate displacement|气候移民|气候难民|气候流离失所
G14.03|气候物理风险与极端事件归因|Physical risks and attribution|climate attribution|attribution study|climate physical risk|extreme event attribution|极端事件归因|气候归因|气候物理风险
G14.04|气候临界点与不可逆变化|Tipping points and irreversible change|climate tipping|tipping points?|irreversible.{0,30}climate|气候临界点|气候临界阈值|不可逆.{0,15}气候
G14.05|地球工程与气候干预治理|Geoengineering and climate intervention|geoengineering|solar radiation management|solar radiation modification|stratospheric aerosol|地球工程|太阳辐射管理|气候干预
G14.06|复合气候风险与级联影响|Compound and cascading climate risks|compound (?:climate |weather )?(?:risk|event|hazard)|cascading.{0,30}climate|climate.{0,30}cascading|复合气候风险|气候级联|复合极端事件
'''
EXTENSIONS={'G12.04','G12.05','G12.06',*(f'G14.{i:02d}' for i in range(1,7))}
TOPICS=[]
for line in ROWS.strip().splitlines():
 code,zh,en,pattern=line.split('|',3)
 TOPICS.append({'code':code,'parent':code[:3],'name_zh':zh,'name_en':en,'evidence_regex':pattern,'definition':en,'origin':'authorized_extension_20261106' if code in EXTENSIONS else 'user_supplied_screenshots','review_status':'research_dictionary_not_official_UNFCCC_standard'})
assert len(TOPICS)==83 and len({t['code'] for t in TOPICS})==83
PATTERNS={t['code']:re.compile(t['evidence_regex'],re.I) for t in TOPICS}
COUNTRY_EXTENSIONS={
 'PM':['Saint Pierre and Miquelon','Saint-Pierre-et-Miquelon'],
 'MO':['Macao','Macau','澳门'], 'HK':['Hong Kong','香港'],
 'VC':['Saint Vincent and the Grenadines','St Vincent and the Grenadines','St. Vincent and the Grenadines'],
 'TT':['Trinidad and Tobago'], 'UM':['United States Minor Outlying Islands','U.S. Minor Outlying Islands','Midway Atoll','Wake Island','Palmyra Atoll'],
 'BV':['Bouvet Island','Bouvetøya'], 'HM':['Heard Island','McDonald Islands'],
 'GS':['South Georgia and the South Sandwich Islands','South Georgia Island','South Sandwich Islands'],
 'WF':['Wallis and Futuna','Wallis-et-Futuna'], 'SJ':['Svalbard','Jan Mayen'],
 'SH':['Saint Helena','St Helena','St. Helena','Ascension Island','Tristan da Cunha'],
 'ST':['São Tomé and Príncipe','Sao Tome and Principe','São Tomé e Príncipe'],
 'TC':['Turks and Caicos'], 'CC':['Cocos Islands','Cocos (Keeling) Islands'],
 'BL':['Saint Barthélemy','Saint Barthelemy','St Barts'],
 'BQ':['Bonaire','Sint Eustatius','Caribbean Netherlands'],
 # Jersey is also a common noun and a US-state substring; contextual only.
 'JE':['Bailiwick of Jersey','Government of Jersey','Jersey government'],
}
COUNTRY_PATTERNS={code:re.compile(r'(?<![A-Za-z])(?:'+'|'.join(re.escape(x) for x in terms)+r')(?![A-Za-z])',re.I) for code,terms in COUNTRY_EXTENSIONS.items()}

def label(title,body):
 legacy=legacy_labels(title,body)
 evidence=[e for e in legacy['evidence'] if e['label_type']!='topic']
 countries=set(legacy['country_mentions'])
 for code,pattern in COUNTRY_PATTERNS.items():
  for field,text in [('title',title),('source_text',body)]:
   for m in list(pattern.finditer(text))[:3]:
    countries.add(code); evidence.append({'label_type':'country','label_id':code,'field':field,'start':m.start(),'end':m.end(),'quote':m.group(),'method':'explicit_territory_alias'})
 scores={}; focal=[]
 for code,pattern in PATTERNS.items():
  ts=list(pattern.finditer(title)); bs=list(pattern.finditer(body)); lead=[m for m in bs if m.start()<2000]
  if not ts and not bs: continue
  scores[code]=len(ts)*8+min(len(lead),4)*2+min(len(bs),3)
  if ts or len(lead)>=2 or (lead and len(bs)>=3): focal.append(code)
  for field,matches in [('title',ts),('source_text',bs)]:
   for m in matches[:3]: evidence.append({'label_type':'subcategory','label_id':code,'field':field,'start':m.start(),'end':m.end(),'quote':m.group()})
 parents=defaultdict(float)
 for code,score in scores.items(): parents[code[:3]]+=score
 primary=max(focal or list(scores),key=lambda k:scores[k]) if scores else None
 country_focal=sorted({e['label_id'] for e in evidence if e['label_type']=='country' and (e['field']=='title' or e['start']<1500)})
 return {'version':VERSION,'method':'evidence_span_lexical_candidates','review_status':'machine_candidate_requires_validation','primary_subcategory':primary,'primary_category':primary[:3] if primary else None,'subcategory_mentions':sorted(scores),'focal_subcategory_candidates':sorted(focal),'category_mentions':sorted(parents),'scores':scores,'country_mentions':sorted(countries),'country_focal_candidates':country_focal,'organization_mentions':legacy['organization_mentions'],'policy_tool_mentions':legacy['policy_tool_mentions'],'policy_stage_mentions':legacy['policy_stage_mentions'],'evidence':evidence}

def dictionary():
 return {'version':VERSION,'parent_count':14,'subcategory_count':83,'count_resolution':'User confirmed sum of screenshot row counts (83), not erroneous displayed total 77.','extension_authorization':'User authorized the nine missing definitions on 2026-11-06.','parents':[dict(zip(('code','name_zh','name_en'),p)) for p in PARENTS],'subcategories':TOPICS,'annotation_guidance':{'unit':'one distinct original article; multilingual translations/updates linked, not automatically new events','multi_label':True,'primary':'headline/lead-weighted lexical candidate; not a validated classifier','evidence':'verbatim Unicode offsets in title or source_text','country':'text mention, not publisher location or national position','events':'official dates and decisions require separate source verification','counting':'report mention and focal counts separately; control publisher/year coverage; no causal interpretation of co-occurrence'}}

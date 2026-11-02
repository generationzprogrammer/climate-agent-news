"""Reproduce the source-checked November expansion; no network or model calls."""
import json
from pathlib import Path
from climate_agent.research import load_jsonl
from climate_agent.stance_pilot import digest

ROOT=Path(__file__).resolve().parents[1]
corpus={r['text_id']:r for r in load_jsonl(ROOT/'data/research_texts.jsonl.gz')}
base=json.loads((ROOT/'data/stance_evidence.json').read_text(encoding='utf-8'))
sources=[];rows=[];lookup={s['id']:s for s in base['sources']}

def source(sid,actor,url,title,day,zh,en,quotes,lang='en'):
    row={'id':sid,'actor_id':actor,'url':url,'title':title,'authority_zh':zh,'authority_en':en,'language':lang,
         'source_text':'\n[…]\n'.join(dict.fromkeys(quotes)),'excerpt_scope':'Selected source-checked verbatim clauses; omissions explicitly marked',
         'publication_date':day,'checked_at':'2026-11-02'}
    sources.append(row);lookup[sid]=row;return sid

def add(sid,prop,quote,zh,en,*,day=None,stance='support',qual=None,reason=None,kind='public_policy_statement'):
    s=lookup[sid];text=corpus[s['corpus_text_id']]['source_text'] if s.get('corpus_text_id') else s['source_text']
    assert quote in text,(sid,quote)
    if qual:assert qual in text,(sid,qual)
    if reason:assert reason[0] in text,(sid,reason)
    rows.append({'id':f"{s['actor_id']}-{prop}-{len(rows)+1:03d}-expand20261102",'actor_id':s['actor_id'],'source_id':sid,
        'proposition_id':prop,'statement_date':day or s['publication_date'],'stance':stance,'statement_kind':kind,
        'date_basis':'Official statement or publication date; historical documents are not current implementation measurements',
        'date_basis_zh':'所引官方表态或文件公布日期；历史承诺不代表当下实施结果。',
        'summary_zh':zh,'summary_en':en,'evidence_quote':quote,'qualifier_quote':qual,
        'reasons':[] if not reason else [{'quote':reason[0],'text_zh':reason[1],'text_en':reason[2]}],
        'review_status':'editorial_source_check_ai_assisted'})

# Existing OGL-3.0 source: preserve its original fingerprint and the first release.
GB='GB-NDC-2025'
add(GB,'mitigation_ndc','reduce all greenhouse gas emissions by at least 81% by 2035, compared to 1990 levels',
    '2035年全经济范围温室气体排放至少比1990年减少81%；文件排除国际航空和航运排放，属于目标而非已实现减排。',
    'Targets at least an 81% economy-wide greenhouse-gas reduction by 2035 from 1990, excluding international aviation and shipping; this is a target, not achieved abatement.',day='2025-01-30',kind='national_commitment')
add(GB,'mitigation_netzero','The NDC is also on the trajectory to UK net zero greenhouse gas emissions by 2050',
    '将2035年国家减排目标置于2050年温室气体净零路径上。','Places the 2035 contribution on a trajectory to UK net-zero greenhouse-gas emissions by 2050.',day='2025-01-30',kind='national_commitment')
add(GB,'science_ipcc','a 1.5°C aligned, economy-wide target, covering all greenhouse gases, sectors and categories, informed by the latest science',
    '说明新目标覆盖各温室气体与部门，以最新科学为基础，并与1.5℃路径相衔接。','Describes its economy-wide target as informed by the latest science and aligned with 1.5°C pathways.',day='2025-01-30')
add(GB,'transparency_methods','The UK accounts for emissions and removals in accordance with methodologies and common metrics assessed by the IPCC and adopted by the CMA',
    '排放与清除量核算采用政府间气候变化专门委员会评估、巴黎协定缔约方会议通过的方法与共同指标。',
    'Accounts for emissions and removals using methods and common metrics assessed by the IPCC and adopted by the CMA.',day='2025-01-30')
add(GB,'transparency_reports','please see the UK’s 1st Biennial Transparency Report',
    '通过首份双年透明度报告公开国家气候、人口、经济等履约背景资料；此处不把报告提及解释为新增减排成效。',
    'Directs readers to its first Biennial Transparency Report for national circumstances; the reference is not evidence of additional achieved reductions.',day='2025-01-30',kind='reporting_action')
add(GB,'justice_workers','The UK is dedicated to supporting workers, communities and businesses to transition to net zero.',
    '承诺支持劳动者、社区和企业向净零转型，并以清洁能源就业机构衔接技能需求。',
    'Commits to supporting workers, communities and businesses in the net-zero transition, linking clean-energy employment with skill needs.',day='2025-01-30')
add(GB,'justice_equity','the principles of equity and “common but differentiated responsibilities and respective capabilities, in the light of different national circumstances”',
    '在解释目标公平性时引用公平、共同但有区别的责任与各自能力，并强调不同国情。',
    'Invokes equity and common but differentiated responsibilities and respective capabilities in light of different national circumstances when explaining target fairness.',day='2025-01-30')
add(GB,'energy_clean','setting out how we will deliver clean power in Great Britain by 2030',
    '提出到2030年在大不列颠实现清洁电力的行动安排；这是政策目标，不是已经完成的电源结构。',
    'Sets out delivery of clean power in Great Britain by 2030; this is a policy objective, not a completed electricity mix.',day='2025-01-30',kind='national_commitment')
add(GB,'energy_efficiency','set out plans to increase the energy efficiency of rented homes to take a million households out of fuel poverty',
    '计划提高出租住房能效，并把减少燃料贫困作为明确政策目的。',
    'Plans to improve rented-home energy efficiency with an explicit objective of reducing fuel poverty.',day='2025-01-30',reason=('to take a million households out of fuel poverty','帮助家庭摆脱燃料贫困。','Help households escape fuel poverty.'))
add(GB,'energy_technology','launched Britain’s carbon capture industry',
    '在国家自主贡献中列举碳捕集产业启动措施，作为低碳产业政策的一部分；未据此认定实际捕集量。',
    'Lists the launch of the carbon-capture industry among low-carbon industrial measures; no captured-volume outcome is inferred.',day='2025-01-30',kind='reported_policy_action')
add(GB,'mitigation_methane','announced £5 million to help developing countries tackle methane emissions in their fossil fuel sectors',
    '宣布提供500万英镑，帮助发展中国家控制化石燃料部门的甲烷排放；该金额为宣布支持，并非已核验拨付。',
    'Announces £5 million to help developing countries tackle fossil-sector methane; this is announced support, not verified disbursement.',day='2025-01-30')
add(GB,'adaptation_plans','The UK’s third National Adaptation Programme [footnote 12] ( NAP3 ) was published on 17 July 2023 and covers the five years up to 2028.',
    '重申第三份国家适应方案覆盖至2028年；方案于2023年发布，2025年的文件再次说明其实施周期。',
    'Restates the third National Adaptation Programme covering the period to 2028; the programme was published in 2023, not newly adopted in 2025.',day='2025-01-30')
add(GB,'adaptation_indicators','the UK government adopted the UAE Framework for Global Climate Resilience',
    '确认采纳阿联酋全球气候韧性框架，作为落实全球适应目标的依据。',
    'Confirms adoption of the UAE Framework for Global Climate Resilience in implementing the global goal on adaptation.',day='2025-01-30')

# A separate historical NDC makes the timeline inspectable without implying achieved progress.
old=corpus['text_01bd13f48e0b8c5e5a97']
s={'id':'GB-NDC-2022-EXP','actor_id':'GB','url':old['publisher_url'],'title':old['title_original'],
   'authority_zh':'英国政府，2030年国家自主贡献更新文本','authority_en':'UK Government; updated 2030 nationally determined contribution',
   'language':'en','corpus_text_id':old['text_id'],'corpus_sha256':digest(old['source_text']),'rights':'OGL-3.0','publication_date':'2022-09-23'}
sources.append(s);lookup[s['id']]=s
needle='at least 68%';i=old['source_text'].find(needle);assert i>=0
quote=old['source_text'][i:i+140].split('.')[0]
add(s['id'],'mitigation_ndc',quote,'2022年更新的国家自主贡献以2030年为目标期，提出至少较1990年减排68%；与2035年目标的差异不代表已实现减排进展。',
    'The 2022 update targets at least a 68% reduction from 1990 by 2030; its difference from the 2035 target is not achieved emission progress.',kind='historical_national_commitment')

sid=source('GB-LOSS-2023-EXP','GB','https://www.gov.uk/government/speeches/pms-national-statement-at-cop28-december-01-2023',
    "PM's National Statement at COP28: December 01 2023",'2023-12-01','时任英国首相苏纳克，COP28国家发言','Then UK Prime Minister Rishi Sunak; COP28 national statement',
    ['This also includes up to £60 million for Loss and Damage… £40 million of which is for the new fund.','To succeed, the fund must be open to all sources of support.'])
add(sid,'loss_fund','£40 million of which is for the new fund','宣布为新损失与损害基金提供4000万英镑支持；这是2023年的承诺记录。','Pledges £40 million to the new loss-and-damage fund; this is a 2023 commitment record.')
add(sid,'loss_support','up to £60 million for Loss and Damage','宣布最高6000万英镑用于损失与损害应对；不能将其与基金4000万英镑相加。','Announces up to £60 million for loss and damage; the £40 million fund pledge is included, not additional.')

sid=source('CN-ADAPT-2026-EXP','CN','https://www.mee.gov.cn/ywdt/xwfb/202606/t20260617_1159586.shtml','中国适应气候变化进展报告（2025）发布','2026-06-17','生态环境部','Ministry of Ecology and Environment',
    ['锚定2035年气候适应型社会基本建成的总体目标','必须加快提升适应气候变化能力，有效化解系统性气候风险'],lang='zh')
add(sid,'adaptation_plans','锚定2035年气候适应型社会基本建成的总体目标','以2035年基本建成气候适应型社会为总体目标，持续完善适应工作体系。','Retains the overall objective of substantially establishing a climate-adaptive society by 2035.')
add(sid,'science_risk','有效化解系统性气候风险','将化解系统性气候风险列为适应工作的明确方向，不将单一灾害事件等同于长期趋势。','Explicitly prioritises addressing systemic climate risks in adaptation action.')
sid=source('CN-EARLY-2025-EXP','CN','https://www.mee.gov.cn/ywdt/xwfb/202506/t20250625_1121907.shtml','中国适应气候变化进展报告（2024）发布','2025-06-25','生态环境部','Ministry of Ecology and Environment',
    ['启动气候变化南南合作早期预警旗舰项目','为其他发展中国家提高早期预警和适应气候变化能力提供支持'],lang='zh')
add(sid,'adaptation_warning','启动气候变化南南合作早期预警旗舰项目','通过气候变化南南合作早期预警旗舰项目，支持其他发展中国家提高预警和适应能力。','Uses a South–South early-warning flagship project to support developing countries’ warning and adaptation capabilities.',reason=('为其他发展中国家提高早期预警和适应气候变化能力提供支持','支持其他发展中国家的预警和适应能力。','Support other developing countries’ warning and adaptation capacity.'))
sid=source('CN-BTR-2025-EXP','CN','https://www.mee.gov.cn/ywgz/ydqhbh/qhbhlf/202501/t20250110_1100393.shtml','我国提交第一次双年透明度报告与第四次两年更新报告','2025-01-10','生态环境部','Ministry of Ecology and Environment',
    ['2024年12月31日，我国如期向《公约》秘书处提交','本次编制国家温室气体清单全面参考《2006年政府间气候变化专门委员会（IPCC）国家温室气体清单编制指南》'],lang='zh')
add(sid,'transparency_reports','2024年12月31日，我国如期向《公约》秘书处提交','2024年12月31日提交首份双年透明度报告及第四次两年更新报告；官方消息于2025年1月发布。','Submitted its first BTR and fourth biennial update report on 31 December 2024; the official notice was published in January 2025.',day='2024-12-31',kind='reporting_action')
add(sid,'transparency_methods','全面参考《2006年政府间气候变化专门委员会（IPCC）国家温室气体清单编制指南》','本轮国家温室气体清单编制参考2006年政府间气候变化专门委员会指南，支持清单可比性。','Uses the 2006 IPCC inventory guidelines in compiling this national greenhouse-gas inventory.',kind='reporting_method')
sid=source('CN-METHANE-2023-EXP','CN','https://www.mee.gov.cn/ywgz/ydqhbh/wsqtkz/202311/t20231107_1055439.shtml','生态环境部联合有关部门发布甲烷排放控制行动方案','2023-11-07','生态环境部等11部门','Ministry of Ecology and Environment and ten other departments',
    ['加强甲烷排放管理控制','推进减污降碳协同增效的内在要求'],lang='zh')
add(sid,'mitigation_methane','加强甲烷排放管理控制','以专项行动方案推进甲烷排放管理控制，强调减污降碳协同。','Adopts a dedicated methane-control action plan, emphasising synergies between pollution control and carbon reduction.',kind='policy_adoption',reason=('推进减污降碳协同增效的内在要求','推进减污降碳协同增效。','Promote synergies between pollution control and carbon reduction.'))
sid=source('CN-COP30-2025-EXP','CN','https://www.mee.gov.cn/ywdt/xwfb/202510/t20251030_1131010.shtml','生态环境部2025年10月例行新闻发布会','2025-10-30','生态环境部气候变化事务发言','Ministry of Ecology and Environment; climate briefing',
    ['应推动全球适应目标、技术实施方案等取得实质性成果','希望大会关注当前单边主义、保护主义抬高全球特别是发展中国家能源转型成本的问题'],lang='zh')
add(sid,'adaptation_indicators','应推动全球适应目标、技术实施方案等取得实质性成果','要求COP30在全球适应目标上形成实质成果，同时推动技术实施方案。','Calls for substantive COP30 outcomes on the global goal on adaptation and the technology implementation programme.')
add(sid,'energy_technology','技术实施方案等取得实质性成果','将技术实施方案的实质成果列为COP30谈判重点。','Identifies substantive outcomes on technology implementation as a COP30 priority.')
add(sid,'justice_trade','单边主义、保护主义抬高全球特别是发展中国家能源转型成本','要求关注单边主义和保护主义对能源转型成本的影响，支持绿色低碳产品流动。','Calls attention to transition costs raised by unilateralism and protectionism and supports green-product flows.',reason=('单边主义、保护主义抬高全球特别是发展中国家能源转型成本','担忧发展中国家的能源转型成本上升。','Concern over higher energy-transition costs, particularly in developing countries.'))

# Short, attributed passages from a Council position; same URL is counted once.
sid=source('EU-COP30-DETAIL-2025-EXP','EU','https://www.consilium.europa.eu/en/press/press-releases/2025/10/21/cop30-council-sets-eu-position-for-the-climate-conference-in-belem/',
    'COP30: Council sets EU position for the climate conference in Belém','2025-10-21','欧盟理事会，COP30共同立场','Council of the European Union; common COP30 position',
    ['nationally determined contributions (NDCs) aligned with 1.5°C pathways','best available science','progress on adaptation goals','triple renewable energy capacity globally','energy efficiency improvements'])
add(sid,'mitigation_ndc','nationally determined contributions (NDCs) aligned with 1.5°C pathways','要求提交与1.5℃路径相衔接的国家自主贡献，并提高主要排放方的目标力度。','Calls for NDCs aligned with 1.5°C pathways and greater ambition from major emitters.')
add(sid,'science_ipcc','best available science','要求国家自主贡献以最佳可用科学为依据，并参考首次全球盘点。','Calls for nationally determined contributions informed by the best available science and the first global stocktake.')
add(sid,'adaptation_indicators','progress on adaptation goals','把推进适应目标列为COP30共同优先事项。','Makes progress on adaptation goals a common COP30 priority.')
add(sid,'energy_clean','triple renewable energy capacity globally','支持到2030年全球可再生能源装机增至三倍；这是全球目标，不是欧盟单独装机目标。','Supports tripling global renewable capacity by 2030; this is a global, not an EU-only, target.')
add(sid,'energy_efficiency','energy efficiency improvements','支持到2030年将全球年均能效改善速度翻倍；不等同于能源消费量减半。','Supports doubling the global average annual efficiency-improvement rate by 2030; this is not a halving of energy consumption.')

sid=source('AU-TARGET-2025-EXP','AU','https://www.dcceew.gov.au/about/news/setting-2035-target-path-net-zero','Setting our 2035 target and path to net zero','2025-09-18',
    '澳大利亚气候变化、能源、环境和水务部','Department of Climate Change, Energy, the Environment and Water',
    ['reduce emissions by 62–70% below 2005 levels by 2035','backed by science and expert advice','Clean electricity across the economy.','electrification and efficiency'])
add(sid,'mitigation_ndc','reduce emissions by 62–70% below 2005 levels by 2035','设定2035年排放较2005年减少62%至70%的目标；不能与以1990年为基年的目标直接比较百分比。','Sets a 62–70% emissions reduction target by 2035 from 2005; the percentage is not directly comparable with a 1990-baseline target.',kind='national_commitment')
add(sid,'science_ipcc','backed by science and expert advice','说明目标以科学及专家意见为支撑，采用气候变化局提出的目标区间。','Describes the target as backed by science and expert advice, adopting the Climate Change Authority’s target range.')
add(sid,'energy_clean','Clean electricity across the economy.','将全经济范围的清洁电力列为净零计划的脱碳优先方向。','Makes clean electricity across the economy a decarbonisation priority in the Net Zero Plan.')
add(sid,'energy_efficiency','electrification and efficiency','把电气化和能效改善并列为减排路径，不将两者视为同一指标。','Identifies electrification and efficiency as complementary emission-reduction pathways.')
sid=source('AU-NETZERO-2025-EXP','AU','https://www.dcceew.gov.au/climate-change/emissions-reduction/net-zero','Net Zero','2025-11-25',
    '澳大利亚气候变化、能源、环境和水务部','Department of Climate Change, Energy, the Environment and Water',
    ['Australia has set a legislated target to reduce our greenhouse gas emissions to net zero by 2050.'])
add(sid,'mitigation_netzero','legislated target to reduce our greenhouse gas emissions to net zero by 2050','以立法确立2050年温室气体净零目标。','Enshrines the 2050 greenhouse-gas net-zero target in legislation.',kind='legislated_target')
sid=source('AU-ADAPT-2025-EXP','AU','https://www.dcceew.gov.au/about/news/adapting-to-climate-risk-in-australia-pathway-forward','Adapting to climate risk in Australia – a pathway forward','2025-09-15',
    '澳大利亚气候变化、能源、环境和水务部','Department of Climate Change, Energy, the Environment and Water',
    ['our first National Climate Risk Assessment','our National Adaptation Plan – a policy framework to respond to these risks.'])
add(sid,'science_risk','our first National Climate Risk Assessment','发布首份国家气候风险评估，为识别全国性气候影响和后续适应规划提供证据。','Releases the first National Climate Risk Assessment to inform nationally significant climate-risk management.',kind='assessment_release')
add(sid,'adaptation_plans','our National Adaptation Plan – a policy framework to respond to these risks.','发布国家适应计划，将国家气候风险评估与政策应对框架相衔接。','Publishes a National Adaptation Plan linking assessed climate risks with a policy-response framework.',kind='policy_adoption')

sid=source('JP-NDC-2025-EXP','JP','https://www.env.go.jp/earth/earth/ondanka/ndc.html','日本のNDC（国が決定する貢献）','2025-02-18','日本环境省','Ministry of the Environment, Japan',
    ['2035年度、2040年度において、温室効果ガスを2013年度からそれぞれ60％、73％削減','2050年ネット・ゼロの実現'],lang='ja')
add(sid,'mitigation_ndc','2035年度、2040年度において、温室効果ガスを2013年度からそれぞれ60％、73％削減','目标为2035和2040财年温室气体排放较2013财年分别减少60%和73%；两个目标期分别列示。','Targets greenhouse-gas reductions of 60% in FY2035 and 73% in FY2040 from FY2013; these are separate target years.',kind='national_commitment')
add(sid,'mitigation_netzero','2050年ネット・ゼロの実現','把新一轮国家自主贡献置于2050年净零路径上。','Places the new national contribution on a pathway to net zero in 2050.',kind='national_commitment')
sid=source('JP-COP30-2025-EXP','JP','https://www.mofa.go.jp/ic/ch/pagewe_000001_00290.html','Outcomes of COP30, CMP20, CMA7, SBSTA63 and SBI63','2025-12-05',
    '日本外务省对环境大臣COP30发言的官方整理','Ministry of Foreign Affairs; official account of the Environment Minister’s COP30 statement',
    ['all countries submitting the NDCs with the highest possible ambition at the earliest','Japan is steadily making progress through mechanisms like JCM'])
add(sid,'mitigation_ndc','all countries submitting the NDCs with the highest possible ambition at the earliest','呼吁各国尽早提交尽可能高力度的国家自主贡献并落实；记录日期采用外务省总结公布日。','Urges all countries to submit the highest-possible-ambition NDCs promptly and implement them; dated by publication of the official account.')
add(sid,'market_article6','Japan is steadily making progress through mechanisms like JCM','通过联合抵消机制推进国际减排合作；并未据此认定所有项目均已完成第六条国际转移。','Reports cooperation through the Joint Crediting Mechanism; this does not establish that all projects have completed Article 6 transfers.')

sid=source('ZA-COP30-2025-EXP','ZA','https://www.gov.za/news/speeches/minister-dion-george-leader%E2%80%99s-summit-cop30-unfccc-07-nov-2025','Minister Dion George: Leader’s Summit COP30 UNFCCC','2025-11-07',
    '南非环境部长迪翁·乔治，代表总统发言','Minister Dion George, speaking on behalf of President Cyril Ramaphosa',
    ['The Global Goal on Adaptation must deliver measurable indicators and the finance to achieve them.','The Loss and Damage Fund must be capitalised.'])
add(sid,'adaptation_indicators','The Global Goal on Adaptation must deliver measurable indicators and the finance to achieve them.','要求全球适应目标形成可衡量指标，同时落实支撑这些指标的资金。','Calls for measurable global adaptation indicators together with the finance needed to achieve them.')
add(sid,'loss_fund','The Loss and Damage Fund must be capitalised.','要求为损失与损害基金充实资金，强调资金落实而非仅有机构设置。','Calls for capitalisation of the Loss and Damage Fund, emphasising actual resourcing.')
sid=source('ZA-CONSULT-2025-EXP','ZA','https://www.gov.za/news/speeches/minister-dion-george-national-stakeholder-consultation-unfcccs-cop30-20-oct-2025',
    'Minister Dion George: National stakeholder consultation on COP30','2025-10-20','南非环境部长迪翁·乔治','Minister Dion George',
    ['Our NDC is informed by science','does not leave any South African behind','early warning systems','addresses the barriers developing-economy countries face in accessing climate finance'])
add(sid,'science_ipcc','Our NDC is informed by science','说明新国家自主贡献以科学为依据，并与本国气候变化法衔接。','States that its NDC is science-informed and aligned with the national Climate Change Act.')
add(sid,'justice_workers','does not leave any South African behind','把不让任何南非人掉队作为低碳转型的社会公正要求。','Frames the low-carbon transition around leaving no South African behind.')
add(sid,'adaptation_warning','early warning systems','把早期预警系统纳入适应重点，与灾害风险管理和韧性居民点建设并列。','Includes early-warning systems among adaptation priorities alongside disaster-risk management and resilient settlements.')
add(sid,'finance_delivery','addresses the barriers developing-economy countries face in accessing climate finance','要求融资路线图解决发展中国家获取气候资金的障碍。','Calls for a financing roadmap that addresses developing countries’ barriers to accessing climate finance.')

# Public collective statements: never inherited by member countries.
for actor in ['BASIC','LMDC']:
    sid=source(actor+'-COP30-2025-EXP',actor,'https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2189018&lang=2&reg=48',
        'Official account of BASIC and LMDC statements at the COP30 opening plenary','2025-11-11',
        '印度代表'+('基础四国' if actor=='BASIC' else '立场相近发展中国家集团')+'发言；印度新闻局官方整理',
        'India speaking for '+actor+'; official Press Information Bureau account',
        ['CBDR-RC remains the cornerstone of the global climate regime','fulfil their obligations on finance, technology transfer and capacity-building'])
    add(sid,'justice_equity','CBDR-RC remains the cornerstone of the global climate regime','重申共同但有区别的责任和各自能力是全球气候制度的基石；本记录归属于集团。','Reaffirms common but differentiated responsibilities and respective capabilities as a cornerstone of the climate regime; attributed to the group.')
    add(sid,'finance_delivery','fulfil their obligations on finance, technology transfer and capacity-building','要求发达国家落实资金、技术转让和能力建设义务；不自动归为每个成员国的单独声明。','Calls on developed countries to fulfil finance, technology-transfer and capacity-building obligations; not automatically attributed to each member state.')
    add(sid,'energy_technology','fulfil their obligations on finance, technology transfer and capacity-building','把技术转让列为发达国家应履行的支持义务，强调发展中国家的落实条件。','Identifies technology transfer as a support obligation of developed countries for developing-country implementation.')

sid=source('G77-GOVERNANCE-2026-EXP','G77','https://www.g77.org/doc/Declaration2026.htm','G77 and China Ministerial Declaration 2026','2026-09-25',
    '七十七国集团和中国外长会议','Ministerial Meeting of the G77 and China',
    ['upholding the principle of equity and common but differentiated responsibilities and respective capabilities','loss and damage response','national adaptation plans by 2030'])
add(sid,'justice_equity','upholding the principle of equity and common but differentiated responsibilities and respective capabilities','重申落实气候议程应维护公平、共同但有区别的责任与各自能力。','Reaffirms equity and common but differentiated responsibilities and respective capabilities in implementing the climate agenda.')
add(sid,'loss_support','loss and damage response','要求发达国家提供可预测、可持续支持，以增强发展中国家的损失与损害应对。','Calls for predictable, sustainable developed-country support for developing countries’ loss-and-damage response.')
add(sid,'adaptation_plans','national adaptation plans by 2030','强调支持发展中国家到2030年落实国家适应计划。','Emphasises support for implementing developing countries’ national adaptation plans by 2030.')

sid=source('IN-NDC-2022-EXP','IN','https://www.pib.gov.in/PressReleasePage.aspx?PRID=1847813&lang=2&reg=48',
    'Cabinet approves India’s Updated Nationally Determined Contribution','2022-08-03','印度联邦内阁，印度新闻局公告','Union Cabinet; Press Information Bureau',
    ['reduce Emissions Intensity of its GDP by 45 percent by 2030','reaching net-zero by 2070'])
add(sid,'mitigation_ndc','reduce Emissions Intensity of its GDP by 45 percent by 2030','2030年单位GDP排放强度较2005年降低45%；该指标不是绝对排放量下降45%。','Targets a 45% reduction in emissions intensity of GDP by 2030 from 2005; this is not a 45% absolute-emissions reduction.',kind='national_commitment')
add(sid,'mitigation_netzero','reaching net-zero by 2070','把国家自主贡献更新与2070年净零长期目标衔接。','Links the NDC update with the long-term goal of net zero by 2070.',kind='national_commitment')
add('IN-FINANCE-2025','justice_equity','incompatible with the principle of Common but Differentiated Responsibilities','评价COP29资金目标时强调共同但有区别的责任原则；与资金目标保留意见来自同一份答复。','Invokes common but differentiated responsibilities in assessing the COP29 finance goal; this is the same source event as its finance reservation.',day='2025-08-11')

sid=source('US-PARIS-2025-EXP','US','https://www.whitehouse.gov/presidential-actions/2025/01/putting-america-first-in-international-environmental-agreements/',
    'Putting America First in International Environmental Agreements','2025-01-20','美国总统，特朗普政府，行政令14162','US President; Trump administration; Executive Order 14162',
    ['shall immediately submit formal written notification of the United States’ withdrawal from the Paris Agreement','These agreements must not unduly or unfairly burden the United States.'])
add(sid,'mitigation_paris','shall immediately submit formal written notification of the United States’ withdrawal from the Paris Agreement',
    '行政令要求提交退出巴黎协定的正式通知；这里记录联邦行政当局对协定参与的撤回，不推断各州减排政策。',
    'Directs formal notification of withdrawal from the Paris Agreement; records federal executive withdrawal from the framework, not a conclusion about state-level mitigation policies.',stance='oppose',reason=('These agreements must not unduly or unfairly burden the United States.','行政令提出，国际协议不应使美国承担过度或不公平负担。','The order argues that international agreements must not unduly or unfairly burden the United States.'))

# Targets are not comparable without their baseline, coverage and target year.
sid=source('CN-NDC-2035-EXP','CN','https://www.mee.gov.cn/ywdt/xwfb/202510/t20251030_1131010.shtml','生态环境部解读中国2035年国家自主贡献','2025-10-30',
    '生态环境部对2025年9月24日公布目标的说明','Ministry of Ecology and Environment; explanation of targets announced on 24 September 2025',
    ['到2035年，中国全经济范围温室气体净排放量比峰值下降7%—10%，力争做得更好','非化石能源消费占能源消费总量的比重达到30%以上','风电和太阳能发电总装机容量达到2020年的6倍以上、力争达到36亿千瓦'],lang='zh')
add(sid,'mitigation_ndc','到2035年，中国全经济范围温室气体净排放量比峰值下降7%—10%，力争做得更好','2035年全经济范围温室气体净排放量比峰值下降7%至10%，并争取更好结果；基准是峰值，不是某个固定历史年。','Targets a 7–10% reduction in economy-wide net greenhouse-gas emissions from peak levels by 2035, striving to do better; the baseline is the peak, not a fixed historical year.',day='2025-09-24',kind='national_commitment')
add(sid,'energy_clean','非化石能源消费占能源消费总量的比重达到30%以上','2035年非化石能源消费比重达到30%以上；这是能源消费口径，不能与清洁电力发电占比混用。','Targets a non-fossil share above 30% of total energy consumption by 2035; this is not an electricity-generation share.',day='2025-09-24',kind='national_commitment')
add(sid,'energy_wind','风电和太阳能发电总装机容量达到2020年的6倍以上、力争达到36亿千瓦','2035年风电与太阳能发电总装机达到2020年的6倍以上，力争36亿千瓦；目标合计包含风电和太阳能。','Targets combined wind and solar capacity above six times the 2020 level by 2035, striving for 3.6 billion kW; the target is not wind capacity alone.',day='2025-09-24',kind='national_commitment')
add(GB,'energy_wind','we have lifted the onshore wind ban','国家自主贡献列明取消陆上风电禁令，作为扩大清洁电力的政策措施。','Lists lifting the onshore-wind ban as a measure supporting clean-power expansion.',day='2025-01-30',kind='reported_policy_action')

sid=source('BR-NDC-2024-EXP','BR','https://www.gov.br/povosindigenas/pt-br/assuntos/noticias/2024/11/brasil-entrega-a-onu-nova-ndc-alinhada-ao-acordo-de-paris','Brasil entrega à ONU nova NDC alinhada ao Acordo de Paris','2024-11-13',
    '巴西政府，原住民事务部官方介绍','Government of Brazil; Ministry of Indigenous Peoples',
    ['entre 59% e 67% até 2035, em comparação aos níveis de 2005','cenários econômicos, de cooperação internacional e de avanços tecnológicos'],lang='pt')
add(sid,'mitigation_ndc','entre 59% e 67% até 2035, em comparação aos níveis de 2005','2035年温室气体净排放量较2005年降低59%至67%，以区间表述目标，并说明经济、国际合作与技术情景变化可能影响执行。','Targets a 59–67% net greenhouse-gas reduction by 2035 from 2005, explicitly allowing a range in light of economic, international-cooperation and technology scenarios.',stance='qualified',qual='cenários econômicos, de cooperação internacional e de avanços tecnológicos',kind='national_commitment')

sid=source('US-WIND-2025-EXP','US','https://www.whitehouse.gov/presidential-actions/2025/01/temporary-withdrawal-of-all-areas-on-the-outer-continental-shelf-from-offshore-wind-leasing-and-review-of-the-federal-governments-leasing-and-permitting-practices-for-wind-projects/',
    'Temporary withdrawal and review of federal wind leasing and permitting','2025-01-20','美国总统，特朗普政府，风电备忘录','US President; Trump administration; wind memorandum',
    ['shall not issue new or renewed approvals, rights of way, permits, leases, or loans for onshore or offshore wind projects pending the completion of a comprehensive assessment and review of Federal wind leasing and permitting practices'])
add(sid,'energy_wind','shall not issue new or renewed approvals, rights of way, permits, leases, or loans for onshore or offshore wind projects',
    '2025年备忘录要求在综合审查完成前暂停新的或续期风电批准、许可、租赁及贷款；本条记录当时行政要求，不据此判断后续诉讼和项目状态。',
    'The 2025 memorandum pauses new or renewed wind approvals, permits, leases and loans pending review; this records the order at that date, not subsequent litigation or project status.',
    stance='qualified',qual='pending the completion of a comprehensive assessment and review of Federal wind leasing and permitting practices',kind='dated_executive_direction')

payload={'version':'1.1.0','checked_at':'2026-11-02','review_method':'AI-assisted editorial comparison against official source passages; not an independent human benchmark','sources':sources,'assertions':rows}
path=ROOT/'data/stance_evidence_expansion_20261102.json'
path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'new_assertions':len(rows),'new_source_versions':len(sources),'output':str(path.relative_to(ROOT))}))

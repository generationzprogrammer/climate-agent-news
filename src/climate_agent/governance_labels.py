"""Versioned, evidence-addressable climate-governance screening labels.

These are lexical research candidates, never inferred national positions.
Offsets always address the original input string (Unicode, end exclusive).
"""
from __future__ import annotations
import re
from collections import defaultdict
from .taxonomy import country_mentions_with_evidence, ORGANIZATION_GROUPS

VERSION = 'governance-2026.11.05-v1'
# id, parent, Chinese, English, explicit bilingual evidence patterns
TOPICS = (
 ('negotiations','institutions','国际谈判与履约','Negotiations and implementation',r'\bUNFCCC\b|\bCOP\s*-?\s*\d{1,2}\b|Paris Agreement|climate negotiations?|global stocktake|nationally determined contributions?|\bNDCs?\b|巴黎协定|全球盘点|国家自主贡献|气候谈判'),
 ('mitigation','transition','减排目标与行动','Mitigation targets and action',r'net[- ]zero|carbon neutral(?:ity)?|decarboni[sz]\w*|emissions? reductions?|reduce.{0,30}emissions?|methane emissions?|碳中和|碳达峰|净零|减排|甲烷排放'),
 ('energy','transition','能源与产业转型','Energy and industrial transition',r'renewable energy|clean energy|energy transition|solar (?:power|energy|panel|farm)|wind (?:power|energy|farm)|coal phase[- ]out|fossil fuels?|electric vehicles?|battery storage|green hydrogen|carbon capture|可再生能源|能源转型|光伏|风电|储能|绿氢|碳捕集|化石燃料'),
 ('adaptation','risk','适应与韧性','Adaptation and resilience',r'climate adaptation|adaptation (?:plan|fund|finance|strategy)|climate resilience|climate[- ]resilient|early warning systems?|coastal protection|flood defen[cs]e|气候适应|适应气候|气候韧性|早期预警|防洪'),
 ('loss_damage','risk','损失与损害','Loss and damage',r'loss and damage|loss[- ]and[- ]damage|climate reparations?|climate compensation|损失与损害|损失和损害|气候赔偿'),
 ('finance','resources','气候资金与金融','Climate finance',r'climate financ\w*|climate fund\w*|green climate fund|green bonds?|climate investment|climate[- ]related financial|adaptation financ\w*|气候资金|气候融资|绿色金融|绿色债券|气候基金'),
 ('markets','institutions','碳市场与定价','Carbon markets and pricing',r'carbon (?:markets?|credits?|pricing|prices?|tax|offsets?)|emissions? trading|Article 6(?:\b|\.)|\bETS\b|碳市场|碳价|碳税|碳信用|碳排放权交易|第六条'),
 ('transparency','institutions','透明度与碳核算','Transparency and carbon accounting',r'carbon accounting|emissions? inventor\w*|biennial transparency|enhanced transparency framework|monitoring.{0,15}reporting.{0,15}verification|\bMRV\b|carbon footprint|碳核算|排放清单|透明度报告|碳足迹|监测.{0,5}报告.{0,5}核查'),
 ('technology','resources','技术合作与能力建设','Technology cooperation and capacity',r'technology transfer|climate technolog\w*|clean technology|capacity[- ]building|technical assistance|climate innovation|技术转让|技术转移|气候技术|能力建设|技术援助'),
 ('nature','land_society','土地、生态与农业','Land, ecosystems and agriculture',r'deforestation|reforestation|afforestation|forest carbon|carbon sinks?|climate[- ]smart agriculture|land[- ]use change|nature[- ]based solutions?|\bREDD\+?|毁林|植树造林|森林碳|碳汇|土地利用变化|气候智慧型农业|基于自然的解决方案'),
 ('justice','land_society','公正转型与社会影响','Just transition and social impacts',r'climate justice|just transition|climate migration|climate refugees?|climate litigation|environmental justice|indigenous.{0,60}(?:climate|carbon|forest)|公正转型|气候正义|气候移民|气候诉讼|环境正义'),
 ('science_impacts','risk','气候科学与灾害风险','Climate science and physical risks',r'global warming|global temperatures?|sea[- ]level rise|climate impacts?|heatwaves?|droughts?|wildfires?|extreme (?:weather|heat|rainfall)|ice sheets?|glaciers?|全球变暖|全球温度|海平面上升|热浪|干旱|野火|极端天气|冰川'),
)
PATTERNS = {t[0]:re.compile(t[4],re.I) for t in TOPICS}
TOOL_PATTERNS = {
 'regulation':r'emissions? standards?|climate law|regulation|mandate|ban on|排放标准|气候法|强制|禁令',
 'economic':r'carbon tax|subsid(?:y|ies)|tax credit|emissions? trading|green bonds?|碳税|补贴|税收抵免|排放权交易',
 'planning':r'action plan|roadmap|nationally determined contribution|行动计划|路线图|国家自主贡献',
 'information':r'disclosure|carbon label|emissions? inventor\w*|信息披露|碳标签|排放清单',
 'cooperation':r'bilateral agreement|memorandum of understanding|technology transfer|双边协定|谅解备忘录|技术转让',
}
STAGES={'proposed':r'proposed|proposal|draft law|拟议|草案|提案','adopted':r'adopted|approved|enacted|通过|批准|颁布','effective':r'entered into force|takes? effect|生效|施行','implemented':r'implemented|implementation|实施|执行','target':r'target|pledge|commitment|目标|承诺'}
GOVERNANCE_ORGANIZATIONS={
 'IPCC':('IPCC','Intergovernmental Panel on Climate Change','政府间气候变化专门委员会'),
 'WMO':('World Meteorological Organization','WMO','世界气象组织'),
 'UNEP':('United Nations Environment Programme','UNEP','联合国环境规划署'),
 'GCF':('Green Climate Fund','绿色气候基金'),
 'GEF':('Global Environment Facility','全球环境基金'),
 'WORLD_BANK':('World Bank','世界银行'),
 'IMF':('International Monetary Fund','国际货币基金组织'),
 'AOSIS':('Alliance of Small Island States','AOSIS','小岛屿国家联盟'),
 'G77':('Group of 77','G77','七十七国集团'),
 'UNDP':('United Nations Development Programme','UNDP','联合国开发计划署'),
}

def governance_organization_evidence(title,body):
    result=[]
    for field,value in [('title',title),('source_text',body)]:
        lower=value.lower()
        if len(lower)!=len(value):lower=value  # Conservative Unicode-offset fallback.
        for code,terms in GOVERNANCE_ORGANIZATIONS.items():
            count=0
            for term in terms:
                start=lower.find(term.lower())
                while start>=0 and count<3:
                    end=start+len(term)
                    left=value[start-1:start] if start else ''
                    right=value[end:end+1]
                    if not term.isascii() or not ((left and left.isascii() and left.isalnum()) or (right and right.isascii() and right.isalnum())):
                        result.append({'label_type':'organization','label_id':code,'field':field,'start':start,'end':end,'quote':value[start:end]});count+=1
                    start=lower.find(term.lower(),end)
    return result

def _evidence(pattern, field, value, limit=3):
    return [{'field':field,'start':m.start(),'end':m.end(),'quote':value[m.start():m.end()]} for m in list(pattern.finditer(value))[:limit]]

def label_text(title: str, body: str, *, countries: bool = True) -> dict:
    title=str(title or ''); body=str(body or '')
    evidence=[]; scores={}; distinct={}
    for code,_,_,_,_ in TOPICS:
        te=_evidence(PATTERNS[code],'title',title)
        be=_evidence(PATTERNS[code],'source_text',body)
        if not (te or be):continue
        # Headline/lead focus precedes long-body incidental mentions.
        lead=len(PATTERNS[code].findall(body[:1800]))
        scores[code]=len(te)*8+min(lead,4)*2+min(len(be),3)
        distinct[code]=len({e['quote'].casefold() for e in te+be})
        evidence += [{'label_type':'topic','label_id':code,**e} for e in te+be]
    # Broad climate wording alone should not displace a concrete policy topic.
    if len(scores)>1 and 'science_impacts' in scores:scores['science_impacts']*=0.35
    primary=max(scores,key=scores.get) if scores else 'unclassified'
    orgs=[]
    for group in ORGANIZATION_GROUPS:
        for code,name,patterns in group['items']:
            pattern=re.compile('|'.join(patterns),re.I)
            es=_evidence(pattern,'title',title)+_evidence(pattern,'source_text',body)
            if es:
                orgs.append(code);evidence += [{'label_type':'organization','label_id':code,**e} for e in es]
    country_codes=set()
    extra_org=governance_organization_evidence(title,body)
    evidence+=extra_org;orgs.extend(e['label_id'] for e in extra_org)
    if countries:
        for field,value in [('title',title),('source_text',body)]:
            count=defaultdict(int)
            for e in country_mentions_with_evidence(value):
                code=e['alpha2'];country_codes.add(code)
                if count[code]<3:
                    evidence.append({'label_type':'country','label_id':code,'alpha3':e['alpha3'],'field':field,'start':e['start'],'end':e['end'],'quote':e['matched_text']})
                count[code]+=1
            country_mentions_with_evidence.cache_clear()
    extra={}
    for kind,patterns in [('policy_tool',TOOL_PATTERNS),('policy_stage',STAGES)]:
        extra[kind]=[]
        for code,p in patterns.items():
            es=_evidence(re.compile(p,re.I),'title',title)+_evidence(re.compile(p,re.I),'source_text',body)
            if es:
                extra[kind].append(code);evidence += [{'label_type':kind,'label_id':code,**e} for e in es]
    for e in evidence:
        assert {'title':title,'source_text':body}[e['field']][e['start']:e['end']]==e['quote']
    return {'label_version':VERSION,'method':'bilingual_lexical_evidence_v1','review_status':'machine_candidate','primary_topic':primary,'topics':list(scores),'topic_scores':scores,'country_mentions':sorted(country_codes),'organization_mentions':sorted(set(orgs)),'policy_tool_mentions':extra['policy_tool'],'policy_stage_mentions':extra['policy_stage'],'evidence':evidence}

def topic_name(code, language='zh'):
    return next((t[3 if language=='en' else 2] for t in TOPICS if t[0]==code), 'Other climate developments' if language=='en' else '其他气候动态')

def group_brief_items(items, language='zh'):
    groups=defaultdict(list)
    for item in items:
        labels=label_text(item.get('title_original') or item.get('title_zh') or item.get('title_en') or '',item.get('summary_source') or item.get('summary_zh') or item.get('summary_en') or '',countries=False)
        groups[labels['primary_topic']].append(item)
    order=[t[0] for t in TOPICS]+['unclassified']
    return [(topic_name(code,language),groups[code]) for code in order if groups.get(code)]

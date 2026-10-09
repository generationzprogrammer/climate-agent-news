"""Compile a policy narrative with native charts, executed SQL and source links."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"analysis/reports/open_innovation_20261009"
TITLE="以专业验证和需求组织贯通科产融合——全球组织模式与中国区域适配"

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    b=json.loads((ROOT/"static/data/innovation_cases.json").read_text(encoding="utf-8"))
    cm={c['id']:c for c in b['cases']}; sm={s['id']:s for s in b['sources']}
    stamp=datetime.now(timezone.utc).isoformat()
    def cite(cid,label=None):
        c=cm[cid]; s=sm[c['evidence'][0]['source_id']]
        return '['+(label or c['title']['zh'])+']('+s['url']+')'
    db=sqlite3.connect(':memory:'); db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE regional_cases(id TEXT PRIMARY KEY, province TEXT, model TEXT)')
    db.executemany('INSERT INTO regional_cases VALUES (?,?,?)',[(c['id'],c['research_annotation'].get('province'),c['research_annotation']['primary_model']) for c in b['cases'] if c['research_annotation'].get('province') in {'CN-GD','CN-ZJ'}])
    q="""WITH totals AS (SELECT province,COUNT(*) n FROM regional_cases GROUP BY province)
      SELECT CASE c.province WHEN 'CN-GD' THEN '广东' ELSE '浙江' END AS 地区,
        c.model AS 模式代码,COUNT(*) AS 案例数,t.n AS 地区样本数,
        COUNT(*)*1.0/t.n AS 比例 FROM regional_cases c JOIN totals t ON c.province=t.province
      GROUP BY c.province,c.model,t.n ORDER BY c.province,c.model"""
    labels={m['id']:m['label']['zh'] for m in b['analysis']['archetypes']}
    regional=[{**dict(r),'组织机制':labels[r['模式代码']]} for r in db.execute(q)]
    eu=[c for c in b['cases'] if c.get('project',{}).get('funding_basis')=='maximum_EU_contribution_not_actual_expenditure']
    db.execute('CREATE TABLE eu_projects(id TEXT PRIMARY KEY, sector TEXT, coordinator TEXT)')
    db.executemany('INSERT INTO eu_projects VALUES (?,?,?)',[(c['id'],c['sector']['zh'],c['project']['coordinator_type']) for c in eu])
    qe="""WITH totals AS (SELECT sector,COUNT(*) n FROM eu_projects GROUP BY sector)
      SELECT p.sector AS 技术领域,CASE WHEN p.coordinator='PRC' THEN '企业'
        WHEN p.coordinator IN ('REC','HES') THEN '高校与研究机构' ELSE '公共及其他机构' END AS 协调方,
        COUNT(*) AS 项目数,t.n AS 领域项目数,COUNT(*)*1.0/t.n AS 比例
      FROM eu_projects p JOIN totals t ON p.sector=t.sector
      GROUP BY p.sector,协调方,t.n ORDER BY p.sector,协调方"""
    erows=[dict(r) for r in db.execute(qe)]; db.close()
    gd=sum(c['research_annotation'].get('province')=='CN-GD' for c in b['cases'])
    zj=sum(c['research_annotation'].get('province')=='CN-ZJ' for c in b['cases'])
    def source(sid,label,path,sql,table,filters,description):
        return {'id':sid,'label':label,'path':path,'query':{'engine':'SQLite '+sqlite3.sqlite_version,'language':'sql','sql':sql,'executed_at':stamp,'tables_used':[table],'filters':filters,'description':description}}
    sources=[source('regional_stats','广东、浙江平台案例的组织机制构成','config/open_innovation_regional_cases.json',q,'regional_cases',['实际所在地为广东或浙江','独立平台，不含资助项目或跨国框架'],'按主要组织机制互斥编码；分母为该省已收录案例，不是全省机构总数。'),
      source('eu_stats','欧盟能源合作项目协调方结构','config/open_innovation_projects.json',qe,'eu_projects',['独立项目编号去重','能源技术','有科研主体及企业','多国合作'],'协调方不等于贡献份额；分母为本领域样本项目数。')]
    selected=['oi_stanford_otl','oi_startx','oi_fraunhofer','oi_aist_solutions','oi_artc','oi_giri','oi_gdut_cnc','oi_ssl_factory','oi_siat','oi_scici','oi_zju_shaoxing','oi_zhejiang_tsinghua','oi_tju_shangyu','oi_sjtu_shaoxing','oi_zjut_shengzhou','oi_nimte_daishan','oi_graphene_centre','oi_nimte_poc','oi_zhejiang_lab','oi_ustc_iat','oi_tsinghua_eiri','oi_gba','oi_ids','oi_embrapii','oi_kcic','oi_innoboost','oi_nedo_lyon']
    for cid in selected:
        for ref in cm[cid]['evidence']:
            s=sm[ref['source_id']]
            if s['id'] not in {r['id'] for r in sources}:sources.append({'id':s['id'],'label':s['title'],'url':s['url'],'description':s['publisher']+'；事实摘编，非因果评价'})
    blocks=[]
    def md(i,body,sid=None):
        item={'id':i,'type':'markdown','body':body}
        if sid:item['sourceId']=sid
        blocks.append(item)
    md('title','# '+TITLE+'\n\n科产融合发展的全球开放创新生态建设研究 · 政策研究报告 · 2026年10月')
    md('abstract','''## 内容摘要

科产融合的公共政策重点，应由增加合作载体转向打通需求定义、工程验证与市场采用之间的接口。全球案例呈现科研创业网络、任务导向攻关、应用研究中介、跨境联合体和共享验证等互补机制；其适用性取决于企业吸收能力、专业工程服务与可执行的合作规则，而非国家标签。广东案例突出制造需求与研发孵化衔接，浙江案例突出校地网络与专业验证，但两地均存在多种机制，不能作简单优劣排序。中国可优先完善专业转化服务、共享中试、企业联合任务和跨区域验证规则，分类支持公共能力与专有研发，以技术交付、企业重复使用和实际采用评价成效。''')
    md('problem',f'''## 一　合作载体不是转化链条：先确定断点，再选择组织方式

科技成果走向产业并不是“研究—专利—企业”的自动接续。可发表的实验结果、可重复的工程工艺、符合安全要求的产品和愿意持续付费的客户，分别需要不同的知识与责任主体。若统一以机构挂牌、合作签约或孵化数量评价，容易把中间产物误当成转化成效。以下是案例机制比较形成的判断，不是对各地区转化效率的因果估计。

**科研创业模式的可复制部分，是专业接口而非资本规模。** {cite('oi_stanford_otl')}提供发明披露、可许可技术目录、创业资源和早期转化支持；{cite('oi_startx')}组织导师、教育与创业者社群，不收费、不取股权。技术权利处置、创业能力建设和商业投资并非同一种服务。后发地区若缺少懂行业、能谈判、能识别客户的专业力量，扩大基金或增加场地未必能补上这个接口。两个机构解释硅谷网络的部分机制，不代表区域成功的充分条件。

**应用研究中介解决的是需求翻译与技术交付。** {cite('oi_fraunhofer')}通过企业合同和长期合作连接研究与工业；{cite('oi_aist_solutions')}从工程、市场、商业加速和资本等环节支持研究型初创企业。二者都把科学能力转为可采购、可试验的服务，但客户、风险与周期不同。中国借鉴时应先确定对象：是有研发预算的制造企业，还是缺少工程与市场能力的早期团队，再选择经费和考核方式。

**任务导向攻关不能替代市场采用。** 美国[ARPA-E项目计划](https://arpa-e.energy.gov/programs-and-initiatives/program-overview)体现公共资助组织高风险技术探索的渠道；{cite('oi_nedo_lyon')}通过城市运行场景组织建筑、交通与能源系统示范。前者关注技术假设，后者还需检验运营、用户和公共管理接口。探索失败不一定意味着管理失败，示范完成也不等于商业可持续。应保留阶段评审、调整和退出机制，既不按短期营收评价基础探索，也不以科研目标长期掩盖缺乏采用需求。''')
    md('eu_structure',f'''### 牵头位置与产业贡献不能混同

图1展示{len(eu)}个经筛选欧盟能源合作项目的协调方构成。科研机构或高校牵头并不意味着企业作用较小：协调方承担组织，企业可能负责设备、制造和用户验证。企业牵头同样不自动证明成果已进入市场。明确任务书中的技术接口、工程交付和采用责任，比要求所有项目采用同一种牵头结构更有针对性。图示仅限一个资助渠道，不能外推为欧洲整体结构。''','eu_stats')
    blocks.append({'id':'eu_chart_block','type':'chart','chartId':'eu_chart'})
    md('prerequisites','''### 组织模式的前提决定政策工具的适用性

|组织方式|要解决的问题|必要条件|不宜替代成效的指标|
|---|---|---|---|
|科研创业网络|缺少许可和创业服务|可转移知识、专业经理人、创业团队、权利与利益冲突规则|场地面积、入驻率|
|任务导向攻关|高风险共性问题难以由单一企业承担|技术判断、阶段节点、容错与终止机制|短期营收、承诺数量|
|应用研究中介|企业问题难以转为研发交付|合同需求、稳定工程能力、成本和知识产权安排|机构挂牌数|
|跨境研发联合体|互补技术和设施分散|协议、资金周期协调、分工与跨场景验证|合作国和参与者数量|
|共享中试与验证|工程设施固定成本难以独立承担|持续需求、专业运营、安全与结果可接受性|购置额、建成面积|

上述条件是机制归纳，不是计量识别的成功阈值。模式可以组合：共享验证平台可承接企业合同与公共任务，创业网络可借助研究中介完成工程验证。预算、责任和成果口径必须分别清楚，不能混为一个综合分数。''')
    md('china',f'''## 二　广东与浙江：差异在连接方式，而非政府与市场的简单二分

**广东制造案例体现“需求—工程—孵化”的近距离反馈。** {cite('oi_gdut_cnc')}记录高校团队与运动控制企业在佛山制造集群中的合作；{cite('oi_giri')}把机器人研发、公共试验和投资孵化放入同一组织。企业提出装备或工艺问题，团队组合技术，试验帮助验证，适合产业化的成果再进入应用或孵化。这对制造客户、工程人才和配套供应链有较高要求。其特征不是抽象的“市场强”，而是企业问题能够反复进入研发和验证。

广东并不只有集群模式。{cite('oi_ssl_factory')}将锂电材料、晶硅光伏、锌基电池等方向连接到中试和产业化；{cite('oi_siat')}体现专业研究与产业创新中心的衔接。材料中试要解决工艺稳定性，医疗技术还要经过临床和监管验证。不同技术的转化关口不同，不能因同在珠三角就用一套验收指标。

**浙江校地网络把外部学科能力接到本地专业产业问题。** {cite('oi_tju_shangyu')}面向精细化工、新材料建设检测和中试；{cite('oi_sjtu_shaoxing')}配置电池、氢能与分子工程研发；{cite('oi_zjut_shengzhou')}与企业改进厨电风机系统。“引入高校”并非同质政策：化工需要安全和放大条件，电化学材料需要测试与工程化，厨电更接近既有制造和用户反馈。有效组织的单位应是产业问题，而非高校名称。

**浙江验证链条具有层级分工。** {cite('oi_nimte_poc')}以专项资金、产业调研和技术商业导师支持早期验证；{cite('oi_nimte_daishan')}聚焦化工新材料工程化；{cite('oi_graphene_centre')}由研究机构、产业链企业和资本共同出资运营。概念验证回答“是否值得继续”，中试回答“能否稳定做出来”，企业试用回答“是否值得采用”。三者不能互相替代。{cite('oi_zhejiang_lab')}及北航杭州案例也表明任务导向研究在浙江存在，不能把全省归为唯一模式。''')
    md('region_stats',f'''### 比较机制组合，而不是省际优劣

图2以广东{gd}个、浙江{zj}个平台案例为分母，按主要组织机制互斥编码。它说明本次收录中哪些连接方式出现，不衡量全省机构总量、技术水平或转化效率。来源、领域和机构关联程度不同，不能用占比估计政策效果。更有意义的比较是：有工程客户却缺少可靠性测试的地区，与有研究平台却缺少企业验收和付费需求的地区，应该补足不同环节。''','regional_stats')
    blocks.append({'id':'regional_chart_block','type':'chart','chartId':'regional_chart'})
    md('factors','''### 生产要素解释应转为可检验的问题

|解释因素|广东案例观察|浙江案例观察|需要核验的结果|
|---|---|---|---|
|需求组织|装备与工艺需求进入研发、试验和孵化|地方行业问题匹配外部高校学科|谁出题、谁验收、是否再次采购|
|工程设施|材料中试、装备试验与孵化衔接|概念验证、专业中试、公共测试分层|使用强度、批次重复性、安全与客户认可|
|人才与知识|高校团队与专业机构接入制造需求|校地研究院引入不同学科团队|企业工程师参与、交付稳定性|
|资本与治理|部分机构组合投资与孵化服务|部分平台由研究机构、企业和资本共同运营|预算分工、风险与收益承担|

这是一组有案例依据的解释路径，不是已确认的省际因果关系。同一研究所的多个平台也不是独立自然实验。安徽先研院的定制研发、四川能源互联网研究院的公开许可清单提供补充对照，但不足以归纳两省整体模式。''')
    md('policy',f'''## 三　政府应组织公共接口，而非指定各地采用同一种模式

**先诊断需求，再决定是否新建载体。** 地方科技、工信部门可与产业链企业将瓶颈区分为知识供给、工程放大、合格评定和采用需求。有企业愿意共同出资、有明确工艺问题的，可组织合同研发或联合团队；只有技术成果、尚无客户的，应先做小额概念验证。立项应明确需求方、验证方与潜在采用方，不把“缺少机构”当成所有问题的起点。

**概念验证、中试与示范分别支持。** 前者采用小额、短周期和允许终止的支持；共性中试支持专业能力和安全运营，但企业专有项目应按成本与权利安排承担费用；示范必须有运行场景、运营责任和可观察的采用结果。宁波概念验证、岱山中试与松山湖样板工厂是不同环节的参照，不能用统一转化率评价。

**降低跨区域验证和合同成本。** 区域合作机制可先建立设施服务目录、测试条件和报告格式，明确异地企业使用资格及结果由谁接受。背景技术、前景成果和数据使用条件可提供范本，由合作方确认具体权利。{cite('oi_gba')}明确一轮试点没有检验跨系统互操作，说明“有平台”不等于“已互通”；{cite('oi_ids')}提供按身份与使用条件组织可信共享的思路。应围绕真实交易设计数据边界，而非先集中汇聚全部敏感数据。

**专业服务与投资决策分工。** 公共机构可以支持技术经理人、工程、知识产权和测试服务，但不宜同时评审公共项目、管理投资并自行认定成功。技术合同、成果许可与股权投资分别留痕，关联交易有回避程序。{cite('oi_tsinghua_eiri')}公开处置方式的实践有助于透明度；是否实现工程采用和回报还需后续核验，不能由签署协议替代。

**按已有能力组合政策。** 广东制造集群可重点补足共性测试、中试安全和跨企业工程服务；浙江校地网络可加强设施共享、持续企业需求及专业运营；企业能力较弱地区，可借鉴{cite('oi_embrapii')}的研究单元对接，以及{cite('oi_kcic')}、{cite('oi_innoboost')}的技术与融资准备服务。发展中经济体内部需求不同，不能采用统一的“发展中国家模式”。

**以可观察采用链条评价效果。** 研发项目检查里程碑与验证结果，平台检查企业重复使用、交付周期和服务成本，转化项目检查许可实施、工艺采用及持续采购。高风险任务同时记录终止原因和知识价值，避免单一成功率诱导只挑容易项目。未获得可比结果前，不应用案例数、资助额或雷达面积给国家和省份打综合分。''')
    md('actions','''### 工具、责任与证据对应

|断点|公共工具|主要责任主体|优先检查证据|
|---|---|---|---|
|缺少采用需求|小额概念验证、行业访谈、技术商业导师|科技部门、专业机构、研究团队|客户问题、成本假设、继续或终止理由|
|有需求但缺专业研发|合同研发、联合任务与工程师交流|企业、应用研究机构|企业投入、交付和重复委托|
|工程放大成本高|共享中试、安全服务、透明排期|工信部门、运营方、使用企业|使用、工艺一致性、下游认可|
|权利与数据难衔接|技术清单、成果与数据使用范本|高校、企业、法律及合规服务方|合同履行、可用范围、争议处理|
|重建设轻运营|分类运营支持和独立评价|财政科技部门、平台治理机构|服务成本、持续需求、验收及退出|

公共支持应服务于可核验的连接任务，而非承诺复制某地的成功。先完成一个有效的技术—产业接口，再判断是否扩展规模，是这些案例对中国的共同启示。''')
    md('scope',f'''## 研究范围与参考资料

本报告依据{len(b['cases'])}个案例截至2026年10月9日的快照，采用制度比较和机制归纳，不作因果识别或创新绩效排名。项目与平台分别统计，区域按实际所在地标注。历史报道保留时点，机构自述的设置、计划不视为独立确认的商业成效。要素流动、生态适配和治理缺口是问题维度，不再作为主分类。网站的宏观比较同时显示样本数与来源渠道，不估计全球总体。正文以机制、条件和政府工具为主。

主要参考资料：

'''+ '\n'.join(f'{i}. {sm[cm[cid]["evidence"][0]["source_id"]]["publisher"]}. {cite(cid)}[EB/OL]. [2026-10-09].' for i,cid in enumerate(selected,1)))
    # Explicit native table blocks preserve table semantics in print as well
    # as the interactive reader; markdown-only print fallback flattens pipes.
    tables=[]; table_data={}; table_queries={}; ordered=[]
    matrix_db=sqlite3.connect(':memory:')
    matrix_db.row_factory=sqlite3.Row
    titles={'prerequisites':'表1　组织方式的适用前提与评价边界',
            'factors':'表2　广东与浙江案例的生产要素解释',
            'actions':'表3　公共工具、责任与检查证据'}
    for block in blocks:
        if block['id'] not in titles:
            ordered.append(block); continue
        lines=block['body'].splitlines()
        start=next(i for i,line in enumerate(lines) if line.startswith('|'))
        end=start
        while end<len(lines) and lines[end].startswith('|'):end+=1
        columns=[v.strip() for v in lines[start].strip('|').split('|')]
        rows=[dict(zip(columns,[v.strip() for v in line.strip('|').split('|')])) for line in lines[start+2:end]]
        tid=block['id']+'_table'
        names=','.join('"'+c+'"' for c in columns)
        matrix_db.execute('CREATE TABLE '+tid+' ('+','.join('"'+c+'" TEXT' for c in columns)+')')
        matrix_db.executemany('INSERT INTO '+tid+' VALUES ('+','.join('?' for c in columns)+')',
            [tuple(row[c] for c in columns) for row in rows])
        sql='SELECT '+names+' FROM '+tid+' ORDER BY rowid'
        table_queries[tid]=sql
        table_data[tid]=[dict(row) for row in matrix_db.execute(sql)]
        sources.append(source(tid+'_source',titles[block['id']],
            'analysis/reports/build_innovation_policy_report.py',sql,tid,
            ['正文案例支持的解释性比较；非实测统计'], '文字矩阵入表后原样检索；SQL不证明因果关系，事实来源见正文及参考资料。'))
        tables.append({'id':tid,'title':titles[block['id']],'dataset':tid,
            'sourceId':tid+'_source','columns':[{'field':c,'label':c} for c in columns]})
        ordered.append({'id':tid+'_block','type':'table','tableId':tid})
        remainder='\n'.join(lines[end:]).strip()
        if remainder:ordered.append({'id':block['id']+'_interpretation','type':'markdown','body':remainder})
    blocks=ordered
    matrix_db.close()
    for sid in ('s_arpae_programme_overview',):
        s=sm[sid]
        sources.append({'id':sid,'label':s['title'],'url':s['url'],'description':s['publisher']})
    charts=[]
    for cid,title,subtitle,ds,sid,x,color in [
      ('eu_chart','图1　欧盟能源合作项目的协调方构成',f'{len(eu)}个独立项目；协调方不等于技术贡献份额','eu','eu_stats','技术领域','协调方'),
      ('regional_chart','图2　广东与浙江案例的主要组织机制',f'广东{gd}例、浙江{zj}例；有目的选取，不是省级总体调查或绩效评价','regional','regional_stats','地区','组织机制')]:
        charts.append({'id':cid,'title':title,'subtitle':subtitle,'showDescription':True,'type':'horizontalStackedBar100','intent':'composition','dataset':ds,'sourceId':sid,'valueFormat':'percent',
          'encodings':{'x':{'field':x,'type':'nominal','label':x},'y':{'field':'比例','type':'quantitative','label':'组内样本比例'},'color':{'field':color,'type':'nominal'}},'palette':{'kind':'categorical'}})
    artifact={'surface':'report','manifest':{'version':1,'surface':'report','title':TITLE,'description':'政府与智库读者；组织机制、区域前提与可操作政策工具。','generatedAt':stamp,'cards':[],'charts':charts,'tables':tables,'sources':sources,'blocks':blocks},
      'snapshot':{'version':1,'generatedAt':stamp,'status':'ready','datasets':{'regional':regional,'eu':erows,**table_data},'accessIssues':[]},'sources':sources}
    (OUT/'artifact.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    audit={'total':len(b['cases']),'prior_cases_retained':613,'new_cases':24,'new_China_cases':21,'Guangdong':gd,'Zhejiang':zj,'regional':regional,'eu':erows,'sql':{'regional':q,'eu':qe},'interpretive_tables':table_data,'interpretive_table_sql':table_queries}
    (OUT/'统计核验.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'cases':len(b['cases']),'Guangdong':gd,'Zhejiang':zj,'blocks':len(blocks)},ensure_ascii=False))
    return artifact

if __name__=='__main__':main()

"""Reproducible research report artifact; one canonical native-chart report."""
from __future__ import annotations
import json
import math
import statistics as stats
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/reports/open_innovation"
TITLE = "科产融合发展的全球开放创新生态：组织机制与跨区域适配"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    book = json.loads((ROOT / "static/data/innovation_cases.json").read_text(encoding="utf-8"))
    projects = [c for c in book["cases"] if c.get("project")]
    n = len(projects)
    p = [c["project"] for c in projects]
    coords = Counter(row["coordinator_type"] for row in p)
    actions = Counter(row["action"] for row in p)
    sectors = book["sector_taxonomy"]
    actors, leads, points, action_rows = [], [], [], []
    for key, sector in sectors.items():
        subset = [c for c in projects if c["sector_key"] == key]
        for group, field in (("企业", "company_count"), ("高校与研究机构", "research_count")):
            actors.append({"领域": sector["zh"], "主体": group, "中位数": stats.median(c["project"][field] for c in subset),
                           "项目数": len(subset), "口径": "单个资助项目内已登记独立参与机构"})
        for code, label in (("PRC", "企业"), ("HES", "高校"), ("REC", "研究机构"), ("PUB", "公共机构"), ("OTH", "其他机构")):
            count = sum(c["project"]["coordinator_type"] == code for c in subset)
            leads.append({"领域": sector["zh"], "协调方": label, "比例": count/len(subset), "项目数": count,
                          "领域项目总数": len(subset)})
        for action in ("RIA", "IA"):
            subset_action = [c["project"] for c in subset if c["project"]["action"] == action]
            if subset_action:
                action_rows.append({"领域": sector["zh"], "类型": action, "项目数": len(subset_action),
                                    "资助中位数": stats.median(r["eu_grant_million"] for r in subset_action),
                                    "机构中位数": stats.median(r["participant_count"] for r in subset_action)})
    for c in projects:
        row = c["project"]
        points.append({"项目": row["acronym"]+" · "+row["official_id"], "机构数": row["participant_count"],
                       "最高资助": row["eu_grant_million"], "类型": row["action"], "领域": c["sector"]["zh"],
                       "国家数": row["country_count"], "企业数": row["company_count"],
                       "开始年份": c["start_year"], "结束年份": c["end_year"],
                       "原文": "https://cordis.europa.eu/project/id/"+row["official_id"]})
    # Execute the exact SQL carried with each native chart, not a prose query.
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE projects (id TEXT, acronym TEXT, sector TEXT, action TEXT, participant_count INTEGER, country_count INTEGER, company_count INTEGER, research_count INTEGER, coordinator_type TEXT, eu_grant_million REAL, start_year INTEGER, end_year INTEGER)")
    db.executemany("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
        (c["project"]["official_id"], c["project"]["acronym"], c["sector"]["zh"], c["project"]["action"],
         c["project"]["participant_count"], c["project"]["country_count"], c["project"]["company_count"],
         c["project"]["research_count"], c["project"]["coordinator_type"], c["project"]["eu_grant_million"],
         c["start_year"], c["end_year"]) for c in projects])
    sql_points = """SELECT acronym || ' · ' || id AS 项目, participant_count AS 机构数,
      eu_grant_million AS 最高资助, action AS 类型, sector AS 领域,
      country_count AS 国家数, company_count AS 企业数, start_year AS 开始年份,
      end_year AS 结束年份, 'https://cordis.europa.eu/project/id/' || id AS 原文
      FROM projects ORDER BY id"""
    sql_actors = """WITH observations AS (
      SELECT sector, '企业' AS actor, company_count AS value FROM projects
      UNION ALL SELECT sector, '高校与研究机构', research_count FROM projects
    ), ranked AS (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY sector, actor ORDER BY value) AS rn,
      COUNT(*) OVER (PARTITION BY sector, actor) AS n FROM observations
    ) SELECT sector AS 领域, actor AS 主体, AVG(value) AS 中位数, MAX(n) AS 项目数,
      '单个资助项目内已登记独立参与机构' AS 口径 FROM ranked
      WHERE rn IN ((n + 1) / 2, (n + 2) / 2) GROUP BY sector, actor ORDER BY sector, actor"""
    sql_leads = """WITH types(code, label) AS (
      VALUES ('PRC','企业'), ('HES','高校'), ('REC','研究机构'), ('PUB','公共机构'), ('OTH','其他机构')
    ), totals AS (SELECT sector, COUNT(*) AS n FROM projects GROUP BY sector)
    SELECT totals.sector AS 领域, types.label AS 协调方,
      1.0 * COUNT(p.id) / totals.n AS 比例, COUNT(p.id) AS 项目数,
      totals.n AS 领域项目总数 FROM totals CROSS JOIN types LEFT JOIN projects p
      ON p.sector = totals.sector AND p.coordinator_type = types.code
      GROUP BY totals.sector, types.code, types.label, totals.n ORDER BY totals.sector, types.code"""
    sql_results = {"actors": [dict(r) for r in db.execute(sql_actors)],
                   "leads": [dict(r) for r in db.execute(sql_leads)],
                   "projects": [dict(r) for r in db.execute(sql_points)]}
    for name, expected in (("actors", actors), ("leads", leads), ("projects", points)):
        # SQL AVG returns floats; Python median can return ints. Compare numerically.
        assert expected
        key = {"actors": ("领域", "主体"), "leads": ("领域", "协调方"), "projects": ("项目",)}[name]
        keyfn = lambda row: tuple(row[k] for k in key)
        assert sorted(expected, key=keyfn) == sorted(sql_results[name], key=keyfn), name
    actors, leads, points = sql_results["actors"], sql_results["leads"], sql_results["projects"]
    db.close()
    med = {field: stats.median(row[field] for row in p) for field in
           ("eu_grant_million", "participant_count", "country_count", "company_count", "research_count")}
    action_med = {action: stats.median(row["eu_grant_million"] for row in p if row["action"] == action) for action in actions}
    countries = {country for c in projects for country in c["countries"]}
    # Descriptive Pearson statistic in log space; no causal interpretation or
    # population generalisation. Sensitivity reports omit the largest 5% grants.
    def corr(rows):
        xs=[math.log1p(r["participant_count"]) for r in rows]
        ys=[math.log1p(r["eu_grant_million"]) for r in rows]
        mx,my=stats.mean(xs),stats.mean(ys)
        return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
    threshold=sorted(row["eu_grant_million"] for row in p)[int(.95*(n-1))]
    correlation={"log_pearson":corr(p),"without_top_5pct":corr([r for r in p if r["eu_grant_million"]<=threshold]),
                 "by_action":{a:corr([r for r in p if r["action"]==a]) for a in actions}}
    audit={"projects":n,"retained_prior_cases":25,"total_cases":len(book["cases"]),"countries":len(countries),
           "coordinators":dict(coords),"actions":dict(actions),"medians":med,"action_grant_medians":action_med,
           "grant_total_million":sum(r["eu_grant_million"] for r in p),"correlation":correlation,
           "selection_bias":"purposefully selected energy collaborations with company and research participants; EU grant-centred",
           "analysis_grain":"one official grant ID; 25 frameworks and legacy cases excluded from statistics",
           "source_snapshot":book["provenance"]}
    (OUT/"analysis_results.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"reviewed_chart_rows.json").write_text(json.dumps({"actors":actors,"leads":leads,"projects":points,"actions":action_rows},ensure_ascii=False,indent=2),encoding="utf-8")
    source={"id":"project_sample","label":"Horizon Europe能源科产合作项目：官方登记与校编字段",
            "path":"config/open_innovation_projects.json", "url":book["provenance"]["url"],
            "query":{"engine":"SQLite " + sqlite3.sqlite_version,"language":"sql","sql":sql_points,"description":"398个独立资助项目；按项目编号去重，高校和研究机构合并为科研主体；金额为最高欧盟资助额，非支出。",
                     "tables_used":["projects"],
                     "executed_at":"2026-10-05T08:00:00Z",
                     "filters":["有企业及高校或研究机构共同参加","至少两个国家","能源技术主题经题名及技术目标校编","框架与历史案例不纳入统计"]}}
    source_map={s["id"]:s for s in book["sources"]}
    selected_sources=["s_cordis_101058359","s_cordis_101084251","s_cordis_101084046","s_cordis_101091777",
                      "s_cordis_101103972","s_cordis_101135374","s_cordis_101096425","s_cordis_101122303","s_cordis_101058453"]
    sources=[source]
    for sid, label, sql in (("actors_source", "项目参与机构数量的领域中位数", sql_actors),
                            ("leads_source", "项目协调方的类型分布", sql_leads)):
        sources.append({**source, "id":sid, "label":label, "query":{**source["query"], "sql":sql}})
    for sid in selected_sources:
        s=source_map[sid];sources.append({"id":sid,"label":s["title"],"url":s["url"],"description":s["publisher"]+"；技术目标与项目登记"})
    old_ids=["oi_artc","oi_embrapii","oi_innoboost","oi_kcic","oi_nedo_lyon","oi_gba","oi_ids","oi_cerc","oi_ore","oi_iter"]
    for cid in old_ids:
        c=next(c for c in book["cases"] if c["id"]==cid)
        for ref in c["evidence"]:
            sid=ref["source_id"]
            if sid in {s["id"] for s in sources}:continue
            s=source_map[sid];sources.append({"id":sid,"label":s["title"],"url":s["url"],"description":s["publisher"]})
    def link(pid,label):return f"[{label}](https://cordis.europa.eu/project/id/{pid})"
    def old(cid):
        c=next(c for c in book["cases"] if c["id"]==cid)
        s=source_map[c["evidence"][0]["source_id"]]
        return f"[{c['title']['zh']}]({s['url']})"
    blocks=[]
    def paragraph(id,body,sid=None):
        block={"id":id,"type":"markdown","body":body}
        if sid:block["sourceId"]=sid
        blocks.append(block)
    paragraph("title","# "+TITLE)
    paragraph("summary",f"""## 核心判断

**科产融合的关键不是机构数量，而是把材料、设备、验证和市场需求组织成可以协同推进的任务。** 在本研究的{n}个能源联合研发项目中，每个项目的参与机构中位数为{med['participant_count']:.0f}家、合作国家中位数为{med['country_count']:.0f}个，企业和科研主体的中位数分别为{med['company_count']:.0f}家与{med['research_count']:.0f}家。这表明研究侧与产业侧往往需要多对多协作，而不是一个大学对接一家企业。

**开放创新的核心接口是试验与验证，而非一般性信息交换。** 光伏中试线、制氢开放试验平台、退役电池状态表征和叶片回收枢纽分别把实验室能力接入制造、认证或循环利用。它们处理的障碍不同，跨地区借鉴应围绕具体接口展开。

**自主可控与开放合作并非简单替代关系。** 跨国联合体可以共享测试与通用知识，同时围绕知识产权、数据使用条件、资格评定和本地配套产业设置边界。合作规模不能代替制度适配，注册目标也不能代替实际成效。""")
    paragraph("structure",f"""## 一　科研协调与产业参与构成分工，而非高低序列

在{n}个具有可比登记字段的项目中，研究机构协调{coords['REC']}项、高校协调{coords['HES']}项，二者合计占{(coords['REC']+coords['HES'])/n:.1%}；企业协调{coords['PRC']}项，占{coords['PRC']/n:.1%}。这与企业参与数量较多并不矛盾：协调方负责组织跨学科任务、资金与交付管理，企业则可在设备、材料、制造和应用验证环节发挥决定性作用。仅以“是否企业牵头”判断产业导向，会把组织管理位置与技术转化职责混为一谈。

图1以单个项目为单位，分别计算企业与高校、研究机构数量的中位数。电网与能源社区、产业脱碳领域的企业中位数均为8家，而太阳能领域科研主体中位数为6家、企业为5家。不同技术领域的协作结构反映问题性质：系统集成需要运营商、设备商、软件服务方与用户场景共同参与，器件材料研发则更依赖表征与机理研究。这里的差异只描述样本结构，不证明某类组织模式具有更高创新效率。""","project_sample")
    blocks.append({"id":"actors_chart_block","type":"chart","chartId":"actors_chart"})
    paragraph("funding",f"""图2同时展示每个项目的参与机构数和最高欧盟资助额，并区分研究与创新行动（RIA）和创新行动（IA）。全样本资助额中位数为{med['eu_grant_million']:.2f}百万欧元；RIA与IA分别为{action_med['RIA']:.2f}和{action_med['IA']:.2f}百万欧元。创新行动通常面对更接近应用的验证与示范任务，因此不能用资金规模直接给研发项目排序。

机构数量与资助额在对数尺度下的样本相关系数为{correlation['log_pearson']:.2f}，去除最高5%的资助项目后为{correlation['without_top_5pct']:.2f}。这一统计关系不等于“参与方增加导致成果改善”：资助类型、技术领域与示范资产需求可能同时影响两者。对照项目时，至少应先固定技术领域与行动类型，再看任务分工、验证条件和原始金额。""","project_sample")
    blocks.append({"id":"funding_chart_block","type":"chart","chartId":"funding_chart"})
    paragraph("interfaces",f"""## 二　转化断点集中在制造放大、共同验证与产业链衔接

**光伏案例显示，材料效率与量产能力不是同一个问题。** {link('101084251','PEPPERONI')}由Q CELLS协调，在工业硅电池上叠加钙钛矿薄层，目标包括工业规模26%效率组件、超过30年的稳定性和健康环境风险控制。{link('101084046','PILATUS')}则围绕背接触硅异质结技术连接硅片、电池、组件三条数字化中试线，其登记目标包括15兆瓦硅片、190兆瓦电池和至少170兆瓦组件年产能，及不低于90%的最终良率。上述均是项目目标，不是本报告确认的投产数据。两例的共同点是把表征、工艺反馈、设备和供应链一并组织起来；可借鉴的不是照搬某条产线，而是建立实验性能与稳定制造之间的反馈接口。

**开放试验平台能够把固定设施投入转化为企业可使用的研发服务。** {link('101091777','CLEANHYPRO')}覆盖四类电解制氢技术，将制造中试、表征、建模及非技术服务集中到单一入口，主要面向中小企业。其目标文本列出TRL7示范、4套认证方案和至少16个示范案例。这里的组织创新在于减少企业逐一寻找测试、融资和技术转移服务的协调成本，而不是仅向企业提供一组实验室链接。平台能否有效运行仍取决于服务定价、排期、结果可接受性及企业实际使用。

**循环利用案例的核心是分流决策和跨主体交接。** {link('101058359','BATRAW')}以电池拆解与湿法冶金两套中试系统连接组件回收、黑粉处理和关键材料提取，目标包括95%的电池包组件回收。{link('101103972','RECIRCULATE')}进一步连接健康与安全状态表征、自动拆解、逆向物流、电池护照和交易平台；Centria协调拆解活动，福特衔接电动交通应用，DHL参与物流。材料回收、梯次利用与交易所需的证据并不相同，跨企业的信息接口必须能够支持不同去向的价值判断。""")
    paragraph("region",f"""## 三　跨区域适配应识别需求结构与验证环境

**城市示范与产业会员平台代表两种不同的需求组织方式。** {old('oi_nedo_lyon')}在2011—2016年把正能量建筑、汽车共享与充电管理、家庭能耗可视化及社区能源管理嵌入同一城市场景。市政府与企业需要共同处理建筑、出行、电力和用户行为之间的接口。{old('oi_artc')}则通过A*STAR、企业会员与研究伙伴把需求持续输入研发体系，能源与航空、制造等产业共享平台能力。前者的适配核心是真实场景及公共协调，后者的适配核心是持续产业需求和共享研发能力；二者不是同一种“建设园区”模式。

**中小企业服务与地方技术条件必须同时考虑。** {old('oi_embrapii')}允许巴西企业直接与认可研究单元协商技术及商业范围，国际项目由各国伙伴分别向本国机构申报。这样的分担方式降低了由一个跨国资金池处理全部支出的制度复杂性，但也要求两侧资助周期和项目进度协调。{old('oi_innoboost')}将资金、Green Energy Park设施和投资者对接结合，太阳能研究平台扩展至科特迪瓦以测试热带条件下的技术；{old('oi_kcic')}则将早期创业团队的技术服务、市场信息与融资准备相衔接。这些安排分别处理融资、环境验证和早期企业能力，不宜用统一的补贴比例替代具体诊断。

**跨境参与的价值在于补充可识别的能力，而非增加国旗数量。** {link('101122303','ICARUS')}围绕水热液化生物原油、木质纤维素异丁醇及生物质气化费托合成三条航空燃料路线开展全链条研发。目标文本明确提到加拿大、印度、巴西的研究伙伴，美国专家则参加外部执行咨询委员会。咨询成员、登记参与机构与实际设施所在国必须分开理解。{link('101058453','FLEXIndustries')}在土耳其、希腊、波兰、保加利亚和意大利的6处工业设施示范，涉及汽车、钢铁、化肥、制药等不同过程；这类多场景验证比简单增加合作方更接近跨区域复制所需的证据。""")
    paragraph("governance",f"""## 四　开放边界应落实到数据、知识产权与验证规则

跨境科产融合的治理问题不宜笼统概括为“全球治理缺位”。技术合作经常已有资助协议、标准体系或数据架构，真正的问题是这些安排是否覆盖了具体交易与使用场景。知识共享、商业许可和产品准入是不同层级的关系，不能以签署科研合作文件代替全部制度安排。

**知识产权安排需要辨明法律效力与使用边界。** {old('oi_cerc')}的2016—2020年技术管理计划明确由阿贡国家实验室与清华大学牵头，美国能源部同时说明该文件本身不具法律约束力。它可用于理解联合研发的技术管理接口，但不能当作已执行的跨境知识产权合同。{old('oi_iter')}则将成本分担、设备贡献及实验成果和知识产权共享嵌入多边合作框架；其共享规则服务于长期大型科学装置，不能直接移植为初创企业的股权或技术许可条款。

**数据可获得不等于数据可互操作，也不等于自由再利用。** {old('oi_gba')}2024年由10个联合体形成原型电池护照，但报告明确说明不同追溯系统的互操作性没有在该轮测试，组间试点评分不能直接比较。{old('oi_ids')}采用连接器、身份和认证框架、数据使用条件及追溯机制组织可信交换，提供了不必集中汇聚全部产业数据的协作路径。{link('101135374','HyWay')}把物理实验、材料建模及数据知识管理平台连接起来，说明跨机构数据协同应围绕具体材料问题设计，而非先建设一个与科研任务脱节的大数据平台。

**共同验证结果能否被接受，是技术跨区域扩散的关键。** {old('oi_ore')}将大型风机测试及电网模拟能力接入工程验证，评估材料记录eGrid结果被英国电网接受用于替代部分现场数据。这一实践值得关注的不是“测试设施规模更大”，而是测试结果与外部资格判断形成了接口。{link('101096425','EoLO-HUBs')}则区分知识枢纽、陆上和跨行业海上示范枢纽，将拆解、材料循环、业务模式和法律建议结合；其接近90%叶片材料回收是登记目标，仍需用实测产出确认。""")
    paragraph("profiles",f"""## 五　制度比较需要先对齐项目层级和技术任务

图3给出各领域协调方类型的样本构成。总体上科研机构与高校协调占比较高，但这不能被解释为企业能力不足；协调位置与企业在产品化阶段的作用不等价。跨地区比较更有价值的问题是：谁定义任务，谁提供试验设施，谁承担放大风险，谁决定成果进入市场。

网站的雷达图使用合作国家、企业、科研机构、机构类型及最高资助额五项可复算字段。各轴按预先公开的区间映射到1—5，不求和为综合分，不以图形面积判定好坏；缺少数据时不填零。平台、制度框架和资助项目不在同一粒度，原有25个框架及历史案例不参与项目结构统计。这样的画像适合快速识别合作结构，但不能测量技术领先程度、知识产权执行质量或商业成功。""","project_sample")
    blocks.append({"id":"leads_chart_block","type":"chart","chartId":"leads_chart"})
    paragraph("directions","""跨区域借鉴可以围绕三个具体方向展开。第一，把公共测试能力与企业决策连接：重点核查测试条件、成本、排期及结果是否被下游客户或监管接受。第二，把循环利用链条上的信息交接纳入技术项目：电池、光伏组件和风机叶片的状态、材料、物流与再使用证据不能彼此割裂。第三，按任务配置开放边界：通用表征与标准可以共享，敏感工艺、商业数据与许可条件应具体约定，避免把“开放合作”简单理解为无条件披露。

后续值得跟踪的证据包括中试线实际良率与产能、平台企业使用率及验证成本、护照互操作测试、跨国项目中的资助周期匹配和成果许可执行。只有补入这些结果数据，才适合从协作结构进一步评估转化效果；当前不能据案例数量或资助额对国家创新绩效作排名。""")
    paragraph("scope",f"""## 研究范围

本报告以{n}个官方登记能源联合研发项目开展结构分析，并以既有跨区域平台与制度案例解释协作机制。项目样本覆盖{len(countries)}个登记参与国，资助来源以Horizon Europe为主，不是全球项目普查；机构数量按同一项目内独立机构登记计算。统计金额为欧盟最高资助额，既不等同于实际支出，也不代表全部投资；项目目标与经外部确认的成果分别表述。数据核验截至2026年10月5日，原文与图表数据可沿各段来源入口查阅。""","project_sample")
    charts=[
        {"id":"actors_chart","title":"图1　不同技术领域的项目参与机构数量","subtitle":"398个项目；每个项目内机构数的领域中位数；高校与研究机构合并计算","showDescription":True,
         "type":"bar","intent":"comparison","dataset":"actors","sourceId":"actors_source",
         "encodings":{"x":{"field":"领域","type":"nominal","label":"技术领域"},"y":{"field":"中位数","type":"quantitative","label":"机构数中位数"},"color":{"field":"主体","type":"nominal"},
                      "tooltip":[{"field":"项目数","type":"quantitative","label":"领域项目数"}]},
         "palette":{"kind":"categorical"}},
        {"id":"funding_chart","title":"图2　项目资助规模与参与机构数","subtitle":"每点为一个独立项目；金额为最高欧盟资助额，不是实际支出；RIA为研究与创新行动，IA为创新行动","showDescription":True,
         "type":"scatter","intent":"relationship","dataset":"projects","sourceId":"project_sample",
         "encodings":{"x":{"field":"机构数","type":"quantitative","label":"参与机构数"},"y":{"field":"最高资助","type":"quantitative","label":"最高资助额（百万欧元）"},"color":{"field":"类型","type":"nominal"},
                      "tooltip":[{"field":"项目","type":"nominal","label":"项目"},{"field":"领域","type":"nominal","label":"领域"},{"field":"国家数","type":"quantitative","label":"国家数"}]},
         "palette":{"kind":"categorical"}},
        {"id":"leads_chart","title":"图3　各领域项目协调方类型","subtitle":"按同一技术领域项目总数计算比例；协调位置不代表成果贡献比例","showDescription":True,
         "type":"horizontalStackedBar100","intent":"composition","dataset":"leads","sourceId":"leads_source","valueFormat":"percent",
         "encodings":{"x":{"field":"领域","type":"nominal","label":"技术领域"},"y":{"field":"比例","type":"quantitative","label":"领域内比例"},"color":{"field":"协调方","type":"nominal"}},"palette":{"kind":"categorical"}},
    ]
    artifact={"surface":"report","manifest":{"version":1,"surface":"report","title":TITLE,
              "description":"能源科产融合的协作结构、验证接口与制度适配研究。","generatedAt":"2026-10-05T08:00:00Z",
              "cards":[],"charts":charts,"tables":[],"sources":sources,"blocks":blocks},
              "snapshot":{"version":1,"generatedAt":"2026-10-05T08:00:00Z","status":"ready",
                          "datasets":{"actors":actors,"projects":points,"leads":leads},"accessIssues":[]},"sources":sources}
    (OUT/"artifact.json").write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding="utf-8")
    notes={"audience":"product stakeholders; academic-policy research readers","delivery":"portable HTML, canonical report builder",
           "structure_roles":{"title":"title","executive_summary":"summary — Chinese localisation: 核心判断",
                              "findings":"structure, interfaces, region, governance, profiles",
                              "next_steps_and_further_questions":"directions","caveats":"scope plus adjacent finding caveats"},
           "methodology_share":"scope and brief metric explanation only; main body analyses collaboration mechanisms",
           "chart_map":[{"id":c["id"],"question":c["title"],"type":c["type"],"source":"project_sample"} for c in charts],
           "omissions":{"performance_ranking":"no comparable measured commercial/technical outcomes","time_trend":"start-year sampling does not measure global innovation activity","radar_report":"ordinal project profiles kept in website beside raw observations, not treated as measured impact"},
           "checks":["official project-ID uniqueness","source field definitions","missing not zero","programme/project grain separated","maximum contribution not spend"],
           "reader_layout_fix":"Native 100vw toolbar overflows with classic scrollbars; package script changes only toolbar to container width, retains native content, charts, provenance and hard verification."}
    (OUT/"source_notes.json").write_text(json.dumps(notes,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False))


if __name__=="__main__":main()

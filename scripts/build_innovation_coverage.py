"""Compile additive, reviewed geographic coverage; offline and deterministic.

One identifiable platform or programme per case. Official public page text and
indexed official excerpts control factual fields; no current outcome estimates,
personal contacts, full-page mirrors, model calls or daily network collection.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-10-09"
CASES, SOURCES, PROFILES = [], [], []

def bi(text):
    zh, en = text.split("|", 1)
    return {"zh": zh, "en": en}

SECTORS = {k: bi(v) for k, v in {
    "general":"跨领域技术转化|Cross-sector technology transfer",
    "manufacturing":"先进制造|Advanced manufacturing",
    "materials":"新材料与工程验证|Materials and engineering validation",
    "digital":"数字技术与智能系统|Digital and intelligent systems",
    "biomanufacturing":"生物制造与食品工程|Biomanufacturing and food engineering",
    "solar":"太阳能技术|Solar technologies", "industry":"工业脱碳|Industrial decarbonisation",
    "marine":"海洋能源与产业|Marine energy and industries",
    "mobility":"交通装备与电气化|Transport engineering and electrification",
}.items()}

def add(key, country, province, city, title, model, sector, url, publisher,
        language, summary, actors, mechanism, observed, constraints, transfer,
        *, source_role="primary"):
    sid, cid = "s_coverage_"+key, "oi_"+key
    SOURCES.append({"id":sid, "url":url, "title":bi(title)["zh"],
        "publisher":publisher, "language":language, "published_date":None,
        "reviewed_at":DATE, "access":"public_metadata_and_paraphrase",
        "source_role":source_role,
        "review_basis":"official_page_text_or_indexed_official_excerpt"})
    CASES.append({"id":cid, "title":bi(title), "countries":[country],
        "scope":"national", "sector":SECTORS[sector], "sector_key":sector,
        "aliases":list(bi(title).values()), "challenges":["factor","adaptation"],
        "modes":["testbed" if model=="pilot" else "incubation" if model=="venture" else "translation"],
        "institutions":["research"], "factors":["knowledge","talent","market"],
        "start_year":None, "end_year":None, "review_status":"reviewed",
        **{k:bi(v) for k,v in zip(("summary","actors","mechanism","observed","constraints","transfer"),
                                  (summary,actors,mechanism,observed,constraints,transfer))},
        "evidence":[{"source_id":sid,"supports":["summary","actors","mechanism","observed"]}],
        "research_annotation":{"primary_model":model,"country":country,
            "province":province,"city":city,"grain":"platform","cohort":"coverage_review",
            "basis":"manual_source_review","reviewed_at":DATE,
            "interpretation_fields":["constraints","transfer","primary_model"]}})

# China: location follows the operating platform, not its partner university.
add("tsinghua_xlab","CN","CN-BJ","北京市",
 "清华x-lab创新创业教育与团队培育|Tsinghua x-lab entrepreneurship and venture development",
 "venture","general","https://www.x-lab.tsinghua.edu.cn/gywm/list.htm","清华大学x-lab","zh",
 "清华x-lab把跨学科创新创业教育与团队培育结合，为科研创业者补充商业化和组织能力。|Tsinghua x-lab combines interdisciplinary entrepreneurship education with team development for research-based founders.",
 "清华经管学院、联合共建院系、创新创业团队及商业合作机构。|Tsinghua SEM, participating departments, entrepreneurial teams and business partners.",
 "通过教育、项目培育和生态连接，将技术团队与商业机构对接，而非仅提供办公空间。|Education, venture development and ecosystem connections link technical teams to business organisations rather than merely providing offices.",
 "官方介绍列出团队建设、商业化合作与公益性成果转化职能，平台面向清华学生、校友和教职工。|The official profile documents team-building, commercialisation partnerships and nonprofit transfer support for the Tsinghua community.",
 "校园创业服务依赖学科和导师网络，不能以参与培训人数衡量产业化成效。|Campus entrepreneurship depends on disciplinary and mentor networks; training attendance is not industrial impact.",
 "把原型验证、客户访谈和团队分工作为早期支持节点，商业投资与公益教育分别管理。|Use prototype tests, customer interviews and team roles as early milestones; manage investment separately from nonprofit education.")
add("beijing_collaborative","CN","CN-BJ","北京市",
 "北京协同创新研究院中心与基金联动|Beijing Institute of Collaborative Innovation centre–fund coupling",
 "consortium","general","https://www.csdp.edu.cn/article/3976.html","教育部学校规划建设发展中心","zh",
 "研究院按行业组织高校与企业共建协同创新中心，并以专属基金连接项目遴选和后续投入。|The institute organises university–industry centres by sector and links project selection to dedicated funds.",
 "参与高校、行业领军企业、协同创新中心及其基金。|Participating universities, industrial firms, collaborative centres and their funds.",
 "采用中心与基金二元耦合安排，由基金遴选及领投项目，科研和产业人员共同参与。|Centres and funds are coupled: funds select and lead investments while research and industrial staff participate.",
 "教育部所属机构2018年介绍记载行业中心、专属基金及基础研究、应用研究、产业人员的分工。|A 2018 education-agency profile documents sector centres, dedicated funds and roles spanning basic research, applied research and industry.",
 "这是特定时期的制度记录；基金投资决定、科研评价和公共支持需避免相互替代。|This is a historical institutional record; investment decisions, research assessment and public support need distinct accountabilities.",
 "明确中心与基金的决策权限、知识产权及关联交易规则，按技术验证阶段释放资金。|Specify centre/fund decision rights, IP and related-party rules; release funding by validation stage.")
add("tianjin_synbio","CN","CN-TJ","天津市",
 "国家合成生物技术创新中心研发转化平台|National Synthetic Biotechnology Innovation Centre",
 "intermediary","biomanufacturing","https://tib.cas.cn/rcdw/rczp/glzczp/202501/t20250116_7519223.html","中国科学院天津工业生物技术研究所","zh",
 "合成生物中心以公司作为法人运营主体，将技术研发、成果转化、企业孵化和资本运营纳入同一平台。|The centre uses a corporate operator to integrate R&D, technology transfer, incubation and capital operations.",
 "天津国家合成生物技术创新中心有限公司、科研团队及产业化企业。|The centre's operating company, research teams and commercialisation firms.",
 "通过专业法人承接技术开发与转化服务，组织科研成果向企业应用衔接。|A specialised legal operator connects technical development and transfer services to industrial applications.",
 "研究所2025年公开说明确认公司的法人和管理运营机构身份及四类业务职能。|The institute's 2025 notice identifies the legal/operating entity and its four functions.",
 "运营职能不等于量产能力，生物工艺仍须验证批次稳定性、成本和安全。|Operating functions do not establish manufacturing readiness; bioprocesses still require repeatability, cost and safety tests.",
 "针对生物工艺分别设置实验验证、放大和生产准入节点，明确平台与企业的责任。|Set distinct laboratory, scale-up and production-admission gates, allocating responsibilities between platform and firms.")
add("tsinghua_hebei","CN","CN-HE","石家庄市",
 "河北清华发展研究院校地技术转移|Hebei Tsinghua institute for regional technology transfer",
 "intermediary","general","https://www.tsinghua-hb.com.cn/yjtgk/jbgk.htm","河北清华发展研究院","zh",
 "省校共建研究院将清华和京津创新资源与河北产业需求连接，方向包括高端装备、低碳环保与新型储能。|A province–university institute links Tsinghua and Beijing–Tianjin capabilities with Hebei industry, including equipment, low-carbon technologies and storage.",
 "河北省、清华大学、京津科研团队及河北产业合作方。|Hebei province, Tsinghua University, Beijing–Tianjin researchers and Hebei industrial partners.",
 "以人才汇聚、项目承载、成果转化和产业服务平台承接跨地区合作。|Talent, project-hosting, transfer and industrial-service platforms support interregional cooperation.",
 "机构简介列出八个布局方向，并明确推动京津人才、技术、项目与资金向河北集聚。|The profile lists eight domains and the connection of Beijing–Tianjin talent, technologies, projects and capital to Hebei.",
 "转移并非简单搬迁；当地工程配套和企业吸收能力决定技术能否被采用。|Transfer is not relocation alone; local engineering support and firms' absorptive capacity condition adoption.",
 "围绕河北企业可执行的工艺任务组织合作，技术交付与落地配套同步约定。|Organise cooperation around executable industrial tasks and agree technical deliverables alongside local implementation support.")
add("sitri_shanghai","CN","CN-SH","上海市",
 "上海微技术工业研究院超越摩尔中试|SITRI More-than-Moore engineering and pilot platform",
 "pilot","digital","https://www.sitri.com/gsjj/","上海微技术工业研究院","zh",
 "上海工研院为超越摩尔集成电路提供共性技术研发、全流程中试与产业孵化服务。|SITRI provides shared R&D, full-process piloting and incubation for More-than-Moore integrated circuits.",
 "上海市科委、嘉定区政府、新微集团、合作企业与创新团队。|Shanghai science authorities, Jiading government, SIMIT-related group, partner firms and innovation teams.",
 "将科学研究、工艺开发、中试和孵化配置在研发转化功能型平台，向合作伙伴开放技术支持。|A functional R&D/transfer platform connects research, process development, piloting and incubation for partners.",
 "官网确认2013年成立及共同发起主体，并列出全流程中试、共性技术研发和人才培养职能。|The official profile identifies the 2013 founding partners and functions in full-process piloting, common technologies and training.",
 "共线工艺需处理客户保密、排产和良率责任，专利或孵化数量不能替代制造验证。|Shared processing needs confidentiality, scheduling and yield responsibilities; patent/incubation counts are not manufacturing validation.",
 "以工艺可复现性、企业试用和工程交付约束中试投入，建立清晰的共享设施使用规则。|Tie pilot investment to repeatable processes, firm trials and engineering delivery, with clear shared-facility rules.")
add("shanghaitech_ott","CN","CN-SH","上海市",
 "上海科技大学技术转移与早期孵化|ShanghaiTech technology transfer and early incubation",
 "venture","general","https://www.shanghaitech.edu.cn/2021/0419/c1001a62844/page.htm","上海科技大学","zh",
 "学校将技术转移办公室、创新创业实践教育和投融资对接衔接，支持科研成果早期孵化。|ShanghaiTech connects technology transfer, entrepreneurial education and investment matching for early research commercialisation.",
 "学校科技发展处、技术转移办公室、科研团队及投融资合作方。|The science-development office, OTT, research teams and investment partners.",
 "校内专门部门协调成果运用与投融资对接，把学科、人才和孵化环节连接。|Specialist offices coordinate research use and investment matching across disciplines, talent and incubation.",
 "2021年校方报道明确记载科技发展处和技术转移办公室的协调与创业投融资职能。|A 2021 university account documents the coordinating and investment-matching roles of the two offices.",
 "专业许可和创业孵化需要不同能力，早期资本对接也不保证形成持续收入。|Licensing and incubation require different capabilities; early investor access does not guarantee sustained revenue.",
 "在成果披露时同时评估许可与创业路径，采用有技术背景的专业转化人员。|Assess licensing and startup routes at disclosure and employ transfer professionals with relevant technical expertise.")
add("jitri_jiangsu","CN","CN-JS","南京市",
 "江苏省产业技术研究院合同科研网络|JITRI contract-research and industrial innovation network",
 "intermediary","general","https://en.jitri.cn/About-Us","江苏省产业技术研究院","zh",
 "江苏产研院以专业研究所、企业需求和全球创新资源组织应用研究，探索合同科研与团队激励。|JITRI organises applied research around specialist institutes, firm demand and global capabilities, using contract research and team incentives.",
 "江苏产研院、专业研究所团队、产业企业及合作高校。|JITRI, specialist institute teams, industrial firms and partner universities.",
 "通过项目经理、团队控股、拨投结合与合同科研，把研发责任和成果转化收益连接。|Project managers, team ownership, grant–investment combinations and research contracts connect delivery responsibility to transfer incentives.",
 "官方概况列出一所两制、合同科研、项目经理、团队控股、股权激励等改革安排。|The official profile lists differentiated institute arrangements, research contracts, project managers, team ownership and equity incentives.",
 "合同收入不能覆盖所有公共研发，团队控股也需配合知识产权与公共资产规则。|Contracts cannot fund all public research; team ownership needs compatible IP and public-asset rules.",
 "区分共性能力建设与企业合同任务，给予团队明确激励，同时保留公共投入绩效审查。|Separate shared-capability building from industrial contracts, with explicit team incentives and accountability for public funding.")
add("tsari_suzhou","CN","CN-JS","苏州市",
 "清华苏州汽车研究院工程研发与验证|Tsinghua Suzhou automotive engineering and validation",
 "intermediary","mobility","https://www.tsari.tsinghua.edu.cn/service/jsyf/znwlyf/","清华大学苏州汽车研究院","zh",
 "研究院把车辆、计算机和信息技术团队与整车、零部件及信息通信企业连接，提供工程咨询和技术服务。|The institute links vehicle, computing and information teams with OEMs, component and ICT firms through engineering services.",
 "清华苏州汽研院研发团队、整车企业、零部件企业及信息通信企业。|The institute's R&D teams, vehicle manufacturers, component suppliers and ICT firms.",
 "以多专业工程团队承接智能网联汽车研发、工程咨询及企业技术合作。|Multidisciplinary engineering teams deliver connected-vehicle R&D, consulting and industrial technical cooperation.",
 "官方智能网联中心介绍明确列出OEM、零部件、ICT等合作对象及工程化经验。|The connected-vehicle centre profile identifies OEM, component and ICT partners and engineering experience.",
 "工程服务的有效性取决于整车集成和用户测试，不能仅按高校合作数量判断。|Engineering services depend on vehicle integration and user testing, not the number of university partners.",
 "围绕整车系统接口组织联合任务，在合同中明确测试环境、验证要求与成果权属。|Organise joint tasks around vehicle-system interfaces and specify test environments, acceptance requirements and ownership.")
add("sdiit_shandong","CN","CN-SD","济南市",
 "山东产业技术研究院产业链研发转化|Shandong industrial-technology research and transfer",
 "intermediary","general","https://www.sdiit.cn/","山东产业技术研究院","zh",
 "研究院围绕山东产业链布局信息技术、装备、材料、能源环保和生物医药研发，连接高校、企业与资本。|The institute links universities, firms and capital across Shandong's ICT, equipment, materials, energy/environment and biomedicine value chains.",
 "山东省举办的新型研发机构、济南市、高校院所、企业与产业资本。|The provincial institute, Jinan authorities, universities/research organisations, firms and industrial capital.",
 "以产业技术需求为牵引搭建研究、成果转化和产业化沟通桥梁。|Industrial technical needs organise connections among research, transfer and commercialisation.",
 "官网明确省属事业单位及济南主管的治理结构，列出五大技术领域和产业链服务定位。|The official site identifies provincial public-institution status, Jinan supervision, five technology domains and value-chain services.",
 "领域宽并不等于技术优势，地方支持需落到具体研发交付与企业采用。|Broad scope is not technical advantage; local support should be linked to specific delivery and firm adoption.",
 "按产业链瓶颈配置小型专业团队和阶段资金，分开评估技术开发与投资回报。|Allocate specialist teams and staged funding to value-chain bottlenecks, assessing technical delivery separately from investment return.")
add("xjtu_innovation_harbour","CN","CN-SN","咸阳市",
 "西安交大创新港企业主导联合研发|XJTU Innovation Harbour enterprise-led joint R&D",
 "consortium","general","https://news.xjtu.edu.cn/info/1014/211678.htm","西安交通大学","zh",
 "创新港将高校研究能力与企业主导研发中心、成果孵化和人才共享连接，服务产业技术任务。|Innovation Harbour links university research to enterprise-led R&D centres, incubation and shared talent for industrial tasks.",
 "西安交通大学、西咸新区、参与企业、科研团队与金融合作方。|XJTU, Xixian New Area, participating firms, researchers and financing partners.",
 "企业作为需求、投入、管理与转化主体，共建联合研发中心；孵化器与人才共用机制提供后续衔接。|Firms define demand, investment, management and transfer in joint centres; incubation and shared recruitment provide follow-through.",
 "校方2024年介绍明确一中心、一孵化、两围绕、一共享安排，以及高校招、企业供的人才合作机制。|The university's 2024 account documents joint centres, incubation, value-chain alignment and university–firm shared recruitment.",
 "企业主导要求承担真实投入和长期任务，联合挂牌不能替代管理权与验收责任。|Enterprise leadership requires real investment and durable tasks; joint branding cannot substitute for decision rights and acceptance responsibilities.",
 "先确定企业任务、资金和工程负责人，再配置校企中心；人才共聘应明确考核和知识产权。|Agree industrial tasks, financing and engineering leads before establishing centres; define joint-staff appraisal and IP.")
add("wuhan_optoelectronics","CN","CN-HB","武汉市",
 "武汉光电工业技术研究院专业转化|Wuhan optoelectronics industrial technology institute",
 "cluster","digital","https://oei.hust.edu.cn/info/1091/3440.htm","华中科技大学","zh",
 "华中科技大学光学工程学科通过专业研究院把人才培养、基础研究、技术研发与光电子成果转化连接。|HUST's optical-engineering capabilities connect training, basic research, development and optoelectronics transfer through an industrial institute.",
 "华中科技大学光学工程团队、武汉光电工业技术研究院及产业合作企业。|HUST optical-engineering teams, the industrial institute and industrial collaborators.",
 "依托光谷产业场景配置技术转移、工程示范和人才培养服务，衔接学科平台与产业链。|Transfer, engineering demonstrations and training connect disciplinary capabilities to Optical Valley's industrial value chains.",
 "大学2017年学科介绍记载牵头成立研究院及专业化创新创业服务体系。|A 2017 university profile documents the institute and its specialist innovation/entrepreneurship services.",
 "学科集聚不是产业协同的充分条件，具体产品仍需企业集成与客户验证。|Disciplinary concentration is insufficient; products still require firm integration and customer validation.",
 "围绕光电子产业共性工艺和工程验证组织服务，允许企业参与任务选择及验收。|Build services around shared optoelectronics processes and engineering validation, involving firms in task selection and acceptance.")
add("xiangyang_optoelectronics","CN","CN-HB","襄阳市",
 "襄阳光电工业技术研究院需求揭榜|Xiangyang optoelectronics demand-led problem solving",
 "mission","digital","https://eic.hust.edu.cn/info/1153/7255.htm","华中科技大学电子信息与通信学院","zh",
 "研究院围绕襄阳臭氧污染监测需求，组织高校团队和产品厂商开发便携式激光雷达。|The institute connects university teams and manufacturers to portable-lidar development for Xiangyang ozone monitoring.",
 "襄阳光电工业技术研究院、华中科技大学团队和国内产品厂商。|The Xiangyang institute, HUST teams and domestic product manufacturers.",
 "以地方应用问题提出技术任务，高校提供探测技术，厂商负责产品实现。|Local application problems define tasks, universities supply sensing technology and manufacturers implement products.",
 "学院转载报道记载2021年成立的研究院及便携式臭氧探测激光雷达合作。|The college-hosted account documents the institute established in 2021 and the portable ozone-lidar collaboration.",
 "单次揭榜不能保证长期运维，应区别原型交付、监测有效性与持续服务。|A challenge award does not guarantee maintenance; prototype delivery, monitoring validity and ongoing service are distinct.",
 "把场景方、科研方和产品方共同纳入验收，以实际环境下的测试结果约束任务。|Include users, researchers and manufacturers in acceptance, using tests in the operating environment.",
 source_role="institution_hosted_media")
add("yuelushan_industry","CN","CN-HN","长沙市",
 "岳麓山工业创新中心组网攻关|Yuelushan industrial innovation network",
 "mission","manufacturing","https://www.hunan.gov.cn/topic/qdgj/kcfn/gzjxs/sz/202508/t20250811_33770082.html","湖南省人民政府门户网站","zh",
 "中心以节点实验室和专业研究部组织跨机构研究，围绕湖南重点产业链的基础问题与技术瓶颈开展攻关。|The centre uses node laboratories and specialist divisions for cross-institution research on Hunan's industrial bottlenecks.",
 "岳麓山工业创新中心、高校科研团队、技术经理人与湖南制造企业。|The centre, university researchers, technology managers and Hunan manufacturers.",
 "节点实验室提供制造、设计、检测和加工能力，技术经理人负责匹配企业问题与科研团队。|Node labs provide manufacturing, design, testing and processing capabilities; technology managers match industrial problems to researchers.",
 "省政府2025年介绍记录四个节点实验室、八个专业研究部及低碳充填等联合研究实践。|The provincial 2025 profile records four node labs, eight specialist divisions and joint work including low-carbon backfilling.",
 "平台网络需要可执行的协同合同，跨机构团队规模不能代替任务进度与交付。|Networks need executable collaboration contracts; team size is not task progress or delivery.",
 "让技术经理人参与需求定义和合同组织，以企业采用和可验证的工艺改进评价攻关。|Involve technology managers in demand definition and contracting; evaluate adoption and verifiable process improvement.")
add("dalian_catalysis_pilot","CN","CN-LN","大连市",
 "大连化物所催化剂与反应过程放大|DICP catalyst and reaction-process scale-up platform",
 "pilot","materials","https://chpt.dicp.ac.cn/ptjs2.htm","中国科学院大连化学物理研究所","zh",
 "催化平台针对辽宁化工产业共性难题开展催化剂和反应过程放大，把实验室成果与化工园区企业连接。|The platform scales catalysts and reaction processes for Liaoning's chemicals industry, linking laboratory work to industrial-park firms.",
 "大连化物所催化平台、科研团队及长兴岛产业化企业。|DICP's catalysis platform, researchers and Changxing Island commercialisation firms.",
 "把催化新材料、清洁转化工艺和中试放大组合，围绕工程化瓶颈组织技术转化。|Catalytic materials, clean-conversion processes and piloting address engineering bottlenecks together.",
 "官方平台介绍列出中试职能，并记录2016年以来衍生的中科催化及延长中科两家企业。|The official profile lists piloting functions and two spin-out firms established since 2016.",
 "衍生企业成立不等于持续盈利，化工过程还需安全评价和连续运行验证。|Spin-out formation is not sustained profitability; chemical processes require safety review and continuous-operation tests.",
 "在产业园区复用工程与安全条件，按连续工艺验证、成本和客户采用分阶段支持。|Reuse industrial-park engineering and safety capabilities, funding stages against process tests, costs and adoption.")
add("haixi_fujian","CN","CN-FJ","福州市",
 "海西研究院团队与产业示范转化|Haixi institute team-based technology translation",
 "intermediary","digital","https://www.fjirsm.cas.cn/gjgdzjtclgcjsyjzx/zxdt/201503/t20150311_4320361.html","中国科学院福建物质结构研究所","zh",
 "海西研究院把前沿研究、关键技术和产业示范连接，通过团队、项目与成果共同转化推动光芯片产业应用。|Haixi links frontier research, enabling technologies and industrial demonstrations through team/project-based translation of optical-chip research.",
 "海西研究院、福建物构所、科研团队及中科光芯等产业化主体。|Haixi, Fujian's structure-of-matter institute, researchers and firms including Sino-Semiconductor.",
 "以人才团队、项目和成果成组对接产业化主体，而非仅出售单项专利。|Teams, projects and results are transferred together to industrial operators rather than through isolated patent sales.",
 "研究所2015年介绍记录开放创新价值链及半导体激光器、探测器成果与企业衔接。|The institute's 2015 account documents the innovation chain and connections between laser/detector research and firms.",
 "历史转化案例不能证明当前产品市场地位；产业化仍依赖制造和可靠性能力。|Historical transfer does not establish current market position; manufacturing and reliability capabilities remain necessary.",
 "对团队持续服务、产品工艺和客户验证共同约定责任，避免专利转让后研发支持中断。|Agree ongoing team support, process delivery and customer validation to avoid discontinuity after patent transfer.")
add("asean_transfer_guangxi","CN","CN-GX","南宁市",
 "中国东盟技术转移协作网络|China–ASEAN technology-transfer cooperation network",
 "intermediary","general","https://gxxxzx.gxzf.gov.cn/qwfb/bps/P020230419299818927646.pdf","广西壮族自治区信息中心","zh",
 "中国东盟技术转移中心以政府间工作机制、联合工作组和企业协作网络连接跨境技术供需。|The China–ASEAN centre connects cross-border technology supply and demand through intergovernmental mechanisms, working groups and firms.",
 "技术转移中心、广西及东盟合作部门、联合工作组与企业。|The centre, Guangxi/ASEAN agencies, joint working groups and firms.",
 "通过双边技术转移机制组织合作，再以企业网络承接对接活动。|Bilateral transfer mechanisms organise cooperation, with enterprise networks supporting matchmaking.",
 "广西官方白皮书记载截至2020年11月已与九个东盟国家建立双边机制，并形成企业协作网络。|An official Guangxi white paper records bilateral mechanisms with nine ASEAN countries by November 2020 and an enterprise network.",
 "机制和成员数不等于技术交易成功，跨境项目仍受法规、知识产权和本地吸收能力约束。|Mechanisms and membership are not completed transfers; regulation, IP and local absorptive capacity still constrain projects.",
 "以具体技术合同、合规支持和本地实施伙伴作为跨境合作的交付单元。|Use technical contracts, compliance support and local implementation partners as the units of cross-border delivery.")
add("lanzhou_pilot","CN","CN-GS","兰州市",
 "兰州化物所兰州新区中试转化合作|LICP–Lanzhou New Area pilot-transfer partnership",
 "pilot","materials","https://www.licp.cas.cn/sy2018/hzjl/sdhz/202205/t20220510_6446122.html","中国科学院兰州化学物理研究所","zh",
 "兰州化物所与兰州新区签署中试转化基地协议，将研究所技术能力与新区产业承载条件衔接。|LICP and Lanzhou New Area agreed a pilot-transfer base linking research capabilities to local industrial capacity.",
 "兰州化物所、兰州新区及相关工程研究平台。|LICP, Lanzhou New Area and associated engineering-research platforms.",
 "地方提供产业化承载条件，研究所依托实验室和工程中心推进技术转移及人才培养。|Local industrial conditions connect with institute laboratories and engineering centres for transfer and training.",
 "2022年官方签约报道确认中试转化基地合作与成果转移、人才培养等任务。|The official 2022 signing report confirms the pilot-transfer cooperation and tasks in transfer and training.",
 "签约是组织安排，不代表基地已全面建成或形成产能。|Signing establishes an arrangement, not proof of completed facilities or production capacity.",
 "将建设协议转成可验收的中试任务，明确设施开放、运营经费和环境安全要求。|Translate agreements into verifiable pilot tasks with access, operating-finance and environmental/safety requirements.")
add("qinghai_salt_pilot","CN","CN-QH","西宁市",
 "青海盐湖所甘河开放中试基地|Qinghai salt-lake institute Ganhe open pilot base",
 "pilot","materials","https://www.isl.cas.cn/jg/zcbm/ghzsjd/","中国科学院青海盐湖研究所","zh",
 "甘河基地面向盐湖资源开发提供开放中试服务，将锂、硼、铷、铯等分离技术从实验开发推进至工艺放大。|Ganhe offers open piloting for salt-lake resources, scaling separation technologies for lithium, boron, rubidium and caesium.",
 "青海盐湖所、中试技术团队及技术验证和工程应用用户。|The salt-lake institute, pilot teams and technology-validation/engineering users.",
 "采用不同规格萃取装置及装备子平台，提供工艺开发、验证、孵化和工程应用服务。|Extraction equipment at different scales supports process development, validation, incubation and engineering services.",
 "官网列出五个装备子平台、箱式萃取槽、离心萃取器及萃取塔，并明确对外开放。|The official page lists five equipment sub-platforms, mixer-settlers, centrifugal extractors and extraction columns, with external access.",
 "不同盐湖卤水差异较大，成功的单点试验不能直接外推到其他资源条件。|Brines vary substantially; successful tests at one site cannot be directly extrapolated to other resource conditions.",
 "按资源成分和环境条件设计中试，以收率、能耗、杂质控制和工程稳定性形成交付。|Design pilots for resource composition and environment, delivering evidence on recovery, energy, impurity control and stability.")
add("henan_molybdenum","CN","CN-HA","三门峡市",
 "中原关键金属实验室钼冶金成果转化|Zhongyuan critical-metals laboratory molybdenum transfer",
 "mission","materials","https://kjt.henan.gov.cn/2024/12-18/3100240.html","河南省科学技术厅","zh",
 "中原关键金属实验室以无氨氮钼冶金新技术成果转让，将科研攻关与三门峡金属材料产业连接。|The laboratory connects research to Sanmenxia's materials industry through transfer of an ammonia-nitrogen-free molybdenum process.",
 "中原关键金属实验室、成果受让方及三门峡产业合作方。|The laboratory, technology recipient and Sanmenxia industrial partners.",
 "围绕钼产业链技术需求开展研发，以成果转让衔接生产端应用。|Research addresses molybdenum value-chain needs and uses technology transfer to connect with production.",
 "省科技厅2024年报道确认首个成果转让签约及其针对钼产业链的技术任务。|The provincial 2024 account confirms the first transfer agreement and its molybdenum-industry focus.",
 "签约不能代替环境绩效和生产成本验证，技术影响须在实际工况下评价。|An agreement is not validation of environmental performance or costs; impacts need operating-condition assessment.",
 "将受让企业的工程验证与低污染工艺指标写入转化合同，保持实验室后续技术支持。|Include engineering and pollution-control tests in transfer contracts, retaining laboratory follow-up support.")
add("hit_heilongjiang","CN","CN-HL","哈尔滨市",
 "哈工大先进技术研究院成果对接|HIT advanced-technology institute industrial matchmaking",
 "intermediary","digital","https://news.hit.edu.cn/2024/0731/c11508a236323/page.htm","哈尔滨工业大学","zh",
 "哈工大先研院组织人工智能与机器人专场，将高校技术成果与地方产业、科技投资及转化服务机构对接。|HIT's institute connects AI/robotics research with local industry, technology investors and transfer services through specialist matchmaking.",
 "哈工大先研院、黑龙江科技部门、新产投集团、投资及成果转化服务机构。|HIT's institute, Heilongjiang science authorities, industrial investors and transfer-service organisations.",
 "以细分技术专场集中展示成果，组织产业与资本方参与交流和对接。|Domain-specific events present research and convene industrial and investment partners.",
 "校方2024年报道列出人工智能与机器人首场活动及政府、投资、产业联盟等参与主体。|The 2024 university account identifies the first AI/robotics event and participating government, investors and industrial alliance.",
 "路演和对接只是合作入口，不能据此判断已经完成许可或形成产业收入。|Events are entry points, not evidence of completed licensing or industrial revenue.",
 "跟踪对接后的技术尽调、联合试验和合同实施，形成专场活动的后续交付链。|Track technical due diligence, joint trials and contract implementation after matchmaking.")
add("cqu_bishan","CN","CN-CQ","重庆市",
 "重庆大学璧山先进技术研究院转化孵化|Chongqing University Bishan advanced-technology incubation",
 "venture","general","https://www.cqu.edu.cn/info/1111/69101.htm","重庆大学","zh",
 "璧山研究院结合校内团队成果转化与校企共同转化，利用校地平台承接企业孵化和中试。|Bishan combines university-team and joint university–industry transfer through a local platform for incubation and piloting.",
 "重庆大学、璧山地方合作方、校内科研团队及校企合作企业。|Chongqing University, Bishan partners, research teams and university–industry firms.",
 "按团队自主转化与校企共同转化组织孵化，并与空间太阳能、生物制造中试场景衔接。|Incubation follows team-led and joint transfer routes, connected to space-solar and biomanufacturing pilot settings.",
 "2026年大学报道记录两类各九家孵化企业入驻、新产品发布及中试平台调研。|A 2026 university report records nine firms in each transfer category, product releases and pilot-platform visits.",
 "入驻与产品发布不等于销售或成熟产能，需要继续验证客户和工程需求。|Occupancy and product releases are not sales or mature capacity; customers and engineering requirements need further validation.",
 "按许可、自主创业和校企合作分别管理权属与评价，公共场景向多种转化路径开放。|Manage ownership and appraisal separately for licensing, startups and joint transfer; open public test settings to multiple routes.")

# Africa: applied services, shared facilities and research–industry co-funding.
add("tia_stations","ZA",None,None,
 "南非技术创新署高校技术站计划|South African TIA Technology Stations Programme",
 "capacity","manufacturing","https://www.tia.org.za/programmes/","Technology Innovation Agency","en",
 "技术站依托技术大学，为中小企业提供工程解决方案和技术开发服务，连接高校能力与生产需求。|University-based technology stations provide engineering solutions and technology development for SMEs.",
 "南非技术创新署、技术大学、技术站与中小企业。|TIA, universities of technology, technology stations and SMEs.",
 "在高校配置技术转移基础设施及专业人员，以技术改进支持本地供应商参与产业链。|University facilities and specialists support technology transfer and supplier upgrading.",
 "官方计划页记录技术站设于高校，并明确其企业技术开发、工程问题解决和技术转移职能。|The programme page documents university hosting, industrial development, engineering problem-solving and transfer functions.",
 "企业工程基础和持续需求影响服务效果；不能把技术站数量当作区域生产率。|Firm capabilities and sustained demand condition results; station counts are not regional productivity.",
 "围绕中小企业共同工艺问题设站，以企业试用、工程交付和技能掌握评价服务。|Create stations around shared SME process problems; assess industrial trials, delivery and skills adoption.")
add("csir_industry_facilities","ZA",None,None,
 "南非CSIR产业创新共享设施|South African CSIR industry-innovation facilities",
 "pilot","manufacturing","https://wwwprod.csir.co.za/industry-innovation-support","CSIR South Africa","en",
 "CSIR向产业开放大规模原型、预商业制造及专业技术能力，支持实验室验证向中试制造衔接。|CSIR opens large-scale prototyping, pre-commercial manufacturing and specialist capabilities to industry.",
 "南非CSIR、科技主管部门、企业及产业创新合作资金。|CSIR, science authorities, firms and the Industry Innovation Partnership Fund.",
 "公共资金支持专业设施，以共享设备、研发技能和企业网络连接产品开发与放大。|Public support funds specialist facilities combining equipment, research skills and business networks for development and scale-up.",
 "官网列出生物制造、纳米材料、生物炼制和光子原型等设施，服务从验证延伸至中试制造。|The official page lists biomanufacturing, nanomaterials, biorefinery and photonics facilities spanning validation to piloting.",
 "本例按共享设施支持体系计一次，不将其下属设施再次累计为独立成果。|This case counts the support system once; subordinate facilities are not added as independent outcomes.",
 "优先建设企业难以独立承担的工程验证能力，并以设施使用、交付和企业投入考核运营。|Prioritise validation capabilities beyond individual firms' resources; evaluate use, delivery and firm contributions.")
add("green_energy_park","MA",None,None,
 "摩洛哥Green Energy Park光伏研发测试|Morocco Green Energy Park solar research and testing",
 "pilot","solar","https://greenenergypark.ma/","Green Energy Park","en",
 "园区将光伏研究、测试认证、培训和创业支持连接，为新能源技术提供实际环境验证条件。|The park connects solar research, testing/certification, training and startup support in an operating environment.",
 "Green Energy Park研究与测试团队、项目合作伙伴及技术用户。|Green Energy Park teams, research-project partners and technology users.",
 "共享试验设施承接光伏性能与环境适应研究，再连接技术应用和人员能力建设。|Shared facilities support photovoltaic performance/environmental testing alongside application and skills development.",
 "官网列出光伏积灰磨损、组件性能和矿区适配电站等项目，并提供测试与认证服务。|The site lists soiling/abrasion, module-performance and mining-site solar projects, alongside testing and certification services.",
 "测试服务与Green Innoboost资助计划不同，不能把关联平台和计划的成果混加。|The testing platform differs from Green Innoboost funding; linked platform/programme outcomes must not be added together.",
 "围绕本地气候、粉尘和客户要求开放测试，把认证条件与工程试用并行推进。|Test against local climate, dust and customer requirements, linking certification to engineering trials.")
add("knust_tcc","GH",None,None,
 "加纳KNUST技术咨询与制造转移中心|Ghana KNUST Technology Consultancy Centre",
 "capacity","manufacturing","https://tcc.knust.edu.gh/index.php/about/about-us","KNUST Technology Consultancy Centre","en",
 "中心以工程研究、先进制造、技术转移和技术创业培训连接大学与产业。|The centre connects university capabilities to industry through engineering research, advanced manufacturing, transfer and entrepreneurship training.",
 "夸梅恩克鲁玛科技大学技术咨询中心、工程研究人员及技术服务用户。|KNUST's consultancy centre, engineering researchers and technology-service users.",
 "把工程技术能力与企业技能、创业训练结合，支持技术采用和商业过程改进。|Engineering capabilities combine with industrial skills and entrepreneurial training for adoption and process improvement.",
 "官方简介确认1972年成立及工程研究、制造、技术转移与创业技能培训等职责。|The official profile records establishment in 1972 and functions in engineering, manufacturing, transfer and entrepreneurship skills.",
 "技能建设与产品商业化有不同时间尺度，培训完成不等于企业已经采用技术。|Skills development and commercialisation have different timescales; training completion does not establish adoption.",
 "将操作训练与现场工艺改进共同安排，按企业掌握和重复使用技术检验培训。|Link practical training to process improvements and verify mastery through repeat use by firms.")
add("dedan_kimathi_park","KE",None,None,
 "肯尼亚德丹基马蒂大学科技园|Kenya Dedan Kimathi Science and Technology Park",
 "cluster","manufacturing","https://stp.dkut.ac.ke/objectives/","Dedan Kimathi University of Technology","en",
 "科技园面向设计制造、材料、生物技术及信息技术，将大学知识与企业、初创团队和市场连接。|The park links university knowledge to firms, startups and markets in manufacturing/materials, biotechnology and ICT.",
 "德丹基马蒂理工大学、科技园、企业、政府及投资合作方。|DeKUT, the science park, firms, government and investment partners.",
 "以共享服务、孵化和技术技能转移组织园区协同，连接本地与更广泛市场。|Shared services, incubation and technology/skills transfer organise cooperation and market connections.",
 "官网目标说明列出三类技术领域、企业共同服务和大学产业间技术及商业技能转移。|The official objectives identify three domains, shared business services and university–industry technology/skills transfer.",
 "目标说明是组织设计，不代表园区全部设施已建成或企业实现增长。|Objectives describe institutional design, not completed facilities or demonstrated firm growth.",
 "先建设有明确企业需求的共享工程服务，再分阶段扩建孵化和场地设施。|Start with shared engineering services backed by demand, then expand incubation and facilities in stages.")
add("mauritius_crigs","MU",None,None,
 "毛里求斯产学合作研发资助|Mauritius Collaborative Research and Innovation Grant Scheme",
 "consortium","general","https://www.mric.mu/collaborative-research-and-innovation-grant-scheme","Mauritius Research and Innovation Council","en",
 "计划要求本地公司与学术或研究机构合作申请支持具有商业潜力的研发项目。|The scheme requires local firms to partner with academic/research institutions on commercially promising R&D.",
 "毛里求斯研究与创新理事会、本地企业及学术研究机构。|MRIC, local companies and academic/research institutions.",
 "以联合申请把企业技术需求和研究能力连接，资助合作研发而非单独的机构建设。|Joint applications connect industrial demand to research capabilities, funding collaborative R&D rather than institutions alone.",
 "官方规则明确公司作为主要申请人，与本地学术或研究机构共同提交创新研发项目。|Official rules identify the firm as lead applicant with a local academic/research partner.",
 "商业潜力属于遴选条件，不是项目已经商业成功；小经济体还需考虑市场规模。|Commercial potential is a selection criterion, not realised success; small economies also face market-size constraints.",
 "用企业需求与合作协议约束资助，分阶段核查技术、客户和持续融资条件。|Condition grants on demand and collaboration agreements, with staged checks of technology, customers and follow-on finance.")
add("nilepreneurs_iot","EG",None,None,
 "埃及NilePreneurs物联网产业加速|Egypt NilePreneurs industrial IoT accelerator",
 "capacity","digital","https://nu.edu.eg/news/nile-university-nilepreneurs-and-qnb-egypt-partner-launch-iot-accelerator","Nile University","en",
 "尼罗大学NilePreneurs与QNB埃及合作推出物联网加速器，帮助本地中小企业和初创企业采用数字技术。|NilePreneurs and QNB Egypt launched an IoT accelerator supporting digital adoption by local SMEs and startups.",
 "尼罗大学NilePreneurs、QNB埃及、中小企业与初创企业。|Nile University/NilePreneurs, QNB Egypt, SMEs and startups.",
 "大学技术与创业支持连接金融机构和企业数字化场景，以加速计划支持物联网应用。|University technical/venture support connects finance and industrial digitalisation through an IoT accelerator.",
 "大学2025年3月公告确认合作推出加速器，面向工业4.0、本地制造与数字转型。|A March 2025 university announcement confirms the accelerator and its Industry 4.0/manufacturing focus.",
 "启动公告不能证明企业已实现降本或效率提升，需要应用前后的实际指标。|Launching does not establish cost or efficiency gains; before/after operating metrics are needed.",
 "把小规模场景试点与技能训练结合，以设备互联、可靠性和用户采用作为阶段验收。|Combine small application pilots with skills training, assessing connectivity, reliability and user adoption.")

# South America: independent public/industry/university operators, not branches.
add("sena_tecnoparque","CO",None,None,
 "哥伦比亚SENA技术园原型开发网络|Colombia SENA Tecnoparque prototype-development network",
 "capacity","manufacturing","https://historico.sena.edu.co/es-co/formacion/Paginas/tecnoparques.aspx","SENA","es",
 "技术园网络向创新者提供免费专业指导和实验设施，支持研发想法形成可运行原型。|Tecnoparque provides free specialist advice and laboratories to develop functional R&D prototypes.",
 "哥伦比亚国家职业培训局、技术园多学科团队、创新者与企业。|SENA, multidisciplinary technology-park teams, innovators and firms.",
 "在电子通信、生物与纳米技术、工程设计和数字技术方向，组合个性化指导与实验室访问。|Personalised advice and lab access cover electronics/telecoms, biotechnology/nanotechnology, engineering/design and digital technologies.",
 "SENA官方介绍明确免费服务、功能原型、技术适配与转移等服务环节。|SENA's official profile documents free services, functional prototyping, adaptation and technology transfer.",
 "原型完成不等于量产或收入，下一步仍需客户、认证和生产组织。|Functional prototypes are not mass production or revenue; customers, certification and production organisation remain necessary.",
 "以原型性能和企业试用决定后续支持，将公共训练与商业化融资分开衔接。|Use prototype performance and industrial trials to select follow-on support, linking public training to separate commercial finance.")
add("inti_transfer","AR",None,None,
 "阿根廷INTI工业技术转移|Argentina INTI industrial technology transfer",
 "intermediary","general","https://www.inti.gob.ar/areas/desarrollo-tecnologico-e-innovacion/transferencia/transferencia-tecnologica","INTI","es",
 "INTI向工业尤其是中小企业提供技术诊断、原型、工艺开发及多种技术转移合同。|INTI provides diagnostics, prototypes, process development and flexible technology-transfer contracts, especially for SMEs.",
 "国家工业技术研究院、多学科技术人员及食品、能源、交通等企业。|INTI, multidisciplinary specialists and firms in food, energy, mobility and other industries.",
 "以实验室和中试能力诊断产品与工艺问题，通过合作、许可或特许权使用费等方式分担风险。|Laboratories/pilots diagnose product and process problems; cooperation, licensing and royalty arrangements share risks.",
 "官方服务页列出专利、许可、专属及风险共担合同，以及中试与先进实验室支持。|The service page lists patents, licensing, exclusive/risk-sharing contracts, pilot plants and laboratories.",
 "风险共担合同需有可核查的销售和权属安排，否则难以收取后续收益。|Risk-sharing contracts require auditable sales and ownership arrangements to support later returns.",
 "按企业问题选择咨询、合同研发或许可，不要求所有成果都设立新公司。|Choose advice, contract R&D or licensing to fit firm problems rather than forcing spin-outs for every result.")
add("senai_sp_innovation","BR",None,None,
 "巴西SENAI圣保罗创新与技术研究所网络|Brazil SENAI São Paulo innovation and technology institutes",
 "intermediary","manufacturing","https://www.sp.senai.br/para-a-sua-empresa/institutos-inovacao-tecnologia","SENAI-SP","pt",
 "SENAI圣保罗把技术教育、应用研发和实验室服务结合，按企业需求定制工业技术方案。|SENAI-SP integrates technical education, applied R&D and laboratory services for tailored industrial solutions.",
 "SENAI圣保罗创新与技术研究所、专业人员及工业客户。|SENAI-SP institutes, technical specialists and industrial clients.",
 "通过研究所网络提供研发、检测和咨询，将技能培养与技术采用连接。|A network delivers R&D, testing and consulting, connecting workforce skills to technology adoption.",
 "官方介绍列出十八个工业服务领域，以及数字化、脱碳和工业4.0等技术方向。|The official profile lists 18 industrial service fields and work on digitalisation, decarbonisation and Industry 4.0.",
 "SENAI是服务实施网络，EMBRAPII是另一资助协作安排，两者相关但不能混作同一成果。|SENAI delivers services while EMBRAPII is a distinct funding arrangement; linked activities are not identical outcomes.",
 "把产业培训与专业研发服务组织成连续支持，以企业实际工艺改进而非服务项目数评价。|Link industrial training to specialist R&D, assessing process improvements rather than service counts.")
add("uc_chile_innovation","CL",None,None,
 "智利天主教大学创新中心开放协作|Chile UC Innovation Centre open collaboration",
 "cluster","digital","https://centrodeinnovacion.uc.cl/espacios/ecosistema-edificio/","Centro de Innovación UC","es",
 "大学创新中心以共享空间、数字制造和企业联合实验连接研究人员、创业者及产业用户。|The university centre connects researchers, entrepreneurs and industry through shared space, digital fabrication and joint laboratories.",
 "智利天主教大学创新中心、学者、创业团队及企业合作平台。|UC's innovation centre, academics, entrepreneurs and industrial collaboration platforms.",
 "将制造原型与企业需求平台共置，促进跨学科交流及从原型到试点的合作。|Co-located fabrication and demand platforms support interdisciplinary exchange and prototype-to-pilot cooperation.",
 "官网列出面向企业和学者开放的FabLab，以及连接企业问题与初创技术的Claro Lab。|The official page identifies a FabLab open to firms/researchers and Claro Lab linking industrial problems to startup technologies.",
 "共置能够创造接触机会，但不能据此推断合作产生因果收益。|Co-location creates contact opportunities, not causal evidence of benefits.",
 "围绕共同任务设置共享空间，明确企业问题、实验条件和后续产品验证责任。|Configure shared space around tasks, with clear industrial problems, experimental conditions and validation responsibilities.")
add("latitud_uruguay","UY",None,None,
 "乌拉圭Latitud应用研发与产业链服务|Uruguay Latitud applied R&D and value-chain services",
 "intermediary","biomanufacturing","https://latitud.org.uy/latitud-la-fundacion-del-latu-para-idi-celebro-sus-primeros-cinco-anos-de-trabajo-junto-al-sector-productivo/","Latitud Fundación LATU","es",
 "LATU的研发创新基金会Latitud与生产部门合作，用科学技术改进企业价值链和可持续性。|Latitud, LATU's R&D foundation, works with production sectors to improve industrial value chains and sustainability.",
 "Latitud、乌拉圭技术实验室LATU、应用研究人员及企业。|Latitud, LATU, applied researchers and firms.",
 "以企业和产业链改进机会组织应用研究，让研究结果进入生产问题解决过程。|Industrial improvement opportunities organise applied research and its use in production problem-solving.",
 "官方成立五周年回顾说明基金会以LATU能力服务企业，推动技术引入和知识生成。|The official five-year review documents the use of LATU capabilities for firms' technology adoption and knowledge development.",
 "产业服务范围不代表各行业采用同一种路径，食品和材料工艺要求需分别处理。|A broad service remit does not imply a single pathway; food and materials require distinct process conditions.",
 "以价值链的具体损耗、质量与资源效率问题组织合作，保持企业参与研究设计。|Organise collaboration around losses, quality and resource efficiency, involving firms in research design.")
add("peru_cite","PE",None,None,
 "秘鲁ITP产业创新与技术转移网络|Peru ITP CITE productive-innovation and transfer network",
 "capacity","manufacturing","https://gestion-repo.itp.gob.pe/items/5dbfd881-ad8c-46ef-80f9-719755771dde","Instituto Tecnológico de la Producción","es",
 "ITP的CITE网络通过产业技术服务连接生产企业与技术能力，并以市场研究支持技术采用和转移决策。|ITP's CITE network connects producers to technical services, using market research to inform adoption and transfer decisions.",
 "秘鲁生产技术研究院、CITE网络与接受技术服务的企业。|ITP, CITE centres and industrial service users.",
 "在技术服务体系中纳入市场需求研究，为采用、适配、开发和技术转移提供决策依据。|Market-demand research informs adoption, adaptation, development and transfer within technical services.",
 "ITP官方仓储收录市场研究应用于研发创新的手册，明确技术采用与专业服务改进的适用方向。|ITP's repository holds a market-research manual covering technology adoption and improvement of specialist services.",
 "手册是工作方法依据，不是所有中心已获得产业绩效的证明。|A manual documents methods, not industrial results across all centres.",
 "技术服务立项前识别用户与需求，用企业试用反馈修订服务内容和转移方式。|Identify users and demand before starting services, then revise delivery and transfer routes using trial feedback.")

# Oceania: different CRCs are independent operators; no subproject inflation.
add("hilt_crc","AU",None,None,
 "澳大利亚HILT重工业低碳合作研究中心|Australia HILT heavy-industry low-carbon CRC",
 "consortium","industry","https://hiltcrc.com.au/news/hilt-crc-launches-energy-infrastructure-project-to-help-guide-heavy-industry-decarbonisation/","HILT CRC","en",
 "HILT把钢铁、氧化铝和水泥等企业与研究机构连接，开展重工业低碳技术开发与示范。|HILT connects heavy-industry firms and researchers on low-carbon technologies for steel, alumina and cement.",
 "HILT、工业企业、CSIRO、高校及澳大利亚能源市场运营机构等伙伴。|HILT, industrial firms, CSIRO, universities and partners including AEMO.",
 "以产业共性技术任务组织企业、大学与政府合作，在技术选择中引入能源系统约束。|Shared industrial tasks organise cooperation, bringing energy-system constraints into technology choices.",
 "官方能源基础设施项目报道列出十二个产业与研究参与方，以及能源成本和转型路径建模任务。|The official infrastructure-project report names 12 industrial/research participants and energy-cost/pathway modelling tasks.",
 "能源成本情景不是已实现的减排效果，应分开处理模型假设和示范结果。|Energy-cost scenarios are not realised emissions reductions; assumptions and demonstrations must remain separate.",
 "由多家企业提出共同瓶颈，用共享模型和工程试验降低重复研发成本。|Let firms define shared bottlenecks and use common models/engineering trials to reduce duplicated R&D.")
add("race_crc","AU",None,None,
 "澳大利亚RACE可靠可负担清洁能源合作|Australia RACE for 2030 collaborative energy research",
 "consortium","general","https://racefor2030.com.au/content/uploads/Annual-Report-2023.pdf","RACE for 2030 CRC","en",
 "RACE以行业主导的合作研究连接能源与碳转型研发、商业化、能力建设和市场应用。|Industry-led RACE connects energy/carbon-transition research, commercialisation, capability building and market adoption.",
 "产业伙伴、澳大利亚高校、CSIRO及国际研究组织。|Industrial partners, Australian universities, CSIRO and international research organisations.",
 "政府资助与伙伴现金、实物投入共同支持研发，再通过市场转化活动推广研究应用。|Public grants and partner cash/in-kind contributions support research and subsequent market-transformation activities.",
 "2023年年报列出行业主导身份、大学及CSIRO伙伴，以及现金和实物共同投入方式。|The 2023 annual report documents industry leadership, university/CSIRO partners and cash/in-kind co-contributions.",
 "承诺资源和减排目标不等于实际支出或效果，合作资金口径需保持一致。|Committed resources and emissions targets are not actual expenditure or impacts; funding definitions must remain consistent.",
 "让成果推广与研发同步规划，明确伙伴投入、试点用户和采用责任。|Plan dissemination alongside research and define partner contributions, pilot users and adoption responsibilities.")
add("blue_economy_crc","AU",None,None,
 "澳大利亚蓝色经济合作研究中心|Australia Blue Economy Cooperative Research Centre",
 "consortium","marine","https://blueeconomycrc.com.au/research/","Blue Economy CRC","en",
 "中心把海洋可再生能源、海上生产与水产产业放在共同研究框架下，组织跨领域研发。|The CRC combines marine renewables, offshore production and aquaculture in a joint research framework.",
 "蓝色经济CRC、产业与科研参与方及外部项目合作机构。|The CRC, industrial/research participants and external project collaborators.",
 "以研究投资框架遴选项目，将海上工程、能源供给和产业应用任务连接。|A research-investment framework selects projects linking offshore engineering, energy supply and industrial use.",
 "官方研究页给出五个研究领域及项目资助遴选框架，并连接成果采用和商业化策略。|The research page lists five areas and funding-selection rules linked to adoption and commercialisation strategies.",
 "跨行业共置增加工程接口，海洋生态、许可和系统可靠性需与技术研发同时验证。|Cross-sector integration adds interfaces; ecology, permits and reliability need validation alongside technology.",
 "先界定共同场景及接口标准，再安排联合研发和海上验证，避免各技术孤立优化。|Define shared settings and interface standards before joint R&D and offshore validation.")
add("smartcrete_crc","AU",None,None,
 "澳大利亚SmartCrete混凝土产业联合研发|Australia SmartCrete industry-led concrete research",
 "consortium","materials","https://smartcretecrc.com.au/","SmartCrete CRC","en",
 "SmartCrete支持企业提出需求、大学承担研发的混凝土创新项目，涵盖设计、材料与技术。|SmartCrete funds industry-led, university-delivered concrete innovation in design, materials and technologies.",
 "SmartCrete、混凝土产业企业、承担研发的大学及联邦资助方。|SmartCrete, concrete-industry firms, research universities and Commonwealth funding.",
 "独立合作研究中心配置公共资金，支持以行业问题为导向的大学研发合作。|An independent CRC allocates public funding to university collaborations driven by industrial problems.",
 "官网明确行业主导、大学交付的研发项目安排，以及联邦资金支持。|The official site specifies industry-led, university-delivered R&D backed by Commonwealth funding.",
 "混凝土应用需满足标准与耐久性要求，实验室减排潜力不能直接作为建筑全寿命效果。|Concrete needs standards and durability checks; laboratory mitigation potential is not whole-life building performance.",
 "让材料研发、工程标准和现场验证同步推进，公共投入与企业采用承诺相衔接。|Align materials research, standards and field validation, connecting public support to adoption commitments.")
add("foodbowl_nz","NZ",None,None,
 "新西兰FoodBowl食品开放中试|New Zealand FoodBowl open food-processing pilots",
 "pilot","biomanufacturing","https://foodinnovationnetwork.co.nz/hubs/","New Zealand Food Innovation Network","en",
 "FoodBowl提供食品级中试与制造空间，让企业在自建产线前测试加工工艺和产品。|FoodBowl offers food-grade pilot/manufacturing space to test processes and products before investing in dedicated lines.",
 "新西兰食品创新网络、FoodBowl工程与食品团队及企业用户。|NZFIN, FoodBowl engineering/food teams and industrial users.",
 "通过可访问的食品加工设施承接研发试验、验证和放大，减少企业早期固定设备投入。|Accessible processing facilities support R&D, validation and scale-up before firms commit to dedicated equipment.",
 "官网列出七个食品级加工空间，以及挤出、萃取、杀菌和高压处理等能力。|The official hubs page lists seven food-grade spaces and extrusion, extraction, sterilisation and high-pressure capabilities.",
 "共享产线需管理过敏原、清洁和配方保密，中试结果还要通过具体产品合规验证。|Shared lines require allergen, cleaning and recipe confidentiality controls plus product-specific compliance checks.",
 "对食品企业采用预约式中试与专业支持，把工艺测试和市场小批量验证连接。|Offer booked pilots with technical support, linking process tests to small-batch market validation.")
add("scion_services","NZ",None,None,
 "新西兰Scion林业与生物经济工程服务|New Zealand Scion forestry and bioeconomy engineering services",
 "intermediary","biomanufacturing","https://www.scionresearch.com/services","Scion","en",
 "Scion为林业、工业制造和先进技术客户提供咨询、检测、中试开发与科研成果商业化服务。|Scion offers advice, testing, pilot development and research commercialisation for forestry, manufacturing and technology clients.",
 "Scion研究人员、工程与商业化人员及国内外企业客户。|Scion researchers, engineering/commercialisation specialists and domestic/international clients.",
 "将研究咨询、技术测试与中试开发组合，为客户补充产品和工艺开发能力。|Advice, testing and pilot development supplement clients' product and process capabilities.",
 "官方服务页明确咨询、技术建议、检测、中试开发及成果商业化的服务链条。|The official service page documents the chain from consulting and testing to pilots and commercialisation.",
 "服务清单说明可提供的能力，并非具体客户已取得效果；机构改革不改变历史案例的日期属性。|A service list describes capabilities, not client impacts; institutional reforms do not make historical observations current outcomes.",
 "围绕生物质资源、材料工艺和客户验证提供连续工程服务，不以论文数量替代产业交付。|Deliver continuing services around biomass, materials processes and customer validation rather than publication counts.")

add("iit_madras_park","IN",None,None,
 "印度理工马德拉斯研究园产学共置|India IIT Madras Research Park industry–academia co-location",
 "cluster","general","https://www.iitm.ac.in/research-park/iitm-research-park","Indian Institute of Technology Madras","en",
 "研究园将产业研发与大学学者共置，通过共享交流和研发环境连接知识应用与产品服务。|The research park co-locates industrial R&D and academics to connect knowledge with products and services.",
 "印度理工马德拉斯、研究园、产业研发团队与学者。|IIT Madras, the research park, industrial R&D teams and academics.",
 "正式、非正式和主题交流空间支持持续接触，在共同研发环境中组织产业学术合作。|Formal, informal and thematic spaces support ongoing interaction and industrial–academic research cooperation.",
 "学校官方介绍明确大学研究园定位及用于持续产学协作的工作、交流与网络空间。|The university profile identifies the park and its working/networking spaces for sustained industry–academia cooperation.",
 "空间共置不是合作合同，仍需解决项目选择、人员时间与知识产权。|Co-location is not a collaboration contract; project selection, staff time and IP still need agreements.",
 "园区准入与实际联合研发挂钩，通过技术经理人把非正式交流转成可执行项目。|Link tenancy to actual joint R&D and use technology managers to turn informal contacts into executable projects.")
add("etri_transfer","KR",None,None,
 "韩国ETRI中小企业技术转化支持|Korea ETRI SME technology-commercialisation support",
 "intermediary","digital","https://www.etri.re.kr/eng/sub6/sub6_0101.etri?departCode=3","Electronics and Telecommunications Research Institute","en",
 "ETRI专门转化部门围绕公共研究成果建立商业化支持体系，帮助中小企业增强技术竞争力。|ETRI's dedicated division commercialises public-research technologies and supports SME technical competitiveness.",
 "韩国电子通信研究院技术商业化部门与中小企业。|ETRI's technology-commercialisation division and SMEs.",
 "将技术转移与企业支持制度结合，帮助研发成果进入企业应用和业务开发。|Technology transfer combines with SME support to connect research results to industrial applications and business development.",
 "官方组织说明明确商业化体系建设、技术转移支持及中小企业培育职责。|The official division profile identifies commercialisation-system development, transfer support and SME development functions.",
 "公共技术供给必须匹配企业工程和市场能力，不能从组织职责推定采用效果。|Public technology supply must match firm engineering/market capabilities; responsibilities do not establish adoption impacts.",
 "技术许可附带必要的工程咨询和企业吸收支持，按采用与产品验证评价转化。|Pair licensing with engineering advice and absorptive support, assessing adoption and product validation.")
add("nrc_irap","CA",None,None,
 "加拿大NRC工业研究援助|Canada NRC Industrial Research Assistance Program",
 "capacity","general","https://nrc.canada.ca/en/support-technology-innovation/financial-support-technology-innovation","National Research Council Canada","en",
 "NRC工业研究援助向加拿大中小企业提供创新研发资金，支持技术型产品与服务走向市场。|NRC IRAP funds innovative R&D by Canadian SMEs to develop market-ready technology products and services.",
 "加拿大国家研究委员会、符合条件的加拿大中小企业及项目团队。|NRC, eligible Canadian SMEs and project teams.",
 "对技术驱动的研发及相关创新活动提供资金，按企业项目连接研究投入与商业化。|Funding for technology-driven R&D and innovation connects industrial projects to commercialisation.",
 "官方资金说明明确中小企业、技术产品服务研发与创新活动的支持范围。|The official funding page specifies SME support for technology products/services and innovation activities.",
 "公共资助不意味着商业成功，企业需承担项目实施并满足资助资格与审查。|Public funding is not commercial success; firms remain responsible for delivery and eligibility/review requirements.",
 "以企业技术瓶颈和商业化计划确定资助范围，保留项目尽调及分阶段监督。|Define support around technical bottlenecks and commercialisation plans, with due diligence and staged monitoring.")

def profile(key, name, archetype, case_ids, mechanism, conditions, factors, government, boundary, province=None):
    PROFILES.append({"id":key,"name":bi(name),"archetype":archetype,"case_ids":["oi_"+i for i in case_ids],
        **{k:bi(v) for k,v in zip(("mechanism","conditions","factors","government","boundary"),
                                  (mechanism,conditions,factors,government,boundary))},
        **({"province":province} if province else {})})

profile("beijing_research_venture","北京案例：科研团队与专业资本衔接|Beijing cases: research teams and specialised capital","venture",["tsinghua_xlab","beijing_collaborative"],
 "校园跨学科培育与行业协同中心分别补充团队能力和项目融资接口。|Campus incubation and sector centres provide complementary team-development and financing interfaces.",
 "有高密度学科、科研团队和专业导师，并能明确高校、中心与投资方的职责。|Dense research capabilities, specialist mentors and clear university/centre/investor responsibilities.",
 "知识与人才集中有利于早期探索，但工程放大仍需产业用户参与。|Knowledge/talent concentration helps early exploration, but scale-up still needs industrial users.",
 "支持概念验证和专业转化人员，公益教育与投资决策分开，按客户验证释放后续支持。|Support proof of concept and transfer staff, separate education from investment, and stage support against customer validation.",
 "这是两个北京机构的互补机制，不代表全市唯一模式，也不能外推到缺少科研团队的地区。|Two complementary institutional mechanisms, not a unique city-wide model or a template for areas without research teams.","CN-BJ")
profile("shanghai_engineering","上海案例：工艺中试与早期创业双通道|Shanghai cases: process piloting and early-venture routes","pilot",["sitri_shanghai","shanghaitech_ott"],
 "共享工艺平台补充企业工程验证，大学转移与孵化提供知识产权和创业接口。|Shared process platforms provide engineering validation; university transfer/incubation adds IP and venture interfaces.",
 "有专业制造工程师、可共享设施、技术用户及能够处理知识产权的转化团队。|Manufacturing engineers, shared facilities, technical users and IP-capable transfer teams.",
 "高固定成本工艺与早期科研项目需要不同载体，不能让同一种孵化服务包办。|High-fixed-cost processes and early research need distinct operators rather than one generic incubator.",
 "对公共工艺能力和单个创业项目分别预算考核，以设备开放、工艺交付和企业试用评价。|Budget shared processes and ventures separately; assess access, process delivery and industrial trials.",
 "两例说明互补路径，不能合并成已验证的统一运营体系。|The cases illustrate complementary routes, not a verified unified operating system.","CN-SH")
profile("jiangsu_contract","江苏案例：合同科研与产业工程服务|Jiangsu cases: contract research and engineering services","intermediary",["jitri_jiangsu","tsari_suzhou"],
 "专业研究网络与行业工程研究院按企业任务组织研发，合同和团队激励承担衔接作用。|Specialist networks and engineering institutes organise research around firm tasks, linked through contracts and team incentives.",
 "企业能明确研发问题并共同投入，团队有工程交付能力，合同与公共资产规则相容。|Firms define problems and contribute resources; teams deliver engineering under compatible contract/public-asset rules.",
 "制造企业需求提供任务来源，外部学科和工程团队补充企业难以独立建设的能力。|Manufacturing demand supplies tasks while external researchers/engineers provide capabilities beyond individual firms.",
 "区分共性能力与合同任务，允许灵活团队激励，用工程验收和后续采用约束支持。|Separate shared capabilities from contracts, permit flexible incentives and evaluate engineering acceptance/adoption.",
 "不要求所有研究所采用相同股权结构；汽车工程案例不能代表全省行业结构。|Not all institutes need the same ownership structure; automotive engineering is not the province's full industrial mix.","CN-JS")
profile("shaanxi_joint_centres","陕西创新港：企业主导的校企联合体|Shaanxi Innovation Harbour: enterprise-led university partnerships","consortium",["xjtu_innovation_harbour"],
 "企业主导需求、投入、管理与转化，高校提供研究和人才，孵化连接后续工程应用。|Firms lead demand, financing, management and transfer; universities supply research/talent and incubation supports follow-through.",
 "有愿意长期投入的工业企业、大学研究团队和可执行的联合管理制度。|Committed industrial firms, university teams and executable joint-management arrangements.",
 "大型科研能力与企业工程需求互补，人才共聘可降低组织边界带来的协作成本。|Research capabilities complement industrial engineering; shared recruitment can reduce organisational frictions.",
 "先落实企业任务和工程负责人，再设立中心；明确共聘、知识产权及失败项目退出。|Agree tasks and engineering leads before centres, with rules for shared staff, IP and project exit.",
 "创新港属于特定组织案例，不是陕西全省的普遍模式；实施效果不能由共建数量推断。|Innovation Harbour is a specific arrangement, not a universal provincial model; partnership counts do not establish effects.","CN-SN")
profile("hubei_photonics","湖北案例：光电子集群与场景揭榜|Hubei cases: photonics clusters and application challenges","cluster",["wuhan_optoelectronics","xiangyang_optoelectronics"],
 "武汉学科与光电子产业集群提供技术供给，襄阳具体环境问题牵引产品任务。|Wuhan's research/industrial cluster supplies technology while Xiangyang's environmental needs define product tasks.",
 "有专业学科、产品厂商和可开展实际测试的应用单位。|Specialist disciplines, product manufacturers and users able to host field tests.",
 "技术密集地区提供专业能力，其他城市以真实场景补充市场和验证条件。|Technology-intensive areas provide expertise; other cities supply demand and validation settings.",
 "连接场景业主、大学和制造商，按现场性能验收，支持跨城共享专业测试能力。|Connect users, universities and manufacturers; accept field performance and share specialised testing across cities.",
 "两例支持专业网络与需求组织的对照，并不证明城市间协作已形成统一制度。|The cases contrast specialist networks and demand organisation, not a demonstrated unified intercity system.","CN-HB")
profile("resource_pilots","辽宁与青海案例：资源工艺牵引的开放中试|Liaoning and Qinghai cases: resource/process-driven open pilots","pilot",["dalian_catalysis_pilot","qinghai_salt_pilot"],
 "将资源或化工工艺的实验结果在专业中试设施中放大，研究人员与工程用户共同验证。|Specialised pilots scale resource/chemical processes with joint researcher–engineering-user validation.",
 "有可重复的原料供给、专业工程人员、安全环保条件及明确技术用户。|Repeatable feedstock supply, engineering staff, safety/environmental conditions and identifiable users.",
 "资源禀赋决定技术问题，工程设备和连续运行能力决定从实验到产业的距离。|Resources shape technical problems; equipment and continuous-operation capabilities shape scale-up requirements.",
 "公共投入优先补齐共享工艺环节，以物料、能耗、成本和稳定性验证安排后续资金。|Fund shared process gaps first and stage follow-on support against material, energy, cost and stability tests.",
 "催化与盐湖分离工艺不能直接互换；可借鉴的是中试组织与验证责任，而非具体技术路线。|Catalysis and brine separation are not interchangeable; transfer organisation and validation responsibilities, not process recipes.")
profile("australia_crc","澳大利亚：行业共投的合作研究中心|Australia: industry-co-invested cooperative research centres","consortium",["hilt_crc","race_crc","smartcrete_crc"],
 "公共支持与产业伙伴共同投入，独立合作中心组织大学和企业围绕中长期共性任务研发。|Public support and industrial co-investment fund independent centres coordinating universities/firms on shared medium-term tasks.",
 "多家企业有共同技术瓶颈，愿投入资源，研究与运营团队能持续组织合作。|Firms share technical bottlenecks and contribute resources, with teams capable of sustained coordination.",
 "重工业、电力用户和材料行业需要系统验证，单个企业难独立承担全部研究风险。|Heavy industry, energy users and materials need systems validation beyond one firm's research-risk capacity.",
 "以共同问题设立联合计划，分开核算现金与实物投入，研发、试点和成果采用同步规划。|Create programmes around common problems, separate cash/in-kind accounts and plan research, pilots and adoption together.",
 "不把计划预算或减排目标写成实现值，合作中心的经验也不代表所有澳大利亚企业。|Budgets and emissions targets are not realised results; CRC experience is not representative of all Australian firms.")
profile("latin_america_services","拉美案例：产业技术服务与技能升级|Latin American cases: industrial services and skills upgrading","intermediary",["inti_transfer","senai_sp_innovation","sena_tecnoparque"],
 "公共或产业技术机构提供检测、中试、合同研发和原型辅导，补充企业内部研发能力。|Public/industrial organisations provide testing, pilots, contract R&D and prototyping to supplement firm capabilities.",
 "有可使用的技术设施、专业人员及提出具体产品和工艺问题的企业。|Usable facilities, specialist staff and firms with concrete product/process problems.",
 "中小企业难负担完整研发体系，共享服务和培训可把知识应用到生产环节。|SMEs cannot always sustain full R&D systems; shared services and training connect knowledge to production.",
 "以企业问题而非机构挂牌配置公共服务，采用咨询、许可、研发合同等不同工具。|Configure services around firm problems rather than institution creation, using advice, licensing and R&D contracts as appropriate.",
 "阿根廷、巴西与哥伦比亚的资金和资格规则不同，此类型不是整个拉美的统一制度。|Funding/eligibility differ across Argentina, Brazil and Colombia; this is not a uniform regional system.")
profile("africa_capability","非洲案例：高校能力与共享工程服务|African cases: university capabilities and shared engineering services","capacity",["tia_stations","knust_tcc","mauritius_crigs"],
 "高校技术服务和产学联合资助相互补充，为企业提供工程技能、研究伙伴和项目支持。|University services and collaborative grants provide complementary engineering skills, research partners and project support.",
 "有具备工程交付能力的高校、可识别的企业需求与持续服务经费。|Universities can deliver engineering, firms express identifiable needs and service finance is sustained.",
 "吸收能力和技能约束常与资金约束并存，仅提供设备或拨款难以完成技术采用。|Absorptive/skills constraints can coexist with financing needs; equipment or grants alone may not deliver adoption.",
 "把共同工艺服务、人员训练和企业联合试验连接，按实际掌握技术和持续使用评价。|Connect process services, training and joint trials, assessing mastery and continued use.",
 "三国案例体现可比较的组织工具，不代表非洲总体，更不能据此推断发展阶段决定创新能力。|These tools are comparable across three countries, not representative of Africa or evidence that development status determines innovation.")

def main():
    # Tags are reviewed from the specific practices above, not inferred from a
    # country name. Supplementary policy interpretations do not establish facts.
    finance={"beijing_collaborative","tianjin_synbio","jitri_jiangsu","shanghaitech_ott",
             "xjtu_innovation_harbour","hit_heilongjiang","mauritius_crigs","nilepreneurs_iot",
             "race_crc","smartcrete_crc","nrc_irap","csir_industry_facilities"}
    facilities={"sitri_shanghai","dalian_catalysis_pilot","lanzhou_pilot","qinghai_salt_pilot",
                "tia_stations","csir_industry_facilities","green_energy_park","sena_tecnoparque",
                "inti_transfer","senai_sp_innovation","uc_chile_innovation","blue_economy_crc",
                "foodbowl_nz","scion_services","iit_madras_park"}
    ip={"shanghaitech_ott","inti_transfer","etri_transfer"}
    for c in CASES:
        key=c['id'].removeprefix('oi_')
        c['factors']=['knowledge','market']
        if key in finance:c['factors'].append('capital')
        if key in facilities:c['factors'].append('infrastructure')
        if key in {"tsinghua_xlab","xjtu_innovation_harbour","knust_tcc","tia_stations","sena_tecnoparque"}:
            c['factors'].append('talent')
        if key in ip:c['institutions'].append('ip')
        if c['research_annotation']['primary_model']=='capacity':c['modes']=['incubation']
    assert len({c['id'] for c in CASES})==len(CASES)
    assert len({s['url'] for s in SOURCES})==len(SOURCES)
    payload={"schema_version":"1.0","reviewed_at":DATE,"cases":CASES,"sources":SOURCES,
             "sector_taxonomy":SECTORS,"model_profiles":PROFILES,
             "provenance":{"coverage_review":{"date":DATE,"grain":"identifiable_platform_or_programme",
                 "selection":"official evidence; thin continents and Chinese provinces prioritised",
                 "facts":"official page text or indexed official excerpts; metadata and paraphrase only",
                 "interpretation_fields":["constraints","transfer","primary_model","model_profiles"],
                 "outcomes":"capabilities, objectives and agreements are not realised impacts"}}}
    path=ROOT/'config/open_innovation_coverage.json'
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({"added_cases":len(CASES),"new_profiles":len(PROFILES),
                      "China":sum(c['countries']==['CN'] for c in CASES)},ensure_ascii=False))

if __name__=='__main__':main()

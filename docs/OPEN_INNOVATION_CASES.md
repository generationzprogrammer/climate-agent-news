# 科产融合全球案例库

更新日期：2026-10-05

所属模块：格润能源技术

研究主题：科产融合发展的全球开放创新生态建设研究

## 使用

进入能源技术模式，在导航选择“科产融合”。可按研究维度、国家、协同模式、制度安排和关键词筛选。国别表沿用平台ISO 3166-1标准；全球或区域机制单独检索，不给欧盟编造国家代码。

- 研究维度：要素流动；生态适配；全球治理与制度缺口。
- 协同模式：跨境联合研发；应用研究与产业转化；开放试验与示范；多边协同网络；创业孵化与能力建设；数据、标准与技术交易。
- 制度安排：科研合作；知识产权；跨境数据与使用权；标准与合格评定。
- 创新要素：知识与技术、人才、资金、试验设施、数据、市场与产业需求。

“查看案例”展示参与主体、协同机制、已记录实践、流动要素、约束与适配条件、可借鉴做法和原始证据。选中两至三个案例打开比较表；手机版比较表横向滚动，不撑宽整页。“导出筛选结果”生成UTF-8 CSV，保留事实、适配分析、标签、项目时间和来源网址，适合后续编码与报告研究。中英文模式保持相同案例和筛选条件。

## 首批范围与事实边界

首批25个案例、40条原始来源、17个国家标签。覆盖IEA技术合作、弗劳恩霍夫、MIT能源计划、清洁氢能伙伴关系、Eurostars、新加坡ARTC、巴西EMBRAPII、摩洛哥Green Innoboost、ITER、WIPO GREEN、CTCN、印美SERIIUS、南非HySA、CSIRO氢能任务、日法里昂示范、ORE Catapult、中美清洁汽车研发安排、ISA资源中心、IECRE、电池护照、国际数据空间、InnoEnergy、肯尼亚气候创新中心、绿色电力未来使命和IEA PVPS Task 13。

记录粒度为一个独立合作项目、平台或制度安排，不是“一篇报道一个案例”。PVPS Task 13以父子关系关联IEA合作框架；二者层级不同，不能作为两个独立项目成果相加。国家标签记录明确的所在地或合作方，不代表多边机制完整成员清单。全球和区域机制的影响也不能计为所有国家已有参与。

摘要、主体、机制与已记录实践是来源支持的事实编译；约束与可借鉴做法为适配分析，不作为经因果识别的结论。分类标签表示研究问题，纳入治理维度不自动说明治理缺位。不得用案例数量或制度标签数量给国家创新绩效打分。

项目时间只填已核验年份；未核验则为空，不用抓取日期替代。来源published_date只在明确发表日期时填写，reviewed_at为来源与编译核验日期。历史研发安排和已结束示范保留时间范围；目标、试点结果与商业运营成果分别表述。

## Agent与持续更新

采编分为证据输入、机制及分类草拟、适配研判、发布核验。可选InnovationCaseAgent复用OpenAICompatibleModel，从操作者提供的公开片段生成中英文草案。每个事实字段需给出对应来源ID和原文支持短句；支持短句必须存在于输入材料。引文匹配只能证明来源中存在该句，不能替代翻译、语义蕴涵、因果关系和制度适配复核。

草案始终标记draft和blocked_pending_review，不能覆盖公开库。完成校编后需将来源、字段引用和标签整合到config/open_innovation_cases.json并明确标记已复核。模型不得自动将报道提升为合作案例。

每日现有GitHub Pages导出任务调用write_innovation_cases，从已有气候及能源归档关联近90天明确出现案例实体的新动态。英文原题与中文题名都参与匹配；不用MIT、ISA等易混缩写，也不以普通的“氢能”“太阳能”直接认定机构参与。相关新闻标记为实体提及，不自动改写已核验事实。每例最多展示12条近期动态，按URL去重，保留前次仍处于窗口内的记录；无命中时不捏造动态。

自动导出不调用模型、不增加采集请求、不增加Secrets，无新增模型费用；复用现有采集与部署算力。只有明确执行带--draft-evidence的命令才调用已配置模型，费用或额度按该账户实际方案计算。本次开发和验证未进行付费模型调用。

## 文件与复现

- config/open_innovation_cases.json：复核案例、分类与来源。
- src/climate_agent/innovation_cases.py：校验、新闻关联、可选模型草案。
- static/data/innovation_cases.json：网站公开数据，随日常导出重建。
- static/innovation-cases.js、static/innovation-cases.css：响应式界面。
- scripts/build_innovation_cases.py：离线重建或显式生成草案。
- scripts/verify_innovation_links.py：一次性HEAD链接检查。
- tests/test_innovation_cases.py、tests/innovation-cases.test.cjs：回归测试。
- scripts/qa_innovation_cases.cjs：独立桌面与手机浏览器检查。

不重新采集、不改历史档案的重建：

~~~powershell
python scripts/build_innovation_cases.py
~~~

可选模型草案需要1—8条公开证据，每条包含唯一id、HTTPS url和不超过12000字符的extract。建议另附原题、发布者、语言及日期。凭据沿用原有模型环境变量，不写入证据文件或命令行。草案只能输出到analysis/；默认草案路径已从Git排除。

~~~powershell
# 此命令才调用模型；公开证据文件需事先准备。
python scripts/build_innovation_cases.py --draft-evidence analysis/public_evidence.json
~~~

测试：

~~~powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -q
node --test tests/innovation-cases.test.cjs
~~~

链接检查为每URL一次有超时的HEAD请求，不复制页面或附件正文。404须更换或移除；403、202或超时仅表示自动检查受限，不能直接推断页面不存在，也不绕过验证或访问限制。事实核验同时参考公开原始页面、官方报告与文档。公开端保存编译、元数据和链接，不镜像全文、照片或图表。

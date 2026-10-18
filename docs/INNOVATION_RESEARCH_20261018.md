# 科产融合案例库：2026年10月18日研究与增量维护

## 数据范围

研究快照：1,189例、825份来源文献。原有769例事实逐字段保持不变，新增420例：美国NSF产学中心111例、中国教育部高校成果转化基地71例、巴西EMBRAPII技术单元95例、澳大利亚CRC-P项目60例、非洲卓越中心46例、日本JST共创平台37例。825份文献并非825个独立证据来源。

新增筛选框包含702条官方目录记录。中国基地认定年份仅作为有日期的活动记录，不作为高校或机构成立年；计划预算不作为实际支出。不同国家方案中的机构、项目与技术单元保持原记录层级，不推定为相互独立的组织样本。

主界面合并为5类合作与5类技术领域；研究用8类主要机制及详细技术标签仍保留。来源批次、国别、地区、时间依据与缺失值均可导出。新增三组计划机制概述只陈述来源支持的组织安排，不把模式名称当成效果评价。

## 采集与合规

来源URL位于 `scripts/collect_innovation_registries.py`。每次检查robots，明确User-Agent，连接超时10秒、总超时45秒、响应上限6MB，单次传输不重试，并缓存内容散列与UTC获取时间。官方页面变更导致字段或规模异常时，该来源失败并保留原有数据；不绕过登录或访问限制。

公开记录为组织事实、项目目标、有限摘要、来源链接及定位字段；不发布原始整页HTML和个人联系方式。事实字段与项目自述、研究解释分开。完整网页的本地缓存位于忽略目录tmp。中国两份DOC名录在本轮经只读转换及71行核对后录入固定TSV；每周自动新增主要覆盖可结构化解析的六套国际目录，不能称为自动覆盖全部全球或中国机构。

中国名录、逐项翻译、18项高校实践与三个新增模式的编码分别保存在config下的innovation_registry_china.tsv、innovation_registry_translations.json、innovation_registry_practices.json及innovation_registry_models.json。新增未提供中文专名的记录保留原名，不编造译名。来源再利用许可须在期刊数据仓储提交前逐项复核。

## 定期运行

- 工作流：`.github/workflows/innovation-watch.yml`，每周日15:20 UTC（北京时间23:20）；GitHub排队可能延后。
- admission：先按主要所在地已有数量排序，再按来源与稳定ID排序；每次最多36条，单国最多12条。
- 去重：稳定ID、标准化题名、官方记录URL；疑似更名列入审阅，不自动新增。
- 审计：`data/innovation_registry_update.json`保存每条候选的处理原因与来源健康；`data/innovation_registry_history.json`记录实际增量，0也是合法结果。
- 更新：重建`static/data/innovation_cases.json`、`innovation_update.json`与`static/innovation/assets/coverage-latest.svg`。
- 发布：Pages通过成功的workflow_run启动。机器人提交本身不会触发普通push工作流，故不能省略此桥接。
- 资源：不使用LLM API；单次最长20分钟。存量队列会耗尽，未来增长取决于官方新增及审阅通过情况，而不是保证每周固定增长。

无需新增Secrets。官方来源失效或字段结构变化须修解析器；不要通过跳过校验维持增长。

## 复现

Python 3.12。固定解析器依赖：beautifulsoup4 4.12.3、lxml 5.3.0。完整项目依赖由pyproject.toml提供。离线核验冻结表与散列：

```text
python scripts/audit_innovation_release.py analysis/innovation_research_20261018
python -m unittest discover -s tests -p "*innovation*.py"
```

在未安装项目的本地环境，先设置PYTHONPATH=src。研究数据包含关系表、嵌套JSON、字段字典、schema、质量统计、来源与筛选审计。manifest记录数据及关键代码的SHA256；文本代码规范化CRLF为LF，数据文件按原字节计算。历史研究版本不得覆盖。

冻结版本的图表可离线重算：

```powershell
$env:INNOVATION_RESEARCH_OUTPUT='analysis/innovation_research_20261018'
python scripts/build_innovation_figures.py
```

正式发布后，不可对该快照执行build_innovation_research_release.py --refresh。以后新研究应使用新目录及版本号；网站日常自动增量不改论文快照。

## 投稿前事项

Data Descriptor与中国政策分析分别成文。描述性结果不推断全国或全球总体比例，不进行国家优劣排名；项目登记目标不是已验证的商业化效果。主要机制与采集项目高度相关，分析须按来源分层或进行逐来源剔除敏感性检验。尚需独立研究者分层复核语义、记录分歧、审查许可、确认作者与贡献、将数据和代码存入正式长期仓储。不得虚构准确率、共同作者、数据DOI或已获伦理审查。

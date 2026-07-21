# Codex 分阶段实施任务

本文件可直接作为本地 Codex 的开发总任务。每次只执行一个阶段，完成测试后再进入下一阶段。

## Phase 0：仓库与运行基线

目标：建立可重复运行的本地开发环境。

- 创建 `pyproject.toml`、`src/`、`tests/`、`alembic/`、`docker-compose.yml`。
- 服务：PostgreSQL 16 + pgvector、Redis；应用容器可暂缓。
- 配置：Pydantic Settings 读取 `.env`；日志使用 JSON 格式并自动脱敏。
- 导入 `config/sources.master.json` 的校验模型和 seed 命令。
- 输出 `make/dev` 或等价的一键启动命令。

验收：全新环境能启动数据库；迁移成功；seed 可幂等执行；`pytest` 通过；日志不出现密钥。

## Phase 1：RSS 与 GDELT 最小闭环

目标：不使用 LLM 也能采集、规范化、入库和生成基础日报。

- 定义 `NormalizedArticle` Pydantic 模型和 SourceAdapter 协议。
- 实现通用 RSS 适配器、GDELT DOC 2.0 适配器。
- 首批源：Carbon Brief、Climate Home、Canary Media、UNEP、Guardian、BBC、UN News、GDELT。
- 实现 ETag/Last-Modified、超时、限速、指数退避、最大重试和响应大小上限。
- URL 规范化、UTC 时间转换、语言检测、内容 hash、幂等 upsert。
- 生成不含 LLM 的 Markdown 日报：新文章数、来源、标题、链接、主题词命中。

验收：离线 fixtures 可重放；重复运行不产生重复文章；单源失败不影响其他源；每篇记录能追溯到 fetch_run。

## Phase 2：官方站点解析器

目标：覆盖对 COP31 和中国政策最关键的非 RSS 页面。

- 实现 UNFCCC News、COP31、Türkiye Directorate of Climate Change、生态环境部应对气候变化四个专用适配器。
- 列表解析与正文解析分离；所有 CSS/XPath 选择器有 fixture 测试。
- PDF/附件只记录链接、媒体类型、文件大小、哈希和版本；必要时异步抽取文本。
- 监测解析器空结果、字段完整率骤降和页面结构变化。

验收：每个来源至少 3 个历史 fixture；选择器失效会报警而非返回“成功但 0 条”；附件版本可追踪。

## Phase 3：相关性、去重与事件聚类

目标：把文章列表转为可用事件流。

- 关键词粗筛使用 `config/keywords.yml`，保存命中/排除原因。
- 标注 300–500 篇中英土文章形成小型验证集。
- 训练或调用可替换的相关性分类器；输出标签、置信度、模型版本。
- 实现 URL hash、标题 hash、SimHash 去重；再加入 embedding 事件候选。
- 对通讯社转载保留 `is_syndicated`、`original_publisher`、`independent_source_count`。

验收：在验证集报告 Precision/Recall/F1；重复率下降但不误删相反观点；事件簇可人工展开到全部文章。

## Phase 4：分析 Agent

目标：生成有引用、可核验的中文分析。

- `EvidenceAgent`：抽取事实、数字、引语主体、政策阶段、证据等级和冲突点。
- `SummaryAgent`：输出中文标题、三句摘要、关键数字、来源引用。
- `DecisionSupportAgent`：输出影响对象、时间尺度、风险/机会、待跟踪事项和不确定性。
- 所有 prompt、模型名、温度、输入文章 ID、输出 JSON、token/成本和版本可追踪。
- JSON Schema 验证失败时最多修复一次，之后进入人工队列。

验收：不存在无 article/event ID 的事实断言；随机抽样的数字与单位能回到原文；冲突来源不会被强行合并成单一结论。

## Phase 5：每日简报与推送

目标：每日固定时间形成可重发、不可重复的简报。

- 简报先写入 `daily_briefs` 和 Markdown/HTML 文件，再进入 delivery 队列。
- 渠道适配器：先实现 Email 或通用 Webhook；ServerChan/企业微信可选。
- `delivery_key = brief_id + channel + recipient`，保证幂等。
- 支持每日版、突发版、COP31 专项版；安静时段和最大消息长度可配置。

验收：模拟失败后重试不会重复推送；每条推送可定位到简报版本；无有效事件时发送“无重大更新”而非编造内容。

## Phase 6：质量、监控与安全

- 来源健康面板：状态码、延迟、解析成功率、新增量、最后成功时间。
- 数据质量：空标题、未来时间、异常正文长度、来源突增、重复簇异常。
- 安全：SSRF 防护、允许域名单、响应大小限制、HTML 清洗、文件类型白名单。
- 合规：每个来源记录 robots/ToS 检查时间、允许的存储范围和复核日期。
- 备份：PostgreSQL 定期备份；原始响应按权限和留存期清理。

验收：故障演练、备份恢复、结构变化报警、密钥扫描和依赖漏洞检查均有记录。

## 不要在首期实现

- 全网无限爬取、社交媒体监控、付费墙绕过、浏览器集群。
- 自动对外发布未经人工复核的高风险政策建议。
- 在没有标注集的情况下宣称分类或聚类“准确”。
- 为每个来源单独复制一套调度、重试和入库逻辑。


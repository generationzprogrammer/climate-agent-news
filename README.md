# ClimateText Lab：国际气候情报与高质量中文文本数据库

以原“气候谈判情报台”为基础升级的数据产品。平台面向中国气候谈判、外交、政策研究与气候文本分析人员，不与通用模型比“摘要数量”，而是强调每日更新、中文信息质量、来源追溯和最多 100000 条版本化文本档案。公开页面优先展示用户真正需要的事件、概要、议题、地域、关键数字与原文入口；采集状态和内部审核字段只用于后台审计。

## 网站现在呈现什么

- 置顶的全球气候现场：中国位于地图中部偏右，可切换“今日队列 / 本周”；红点仅标记文本明确涉及的国家或地区，并通过自动错位避免密集点遮挡。
- 今日重要气候情报：优先展示最新北京时间自然日；当天达到约 8–10 条、至少 3 个来源且有明确定位时按单日发布，当天合格记录不足但已有多个可靠来源时，以当天记录领衔并用近 7 天高质量记录补足。先做同事件转载去重，再在质量优先的前提下限制单一来源和单一洲别占比。每条均包含中文标题、完整中文概要、议题、来源、发布时间和原文链接。
- 语料库统计分析：基于三年 JSONL 语料自动生成月度频率、主题频率、国家/地区分布、洲别结构、主要来源和国家—主题热力矩阵；图表用于描述样本分布，不把采集频率误写成全球事件真实频率。
- 双模式入口：右上角可在“气候情报”和“能源技术”之间切换。能源技术模式使用同一页面结构，但加载 `energy_dashboard.json`、`energy_archive.json` 和 `energy_corpus_analytics.json`，聚焦能源转型、能源技术趋势、数字能源、储能、电网、风光氢等记录。
- 企业情报：仅在“能源技术”模式显示。`energy_companies.json` 提供可搜索的全球能源企业持续扩展名录，并把站内新闻识别为“能源巨头项目、能源初创企业、企业合作”三类；企业地图可切换今日队列和本周。地图优先采用新闻明确地点，缺失时才以企业总部定位并显示定位依据。初始名录参考企业官网、IEA Energy Start-up Data Explorer 与 IEA 清洁能源技术指南；每日模型还会抽取原文明确点名的新企业，只有企业名称可在素材中逐字核验且业务描述非空时才进入动态名录，因此不声称穷尽全球全部企业。
- 气候情报问答：浏览器内执行“问题规划—证据检索—比较/时间线—引用”流程，支持中美等国家比较、政策含义和连续追问；不需要 API 密钥，也不会用档案外知识补写当日事实。
- ClimateText-100000 文本数据库：支持关键词与议题检索；按规范 URL 去重后最多保留 100000 条。
- 今日 PDF 简报：与页面和问答中的“今日简报”使用同一批最新日记录；每条包括中文标题和一段实质性概括，原文链接统一置于文末。中文使用宋体兼容字体，英文与数字使用 Times Roman（Times New Roman 兼容度量），避免拉宽。
- 周报订阅：每周自动汇总最近 7 天每日简报，提炼高频议题、重点地区和推荐阅读；订阅按钮默认使用公开联系邮箱发起人工订阅请求，若配置订阅接口则改为接口提交。
- 曲线监测：全球气候现场上方展示文本档案累计曲线和网站访问累计曲线。访问曲线使用 Cloudflare Web Analytics 页面加载事件，适合观察趋势，不等同于严格独立访客审计。

网页不展示 Agent 流水线、P0 接入状态、新闻元数据、相关度分数、A/B 审核等级、内部质量方法等后台信息；这些字段仍保留在数据库中，供审计和编辑使用。

## 本地预览

需要 Python 3.11 或更高版本，无第三方运行依赖。

```powershell
.\run.ps1
```

打开 <http://127.0.0.1:8765>。

同步动态 P0 RSS/API，并更新新闻快照：

```powershell
.\run.ps1 sync --skip-ndc
```

更新 NDC 十年档案时去掉 `--skip-ndc`。外部入口失败会被记录，不会伪装成成功，也不会阻断其他来源。

## 导出真正的静态网站

网站不依赖常驻 Python 服务。执行：

```powershell
.\run.ps1 export-web --output dist
```

`dist/` 可直接上传到 GitHub Pages、Cloudflare Pages、Netlify 或任意静态文件服务器。静态数据位于 `static/data/dashboard.json`，PDF 简报位于 `static/data/daily_brief.pdf`。

## 发布到 GitHub Pages

公开演示：<https://generationzprogrammer.github.io/climate-agent-news/>

仓库包含完整采集代码与 `.github/workflows/pages.yml`。推送到 `main` 会部署；定时任务每天北京时间 06:30 增量抓取、编译、合并档案并重新发布；每周一北京时间 08:00 生成并发送周报。

1. 在 GitHub 新建仓库，把本目录作为仓库根目录推送到 `main`。
2. 打开仓库 `Settings → Pages`，将 Source 设为 **GitHub Actions**。
3. 在 `Actions` 中手动运行一次“发布气候情报网站”，或等待首次推送触发。
4. 部署完成后，Pages 页面会显示公开网址。

GitHub Models 已于 2026 年 7 月 30 日退役，不能再使用工作流自带的 `GITHUB_TOKEN` 推理。当前默认接入 Gemini 的 OpenAI 兼容接口，建议在 Google AI Studio 创建 API Key，并仅将其保存为仓库 Secret `GEMINI_API_KEY`；默认模型为低成本的 `gemini-3.5-flash-lite`。如需切换到付费 OpenAI 兼容服务，可同时配置下列三个 Secrets。工作流带有中文、来源、时间、HTTPS 链接和 100000 条上限门禁，检查不通过时停止部署并保留上一版网站：

```text
CLIMATE_MODEL_BASE_URL
CLIMATE_MODEL_API_KEY
CLIMATE_MODEL_NAME
```

免费方案只需配置 `GEMINI_API_KEY`；付费或其他服务使用上面的三个通用 Secret。密钥只保存在 GitHub Secrets 中，不要写入代码或提交到仓库。仓库配置为每天 `22:30 UTC`，即北京时间次日 06:30；周报配置为每周一 `00:00 UTC`，即北京时间 08:00。内部仍保存审核状态用于发布门禁，但不在公开网站展示等级。正式决策使用前仍应核对原文。

访问曲线使用 Cloudflare Web Analytics 的真实页面加载事件。前端只注入Cloudflare公开站点令牌；只读API令牌和Account ID仅由每日工作流从GitHub Secrets读取，不进入网页、源码或日志。配置项为 `CLOUDFLARE_WEB_ANALYTICS_SITE_TOKEN`、`CLOUDFLARE_ACCOUNT_ID` 和 `CLOUDFLARE_ANALYTICS_API_TOKEN`。曲线随每日部署刷新，并从启用统计之日起累计。

## 每日更新与 100000 条档案

1. P0 RSS/API 各自限时、有限重试；单源失败不阻塞其他来源。连续失败 3 次进入观察，7 次进入隔离；隔离来源每 7 天自动复测，恢复后自动启用。
2. 新文章执行 URL 规范化、未来时间剔除、主题与相关性评分。
   Google News 发现查询同时覆盖能源企业项目、能源初创企业、投资与合作关键词；新记录仍经过气候或能源技术范围门禁，避免泛商业新闻进入公开数据。
3. 在来源许可与 `robots.txt` 允许的情况下，系统以明确 User-Agent、10 秒超时和 1 MB 响应上限读取公开文章页，只在内存中提取短正文片段，不保存网页全文。管理员配置的模型根据英文标题、来源短摘要和该片段生成忠实中文标题与实质性概括；若模型失败、输出套话或把标题改写成分类标签，该记录继续留在待重试队列，不进入公开首页。
4. 只有中文标题、中文概要、来源、发布时间和 HTTPS 原文全部存在，且权威度与相关性达标的记录才进入公开数据集。
5. `data/news_archive.json` 按 canonical URL 合并，保留内容哈希与首次/最近归档时间，按发布时间排序并裁剪为最多 100000 条。
6. 质量门禁通过后才部署 Pages；失败时网站保持上一成功版本。
7. 合格档案和 `data/source_health.json` 由工作流机器人提交回仓库，使下一次定时运行能够增量合并并判断来源健康状态。
8. 公开首页和 PDF 优先采用最新北京时间自然日，目标展示约 10 条；当日合格记录不足但已有多个可靠来源和明确地点时，系统会用近 7 天高质量记录补足，并在 `daily_backfilled` 中记录补足条数。地图“本周”仍取最近 7 日窗口；位置识别会优先从标题、摘要和国家标签中抽取一个主地点，无法合理归类时才保留为“全球”。
9. 2026-07-29 的来源扩展在代码推送时把中文编译上限临时提高到 40 条，完成一次美国、中国及其他地区的七日补录；后续定时任务恢复每日 20 条，canonical URL 去重保证不会重复灌库。

本次地域修复另含 8 条人工逐页核验的中美基准记录（中美各 4 条），文件为 `data/one_time_regional_intelligence.json`。其中本周样本覆盖中国可再生能源规划、零碳工厂，以及美国野火、光储项目、海上风电和车网互动；导入器校验来源域名、发布日期和 HTTPS 链接，并以 `human_reviewed` 标记。它只用于这次补录，之后的常规 RSS/API 日更与 100000 条去重上限不变。

站内问答不会调用远程模型，因此每次提问不消耗 GitHub Models 额度。它借鉴 `reference_code` 的 Planner、Event/Trend 与 Decision 分工，把问题拆成时间、地区、议题和任务类型，再从当前归档中选择证据；比较和政策含义均标为“当前样本归纳”。

## 每日推送：可落地方案

采用“网站承载详情、企业微信群机器人发三条提醒、邮件发送同一份文本兜底”的组合。它不依赖个人微信的 AI 群发权限，也不会把全文挤进聊天窗口。

先预览将要发送的内容，不产生外部操作：

```powershell
.\run.ps1 deliver --channel preview --public-url https://你的域名/
```

企业微信群机器人：在内部群添加机器人，将 Webhook 保存为 `CLIMATE_WECOM_WEBHOOK_URL`，然后执行：

```powershell
.\run.ps1 deliver --channel wecom --public-url https://你的域名/
```

邮件兜底使用 `CLIMATE_SMTP_*` 和逗号分隔的 `CLIMATE_MAIL_TO`。`--channel auto` 会发送到已配置的渠道；没有配置渠道时安全跳过。GitHub Pages 工作流会在每天 06:30 完成同步、中文质量门禁和部署后，再自动运行这一步。手动运行工作流时，需要勾选“发送企业微信/邮件提醒”。

每周订阅发送使用 `CLIMATE_WEEKLY_SUBSCRIBERS`，以逗号分隔收件人；同时必须配置 `CLIMATE_SMTP_*`。网页“订阅”按钮不会在静态站点中保存邮箱；默认打开邮件请求，管理员确认后把地址加入 GitHub Secrets。每周一北京时间 08:00 的工作流读取最新周报快照并逐一发送，日志只显示收件人数。若接入具备访问控制的外部表单服务，可设置 `CLIMATE_SUBSCRIBE_ENDPOINT` 与 `CLIMATE_UNSUBSCRIBE_ENDPOINT`，订阅地址仍不得写入仓库。

GitHub Secrets 可配置：

```text
CLIMATE_WECOM_WEBHOOK_URL
CLIMATE_MAIL_TO
CLIMATE_SMTP_HOST
CLIMATE_SMTP_PORT
CLIMATE_SMTP_SECURITY       # starttls 或 ssl
  CLIMATE_SMTP_USERNAME
  CLIMATE_SMTP_PASSWORD
  CLIMATE_SMTP_SENDER
  CLIMATE_WEEKLY_SUBSCRIBERS
  CLIMATE_SUBSCRIBE_ENDPOINT
  CLIMATE_UNSUBSCRIBE_ENDPOINT
  CLIMATE_PUBLIC_CONTACT_EMAIL
```

Webhook 和邮箱密码属于密钥，不应写进 `.env.example` 的真实值或提交到仓库。首次应只向 5—15 人的内部试点群发送，连续观察两周的打开率、退订意见、误报和重复事件，再扩大范围。

## 数据质量与边界

- 动态 P0 入口包括 Carbon Brief、Climate Home News、Mongabay 气候专题与拉美专题、Yale Climate Connections、Dialogue Earth、Canary Media、Grist、Guardian Climate Crisis、BBC Science & Environment、UN News Climate、UNEP、British Antarctic Survey、NASA Earth Observatory、GDELT DOC 2.0，以及限定 `news.cn`、`gov.cn`、`mee.gov.cn`、`cma.gov.cn` 和 `dialogue.earth` 的中国气候定向发现入口。
- 内容排序首先看来源权威性、气候相关性和时效性；地域与来源均衡只作为二级排序，不设降低质量的洲际硬配额。
- 来源清单可动态调整；长期失败者自动隔离，新入口必须先核验官方 Feed、内容范围和使用边界。
- 宽泛入口执行二次门禁：NASA Image of the Day Feed 同时要求 `/earth/` 路径和气候主题词，并会从既有档案剔除误收的行星科学条目；中国定向发现同时通过域名白名单和标题气候关键词，GDELT 返回但未通过门禁的项目不会入库。
- NDC 档案只接受可解析日期且文件 URL 属于 `unfccc.int` 的记录，并按缔约方、版本和提交日期去重。
- 新闻只保存标题、来源短摘录、链接和结构化分析；不绕过登录、付费墙、验证码、robots.txt 或技术限制。
- 中文概要、事实、观点、模型推断和编辑建议分开存储；高风险结论必须回到官方或原始来源。
- GDELT 等入口遇到 429 会标记为外部限流，不会用演示数据冒充实时结果。

## 常用命令

```powershell
# 初始化数据库
.\run.ps1 init

# 只重试一个入口
.\run.ps1 sync --skip-ndc --source INT001

# 使用已配置模型编译最近 20 条
.\run.ps1 translate --limit 20

# 生成 Markdown 简报
.\run.ps1 brief --output outputs\daily_brief.md

# 预览三条每日推送，不发送
.\run.ps1 deliver --channel preview --public-url https://你的域名/

# 离线测试
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```

## 目录

```text
config/                 来源配置、关键词、企业名录和人工校编覆盖
data/                   SQLite 数据库与演示事件
src/climate_agent/      采集、档案、翻译、简报和静态导出
static/                 网站源文件、地图和低干扰海报背景
dist/                   可直接部署的静态网站
database/schema.sql     PostgreSQL + pgvector 目标基线
docs/                   产品定位、系统设计和合规说明
tests/                  离线单元与集成测试
```

更完整的定位与边界见 [产品策略](docs/PRODUCT_STRATEGY.md)、[系统设计](docs/SYSTEM_DESIGN.md) 和 [合规清单](docs/COMPLIANCE_CHECKLIST.md)。
面向软著申请和正式交付的操作说明见 [用户说明手册](docs/USER_MANUAL.md)。

## 三年历史文本数据库回填

目标库名为 **Global Climate Change Key Intelligence Text Database**，用于后续国家分类、主题分类、时间热度趋势和来源分布分析。它与“今日简报”分开维护：今日简报面向展示，历史库面向统计。

默认粒度为“一条规范化 canonical URL = 一条新闻记录”。历史库写入两处：

- SQLite：`data/climate.db` 中的 `historical_articles` 表；
- JSONL：`data/climate_text_corpus.jsonl`，配套说明为 `data/climate_text_corpus.manifest.json`。
- 网站分析文件：`static/data/corpus_analytics.json`，由静态导出时从 JSONL 自动聚合生成。

推荐三年完整回填命令：

```powershell
.\run.ps1 backfill-history --start 2023-08-04 --end 2026-08-03 --target-per-day 8 --limit 100000
```

为了避免公共 API 限流，也可以分批运行：

```powershell
.\run.ps1 backfill-history --max-months 1 --sleep-seconds 3
```

历史库会预置以下分析标签：

- 时间：`published_date`、`year`、`month`、`quarter`
- 地理：`country_tags`、`continent_tags`、`places`
- 主题：`topics`
- 来源：`source_domain`、`source_name`
- 数字：`numbers`
- 质量：`quality_flags`

2026-08-03 已跑完 36 个月历史库：`data/climate_text_corpus.jsonl` 当前含 **8683 条** canonical URL 去重后的高质量记录，覆盖 **2023-08-04 至 2026-08-03** 共 1096 天，日均 7.92 条。公开归档上限已提高至 100000 条，但系统不会为凑满上限而写入重复 URL、弱相关新闻或无效后台信息。当前样本中美国 802 条、中国 710 条，主题以能源与排放、气候适应、气候资金和国际谈判为主；未明确国家/地区的全球性文本保留为 `未标注`，避免模型臆造地理标签。

如果只更新标签而不重新请求外网，可运行：

```powershell
.\run.ps1 refresh-history-tags --limit 100000 --target-per-day 8
```

静态网站导出时会同步发布 `data/climate_text_corpus.jsonl` 与 `data/climate_text_corpus.manifest.json`，公开页面中的“每日气候文本档案”也使用 100000 条上限。

## 全球气候分析报告

`reports/global_climate_analysis_report_2026-08-04.html` 基于当前 8683 条三年语料生成，定位为“全球气候变化重点情报与文本数据库三年分析”。报告采用行业研究报告风格：顶部给出核心判断，正文使用趋势线、动量气泡图、季度热力矩阵、结构条形图、地区表格和相关性表格呈现重点信息。报告不再使用 “Executive Summary” 和 “NDC/COP/谈判” 合并标签；相关议题拆分为“国家气候承诺”“联合国气候大会”“国际谈判”，便于政策读者快速理解。

配套数据文件包括：

- `reports/global_climate_analysis_data_2026-08-04.json`
- `reports/quarter_global_keywords_2026-08-04.csv`
- `reports/quarter_continent_keywords_2026-08-04.csv`

静态导出时，报告会复制为 `static/data/global_climate_analysis_report_latest.html`，网站页脚提供入口。

# ClimateText Lab：高质量气候新闻文本数据与智能分子平台

以原“气候谈判情报台”为基础升级的数据产品。平台面向中国气候谈判、外交、政策研究与气候文本分析人员，不与通用模型比“摘要数量”，而是强调每日更新、中文质量门禁、来源追溯、3000 条版本化文本档案，以及把新闻拆解为来源、证据、议题、数字、地域和决策信号的“智能信息分子”。

## 网站现在呈现什么

- 今日高质量情报：中文标题、中文概要、自然议题、来源、发布时间和原文链接。
- ClimateText-3000 文本数据库：检索、议题筛选、质量分级和 JSON 下载；规范 URL 去重后最多保留 3000 条。
- 智能信息分子：选中任一文本，查看来源、证据、议题、数字、地域与政策信号原子。
- 中国居中的全球现场地图：红点仅标记文本明确涉及的国家或地区。

网页不再展示 Agent 流水线、P0 接入状态、新闻元数据、相关度分数、官方证据列表等后台信息；这些数据仍保留在数据库中，供审计和编辑使用。

## 本地预览

需要 Python 3.11 或更高版本，无第三方运行依赖。

```powershell
.\run.ps1
```

打开 <http://127.0.0.1:8765>。

同步 8 个 P0 RSS/API，并更新新闻快照：

```powershell
.\run.ps1 sync --skip-ndc
```

更新 NDC 十年档案时去掉 `--skip-ndc`。外部入口失败会被记录，不会伪装成成功，也不会阻断其他来源。

## 导出真正的静态网站

网站不依赖常驻 Python 服务。执行：

```powershell
.\run.ps1 export-web --output dist
```

`dist/` 可直接上传到 GitHub Pages、Cloudflare Pages、Netlify 或任意静态文件服务器。静态数据位于 `static/data/dashboard.json`，简报位于 `static/data/daily_brief.md`。

## 发布到 GitHub Pages

公开演示：<https://generationzprogrammer.github.io/climate-agent-news/>

仓库包含完整采集代码与 `.github/workflows/pages.yml`。推送到 `main` 会部署；定时任务每天北京时间 07:30 增量抓取、编译、合并档案并重新发布。

1. 在 GitHub 新建仓库，把本目录作为仓库根目录推送到 `main`。
2. 打开仓库 `Settings → Pages`，将 Source 设为 **GitHub Actions**。
3. 在 `Actions` 中手动运行一次“发布气候情报网站”，或等待首次推送触发。
4. 部署完成后，Pages 页面会显示公开网址。

默认使用工作流自带的 `GITHUB_TOKEN` 调用 GitHub Models（`openai/gpt-4.1`）编译新记录，无需另存模型密钥。工作流带有中文、来源、时间、HTTPS 链接和 3000 条上限门禁，检查不通过时停止部署并保留上一版网站。需要替换为其他 OpenAI 兼容模型时，可添加：

```text
CLIMATE_MODEL_BASE_URL
CLIMATE_MODEL_API_KEY
CLIMATE_MODEL_NAME
```

密钥只保存在 GitHub Secrets 中，不要写入代码或提交到仓库。仓库配置为每天 `23:30 UTC`，即北京时间次日 07:30。模型生成内容标记为 B 级“AI 编译待复核”；人工校编内容标记为 A 级。正式决策使用前仍应核对原文。

## 每日更新与 3000 条档案

1. 8 个 P0 RSS/API 各自限时、有限重试；单源失败不阻塞其他来源。
2. 新文章执行 URL 规范化、未来时间剔除、主题与相关性评分。
3. GitHub Models 将最近新记录编译为中文结构化字段；失败记录不会公开。
4. 只有中文标题、中文概要、来源、发布时间和 HTTPS 原文全部存在，且权威度与相关性达标的记录才进入公开数据集。
5. `data/news_archive.json` 按 canonical URL 合并，保留内容哈希与首次/最近归档时间，按发布时间排序并裁剪为最多 3000 条。
6. 质量门禁通过后才部署 Pages；失败时网站保持上一成功版本。
7. 合格档案由工作流机器人提交回仓库，使下一次定时运行继续增量合并。

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

邮件兜底使用 `CLIMATE_SMTP_*` 和逗号分隔的 `CLIMATE_MAIL_TO`。`--channel auto` 会发送到已配置的渠道；没有配置渠道时安全跳过。GitHub Pages 工作流会在每天 07:30 完成同步、中文质量门禁和部署后，再自动运行这一步。手动运行工作流时，需要勾选“发送企业微信/邮件提醒”。

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
```

Webhook 和邮箱密码属于密钥，不应写进 `.env.example` 的真实值或提交到仓库。首次应只向 5—15 人的内部试点群发送，连续观察两周的打开率、退订意见、误报和重复事件，再扩大范围。

## 数据质量与边界

- 8 个 P0 适配器：Carbon Brief、Climate Home News、Canary Media、Guardian Climate Crisis、BBC Science & Environment、UN News Climate、UNEP、GDELT DOC 2.0。
- 当前人工校编快照含 10 条中文重点情报、13 个地图点位和 8 条短语。
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
config/                 来源配置、关键词和人工校编覆盖
data/                   SQLite 数据库与演示事件
src/climate_agent/      采集、档案、翻译、简报和静态导出
static/                 网站源文件、地图和低干扰海报背景
dist/                   可直接部署的静态网站
database/schema.sql     PostgreSQL + pgvector 目标基线
docs/                   产品定位、系统设计和合规说明
tests/                  离线单元与集成测试
```

更完整的定位与边界见 [产品策略](docs/PRODUCT_STRATEGY.md)、[系统设计](docs/SYSTEM_DESIGN.md) 和 [合规清单](docs/COMPLIANCE_CHECKLIST.md)。

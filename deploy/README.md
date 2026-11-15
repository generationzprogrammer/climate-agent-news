# deploy/ · zerocarbonx.cn 服务器部署

把本仓库的网站部署到阿里云轻量服务器（https://zerocarbonx.cn），并在服务器上运行气候新闻数据库。
GitHub Actions 与 GitHub Pages 不使用这里的任何文件；合并到 main 不会改变 github.io 的构建与发布。

## 网站

- `publish.sh` — 本机执行（Git Bash，需要 `~/.ssh/config` 里名为 `grenn` 的主机）：打包 `static/`（不含 `data/`）上传为新版本并切换。
  `--app` 另外上传后端代码（`src/climate_agent`、`config/`，供服务器爬虫使用）；`--setup` 另外安装 nginx、cron、证书续期钩子、数据库用户 / 虚拟环境 / systemd 定时器。
- `server/activate-release.sh` — 在页脚加备案号、把版本里的 `data` 接到数据快照、原子切换当前版本（保留 5 个，可回滚）。
- `server/sync-data.sh` — 每 2 小时镜像原项目发布的网站数据（`dashboard.json` 的生成时间变了才取，校验后一次性切换；文本文件另存 `.br` / `.gz` 预压缩副本供 nginx 直接发送）。数据来源：`--from <目录|zip>` 手动指定的快照；否则若有 `/srv/grenn/conf/github-token`（只读令牌，`root:grenn 640`）就经 GitHub API 取原项目工作流每次上传的 `daily-publish-snapshot` 构件（2026-11-05 起原仓库转为私有、github.io 已下线，构件仍每次生成）；都没有时仍从 github.io 取。令牌建议用 fine-grained token：只选该仓库，权限 Actions: Read-only、Contents: Read-only（新闻数据库 `grenn-newsdb` 也用它经 codeload 取原项目 `data/`）。
  `grenn-pipeline.timer` 启用时（见下节「网站数据流水线」），网站数据由服务器自己生成，cron 的这次同步不再镜像原项目，只在流水线完成后由它以 `--from` 调用。
- `server/grenn_brief.py` — 每次同步后由 sync-data.sh 调用，把 `dashboard.json` 的 `intelligence` 排成「每日气候通讯」PDF（版式按 `1223-0120-中文-讲话收集-ICCSD-杨秀精简.docx`；字体按模板：仿宋_GB2312（`/srv/grenn/app/fonts/FangSong_GB2312.ttf`），目录中的西文与数字为 Times New Roman Bold（`timesbd.ttf`）——均为商业字体，手动上传到该目录，不进仓库、不对外提供；缺 仿宋_GB2312 时脚本报错）替换 `daily_brief.pdf`，上游原件另存 `daily_brief_source.pdf`；排版失败则保留原件。
- `server/nginx-*.conf`、`server/grenn-site.conf` — nginx 配置（HTTPS、www 跳转、`/` → `/cop31/`、`/downloads/` 下载目录、
  `/datasets/` 组内数据集（账号密码保护，`--setup` 首次生成共用账号 `grenn`，密码只存在服务器 `/root/grenn-datasets-credentials.txt`））。
- 本机开着全局代理时，上传请让 ssh 直连：`ssh -b <本机网卡地址> grenn …`（否则流量绕道境外，大文件会传不完）；
  `publish.sh` 用环境变量传：`GRENN_SSH_OPTS="-b <本机网卡地址>" deploy/publish.sh`。

## 网站数据流水线（`pipeline/`，2026-11-07）

2026-11-05 起原仓库转为私有，没有仓库主人的令牌就镜像不到它的网站数据；中文编译原用 Gemini，服务器连不上 Google。
现在由服务器自己跑原项目的每日流程（`.github/workflows/pages.yml` 的定时运行），模型换成智谱 bigmodel.cn 的免费模型 **GLM-4-Flash**（`glm-4-flash-250414`，用户指定只用这一个）：
（同日先试过并行智算云的 GLM-Z1-Flash，编造细节与数字太多，按用户要求整体换掉，其输出未保留。）
`grenn-pipeline.timer`（每天 06:30 / 18:30，同原项目）→ `grenn-pipeline.service`（用户 grenn）运行 `grenn-pipeline.sh`：
爬取（只爬服务器连得上的 14 个 P0 来源，同新闻数据库；没有 Google News、Guardian、BBC）→ 采集来源正文 → GLM-4-Flash 编译中英文标题摘要 → `export-web` → `validate-publish` 质量门禁；
通过后由 root 执行 `sync-data.sh --force --from /srv/grenn/pipeline/repo/site/data` 校验、重排每日气候通讯、预压缩并切换上线。任何一步失败都不发布，网站保留上一版。

- **2026-11-10 起（原仓库重新公开，用户选「每次先取原项目数据」）**：每次运行先查原仓库 main 的最新提交，有新提交就下载其 tarball（codeload，公开、无需令牌）整个替换 `repo`（代码 + data/：原项目自己全部来源的抓取与 Gemini 摘要），再补抓服务器能访问的来源；GLM 只编译还没有模型摘要的条目（`grenn_glm.py` 包装 `cop_coverage.prioritize_translation`），已有 Gemini 摘要的不动；原仓库连不上或下载失败时沿用上一份副本。导出、质量检查与上线格式不变（每日气候通讯照旧按模板重排）。
- `grenn_glm.py` — 每一步都经它启动，原项目代码不改：只允许调用 `open.bigmodel.cn` 上的 `glm-4-flash-250414`（其他模型名一律拒绝，同一密钥本可调用收费模型）；超时放宽到 180 秒（原 60 秒）；
  **提示补充**（只加在新闻编译请求上）：必须给出 `title_en` / `summary_en`（GLM-4-Flash 会漏掉原提示末尾追加的英文要求）、摘要是概括不是逐句翻译、数字与单位换算规则。
  **事实核对**：每条新闻编译与模型拿到的证据比对，以下任一情况整条丢弃——摘要长度超过证据的约 0.7 倍；出现证据里没有的数字（按有效数字比对，允许四舍五入，`31亿` ≈ `3.1 billion`，`1627万` ≈ `16,266,801.60`；≤31 的整数不查）；
  把 billion / million 原样写成「亿 / 万」；4 位以上有效数字的精确数值换算单位后与证据不符（小数点移位，如 `16,266,801.60` → `162668016.00`）。
  丢弃后原项目写入保守的「题名 + 元数据」版本（不会覆盖此前已有的好摘要），下次运行再试。
  依据（2026-11-07 实测）：GLM-Z1-Flash 只有标题时编出 150–180 字细节、有全文时加入原文没有的数字、把「31 亿美元」写成「3.1 亿美元」；GLM-4-Flash 只有标题时也会扩写到 200 字左右、把融资额抄错小数点或数字，
  还会把网页的站点说明一并逐句译出。日志里的 `grenn_glm` 行记录每次丢弃的原因。
- 与原项目的差别：历史语料中英翻译、立场试点两步只接受免费的 Gemini，跳过；不统计访问量（Cloudflare）；不提交 git。`repo/data` 里的档案从此在服务器上独立增长。
- 文件：`/srv/grenn/pipeline/repo`（原仓库一份完整副本：代码 + data/，一次性从其 tarball 解开；以后要换新版本代码时同样解开到 `repo.new`，把 `repo/data` 搬过去再替换）、
  `/srv/grenn/pipeline/state/model_usage.json`（模型请求账本，每天上限 `CLIMATE_MODEL_DAILY_REQUEST_LIMIT`，默认 40，请求间隔 12 秒）、
  `/srv/grenn/secrets/model.env`（`CLIMATE_MODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4`、`CLIMATE_MODEL_API_KEY`（智谱 API Key，`id.secret` 两段）、`CLIMATE_MODEL_NAME=glm-4-flash-250414`；root:grenn 640，手写，不进仓库）。
- `publish.sh --setup` 安装服务与定时器；`repo` 与 `model.env` 都在时才启用定时器。改回镜像原项目（例如拿到了仓库主人的只读令牌）：`systemctl disable --now grenn-pipeline.timer`。
- 常用：`systemctl start grenn-pipeline.service`（立即跑一次）、`journalctl -u grenn-pipeline -n 80`、`journalctl -u grenn-pipeline | grep grenn_glm`（事实核对记录）。

## 周报订阅（`subscriptions/`，2026-11-06）

原项目的订阅服务（Cloudflare Workers / Pages）只放行 github.io，且国内连不上，所以 zerocarbonx.cn 自己登记与发信：
`grenn_subscriptions.py serve`（systemd `grenn-subscriptions`，127.0.0.1:8796，nginx `/api/subscriptions/`；请求与响应同原 Worker）把邮箱与语言存进
`/srv/grenn/subscriptions/subscribers.db`（700，不对外提供）；`/data/subscription.json` 由 nginx 改指 `/srv/grenn/conf/subscription.json`，表单因此发往本站。
`grenn-subscriptions-weekly.timer` 每周一 08:00（10:00、14:00 补发失败的）用原项目的周报正文（`climate_agent.delivery.build_weekly_message`，读 `data/current/weekly_report.json`）
逐个收件人发信，每封附个人一键退订链接。发信设置 `/srv/grenn/subscriptions/smtp.env`（root 600，变量名同原项目 `CLIMATE_SMTP_*`，模板 `subscriptions/smtp.env.example`；
本机房封 25 端口，用 465 SSL）。常用：`grenn-subscriptions status | send-weekly --dry-run | test-mail <地址>`；`--setup` 安装服务、定时器与 nginx 限流（`/etc/nginx/conf.d/grenn-limits.conf`）。

## 研究检索接口（`research/`，2026-11-13）

「功能更新1113」交接包（`COP31_research_handover`：`research_store.py` 参考实现）在本服务器上的落地，供研究工具的「国家立场」「事件追踪」使用。
交接包的做法是把 JSONL 包导入自己的 SQLite；本服务器的语料已经在新闻数据库里（`news.db`：文章 ID、83 小类编码、国家代码、机构标签、日期；
全文在 `governance/current/texts/`，不对外），所以 `grenn_research.py` 改为从它派生索引：

- `grenn-research sync`：由 `news.db` 重建 `/srv/grenn/newsdb/research/index.sqlite`（只有元数据与标签，没有正文；约 24 万篇 22 秒，原子替换；
  数据库没变时什么也不做，重复运行不增量）。`grenn-newsdb-update.service` 每次更新完自动跑一遍（`ExecStartPost`）。
- `grenn-research claims --input reviewed.jsonl`：登记**人工核验过**的立场（字段见 `grenn_research_claim_schema.json`）。每条必须写明
  `reviewer` / `reviewed_at`，引文必须与库内原文 `[start, end)`（Unicode 字符位置）逐字一致，文章必须带有该议题标签；任一不符整条拒收并报出行号。
  同一 `id` 再次提交内容相同则跳过，内容不同则拒收（旧立场不被覆盖）。存在 `research/claims.sqlite`，重建索引不会动它。
  这只是机械校验：发言主体、归因、立场与理由仍由审阅人负责。库内原文里的邮箱已替换为 `[REDACTED_EMAIL]`，含邮箱的文章偏移以库内文本为准。
- `grenn-research serve`（systemd `grenn-research`，只监听 127.0.0.1:8797，只读，服务本身不能写盘、不能连外网）：
  `GET /api/research/topics`（14 大类 / 83 小类及各自的「可检索报道数」「已核验立场数」、国家表、集团表）、
  `/api/research/events?topic=G06.01&country=CN&group=G77&year=2015&limit=30&cursor=…`（报道时间线：标题、日期、发布方、链接、标签；不合并为“事件”）、
  `/api/research/positions?topic=…&country=…`（只有已核验立场；没有就是空列表 + `证据不足：尚无已核验立场`）。每页默认 30 条、最多 100 条，
  游标按（日期，ID）翻页不漏同日记录。**没有全文接口**。nginx `location ^~ /api/research/`（仅 GET，限流 `grenn_research` 180 次 / 分钟）。
- `GET /api/research/search?q=…&topic=…&country=…&year=…&limit=20&cursor=…`（2026-11-14）：文本数据库页面的检索。第二批并入后列表有 43.7 万行，
  不能再整份下载到浏览器，改由这里回答：行格式与 `downloads/search-index.json` 完全相同，关键词（最多 6 个、共 80 字符）须全部出现在
  标题 / 中文标题 / 摘录 / 来源里（对一张窄表 `hay` 做小写子串匹配，顺序扫描约 0.3—0.6 秒；带稀有标签时从标签的日期有序区间出发）。同样不返回正文。
  服务每 2 分钟读一遍 `hay` 保持在页缓存里；`MemoryMax=900M` 是因为 cgroup 把它读过的索引文件缓存也计入上限（250M 时会反复回收，检索慢到数秒）。
- `grenn-research status`：条数、标签数、已登记立场数。测试：`cd deploy/research && python -m unittest test_grenn_research`（18 项）。
- 待复核批次（`GREEN_batch2_02_review`，`research_eligible=false`）**不导入**；新的合格全文批次先进新闻数据库
  （`grenn-newsdb ingest-governance-batch <目录> --label <批次>`：目录里是 `manifest.json` + `data/new_fulltexts_*.jsonl.gz`；按清单核对指纹，
  逐条核对正文指纹与标签版本，只收合格全文，全文接着写成新的分块，原包只读留在 `governance/current/batches/`；重复执行不增量。
  2026-11-14 用它并入了第二批 195,007 篇，合格全文共 435,071 篇），随后 `grenn-research sync`（更新任务会自动跑）。
  本接口不做模型抽取、不做事件聚类，也不会自己产生任何立场。

## 气候新闻数据库（`newsdb/`）

`grenn_newsdb.py`（服务器命令 `grenn-newsdb`）维护 `/srv/grenn/newsdb/news.db`，一条新闻链接一行。

**2026-11-09 起**：历史数据换为 5 个 ZIP 的交付版（合格全文 240,064 篇、待复核 77,196 条不入库，标签版本不变）。导入前在服务器解压（不解 `*.jsonl.gz`，它们与 SQLite 是同一批数据）、按 `sqlite_parts.json` 校验并合并 `data/corpus.sqlite`，然后 `grenn-newsdb ingest-governance <目录>`：校验 `handover_manifest.json`，`raw/` 只留 SQLite 与说明、方法、运行记录，正文写成 `texts/tNNNN.json`（每块 150 篇，新到旧，共 1,601 块），`policy_timeline*.json`（新包没有）从上一版带过来，`daily_since` 取「上一版的值」与「最新日期次日」中较早者（新包最后几天很稀，每日新闻不能被截断）。**包内文件不再提供下载**（其说明禁止放到开放下载站点），`GRENN_PUBLIC_BULK=1` 也只恢复每日新闻的批量文件。检索索引与分析图改为流式写入，日常更新在原 900 MB 内存上限内跑通。以下是更早的说明。

**2026-11-05 起**：历史数据为全球气候治理全文数据库交接包（`governance_handover_20261105_final_交接包`，27,159 篇正文，12 议题 / 5 领域标签），
用 `grenn-newsdb ingest-governance <目录>` 一次性导入：先校验 `checksums.json`，在 `governance/<版本>/raw` 存只读原件，生成下载文件（`release/`）
与网站阅读全文用的分块（`texts/tNNNN.json`，每块 150 篇），然后把此前的全部数据（旧 news.db、全文归档与图片、组内数据集原件、爬虫状态）
打成一个压缩包 `archive/pre-governance-<时间>.tar.gz` 留底并删除旧目录与旧备份，再用交接包重建 news.db（元数据、标签与 ≤600 字符摘录）。
此后下面 2、3 两路每天照常更新，但只收历史数据最后一天之后发布的新闻（meta `daily_since`），并用交接包同一套规则打标签
（`newsdb/grenn_governance/`，交接包 reproducibility 代码原样复制，`publish.sh` 安装到 `/srv/grenn/bin/`）。
每次导出另写 `search-index.json`（网站 `static/cop31/textdb.js` 的检索列表）、`analytics.json`（`static/cop31/analysis.js` 的四张科研分析图，由研究集计算）并硬链接 `texts/`；全文公开（用户 2026-11-05 决定）。
**下载一次最多 100 条（用户 2026-11-05）**：默认不再生成整库 / 分段文件、不再链接 `datasets/`（`manifest.files` 与 `datasets` 为空，下载栏与数据集列表自动隐藏），网站在检索列表里勾选导出（≤100 条，含全文）；环境变量 `GRENN_PUBLIC_BULK=1` 可恢复整库文件。
下面 1、4 及组内数据集是此前的渠道，代码保留，数据已归档删除。

1. 交接的历史数据（2026-10-30 交接包，一次性 `import-handover`）；
2. 本仓库每日两次的采集结果（从 codeload.github.com 下载 main 的 `data/climate.db`、语料与滚动档案合并）；
3. 服务器用本仓库爬虫（`climate_agent.sync`）自己抓取能访问的来源；
4. 全文归档（`fulltext/grenn_fulltext.py package` 打的包，`ingest-fulltext <目录>`）：元数据与 ≤600 字符摘录进 `news`，
   全文与图片私存 `/srv/grenn/newsdb/fulltext/`，不进下载。

每次更新后导出下载文件（最近 7 / 30 天、各月份、全部；CSV / JSONL / SQLite，附 `manifest.json` 与 `README.txt`），
由 `static/cop31/downloads.js` 在 COP31 页「文本数据库」中提供下载；没有 `downloads/manifest.json` 的站点（如 github.io）下载栏自动隐藏。

研究组自己的全文数据（`历史新闻正文/`、`新增历史气候能源全文库/`、`高相关全文研究索引与样本/` 三个文件夹）不并入 `news`：
上传到 `/srv/grenn/import/<目录>/` 后 `grenn-newsdb ingest-group <目录> [--label YYYYMMDD]`——校验后在 `group/raw/<批次>/` 存一份只读原件
（附 SHA256SUMS.json），再分门别类生成数据集到 `group/builds/<时间>/`，经 `group/current` 链接原子切换：
`protected/`（全文：按队列与质量分级 6 个、按主题 6 个、合并 SQLite、复现材料与说明）由 nginx 在 `/datasets/` 凭组内账号提供；
`public/`（目录、原库补齐台账、研究标签，均不含正文）每次导出时硬链接进 `/downloads/datasets/`，列在 `manifest.json` 的 `datasets`
（下载栏只读 `files`，界面不变）。正文全部标为未取得再分发许可，所以不公开。新一批交付换一个 `--label`；同一批重跑只重建数据集。

定时任务：`grenn-newsdb-update.timer`（每天 03:20 / 09:20 / 15:20 / 21:20）、`grenn-newsdb-backup.timer`（每天 04:40 备份并自检，保留 14 天 / 8 周 / 12 个月）。
常用：`grenn-newsdb status | verify [--deep] | update | backup | restore <备份> | export --force`；`verify` 也核对全文库、图片与组内数据集。

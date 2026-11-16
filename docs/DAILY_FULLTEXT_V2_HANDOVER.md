# 每日新闻全文采集与中文翻译：更新交接

版本：2026-11-17。适配 GRENN_代码交接包_20261116.zip 的 climate-agent-news 目录。

## 1. 这次修复什么

已读取 GitHub 运行 43801046871 的 build 日志。2026-11-16 04:09 UTC，站点导出在 `stance_pilot.py` 中因 `Original source version changed; review required` 中断；同次日志还显示摘要模型预算耗尽。不是服务器CPU不足，也不能据此认定整个新闻采集器失效。

修复将版本不匹配或缺失的立场来源隔离到 `source_review_queue`，不再发布依赖该来源的判断；其他立场和新闻照常导出。原证据库不删除、不重写哈希。研究用 `build_pilot()` 默认仍严格报错，只有网站发布入口使用隔离模式。结构错误、重复ID、伪造引文等其他问题不静默放行。

原交接包没有每日全文执行脚本，也没有 trafilatura 依赖；本更新补齐这些文件。单独增加脚本不会自动改变服务器的定时任务，需负责人完成下文的一次接入。

## 2. 数据流与验收口径

现有RSS/API新闻发现 → 取当天全部符合相关性门槛的候选，优先原今日队列 → 原发布者链接解析 → 遵守robots、限速、超时与访问限制获取网页 → 标题匹配及正文完整性检查 → 私有SQLite保存原文 → 百炼逐段翻译 → 对齐与数字检查 → 输出当天文件。

- “当天”采用北京时间自然日，必须有可解析的来源时间，不用往日新闻补数。
- 目标为12条去重的真实原文与完整中文译文。先处理现有今日队列；无法获取的条目保留失败状态，可从其他当天合格候选中形成全文精选12条。不会悄悄替换原站已发布的新闻卡片。
- 全部候选先入队，不截取前12条。模型未配置或额度耗尽时仍采集正文；未译正文及未完成段落保留，下轮续跑。每日240次模型HTTP请求上限含重试；段落合批不超过约2400原文字符，单次输出上限4096 tokens。
- 当天优先，随后处理旧的待译正文；网络补采最多4轮自动尝试，间隔至少1小时。付费墙、禁止访问、明确受限来源不绕过。
- 不将RSS摘要、标题、页面简介当作全文。正文少于800字符或存在完整性警报时保留待复核；短但真实的新闻可能因此未入精选，不能据此推断原文不存在。
- 原文指纹去重、段落缓存；同文跨日不重复下载或翻译。不同URL的同文仍保留来源映射，但只计一个精选正文。
- 逐段ID、中文存在性、长度和数字保留检查属于自动质量筛查，不等于人工确认语义100%准确。不得把“机器检查通过”写成“全文已人工核验”。
- 原文与译文仅在私有研究存储中。公开可访问不等于具有全文再发布授权；上线全文阅读前负责人应逐源确认许可，尤其商业媒体、通讯社及转载。

## 3. 输出合同（给服务器和前端负责人）

输出目录：`data/private_daily_fulltext/`，不得放入static、site、dist或Git。

| 文件 | 用途 |
|---|---|
| daily_fulltext.sqlite | 长期累计库、待处理队列、分段缓存、每日请求与实际token账本 |
| YYYY-MM-DD.json | 当天全部候选，包含成功与失败记录；不是只输出12条 |
| YYYY-MM-DD.selected.json | 当天最多12条正文、译文均完成的去重精选 |
| YYYY-MM-DD.status.json | 实际成功数、缺口、失败状态、预算消耗 |

每条关键字段：`id`、`canonical_url`（原记录关联）、`publisher_url`（实际回源地址）、`title_original`、`published_at_utc/published_at`、`source_text`、`source_sha256`、`fulltext_zh`、`status`、`failure_reason`、`fetched_at`、`translated_at`、`translation_model`、`translation_profile`、`checks`。原有国家、议题、来源标签随记录保留，不改写原climate.db结构。

只有 `status == translated` 才表示该条有已完成译文。`fetch_pending`、`translation_pending`、`blocked` 不得显示为全文已完成。不能把空译文回退为摘要却仍标“全文翻译”。

接网站时按 `canonical_url` 与现有新闻关联。服务器内部接口读取SQLite或每日JSON，访问权限和全文授权沿用服务器规则；本包没有擅自新增公开全文接口。若服务器仍直接展示GitHub静态摘要，负责人须单独接入上述字段。本包不修改原站视觉布局、现有数据库和历史正文。

## 4. 负责人一次操作：推荐复用现有阿里云运行环境

用户没有服务器权限，这一节由服务器负责人操作。将本交接包解压，在原项目目录确认当天新闻发现仍正常执行；不要停止或覆盖原数据库。

1. 在交接包所在目录执行（把 `/path/to/climate-agent-news` 换成真实项目目录）：

```bash
python3 apply_updates.py --target /path/to/climate-agent-news
```

默认只检查，不改文件。若显示冲突，负责人用Claude Code比较本包patch.diff和现有代码后合并，不覆盖他人改动。

2. 检查通过后：

```bash
python3 apply_updates.py --target /path/to/climate-agent-news --apply
cd /path/to/climate-agent-news
.venv/bin/python -m pip install -e . -r requirements-daily-fulltext.txt
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_daily_fulltext_v2.py -v
```

3. 由管理员创建 `/etc/green-daily-fulltext.env`，权限设为600，参照 `config/daily_fulltext.env.example` 填入专用API Key。不要把真实文件放进仓库，不在命令参数或聊天中粘贴Key；可使用已有服务器密钥管理服务。项目Python路径不同时修改 `GREEN_PYTHON`。

4. 在原新闻采集并更新数据库之后，追加：

```bash
bash scripts/run_daily_fulltext.sh
```

可放在原定时脚本的采集阶段之后、网页导出之前；不要只放在整个发布成功后，否则旧模块失败仍会阻止采集。已有发现器继续负责发现新闻，此脚本负责正文与翻译。flock防止本服务器重复运行。

5. 查阅当天 `.status.json`。`target_met: true` 且 `selected: 12` 才达到12条目标；否则保留缺口和错误原因。返回码2表示目标不足，不表示已丢弃当次成功正文。原网站发布可独立继续，但不能掩盖全文缺口。

不要同时启用下面的GitHub定时采集，避免双端重复消费和两个状态库分叉。

## 5. 无服务器权限的备用方案：GitHub Actions独立运行

新增工作流 `Daily fulltext and Chinese translation`，默认关闭。北京08:45及20:45运行，不依赖原Pages任务成功；每次重新从现有RSS/API发现新闻。GitHub运行时间可能延迟。

用户只需新增两个Secrets及一个Variable（代码须先合入main）：

| 类型 | 名称 | 内容 |
|---|---|---|
| Secret | DAILY_FULLTEXT_API_KEY | 百炼按量付费API Key |
| Secret | DAILY_FULLTEXT_STORAGE_KEY | 至少32字符的随机加密口令，单独安全备份 |
| Variable | DAILY_FULLTEXT_ENABLED | true |

若API Key不是北京地域，额外设置Variable `DAILY_FULLTEXT_BASE_URL` 为同一地域控制台给出的OpenAI兼容Base URL。默认北京 `https://dashscope.aliyuncs.com/compatible-mode/v1`。可用工作空间专属域名覆盖；勿填Coding Plan端点。

模型默认 `qwen-plus`，可设置Variable `DAILY_FULLTEXT_MODEL`，必须使用账号中实际可用且支持非思考JSON输出的模型名称；不自动降级到未经验证的模型。

路径：仓库 → Settings → Secrets and variables → Actions。
在Secrets页点New repository secret，分别添加两个Secret；切换Variables页点New repository variable，添加启用开关。Key名称须逐字一致。

旧PowerShell生成加密口令并复制到剪贴板（不显示、不写文件）：

```powershell
$greenBytes = New-Object byte[] 48
$greenRng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$greenRng.GetBytes($greenBytes)
$greenRng.Dispose()
[Convert]::ToBase64String($greenBytes) | Set-Clipboard
```

将剪贴板内容粘贴到 `DAILY_FULLTEXT_STORAGE_KEY`。同时存入自己的密码管理器；GitHub不能再显示Secret原值。以后不要随意更换，否则旧备份无法解密。

然后 Actions → Daily fulltext and Chinese translation → Run workflow → Branch选择main → 默认不勾选清空状态选项 → Run workflow。

查看运行Summary：Ready至少12、shortfall为0，且状态有translated。Artifacts中的 `green-daily-fulltext-state-...` 是加密累计检查点，含原文、译文与队列，不能直接当明文ZIP打开。每次从上一检查点续跑，失败也尽量保存；保留90天。必须由负责人定期下载并长期备份，GitHub Artifacts不是永久数据库。

如需恢复到服务器：下载Artifact，解压得到state.fulltext.enc，安全配置同一 `DAILY_FULLTEXT_STORAGE_KEY` 后运行：

```bash
python scripts/daily_fulltext_state.py unseal --file state.fulltext.enc --root /private/green-fulltext
```

只能恢复到未打开SQLite连接的私有目录。验证无误后由负责人将该目录交给服务器流程续用。若备份过期或密码错误，流程会失败停止，不会悄悄把累计库重置为空。只有首次失败尚无任何数据、且确认可初始化时，才勾选 `allow_empty_state`。

配置 `DAILY_FULLTEXT_API_KEY` 后，旧Pages日更摘要也优先使用百炼；原历史研究语料的特定Gemini功能若不支持该模型，会按已有逻辑跳过，不强行调用。旧Gemini Key不必删除。百炼摘要预算与全文240请求预算分别计数，账单上会合并，不是240次覆盖全站所有功能。

## 6. 百炼操作（用户）

1. 登录 https://bailian.console.aliyun.com/ ，使用之前的阿里云账号，无需购买ECS服务器。
2. 选择与API Key相同的地域，建议使用已有北京地域账号。首次按页面提示开通大模型服务、完成必要实名。
3. 在API Key管理中为GREEN创建专用的“按量付费”API Key；不要购买Coding Plan，不使用编程订阅专属Key。若旧Key仍安全且地域匹配，也可复用。
4. 在模型广场确认 `qwen-plus` 可调用。收费标准以该地域的模型详情为准；本项目是输入和输出token计费，不是按新闻篇数。
5. 在阿里云费用中心完成账户余额准备，并设置余额提醒。若“免费额度用完即停”已开启，额度用尽会停调用；是否关闭由用户决定，关闭后会产生按量费用。不要认为创建Key即代表免费无限量。
6. Key只填GitHub Secret或服务器私有环境文件，不发给聊天机器人、不提交源码。先完成一次少量试运行，再按实际usage账本评估费用；本次未代用户充值或调用付费模型。

官方接口说明：https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope
官方Key说明：https://help.aliyun.com/zh/model-studio/get-api-key/
免费额度与用完即停：https://help.aliyun.com/zh/model-studio/new-free-quota/

## 7. 交接与回滚

代码包只包含本次修改、必要正文提取器、测试和说明，不含API Key、订阅名单、旧数据库、证书或报告。`manifest.json`记录SHA-256和修改前文件指纹，`patch.diff`供审查；安装器会为被替换文件做备份。若目标版本不同，停止覆盖并按diff合并。

原爬取数据库保留；全文模块独立存储。关闭GitHub Variable `DAILY_FULLTEXT_ENABLED` 或移除服务器新增调用即可停止新任务，既有全文库不删除。恢复旧源码不会删除新增私有数据。

已完成本地离线验证不等于云端生产验收。尚需真实百炼Key、负责人部署和至少一次实际运行。日更失败修复的证据来自上文指定运行；不能宣称已证明所有历史失败均为同一原因。

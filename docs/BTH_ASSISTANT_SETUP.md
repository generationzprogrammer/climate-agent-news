# 京津冀研究问答接入说明

问答采用独立的 Cloudflare Worker 和阿里云百炼，不改变订阅 Worker、邮箱列表及每周推送。浏览器只公开 Worker 地址和 Turnstile 站点密钥；模型密钥及验证密钥保存在 GitHub Secrets 和 Worker Secrets。

## 一次性配置

### 1. 百炼

已创建的 API Key 不需要重新创建，也不要粘贴到聊天、文件或 PowerShell 命令中。确认它属于中国内地服务区域，默认使用 `qwen3.5-plus` 和 `https://dashscope.aliyuncs.com/compatible-mode/v1`。如只愿使用免费额度，在百炼模型设置中打开“免费额度用完即停”；免费额度、有效期及开通权限以控制台为准。

GitHub 仓库 → Settings → Secrets and variables → Actions → Secrets → New repository secret：

| 名称 | 值 |
|---|---|
| `BTH_LLM_API_KEY` | 您刚创建的百炼 API Key |

### 2. 防滥用验证（可选，默认关闭）

2026年10月10日起，默认`BTH_VERIFICATION_MODE=off`，访客无需加载Turnstile。后端仍有原子全站日额度、匿名网络地址日额度、10秒频率限制、请求长度限制、固定模型接口和来源校验。关闭人机验证不等于取消费用上限。以下配置仅在管理员主动将Worker和网站导出的`BTH_VERIFICATION_MODE`同时设为`required`时需要；已有验证Secret可保留，不需要删除或重建。

Cloudflare 控制台 → Turnstile → Add widget：

- 名称：`gruen-bth-assistant`。
- Hostname：`generationzprogrammer.github.io`，不填协议或路径。
- Widget mode：Managed。保存后得到 Site Key 与 Secret Key。

GitHub 同一位置的 **Secrets** 新增 `BTH_TURNSTILE_SECRET_KEY`，值为 Secret Key。

GitHub **Variables**（不是 Secrets）新增 `BTH_TURNSTILE_SITE_KEY`，值为 Site Key。Site Key 是可公开标识，Secret Key 不可公开。后台必须验证 action=`bth_chat` 和域名，不以跨域设置代替安全验证。

### 3. 允许部署独立后端

Cloudflare → My Profile → API Tokens → Create Token → 使用 **Edit Cloudflare Workers** 模板。权限至少包括本账户 Workers Scripts 编辑和部署所需的账户读取权限；资源只选择本账户，避免全账户通用令牌。不需要添加邮箱或订阅 KV 权限。

将生成的令牌保存为 GitHub Secret `BTH_CLOUDFLARE_API_TOKEN`。不要使用之前只读的 Analytics Token。已有 `CLOUDFLARE_ACCOUNT_ID` 可继续使用，不必重新填写。

### 4. 部署后端

GitHub → Actions → **部署京津冀研究问答后端** → Run workflow → Branch 选 `main` → Run。

流程会部署 `gruen-bth-assistant`，自动创建 SQLite Durable Object 配额计数器，并将两个 Secret 写入 Worker。不会更新 `climate-news-subscriptions`。

部署输出中会出现 `https://gruen-bth-assistant.<您的子域>.workers.dev`。打开该地址加 `/health`，应返回 `"ready":true`。它只检查配置是否齐全，不代表模型账户余额或权限已经实测。

如果您沿用现有 workers.dev 子域，预计地址为 `https://gruen-bth-assistant.1090697345.workers.dev`；以实际部署输出为准。

### 5. 启用网站

GitHub → Settings → Secrets and variables → Actions → **Variables** 新增：

| 名称 | 值 |
|---|---|
| `BTH_ASSISTANT_ENDPOINT` | 第4步的完整 Worker 地址，不加 `/chat` |

Actions → **每日更新气候文本数据平台** → Run workflow，Branch 选 `main`。提醒和周报勾选项与本功能无关，可不勾。成功后打开网站的京津冀绿色转型专题。

## 验收

1. 输入“比较北京、天津和河北2025年的光伏装机规模，生成图表和简短报告”。
2. 直接发送，检查中文回答和可点击来源；默认不出现人机验证。
3. 下载 Word、PDF 和图表 PNG，检查年份、单位和参考资料。
4. 追问“解释三地差异，不要把装机规模当作发电量”，检查能承接上文。
5. 手机试提问、停止、清空和下载；切换英文时问答界面随之切换，要求英文回答即可。

回答正文以可点击的 `[1]`、`[2]` 标注参考来源，下方来源列表与下载报告使用相同编号；内部证据ID仅用于核验和连续对话，不直接显示。流式生成时暂不显示尚未校验的引用。没有匹配到有效来源的引用标为“来源待核验”，不生成虚假的来源链接。

网页将完整的 `**重点**` 安全显示为加粗；Word和PDF去除Markdown标记。普通回答以问题判断、机制和区域差异为主，不以检索数量或数据库介绍作为正文。

手机和电脑均使用 `transport=stream`，通过XMLHttpRequest的文本进度读取事件，不要求浏览器提供Fetch的ReadableStream。请求采用`text/plain;charset=UTF-8`编码JSON，以避免移动网络的额外OPTIONS预检；后台检查Origin、请求长度与配额，仅在管理员启用验证时检查Turnstile。Worker在模型调用之前立即返回连接状态，随后每8秒发送保活注释，关闭代理内容变换。客户端即使缓冲完整响应，也会在加载结束时解析全部事件；收到完整且经后台核验的结果即可结束等待，不必等代理关闭连接。旧JSON接口保留兼容。

提交直接进入`/chat`，不再强制先完成一次10秒`/health`请求；`/health`保留给管理员诊断。整个操作最长120秒，后端模型限时90秒、请求总限时115秒，并处理停止、后台恢复、迟到响应和客户端断线。每个问题最多一次模型调用，无收费重试或服务器聊天存储。网络不可达时恢复发送按钮。取消Turnstile只能消除验证依赖，不能保证所有运营商均能访问`workers.dev`。若某个网络仍无法访问两个服务域名，需要绑定管理员自有可达的HTTPS自定义域名；不能用关闭密钥校验或把API Key移到浏览器来解决域名可达性。

离线回归包括分片UTF-8、最后一帧缺少空行、代理整包缓冲、连接未关闭但结果已到达、网络失败、超时、停止和取消后禁止调用模型；`scripts/check_bth_assistant_browser.cjs`另以触屏手机配置和真实本地跨域HTTP分段传输验证，不调用百炼，也不使用真实验证Token。接口密钥、订阅服务与历史档案不变。

后端文件推送至main后自动触发“部署京津冀研究问答后端”；原手动入口保留。无需新增Secrets。`/health`仅返回就绪状态、公开模型名、部署版本及传输方式，不返回密钥、问题或用户信息。

PDF采用高分辨率页面图像，避免不同终端中文字体缺失；内容不可直接选择复制。Word为可编辑的真正 `.docx`，使用宋体和 Times New Roman。图表按来源值绘制，不执行模型生成的程序。

## 额度与数据

- 每次请求最多2000字问题、最近6条消息（各1000字符）、约18000字符证据和4096个输出Token；关闭思考模式，无自动付费重试。
- 默认全站每天50次、同一网络地址每天10次，两次至少间隔10秒；UTC零点重置。失败请求也占一次额度，以免重试失控。计数器是原子配额，不因并发超发。
- 这些限制降低费用风险，但不保证费用为零。若百炼允许付费，仍按实际Token收费；需要零费用保障时启用百炼的“免费额度用完即停”。Cloudflare Free计划超额会失败，不自动升级付费计划。
- 服务器不保存聊天及邮箱，不输出问题、模型响应或凭据日志。只保存每日总次数、经每日HMAC匿名化的网络地址计数，过期自动删除。百炼及Cloudflare自身的数据处理按其服务条款执行。
- 统计库包含1214条主选观测值、43个公开来源，覆盖三地2015、2020、2025年；政策资料从现有政策库读取，每次静态发布自动重建证据包。政策题名不当作已读取全文，不确定条款须核对原文。
- 2025年缺失指标不补零，不混合不同单位和指标。未经专家核验的CIB评分不作为观测事实。历史统计数据库不会因每日新闻更新而被覆盖。

## 故障定位

| 显示 | 检查 |
|---|---|
| 实时服务待管理员启用 | 两个GitHub Variables是否已填写，Pages是否重新发布 |
| 管理员尚未启用模型服务 | 独立后端部署是否成功，两个Worker Secret是否存在 |
| 安全验证失败或无法加载 | Turnstile域名、Secret、网络可达性和action是否匹配 |
| 模型免费额度已用完或未开通权限 | 百炼控制台额度、地域和模型权限；不自动切换付费 |
| 今日使用额度已满 | 全站或同网络额度已耗尽；等待UTC零点 |
| 模型输出不完整 | 请求较长；缩短范围，分两次生成报告和图表 |

官方文档：[百炼API Key](https://help.aliyun.com/zh/model-studio/get-api-key)、[结构化输出](https://help.aliyun.com/zh/model-studio/qwen-structured-output)、[免费额度](https://help.aliyun.com/zh/model-studio/new-free-quota/)、[Turnstile验证](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)、[Durable Objects额度](https://developers.cloudflare.com/durable-objects/platform/pricing/)。

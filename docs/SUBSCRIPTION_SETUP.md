# 周报订阅配置说明

网站是 GitHub Pages 静态站点，需要由 Cloudflare Worker 接收订阅请求，并由 Workers KV 保存邮箱。以下名称请原样使用，不要自行缩写。

## 一、统一名称

| 用途 | 固定名称 | 是否保密 |
| --- | --- | --- |
| Cloudflare KV 实例 | `climate-news-subscribers-kv` | 否 |
| Cloudflare Worker | `climate-news-subscriptions` | 否 |
| Worker 的 KV 绑定变量 | `CLIMATE_SUBSCRIBERS_KV` | 否 |
| Worker 允许访问的网站 | `CLIMATE_ALLOWED_ORIGIN` | 否 |
| Worker 与 GitHub 共用的管理令牌 | `CLIMATE_SUBSCRIBER_ADMIN_TOKEN` | 是 |
| Worker 基础网址 | `WORKER_BASE_URL`（仅为本文代称，不创建该变量） | 否 |

## 二、在 Cloudflare 创建 KV

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)。
2. 在左侧搜索框输入 `KV`，打开 **Workers KV**。若没有搜索框，依次进入 **Storage & databases → KV**。
3. 点击 **Create instance**。
4. 名称填写 `climate-news-subscribers-kv`，点击 **Create**。
5. 使用网页控制台绑定 KV 时，不需要复制 Namespace ID。

## 三、创建并部署 Worker

1. 进入 **Workers & Pages**，点击 **Create application**，再选择创建 Worker。
2. Worker 名称填写 `climate-news-subscriptions`，先完成一次默认部署。
3. 打开该 Worker，点击 **Edit code**。
4. 删除示例代码，完整粘贴 `cloudflare/subscription-worker/src/index.js`，点击 **Deploy**。
5. 复制 Worker 网址，例如 `https://climate-news-subscriptions.<你的子域>.workers.dev`。下文把它称为 `WORKER_BASE_URL`；复制时不要带末尾 `/`。

## 四、把 KV 绑定到 Worker

1. 打开 `climate-news-subscriptions` Worker。
2. 进入 **Bindings**，点击 **Add binding**。
3. 类型选择 **KV namespace**。
4. **Variable name** 必须填写 `CLIMATE_SUBSCRIBERS_KV`。
5. KV 实例选择 `climate-news-subscribers-kv`。
6. 点击 **Add binding** 或 **Deploy** 保存。

注意：`climate-news-subscribers-kv` 是数据库名称，`CLIMATE_SUBSCRIBERS_KV` 是代码绑定变量，二者不能互换。

## 五、添加 Worker 变量和 Secret

打开 Worker 的 **Settings → Variables and Secrets → Add**，新增两项：

1. 普通文本变量：Name 填 `CLIMATE_ALLOWED_ORIGIN`，Value 填 `https://generationzprogrammer.github.io`。
2. 加密 Secret：Name 填 `CLIMATE_SUBSCRIBER_ADMIN_TOKEN`，Value 填自行生成的至少 32 字节随机字符串。

旧版 Windows PowerShell 可用以下命令生成令牌：

```powershell
$bytes = New-Object byte[] 32
$rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
$rng.GetBytes($bytes)
[BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
$rng.Dispose()
```

立即把结果保存到密码管理器。不要发到聊天框、写入源码或截图公开。添加两项后点击 **Deploy**。

## 六、验证 Cloudflare

访问 `WORKER_BASE_URL/health`，例如：

```text
https://climate-news-subscriptions.<你的子域>.workers.dev/health
```

看到 `{"ok":true,"service":"climate-news-subscriptions"}` 即表示 Worker 已运行。

## 七、在 GitHub 新增 Repository Secrets

进入仓库 `generationzprogrammer/climate-agent-news`：

**Settings → Secrets and variables → Actions → Secrets → New repository secret**

逐项新增：

| GitHub Secret 名称 | 填写的值 |
| --- | --- |
| `CLIMATE_SUBSCRIBE_ENDPOINT` | `WORKER_BASE_URL/subscribe` |
| `CLIMATE_UNSUBSCRIBE_ENDPOINT` | `WORKER_BASE_URL/unsubscribe` |
| `CLIMATE_WEEKLY_SUBSCRIBERS_ENDPOINT` | `WORKER_BASE_URL/subscribers` |
| `CLIMATE_SUBSCRIBER_ADMIN_TOKEN` | 第五步生成的同一个令牌 |

前三项虽然不是密码，也统一放在 Repository Secrets 中。不要创建名为 `WORKER_BASE_URL` 的 Secret。

邮件发送还需要以下六项 Repository Secrets；具体值由邮箱服务商提供：

| GitHub Secret 名称 | 含义 |
| --- | --- |
| `CLIMATE_SMTP_HOST` | SMTP 服务器地址 |
| `CLIMATE_SMTP_PORT` | SMTP 端口，常见为 `465` 或 `587` |
| `CLIMATE_SMTP_SECURITY` | 按服务商配置填写 `ssl` 或 `starttls` |
| `CLIMATE_SMTP_USERNAME` | SMTP 登录用户名，通常是发件邮箱 |
| `CLIMATE_SMTP_PASSWORD` | SMTP 授权码，不是邮箱登录密码 |
| `CLIMATE_SMTP_SENDER` | 发件邮箱地址 |

## 八、重新部署并测试

1. 打开仓库 **Actions → 每日更新气候文本数据平台 → Run workflow**。
2. 选择 `main` 分支；第一次只运行部署，不勾选发送周报。
3. 工作流成功后，在网站用自己的测试邮箱完成一次“订阅—退订—重新订阅”。
4. 再次运行同一工作流，勾选“部署成功后发送周报邮件”。
5. 确认测试邮箱收到周报，并检查邮件中的退订入口。

如果订阅和退订成功但收不到邮件，先在周一工作流的 `weekly_notify` 输出中核对 `active_subscribers`、`recipients`、`sent` 和 `failed`。`subscriber_endpoint` 必须为 `ok`；名单读取失败时任务会直接失败，不再静默只发送固定邮箱。KV 只负责保存订阅邮箱，邮件仍由六项 `CLIMATE_SMTP_*` 配置发送。`sent`表示SMTP服务器接受，不代表对方收件箱已确认收到；之后仍可能退信或进入垃圾邮件。

## 2026年10月10日链路修复

- 最近一次周一作业（2026年10月5日）的实际输出为有效订阅者2、发送2、失败0。不能据此声称其他订阅者的邮件也发出。
- 网页只接受明确的`ok:true`与`status:subscribed`响应，HTML验证页、空JSON和错误状态不再被当作成功。移动端使用限时XHR，超时覆盖整个响应体。
- 主要端点失败时，通过已部署的京津冀问答Worker固定转发到原订阅Worker，仅允许subscribe与unsubscribe，不代理管理接口，不产生第二份名单。不需要重建原KV或订阅管理令牌。
- 周报从同一`CLIMATE_SUBSCRIBE_ENDPOINT`推导受保护的`/subscribers`，避免表单与发送任务指向不同Worker。原管理Token仍从Secret读取，接口读取失败不得只向固定邮箱发送。
- 可运行Actions中的“检查周报订阅链路”。它核对已发布表单与发送端是否一致，仅输出有效人数和固定名单以外的人数，不发邮件，不显示任何邮箱或密钥。
- 过去没有真正写入KV的邮箱无法恢复，也不能代替他人猜测或添加邮箱。请相关订阅者在新版本重新提交一次，再执行上述检查确认有效人数增加。

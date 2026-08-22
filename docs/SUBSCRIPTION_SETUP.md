# 周报订阅部署说明

网站是 GitHub Pages 静态站点，必须通过独立后端保存邮箱。本项目提供 Cloudflare Worker + Workers KV 实现，免费额度足以支持早期订阅规模。

## 一次性部署

1. 登录 Cloudflare Dashboard，进入 **Workers & Pages → KV**，创建命名空间，例如 `climate-news-subscribers`，复制 Namespace ID。
2. 进入 **Workers & Pages → Create → Worker**，创建 Worker，例如 `climate-news-subscriptions`。
3. 将 `cloudflare/subscription-worker/src/index.js` 的内容粘贴到 Worker 编辑器并部署。
4. 在 Worker 的 **Settings → Bindings** 中新增 KV Namespace binding：变量名必须为 `SUBSCRIBERS`，选择第 1 步创建的命名空间。
5. 在 **Settings → Variables and Secrets** 中新增加密 Secret `ADMIN_TOKEN`。建议使用密码管理器生成至少 32 字节随机值；不要把值发到聊天、提交到 Git 或写入网页。
6. 新增普通变量 `ALLOWED_ORIGIN`，值为 `https://generationzprogrammer.github.io`。
7. 重新部署并访问 `https://你的Worker域名/health`；应返回 `{"ok":true,...}`。

## GitHub Secrets

在仓库 **Settings → Secrets and variables → Actions** 新增：

- `CLIMATE_SUBSCRIBE_ENDPOINT`：`https://你的Worker域名/subscribe`
- `CLIMATE_UNSUBSCRIBE_ENDPOINT`：`https://你的Worker域名/unsubscribe`
- `CLIMATE_WEEKLY_SUBSCRIBERS_ENDPOINT`：`https://你的Worker域名/subscribers`
- `CLIMATE_SUBSCRIBER_ADMIN_TOKEN`：与 Worker 的 `ADMIN_TOKEN` 完全相同
- `CLIMATE_SMTP_HOST`、`CLIMATE_SMTP_PORT`、`CLIMATE_SMTP_SECURITY`、`CLIMATE_SMTP_USERNAME`、`CLIMATE_SMTP_PASSWORD`、`CLIMATE_SMTP_SENDER`：用于真正发送邮件

`CLIMATE_WEEKLY_SUBSCRIBERS` 可继续保留，工作流会把其中的人工收件人与 Worker 订阅者合并去重。

## 验证

1. 在 Actions 手动运行网站工作流，使公开的 `subscription.json` 写入 Worker 的订阅和退订地址。
2. 在线上网页点击“订阅”，提交一个测试邮箱，再用同一邮箱测试退订。
3. 再次订阅测试邮箱，手动运行工作流并勾选“部署成功后发送周报邮件”。
4. 检查测试邮箱收到周报；工作流日志只应出现发送数量，不应出现具体邮箱、SMTP 密码或管理令牌。

如未配置 SMTP，订阅地址仍会安全保存，但每周邮件不会真正发出。

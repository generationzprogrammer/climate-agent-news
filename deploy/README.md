# deploy/ · zerocarbonx.cn 服务器部署

把本仓库的网站部署到阿里云轻量服务器（https://zerocarbonx.cn），并在服务器上运行气候新闻数据库。
GitHub Actions 与 GitHub Pages 不使用这里的任何文件；合并到 main 不会改变 github.io 的构建与发布。

## 网站

- `publish.sh` — 本机执行（Git Bash，需要 `~/.ssh/config` 里名为 `grenn` 的主机）：打包 `static/`（不含 `data/`）上传为新版本并切换。
  `--app` 另外上传后端代码（`src/climate_agent`、`config/`，供服务器爬虫使用）；`--setup` 另外安装 nginx、cron、证书续期钩子、数据库用户 / 虚拟环境 / systemd 定时器。
- `server/activate-release.sh` — 在页脚加备案号、把版本里的 `data` 接到数据快照、原子切换当前版本（保留 5 个，可回滚）。
- `server/sync-data.sh` — 每 2 小时从 github.io 镜像网站数据（`dashboard.json` 的生成时间变了才下载，校验后一次性切换）。
- `server/nginx-*.conf`、`server/grenn-site.conf` — nginx 配置（HTTPS、www 跳转、`/` → `/cop31/`、`/downloads/` 下载目录）。

## 气候新闻数据库（`newsdb/`）

`grenn_newsdb.py`（服务器命令 `grenn-newsdb`）维护 `/srv/grenn/newsdb/news.db`，一条新闻链接一行：

1. 交接的历史数据（2026-10-30 交接包，一次性 `import-handover`）；
2. 本仓库每日两次的采集结果（从 codeload.github.com 下载 main 的 `data/climate.db`、语料与滚动档案合并）；
3. 服务器用本仓库爬虫（`climate_agent.sync`）自己抓取能访问的来源。

每次更新后导出下载文件（最近 7 / 30 天、各月份、全部；CSV / JSONL / SQLite，附 `manifest.json` 与 `README.txt`），
由 `static/cop31/downloads.js` 在 COP31 页「文本数据库」中提供下载；没有 `downloads/manifest.json` 的站点（如 github.io）下载栏自动隐藏。

定时任务：`grenn-newsdb-update.timer`（每天 03:20 / 09:20 / 15:20 / 21:20）、`grenn-newsdb-backup.timer`（每天 04:40 备份并自检，保留 14 天 / 8 周 / 12 个月）。
常用：`grenn-newsdb status | verify | update | backup | restore <备份> | export --force`。

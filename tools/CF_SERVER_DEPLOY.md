# CF补完计划服务器部署

目标地址：<https://haduk1.top/extracker/>。网页、抓取和 AI 摘要均在 `aliyun` 服务器运行，GitHub 保留代码备份。现有 GitHub Actions 工作流只用于必要时回退旧部署。

## 目录与依赖

- `/srv/cf-knowledge`：代码、原始数据、摘要缓存和构建产物，由 `haduki` 用户维护。
- `/etc/cf-knowledge/ai.env`：`OPENAI_API_KEY=...`，权限 `600`，归 root 所有，由 systemd 加载。
- `/srv/cf-knowledge-backups`：每次更新前的数据压缩备份，默认保留最近 28 份。
- `/var/www/cf-knowledge/releases`：仅含四个静态文件的发布版本，保留最近三版。
- `/var/www/cf-knowledge/current`：当前网页版本的符号链接，校验通过后原子切换。
- `/var/www/letsencrypt`：HTTPS 证书 HTTP 验证目录。

服务器使用 Python 3、Node.js、Nginx、Certbot，不需要第三方 Python 包。阿里云安全组入方向需要开放 TCP 80、443；域名 A 记录应解析到服务器公网 IP。

## 首次部署

创建上述目录，将代码、测试、`.github/workflows`、`config.json`、两份构建脚本、原始 JSON 和 `problem-insights-browser` 上传至 `/srv/cf-knowledge`。测试会检查保留的 GitHub 工作流，因此也需要上传 `.github`。不要上传本机配置、缓存和密钥。服务器采用公开配置中的 AI 地址和模型，需要覆盖时使用服务器自己的 `config.local.json`。

`deploy/cf-knowledge-update.service` 和 `.timer` 安装到 `/etc/systemd/system/`。服务以 `haduki` 运行，先备份，再抓取并保留检查点，再生成 AI 摘要，最后重建、测试、检查发布门并切换网页。AI 或校验失败不会切换页面，也不会回滚已抓取数据。更新锁防止重叠执行。

先将 `deploy/nginx-extracker.conf` 安装为 `/etc/nginx/sites-available/extracker`，并在 `sites-enabled` 中创建对应链接。此配置只开放 `/extracker/` 和证书验证目录，`/extracker` 会重定向至带斜杠的地址；源码、原始数据和密钥不在网站目录中。

```bash
sudo nginx -t
sudo systemctl reload nginx
cd /srv/cf-knowledge
python3 tools/cf_server_update.py --publish-only
sudo certbot certonly --webroot -w /var/www/letsencrypt -d haduk1.top \
  --non-interactive --agree-tos --register-unsafely-without-email
```

证书签发成功后，将 `deploy/nginx-extracker-tls.conf` 安装到相同 Nginx 配置位置，检查并重载。将 `deploy/reload-nginx` 以 `755` 权限安装为 `/etc/letsencrypt/renewal-hooks/deploy/reload-nginx`，并确认 `certbot.timer` 已启用。

公网网页和服务器首次更新验证通过后，启用服务器定时任务并关闭旧 GitHub 工作流：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cf-knowledge-update.timer
gh workflow disable cf-auto-update.yml --repo Fyrskd/cf-knowledge
```

定时任务按北京时间每天 `00:17`、`06:17`、`12:17`、`18:17` 运行；错过的任务在恢复运行后补执行。GitHub 工作流的关闭必须在新部署验证后执行，避免迁移期间失去更新来源。

## 日常维护

```bash
# 手动执行完整更新；密钥由服务加载
sudo systemctl start --no-block cf-knowledge-update.service

# 查看任务和日志
systemctl list-timers cf-knowledge-update.timer
systemctl status cf-knowledge-update.service
journalctl -u cf-knowledge-update.service -n 80 --no-pager

# 只重建并发布已有数据，不调用 AI
cd /srv/cf-knowledge
python3 tools/cf_server_update.py --publish-only

# 验证证书续期
sudo certbot renew --dry-run
```

服务器发布路径和备份保留数配置在 `config.json` 的 `deployment.server_*` 字段中。服务器数据会持续变化，更新代码时只上传改动的代码和静态资源，再使用服务器入口重建；不要用旧本机 JSON 覆盖服务器的新数据，也不要直接覆盖 `current` 指向的发布文件。

迁移到新域名后，浏览器的旧 GitHub Pages 账号缓存不会自动转移，需要在新地址重新绑定公开 Codeforces handle。

## 失败与恢复

外网请求未到达服务器且证书校验连接超时时，先检查阿里云安全组；Nginx 本机正常不代表公网已经放行。AI 失败检查受限密钥文件和服务日志。数据备份只包含项目数据，不包含密钥。

需要恢复数据时先停止服务器更新任务，查看备份内容，将选定备份解压到单独恢复目录，确认后再替换需要恢复的数据并运行 `--publish-only`。网页的前三个发布版本保留在 `releases`，可将 `current` 原子切换至选定版本。恢复旧 GitHub 更新前先停用服务器定时任务，避免两套任务同时运行。

参考：[Nginx 路径映射](https://nginx.org/en/docs/http/ngx_http_core_module.html#alias)、[systemd 定时任务](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html)、[Certbot webroot](https://eff-certbot.readthedocs.io/en/stable/using.html#webroot)。

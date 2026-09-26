# Codeforces 自动更新

`tools/cf_auto_update.py` 把现有抓取器和本地 AI 管理器串成一次增量更新：

```text
Codeforces API / 题面镜像 / Tutorial
        -> cf_knowledge_index.py crawl
        -> enrich 非完整题解
        -> problem-insights 重建
        -> 校验并提交抓取检查点
        -> 所有待生成题目调用 AI
        -> AI 质量校验通过后重建 problem-insights
        -> 生成题面缺口与自动更新状态报告
        -> GitHub Actions 提交源数据并更新 Fyrskd.github.io
```

`cftracker.netlify.app/contests` 是浏览界面，不是稳定的数据接口。自动任务使用 Codeforces 官方 `contest.list`、`problemset.problems` 和已有的题面/Tutorial 抓取逻辑作为数据源，网页继续保留 CFTracker 链接作为入口。

## 配置来源

公共默认配置位于仓库根目录的 `config.json`，本机覆盖使用被 `.gitignore` 忽略的 `config.local.json`。配置分组如下：

- `ai`：API 地址、模型、请求超时、输出长度和重试策略；
- `crawler`：抓取间隔、重试次数、请求超时和断点保存频率；
- `auto_update`：回看天数、AI 数量、是否强制 AI、是否重生成和是否跳过题解补抓；
- `batch_upload`：日期范围、Action 轮询/重试、状态文件、工作流、分支和源仓库；
- `deployment`：Pages 仓库和分支。

本机覆盖只需要写要调整的字段，并保持分组结构，例如：

```json
{
  "ai": {
    "model": "gpt-5.6-luna",
    "timeout_seconds": 240
  },
  "batch_upload": {
    "from_date": "2023-01-01"
  }
}
```

配置文件合并优先级为 `config.local.json` > 旧版 `ai-config.local.json` > `config.json`，具体命令行参数再覆盖对应配置。`AI_BASE_URL`、`AI_MODEL` 和 `AI_TIMEOUT_SECONDS` 仍兼容读取，但只是旧脚本的临时覆盖。API key 不放入公开配置：本地使用 `OPENAI_API_KEY`，GitHub Actions 使用 `OPENAI_API_KEY` 和 `PAGES_DEPLOY_TOKEN` Secrets。旧版 `ai-config.local.json` 是平铺 AI 配置，仅用于兼容；不要把它直接改名为 `config.local.json`。

题面抓取遵循宁缺毋滥，并按来源回退：先尝试 `cf-problemset.herokuapp.com`，如果它只返回比赛元数据、提交列表或导航，再尝试 Codeforces 官方题目页的 `problem-statement` 区块。任何来源都必须通过题面校验才会保存；元数据页不会被当作题面。每条记录会写入 `statement_source`、`statement_source_url` 和 `statement_source_attempts`，便于复核来源和失败原因。

旧版本记录如果已经保存了可靠题面但没有来源字段，离线归一化会依据历史 `statement_url` 补回镜像或官方来源；无法从 URL 确定的自定义来源保持未标注，不会强行猜测。

如果所有来源都不可用，题目会保留在 `statement-gaps.json`，跳过 AI 摘要，并在下一轮自动重试。题面缺失现在也属于 `--only-incomplete` 队列，即使该题已有完整 Tutorial，也不会被漏掉。

本地运行：

```bash
cd /Users/welp/Haduki/cf-knowledge
python3 tools/cf_auto_update.py --lookback-days 30 --ai-limit -1 --require-ai
```

自动工作流会把完整流程拆成两个阶段。也可以在本地单独运行：

```bash
python3 tools/cf_auto_update.py --phase crawl --lookback-days 30
python3 tools/cf_auto_update.py --phase ai --ai-limit -1 --require-ai
```

`crawl` 阶段只负责比赛、题面、题解和基础发布数据；`ai` 阶段只处理已有记录的摘要。这样
AI 服务不可用或运行超时时，已抓到的新比赛仍能先提交到源仓库，下一轮可以直接继续生成摘要。

历史比赛可以按比赛 ID 单独处理，适合一场一场补发布；抓取、题解补抓、AI 摘要、源仓库提交和 Pages 发布仍由同一轮任务完成：

```bash
python3 tools/cf_auto_update.py --contest-id 2262 --ai-limit -1 --require-ai
```

GitHub Actions 的手动运行也提供 `contest_id` 输入。填写后只抓取和补全该比赛；留空时继续按 `lookback_days` 的日期窗口运行。

需要按新提示词重生成现有 AI 摘要时，增加 `--refresh-ai`；它只选择已有当前 AI 摘要的题目，不会重跑人工覆写结果：

```bash
python3 tools/cf_auto_update.py --lookback-days 30 --ai-limit -1 --refresh-ai --require-ai
```

手动跳过 Tutorial 补抓时可以使用：

```bash
python3 tools/cf_auto_update.py --lookback-days 30 --ai-limit 0 --skip-editorial-enrich
```

需要自动生成摘要时，在当前 shell 设置 `OPENAI_API_KEY`；默认 API 地址、模型和请求参数见根目录 `config.json` 的 `ai` 分组。`--ai-limit -1` 表示处理全部待生成题目，`0` 只适合本地调试；`--refresh-ai` 表示重生成已有 AI 摘要。正式工作流使用 `--require-ai`：缺少 key 或本批次全部 AI 生成失败时阻止提交；单题 AI 调用失败、输出质量校验失败时只保留该题待重试，其他成功题目照常提交，避免一题失败阻塞整场比赛。题解抓取失败仍会保留已有数据并在下一轮重试。

GitHub Actions 文件是 `.github/workflows/cf-auto-update.yml`，默认每 6 小时运行一次，也支持 `workflow_dispatch` 手动运行。需要在 `Fyrskd/cf-knowledge` 仓库配置两个 Secrets：

- `OPENAI_API_KEY`：必需；用于待生成题目的中文摘要。
- `PAGES_DEPLOY_TOKEN`：必需；Fine-grained token，只给 `Fyrskd/Fyrskd.github.io` 的 Contents Read and write 权限。

首次把包含 `.github/workflows/` 的提交推送到源仓库时，GitHub OAuth token 还必须有 `workflow` scope；本机 `gh` 可以用下面的命令刷新：

```bash
gh auth refresh -h github.com -s workflow
git push origin main
```

如果 GitHub 仍拒绝推送，先检查 `gh auth status` 是否列出 `workflow`；不要用强制推送绕过这个检查。

## 批量逐场提交和失败重试

`tools/cf_batch_upload.py` 会同时读取 Codeforces 官方 `contest.list`、本地比赛、题目和发布
数据，默认从 `batch_upload.from_date`（当前为 `2023-01-01`）之后找出尚未进入本地数据，
或仍有题目没有进入 `problem-insights.json` 的比赛，然后按比赛日期串行触发
`cf-auto-update.yml`。因此新比赛即使还不在 `contests.json` 中，也不会再被误判为 0 场。
每场比赛默认允许失败后重试 3 次；成功后写入本地状态并自动跳过。

批量上传的默认日期、重试次数、轮询间隔、等待超时、状态文件、workflow、ref 和仓库从
`config.json` 的 `batch_upload` 分组读取；命令行参数（例如 `--from-date`、`--repo` 和
`--max-retries`）可以临时覆盖配置。官方比赛列表请求复用 `crawler` 分组的超时和重试设置；
API 查询失败会明确报错，不会静默退回可能不完整的本地清单。

先用 dry-run 检查候选列表：

```bash
python3 tools/cf_batch_upload.py --dry-run
```

确认候选列表后开始提交：

```bash
python3 tools/cf_batch_upload.py --from-date 2023-01-01
```

也可以只处理指定比赛：

```bash
python3 tools/cf_batch_upload.py --contest-id 1778 --contest-id 1788
```

状态文件默认是 `batch-upload-state.local.json`，已加入 `.gitignore`。
脚本中断后重新运行会等待仍在运行的 Action；已成功的比赛会跳过，失败的比赛会重新开始
本轮重试。某场达到重试上限后会继续处理后续比赛，脚本最后以非零状态退出并保留失败日志摘要。

交互终端默认显示彩色比赛进度条、当前 Action 阶段、等待时间和简短失败原因。GitHub
Actions API 只提供 `queued`、`in_progress` 和 `completed` 等状态，不提供真实执行百分比，
因此总进度条按比赛数量计算，单场 Action 使用阶段状态和计时显示。

默认只显示最有用的失败原因和 Run 链接，避免在失败、重试和最终汇总中重复整段日志。需要
排查完整 Actions 错误片段时使用：

```bash
python3 tools/cf_batch_upload.py --from-date 2023-01-01 --verbose
```

输出被重定向、通过管道使用或显式添加 `--plain` 时，脚本会输出稳定的纯文本事件行，方便
保存和搜索。设置通用的 `NO_COLOR` 环境变量会关闭颜色和动态刷新，但仍保留易读文案。

如果手动按 `Ctrl-C` 中断，脚本会打印 `BATCH_UPLOAD_INTERRUPTED`；状态文件会保留当前 run，下一次运行会先恢复等待，不会立即重复触发。
如果项目迁移了源仓库，旧状态文件中的 Actions run ID 可能在新仓库中不存在；脚本会识别
GitHub 的 404，自动丢弃旧断点并为该比赛重新派发一次工作流。旧仓库 URL 对应的 `success`
状态也不会在新仓库中被信任，会自动重置后重新处理。

余额不足、认证失败、限流、网络失败、模型返回非法 JSON 或中文质量校验失败会写入本地 AI 运行日志与复核队列；单题失败不会阻止同批次成功题目提交，失败题目会在下一轮继续处理。低质量或未生成的题目不会被静默发布。

每轮还会生成：

- `statement-gaps.json` / `.md`：没有可靠题面正文的题目清单。
- `auto-update-status.json` / `.md`：窗口、新题数、题解/题面缺口、AI 成功/失败和警告。
- `state.json`：失败记录按 URL 去重，并限制为最近 500 条。

任务会先把抓取结果作为检查点提交到 `Fyrskd/cf-knowledge`，再从该检查点生成 AI 摘要并
覆盖 Pages 仓库根目录的 CF补完计划静态页。当前发布范围只包含题目洞察页，不再维护独立的
lemma 页面或其他旧知识索引产物。

抓取检查点、AI 数据提交和 Pages 发布是三个连续但独立的持久化阶段：AI 超时、Pages token
缺失或发布失败时，已经提交的抓取数据不会回滚；下一轮会从现有检查点继续处理。

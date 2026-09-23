# Codeforces 自动更新

`tools/cf_auto_update.py` 把现有抓取器和本地 AI 管理器串成一次增量更新：

```text
Codeforces API / 题面镜像 / Tutorial
        -> cf_knowledge_index.py crawl
        -> enrich 非完整题解
        -> problem-insights 重建
        -> 所有待生成题目调用 AI
        -> AI 质量校验通过后重建 problem-insights
        -> 生成题面缺口与自动更新状态报告
        -> GitHub Actions 提交源数据并更新 Fyrskd.github.io
```

`cftracker.netlify.app/contests` 是浏览界面，不是稳定的数据接口。自动任务使用 Codeforces 官方 `contest.list`、`problemset.problems` 和已有的题面/Tutorial 抓取逻辑作为数据源，网页继续保留 CFTracker 链接作为入口。

题面抓取遵循宁缺毋滥，并按来源回退：先尝试 `cf-problemset.herokuapp.com`，如果它只返回比赛元数据、提交列表或导航，再尝试 Codeforces 官方题目页的 `problem-statement` 区块。任何来源都必须通过题面校验才会保存；元数据页不会被当作题面。每条记录会写入 `statement_source`、`statement_source_url` 和 `statement_source_attempts`，便于复核来源和失败原因。

旧版本记录如果已经保存了可靠题面但没有来源字段，离线归一化会依据历史 `statement_url` 补回镜像或官方来源；无法从 URL 确定的自定义来源保持未标注，不会强行猜测。

如果所有来源都不可用，题目会保留在 `statement-gaps.json`，跳过 AI 摘要，并在下一轮自动重试。题面缺失现在也属于 `--only-incomplete` 队列，即使该题已有完整 Tutorial，也不会被漏掉。

本地运行：

```bash
cd /Users/welp/Haduki/cf-knowledge
python3 tools/cf_auto_update.py --lookback-days 30 --ai-limit -1 --require-ai
```

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

需要自动生成摘要时，在当前 shell 设置 `OPENAI_API_KEY`；当前默认使用 `https://api.zhehentiaohe.cn/v1` 的 `gpt-5.6-luna`，也可以通过 `AI_BASE_URL`、`AI_MODEL` 和 `AI_TIMEOUT_SECONDS` 覆盖。`--ai-limit -1` 表示处理全部待生成题目，`0` 只适合本地调试；`--refresh-ai` 表示重生成已有 AI 摘要。正式工作流使用 `--require-ai`：缺少 key 或本批次全部 AI 生成失败时阻止提交；单题 AI 调用失败、输出质量校验失败时只保留该题待重试，其他成功题目照常提交，避免一题失败阻塞整场比赛。题解抓取失败仍会保留已有数据并在下一轮重试。

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

`tools/cf_batch_upload.py` 会读取本地比赛、题目和发布数据，默认找出 2023-01-01
之后仍有题目没有进入 `problem-insights.json` 的比赛，然后按比赛日期串行触发
`cf-auto-update.yml`。每场比赛默认允许失败后重试 3 次；成功后写入本地状态并自动跳过。

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
如果项目迁移了源仓库，旧状态文件中的 Actions run ID 可能在新仓库中不存在；脚本会识别
GitHub 的 404，自动丢弃旧断点并为该比赛重新派发一次工作流。旧仓库 URL 对应的 `success`
状态也不会在新仓库中被信任，会自动重置后重新处理。

余额不足、认证失败、限流、网络失败、模型返回非法 JSON 或中文质量校验失败会写入本地 AI 运行日志与复核队列；单题失败不会阻止同批次成功题目提交，失败题目会在下一轮继续处理。低质量或未生成的题目不会被静默发布。

每轮还会生成：

- `statement-gaps.json` / `.md`：没有可靠题面正文的题目清单。
- `auto-update-status.json` / `.md`：窗口、新题数、题解/题面缺口、AI 成功/失败和警告。
- `state.json`：失败记录按 URL 去重，并限制为最近 500 条。

任务会把抓取结果和摘要存回 `Fyrskd/cf-knowledge`，再覆盖 Pages 仓库根目录的 CF补完计划静态页。当前发布范围只包含题目洞察页，不再维护独立的 lemma 页面或其他旧知识索引产物。

源数据提交和 Pages 发布是两个连续步骤：Pages token 缺失或发布失败时，已完成的源数据提交不会被回滚；下一轮修复 token 后可独立重试发布。

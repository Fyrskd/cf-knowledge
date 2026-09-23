# CF补完计划

CF补完计划是一个面向 Codeforces 题目复习的静态知识页面。项目会抓取比赛、题面和 Tutorial，生成中文题意、建模转换、关键观察与题解摘要，并通过 GitHub Pages 发布浏览器页面。

- 在线页面：<https://fyrskd.github.io/>
- 源代码仓库：<https://github.com/Fyrskd/cf-knowledge>
- 页面仓库：<https://github.com/Fyrskd/Fyrskd.github.io>

## 本地运行

项目根目录就是当前仓库，数据文件和构建脚本直接位于根目录。项目只依赖 Python 3.x 和浏览器；Node.js 仅用于 JavaScript 语法检查。

构建发布数据：

```bash
python3 build_problem_insights.py
python3 build_problem_insights_browser_data.py
```

增量更新和批量补传：

```bash
python3 tools/cf_auto_update.py --lookback-days 30 --ai-limit -1 --require-ai
python3 tools/cf_batch_upload.py --from-date 2023-01-01
```

抓取器也可以单独运行，输出目录使用项目根目录：

```bash
python3 tools/cf_knowledge_index.py all \
  --since 2024-09-05 \
  --until 2026-09-22 \
  --out .
```

## 自动更新与发布

`.github/workflows/cf-auto-update.yml` 每 6 小时运行一次，也支持手动触发。工作流会抓取 Codeforces 数据、生成并校验 AI 摘要、提交源数据，然后把 `problem-insights-browser/` 下的四个静态文件发布到 `Fyrskd/Fyrskd.github.io`。

在 `Fyrskd/cf-knowledge` 的仓库设置中配置：

- `OPENAI_API_KEY`：生成中文摘要；
- `PAGES_DEPLOY_TOKEN`：对 `Fyrskd/Fyrskd.github.io` 具有 Contents Read and write 权限的 fine-grained token。

不要提交 `ai-config.local.json`、批量上传状态、运行日志或其他本地缓存；这些文件已经加入 `.gitignore`。

## 验证

提交前运行：

```bash
python3 -m unittest tools/test_cf_knowledge_index.py tools/test_cf_auto_update.py tools/test_cf_batch_upload.py
python3 -m py_compile \
  tools/cf_knowledge_index.py \
  tools/cf_auto_update.py \
  tools/cf_ai_manager.py \
  build_problem_insights.py \
  build_problem_insights_browser_data.py
node --check problem-insights-browser/app.js
node --check problem-insights-browser/data.js
git diff --check
```

更多抓取器和自动更新说明见 `tools/CF_KNOWLEDGE_INDEX.md` 与 `tools/CF_AUTO_UPDATE.md`。

# CF补完计划

一个面向 Codeforces 题目复习的知识页面。

CF补完计划把比赛题目整理成可复习的知识卡片，集中展示中文题意、建模转换、关键观察和简要题解，帮助你按比赛、知识点和难度重新阅读做过的题。

**在线使用：** [fyrskd.github.io](https://fyrskd.github.io/)

## 能做什么

- 按比赛或知识点浏览题目；
- 按竞赛类型、难度和题解状态筛选；
- 查看题意、原始标签、建模转换、关键观察和简要题解；
- 直接跳转到 Codeforces 原题、比赛页和题解来源；
- 随机抽题；
- 在浏览器中绑定多个公开 Codeforces handle，同步通过记录并标记已完成题目。

题目详情默认只展示题意；转换、关键观察和题解分别单独展开，适合先自己思考，再逐层查看提示。

## 数据说明

本仓库同时保存抓取快照、结构化摘要和浏览器发布数据：

```text
Codeforces API / 题面 / Tutorial
                ↓
          records.json
                ↓
      结构化摘要与发布门
                ↓
problem-insights-browser/data.js
```

抓取器会保留来源 URL、来源类型和质量信息。没有可靠题面或题解正文时，项目不会用模型猜测内容来填补缺口。AI 摘要用于辅助复习，不等同于 Codeforces 官方题解。

## 本地预览

项目不需要安装第三方 Python 包。直接启动静态服务器即可预览页面：

```bash
python3 -m http.server 8000 --directory problem-insights-browser
```

然后打开 <http://localhost:8000/>。

## 配置

项目的公开默认配置集中在 [`config.json`](config.json)，包括 AI 服务、抓取器、自动更新、批量补传和 Pages 发布目标。需要在本机调整时，复制一份为 `config.local.json`；该文件已加入 `.gitignore`，不会提交到仓库：

```bash
cp config.json config.local.json
```

本机覆盖文件使用与公开配置相同的分组结构，只填写要覆盖的字段即可。例如：

```json
{
  "ai": {
    "model": "gpt-5.6-luna",
    "timeout_seconds": 240
  },
  "auto_update": {
    "ai_limit": 20
  }
}
```

API 地址、模型、超时、抓取重试、自动更新窗口、批量上传参数和 Pages 仓库等都应该在配置文件中调整。API key 不写入公开配置：本地使用环境变量 `OPENAI_API_KEY`，GitHub Actions 使用同名 Secret；Pages 发布使用 `PAGES_DEPLOY_TOKEN` Secret。

配置文件合并优先级为：`config.local.json` > 旧版 `ai-config.local.json` > `config.json`；具体命令行参数再覆盖对应配置。`AI_BASE_URL`、`AI_MODEL` 和 `AI_TIMEOUT_SECONDS` 仍保留为兼容旧脚本的临时环境变量，但新配置应优先写入 `config.local.json`。旧版 `ai-config.local.json` 仍可读取，格式是平铺的旧 AI 配置；不要把它的内容直接改名为 `config.local.json`，新的本机文件必须使用 `{"ai": {...}}` 这样的嵌套结构。

## 开发与构建

抓取器、摘要构建器和浏览器前端都在同一个仓库中。常用入口如下：

```bash
# 构建发布数据
python3 build_problem_insights.py
python3 build_problem_insights_browser_data.py

# 增量更新比赛、题面、题解和摘要
python3 tools/cf_auto_update.py --lookback-days 30 --ai-limit -1 --require-ai
```

完整的抓取参数、批量补传、AI 配置和 GitHub Actions 说明见：

- [`tools/CF_KNOWLEDGE_INDEX.md`](tools/CF_KNOWLEDGE_INDEX.md)
- [`tools/CF_AUTO_UPDATE.md`](tools/CF_AUTO_UPDATE.md)

提交修改前可以运行：

```bash
python3 -m unittest tools/test_cf_config.py tools/test_cf_knowledge_index.py tools/test_cf_auto_update.py tools/test_cf_batch_upload.py
python3 -m py_compile \
  tools/cf_config.py \
  tools/cf_knowledge_index.py \
  tools/cf_auto_update.py \
  tools/cf_ai_manager.py \
  build_problem_insights.py \
  build_problem_insights_browser_data.py
node --check problem-insights-browser/app.js
node --check problem-insights-browser/data.js
```

## 仓库关系

- 源码、抓取快照和构建流程：[`Fyrskd/cf-knowledge`](https://github.com/Fyrskd/cf-knowledge)
- GitHub Pages 发布镜像：[`Fyrskd/Fyrskd.github.io`](https://github.com/Fyrskd/Fyrskd.github.io)
- 在线页面：[`fyrskd.github.io`](https://fyrskd.github.io/)

本项目目前没有声明开源许可证；如需基于项目再分发，请先联系仓库维护者。

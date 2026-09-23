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
python3 -m unittest tools/test_cf_knowledge_index.py tools/test_cf_auto_update.py tools/test_cf_batch_upload.py
python3 -m py_compile \
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

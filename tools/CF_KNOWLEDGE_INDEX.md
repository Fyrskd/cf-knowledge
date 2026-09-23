# Codeforces 题目/题解知识索引工具

`cf_knowledge_index.py` 是一个保留证据链的抓取器。它不会把模型猜测写成定理：

```text
Codeforces API（比赛、题号、rating、tags）
    + 题面镜像（cf-problemset.herokuapp.com）
    + Tutorial/相关博客链接（从题面镜像页逐题发现，未必是官方完整题解）
    -> records.json
    -> knowledge-index.md
```

## 为什么不是直接照搬现成爬虫

调研过的项目可以复用，但没有一个能直接满足“近两年正式赛、逐题题面、官方题解、可审计知识点索引”这组约束：

| 项目/组件 | 能复用的部分 | 不能直接作为本工具的原因 | 当前处理 |
|---|---|---|---|
| [Codeforces API](https://codeforces.com/apiHelp) | 比赛、题号、rating、tags | 不提供完整题面和逐题 Tutorial 正文 | 作为元数据主源 |
| [Codeforces-Contest-Scraper](https://github.com/ritwiksaha/Codeforces-Contest-Scraper) | 从 contest HTML 找题目和 `Tutorial` 链接 | 2017 年代码；下载 PDF、依赖 `wkhtmltopdf`；不保存逐题 provenance，也不处理动态 Tutorial | 复用了“检查比赛页 Tutorial 锚点”的发现思路，并改为标准库、JSON、哈希和断点续跑 |
| [codeforces-problem-scraper-api](https://github.com/kerolloz/codeforces-problem-scraper-api) | 单题 HTML → statement、样例、限制的字段解析 | Flask 服务化、较旧依赖；需要额外部署；不抓比赛级题解 | 当前镜像解析器直接输出本地记录；需要服务化时可按 MIT 项目接口接入 |
| [lovrop/codeforces-scraper](https://github.com/lovrop/codeforces-scraper) | 样例提取和并发下载思路 | 2014 年项目，只保存样例文件，不保存题面/题解证据 | 不作为核心依赖 |
| [dsa-search-engine](https://github.com/sujeeth-kumar/dsa-search-engine) | TF-IDF/Cosine 的文本检索思路 | 主要是静态 LeetCode/CF 搜索站，不含官方题解切分和证据等级 | 后续相似题阶段可复用其检索思想；本阶段先保证抓取证据 |
| `codeforces-cli` | 比赛页、样例和提交相关 CLI 能力 | 目标是竞赛工作流，不是题解知识库；没有博客正文/知识点 provenance | 可作为本地提交数据源，不与抓取器耦合 |

因此本工具不是重新发明 API 或 HTML 解析，而是把这些成熟的“零件”组合成一个不同的、可核验的流水线：官方 API + 镜像题面 + contest-page/Tutorial 发现 + Codeforces Blog API + 动态 `problemTutorial` POST + 逐题切分 + 来源哈希。外部项目的链接和许可证应在使用其代码时继续遵守；当前实现没有复制它们的代码文件。

## 使用

### 配置

抓取器默认从仓库根目录的 `config.json` 读取 `crawler` 分组：

```json
{
  "crawler": {
    "delay_seconds": 0.7,
    "retries": 3,
    "timeout_seconds": 30,
    "checkpoint_every": 25
  }
}
```

本机可以在被忽略的 `config.local.json` 中只覆盖需要调整的字段。命令行参数仍然优先，例如 `--delay`、`--retries`、`--timeout` 和 `--checkpoint-every` 会覆盖配置文件值。`cf_auto_update.py` 还会把 `auto_update.crawler` 作为自动更新专用覆盖；未设置时回退到顶层 `crawler`。旧的 `ai-config.local.json` 只用于 AI 配置兼容，不影响抓取器参数。

只抓一场比赛做测试：

```bash
python tools/cf_knowledge_index.py all \
  --since 2026-07-12 --until 2026-07-12 \
  --out /tmp/cf-knowledge-smoke
```

抓最近两年（默认日期也可以显式指定）：

```bash
python tools/cf_knowledge_index.py all \
  --since 2024-09-05 --until 2026-09-06 \
  --out .
```

只重新生成索引，不重新联网：

```bash
python tools/cf_knowledge_index.py index --data .
```

如果数据来自旧版本脚本，或只修改了分类/词表而不想重新联网，可以离线修复
记录字段并重建 `coverage.*`、`editorial-gaps.*` 和 `knowledge-index.md`：

```bash
python tools/cf_knowledge_index.py reindex --data .
```

如果已经完成题面抓取，推荐单独运行题解增强阶段；它会按博客去重下载，
再按题号切分，且可从 `state.json` 续跑：

```bash
python tools/cf_knowledge_index.py enrich \
  --data . \
  --checkpoint-every 25
python tools/cf_knowledge_index.py index --data .
```

只补抓缺少 Tutorial URL 的记录时可使用：

```bash
python tools/cf_knowledge_index.py enrich \
  --data . \
  --only-missing-url
```

若某些博客后来补上了动态正文，可用 `--only-incomplete` 只重试非完整记录，避免重新下载已经完整的题解。

## 官方题解映射

Codeforces 正站可能对匿名请求返回 403，因此不能假定每场比赛都能自动抓到 editorial。可以提供一个 JSON 或 TSV：

`cf-editorials.json`：

```json
{
  "2246": "https://codeforces.com/blog/entry/146000",
  "2252": "https://codeforces.com/blog/entry/146100"
}
```

然后运行：

```bash
python tools/cf_knowledge_index.py crawl \
  --since 2024-09-05 --until 2026-09-06 \
  --out . \
  --editorials cf-editorials.json
```

没有题解 URL 的记录会保留 `editorial_discovery=missing`，只使用 CF 的 tags 和题面证据；不会伪称“已分析官方题解”。显式映射或自动发现的 contest-level 博客只在题面镜像没有逐题 Tutorial 链接时作为回退；若无法从博客定位到当前题目，记录仍为 `url_only`。抓取中断后直接重跑即可从 `state.json` 续跑。

## 输出

- `contests.json`：时间窗口内的正式 CF contests。
- `problems.json`：API 返回的题目元数据。
- `records.json`：每道题的题面、逐题题解证据、URL、SHA-256 和候选知识点。
- `state.json`：断点状态与失败 URL。
- `editorials.json`：去重后的博客元数据、覆盖题号和正文哈希。
- `coverage.json` / `coverage.md`：题面、题解 URL、题解文本、完整/部分正文及失败请求覆盖率。
- `knowledge-index.md`：知识点到真实题目的反向索引。

`editorial_status` 表示来源类型，可能为 `official`、`community`、`associated`、`external`、
`url_only`、`missing_url` 或 `fetch_failed`；`editorial_quality` 表示正文完整度，可能为
`complete`、`partial`、`url_only`、`missing_url` 或 `fetch_failed`。含 `Tutorial is loading...` 的官方博客
会保留原文但标为 `partial`（只有占位/元数据时标为 `url_only`），不会冒充完整题解。镜像页面给出的 Codeforces 博客链接
是来源证据，但博客标题含 `discussion`/`video`/`alternative` 时会明确标成社区/视频类，
不会冒充官方完整题解。脚本中的词表只从有题解文本的记录产生“命名知识点候选”；
`tag:*` 条目直接来自 Codeforces tags。候选知识点仍需人工复核并绑定迁移题，不能直接视为掌握。

## 索引边界与证据解释

当前版本的“知识点”不是对题解全文做开放式语义抽取，而是一个可复现的候选索引：

- `tag:*` 来自 Codeforces API 的题目标签；
- 其他命名知识点只在保留下来的题解正文中，用脚本内固定词表做字面匹配，并保存命中词和摘录作为证据。

因此，词表之外的定理、技巧或同义表达可能不会被列出；没有命中不表示题目没有该知识点，命中也不等于已经验证算法正确。使用
`records.json` 中的原文、URL、哈希和 `evidence_excerpt` 做人工复核，不要把这份索引当作“近两年所有知识点”的穷尽清单。

`official` 是基于博客标题/题解链接标签的启发式来源分类，不是 Codeforces 官方认证；标题含
`discussion`、`video`、`alternative` 等词的条目会降为 `community`，无法确定来源的条目保留为
`associated`。`editorial_status` 描述来源类别，`editorial_quality` 描述逐题正文可用程度，两者不能互相替代：

- 被识别为官方的博客，其正文质量仍可能是 `partial` 或 `url_only`（此时 `editorial_status` 通常会规范化为 `official` 或 `url_only`）；
- `complete` 只表示抓到足够长的解释性正文，不保证证明完整或分类绝对正确；
- `fetch_failed` 表示请求失败，不应与“没有题解”混同。

## 测试

在仓库根目录运行：

```bash
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 -m py_compile tools/cf_knowledge_index.py tools/test_cf_knowledge_index.py
git diff --check -- tools/cf_knowledge_index.py tools/test_cf_knowledge_index.py tools/CF_KNOWLEDGE_INDEX.md
```

## 生成数据的提交策略

当前项目目录是可断点续跑的本地缓存，包含题面、题解正文和原始来源哈希；完整两年快照体积较大，通常只提交脚本、测试和覆盖率摘要即可。项目 `.gitignore` 会忽略本地配置和生成报告。提交前应明确选择：

- 默认不提交大体积生成物，并在本地保留缓存；或
- 只提交经过审查的精简/压缩快照，并同时记录抓取日期、窗口和来源哈希。

不要在未确认体积和隐私/许可证边界的情况下强制加入完整 `records.json`、`state.json` 等大文件。

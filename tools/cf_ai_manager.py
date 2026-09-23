#!/usr/bin/env python3
"""Local manager for AI-generated Codeforces problem insights.

Run:
  python3 tools/cf_ai_manager.py

Then open:
  http://127.0.0.1:8787
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import random
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = REPO_ROOT
RECORDS_PATH = KNOWLEDGE_DIR / "records.json"
PROBLEM_INSIGHTS_PATH = KNOWLEDGE_DIR / "problem-insights.json"
AI_CONFIG_PATH = KNOWLEDGE_DIR / "ai-config.local.json"
AI_GENERATED_PATH = KNOWLEDGE_DIR / "ai-generated-insights.json"
AI_RUN_LOG_PATH = KNOWLEDGE_DIR / "ai-run-log.jsonl"
AI_REVIEW_QUEUE_PATH = KNOWLEDGE_DIR / "ai-review-queue.md"
BROWSER_DATA_PATH = KNOWLEDGE_DIR / "problem-insights-browser" / "data.js"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

TOPICS = [
    "数论与同余",
    "组合计数与概率",
    "动态规划与状态设计",
    "图论与网络流",
    "树结构",
    "字符串",
    "博弈",
    "数据结构",
    "构造与贪心",
    "几何",
    "代数、矩阵与多项式",
    "交互",
    "基础实现与模拟",
]

UNUSABLE_EDITORIAL_QUALITIES = {"missing_url", "url_only", "fetch_failed", "missing_editorial"}
QUOTA_ERROR_CODES = {
    "insufficient_quota",
    "credit_balance_exhausted",
    "organization_usage_limit_exceeded",
    "organization_spend_limit_exceeded",
    "project_spend_limit_exceeded",
}
INSIGHT_FIELDS = (
    "statement_brief",
    "transformed_statement",
    "key_observations",
    "solution_brief",
    "primary_topic",
    "secondary_topics",
    "extraction_status",
    "source_provenance",
    "quality_flags",
)

INSIGHT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": list(INSIGHT_FIELDS),
    "properties": {
        "statement_brief": {"type": "string"},
        "transformed_statement": {"type": "string"},
        "key_observations": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 0,
            "maxItems": 4,
        },
        "solution_brief": {"type": "string"},
        "primary_topic": {"type": "string", "enum": TOPICS},
        "secondary_topics": {
            "type": "array",
            "items": {"type": "string", "enum": TOPICS},
            "minItems": 0,
            "maxItems": 3,
        },
        "extraction_status": {
            "type": "string",
            "enum": [
                "ai_generated_with_editorial",
                "ai_generated_partial_editorial",
                "statement_only_missing_editorial",
                "low_confidence",
            ],
        },
        "source_provenance": {"type": "string"},
        "quality_flags": {"type": "array", "items": {"type": "string"}},
    },
}

SYSTEM_PROMPT = """你是一个 Codeforces 题解压缩与训练索引生成器。

你的任务不是重新解题，也不是写完整题解，而是把给定的题面和题解正文压缩成适合竞赛复盘的中文结构化摘要。

必须遵守：
1. 只能使用输入中提供的 statement_text、editorial_text、title、rating、tags、URL。
2. 不允许编造题解、复杂度、结论、证明或不存在的做法。
3. 如果 editorial_text 缺失、URL-only、明显只有占位内容，不能补写算法；只能生成题意摘要，并把 solution_brief 标记为“本地题解正文不足”。
4. 输出字段中的自然语言必须是自然、完整的简体中文。输入题解通常是英文，必须翻译并重写，禁止逐句复制英文或中英逐词拼接；公式、变量名、复杂度、算法缩写（如 DP、MEX、SCC）可以保留。
5. 输出必须是严格 JSON，不要 Markdown，不要解释，不要额外文本。
6. key_observations 不是普通步骤列表，而是解题中真正降低难度的观察、等价变形、不变量、单调性、计数转化、状态设计理由或证明核心。
7. 不要把“排序、二分、DFS、BFS、DP、线段树、枚举、贪心”等普通算法名本身当作关键观察；只有当题解说明了为什么这样建模或为什么正确时，才写成观察。
8. 如果题解有多个版本，只提炼最主要、最可复用、最容易训练的方案；除非两个方案本质不同且都很重要。
9. 对低质量题解要保守，宁可少写，不要猜。
10. 语言要短、准、具体，避免空话，例如“可以用 DP 解决”“注意优化复杂度”“维护信息即可”都不合格。
11. statement_brief 必须让一个没做过题的人看完就知道“题目给了什么、允许做什么、最后要求什么”。至少写一到两句自然语言；如果题目有操作、博弈回合、移动、修改、删除、合并、查询或构造规则，必须明确说明这些规则，不能只写“求最大值/求答案”。不要包含 time limit、memory limit、input/output 模板或故事套话。
12. transformed_statement 必须写出题解采用的核心重述或模型，不能只是重复 statement_brief，也不能只写“把题目看成……”。
13. 每条 key_observations 都要写成“非显然结论 + 它如何降低问题难度/保证正确”的完整句子；如果题解没有足够证据，宁可减少条目并标记 low_confidence。
14. 需要展示公式时，必须使用 `$...$` 包裹行内公式，或使用 `$$...$$` 包裹独立公式；不要输出没有分隔符的裸 LaTeX 命令。变量名和复杂度也尽量放在公式分隔符中。

字段要求：
- statement_brief：一到两句话，建议 45 到 180 字；必须同时说明题目对象、关键操作/规则和目标（求最大/最小/计数/判定/构造）。
- transformed_statement：一到两句话，说明题目被题解如何重新建模、等价转化或抽象，不超过 180 字。
- key_observations：2 到 4 条。每条必须是具体结论，不超过 100 字。
- solution_brief：一段中文简要题解，不超过 140 字。
- primary_topic：只能从给定集合选择一个。
- secondary_topics：从同一集合中选择 0 到 3 个，不能包含 primary_topic。
- extraction_status：按题解证据质量选择。
- source_provenance：简短说明依据来自 statement、editorial、tags 中哪些部分。
- quality_flags：列出风险，例如 missing_editorial、partial_editorial、statement_inferred、ambiguous_solution；没有则返回 []。

合格 key_observations 示例：
- “把每个字符串看作 5 种入口状态下的转移，选或不选只影响当前匹配到目标串的前缀长度。”
- “异或和只关心贡献奇偶，组合数奇偶可由 Lucas 定理转成二进制无进位条件。”
- “新增一条 good pair 只会拆分它所在的最小平衡括号块，其他块的计数因子不变。”
- “固定阈值后可行性单调，因此答案可以二分，判定问题变成是否存在阻断路径的割。”

不合格 key_observations 示例：
- “使用动态规划。”
- “可以二分答案。”
- “用线段树维护。”
- “贪心选择最优位置。”
- “注意复杂度要优化。”
- “根据题意模拟即可。”
"""

HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>CF AI 摘要管理</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f3f5f7;
        --surface: #ffffff;
        --line: #d7dde5;
        --line-strong: #aeb7c3;
        --text: #17202a;
        --muted: #647181;
        --nav: #252a31;
        --green: #287c57;
        --blue: #2457a6;
        --red: #c2382c;
        --yellow: #fff7db;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        line-height: 1.45;
      }
      button, input, select { font: inherit; }
      .topbar {
        display: flex;
        align-items: center;
        gap: 14px;
        min-height: 56px;
        padding: 10px 18px;
        background: var(--nav);
        color: #fff;
      }
      .brand { font-size: 18px; font-weight: 800; }
      .subtle { color: #b9c2ce; font-size: 13px; }
      main { padding: 18px; }
      .grid {
        display: grid;
        grid-template-columns: minmax(320px, 420px) 1fr;
        gap: 14px;
      }
      .panel {
        min-width: 0;
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
      }
      .panel h2 {
        margin: 0;
        padding: 12px 14px;
        border-bottom: 1px solid var(--line);
        font-size: 15px;
      }
      .panel-body { padding: 14px; }
      label {
        display: grid;
        gap: 5px;
        margin-bottom: 10px;
        color: var(--muted);
        font-size: 12px;
        font-weight: 700;
      }
      input, select {
        width: 100%;
        min-height: 36px;
        padding: 7px 9px;
        border: 1px solid var(--line-strong);
        border-radius: 6px;
        background: #fff;
        color: var(--text);
      }
      .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
      .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
      button {
        flex-shrink: 0;
        white-space: nowrap;
        min-height: 36px;
        padding: 7px 12px;
        border: 1px solid var(--line-strong);
        border-radius: 6px;
        background: #fff;
        cursor: pointer;
      }
      button.primary { background: var(--blue); border-color: var(--blue); color: #fff; }
      button.danger { color: var(--red); }
      button:disabled { opacity: 0.55; cursor: not-allowed; }
      .summary {
        display: grid;
        grid-template-columns: repeat(5, minmax(100px, 1fr));
        gap: 10px;
        margin-bottom: 14px;
      }
      .metric {
        padding: 11px 12px;
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
      }
      .metric strong { display: block; font-size: 20px; }
      .metric span { color: var(--muted); font-size: 12px; }
      .toolbar {
        display: flex;
        flex-wrap: wrap;
        align-items: end;
        gap: 10px;
        padding: 12px;
        border-bottom: 1px solid var(--line);
      }
      .toolbar label { margin: 0; }
      .grow { flex: 1 1 240px; }
      .toolbar input[type="number"] { width: 90px; }
      input[type="checkbox"] { width: 16px; min-height: 16px; margin: 2px; }
      .empty { padding: 24px; text-align: center; color: var(--muted); }
      .log, .small, td { overflow-wrap: anywhere; }
      .table-wrap { overflow: auto; max-height: 640px; }
      table { width: 100%; border-collapse: collapse; font-size: 13px; }
      th, td { padding: 8px 9px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
      th { position: sticky; top: 0; background: #f8fafc; z-index: 1; }
      tr:hover td { background: #f8fafc; }
      .key { font-weight: 800; white-space: nowrap; }
      .pill {
        display: inline-block;
        padding: 2px 7px;
        border-radius: 999px;
        background: #edf1f5;
        color: var(--muted);
        font-size: 12px;
      }
      .pill.ok { background: #e4f3ea; color: var(--green); }
      .pill.warn { background: var(--yellow); color: #8a5a00; }
      .pill.err { background: #fde8e6; color: var(--red); }
      .log {
        white-space: pre-wrap;
        min-height: 170px;
        max-height: 360px;
        overflow: auto;
        padding: 10px;
        border: 1px solid var(--line);
        border-radius: 6px;
        background: #111820;
        color: #dce3ea;
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        font-size: 12px;
      }
      .small { color: var(--muted); font-size: 12px; }
      @media (max-width: 980px) {
        .grid { grid-template-columns: 1fr; }
        .summary { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
      }
    </style>
  </head>
  <body>
    <header class="topbar">
      <div class="brand">CF AI 摘要管理</div>
      <div class="subtle">本地运行，key 不进入静态页面</div>
    </header>
    <main>
      <section class="summary" id="summary"></section>
      <section class="grid">
        <aside class="panel">
          <h2>API 配置</h2>
          <div class="panel-body">
            <label>Base URL <input id="baseUrl" placeholder="https://api.openai.com/v1" /></label>
            <label>Model <input id="model" placeholder="gpt-5-mini" /></label>
            <label>API Key 环境变量 <input id="apiKeyEnv" placeholder="OPENAI_API_KEY" /></label>
            <label>API Key（留空表示不覆盖已保存值） <input id="apiKey" type="password" autocomplete="off" /></label>
            <label><span><input id="clearKey" type="checkbox" style="width:auto;min-height:auto" /> 清空已保存的明文 key</span></label>
            <div class="row">
              <label>输出 token <input id="maxOutputTokens" type="number" min="200" max="4000" /></label>
              <label>请求超时秒 <input id="timeoutSeconds" type="number" min="10" max="300" /></label>
            </div>
            <div class="row">
              <label>题面字符上限 <input id="maxStatementChars" type="number" min="1000" max="60000" /></label>
              <label>题解字符上限 <input id="maxEditorialChars" type="number" min="1000" max="90000" /></label>
            </div>
            <div class="actions">
              <button class="primary" id="saveConfig">保存配置</button>
              <button id="testConfig">测试连接</button>
              <button id="rebuild">重建前端数据</button>
            </div>
            <p class="small" id="configHint"></p>
          </div>
          <h2>运行日志</h2>
          <div class="panel-body"><div class="log" id="log"></div></div>
        </aside>
        <section class="panel">
          <h2>题目队列</h2>
          <div class="toolbar">
            <label class="grow">搜索 <input id="query" placeholder="题号 / 标题 / 比赛" /></label>
            <label>筛选
              <select id="filter">
                <option value="pending">待生成</option>
                <option value="generated">AI 已生成</option>
                <option value="manual">已有摘要</option>
                <option value="failed">失败/待复核</option>
                <option value="all">全部</option>
              </select>
            </label>
            <label>数量 <input id="limit" type="number" min="1" max="1000" value="200" /></label>
            <button id="refresh">刷新</button>
            <button class="primary" id="generateSelected">生成选中</button>
            <button id="generateTop">生成前 N 个待处理</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th><input id="selectAll" type="checkbox" /></th>
                  <th>题目</th>
                  <th>比赛</th>
                  <th>Rating</th>
                  <th>题解质量</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody id="rows"></tbody>
            </table>
          </div>
        </section>
      </section>
    </main>
    <script>
      const $ = (id) => document.getElementById(id);
      let problems = [];
      const errorHints = {
        auth_error: "认证或权限失败：检查 Key、API 地址与模型访问权限。批次已停止。",
        quota_or_billing_error: "余额或额度不足：检查账户余额、项目预算和额度。批次已停止，恢复后可重试失败题。",
        rate_limited: "请求限流：已达到本次重试上限，请稍后重试或减少每批题数。",
        network_error: "网络连接失败：检查网络、代理及 API 地址。生成请求会有限重试。",
        server_error: "API 服务暂时异常：已达到本次重试上限，请稍后重试。",
        input_too_long: "输入超出模型限制：请减小题面和题解字符上限。",
        bad_response: "返回格式不符合要求：检查接口是否支持 Responses API 和结构化输出；若输出截断，请提高输出 token 上限。",
        bad_request: "API 参数不被支持：检查模型名称及接口兼容性。批次已停止。",
      };

      function log(line) {
        const box = $("log");
        const text = typeof line === "string" ? line : JSON.stringify(line, null, 2);
        box.textContent += `${new Date().toLocaleTimeString()} ${text}\n`;
        box.scrollTop = box.scrollHeight;
      }

      async function request(path, options = {}) {
        const response = await fetch(path, {
          ...options,
          headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.ok === false) {
          const message = data.error || response.statusText || "请求失败";
          throw new Error([errorHints[data.category], message].filter(Boolean).join("\n"));
        }
        return data;
      }

      function statusPill(item) {
        if (item.has_current_ai) return '<span class="pill ok">AI 已生成</span>';
        if (item.manual_override) return '<span class="pill ok">已有摘要</span>';
        if (item.last_error) return '<span class="pill err">失败</span>';
        return '<span class="pill warn">待生成</span>';
      }

      function renderRows() {
        $("selectAll").checked = false;
        if (!problems.length) {
          $("rows").innerHTML = '<tr><td colspan="6" class="empty">当前筛选下没有题目</td></tr>';
          return;
        }
        $("rows").innerHTML = problems.map((item) => `
          <tr>
            <td><input class="row-check" type="checkbox" value="${item.problem_key}" /></td>
            <td><div class="key">${item.problem_key}</div><div>${escapeHtml(item.title || "")}</div></td>
            <td>${escapeHtml(item.contest_date || "")}<br /><span class="small">${escapeHtml(String(item.contest_id || ""))}</span></td>
            <td>${escapeHtml(item.rating ?? "未评级")}</td>
            <td>${escapeHtml(item.editorial_quality || "")}</td>
            <td>${statusPill(item)}${item.last_error ? `<div class="small">${escapeHtml(item.last_error)}</div>` : ""}</td>
          </tr>
        `).join("");
      }

      function escapeHtml(value) {
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      }

      async function loadStatus() {
        const data = await request("/api/status");
        const s = data.status;
        $("summary").innerHTML = [
          ["题目总数", s.total_records],
          ["待生成", s.pending_count],
          ["AI 已生成", s.ai_generated_count],
          ["已有摘要", s.manual_count],
          ["失败", s.failed_count],
        ].map(([k, v]) => `<div class="metric"><strong>${v}</strong><span>${k}</span></div>`).join("");
        const c = data.config;
        $("baseUrl").value = c.base_url || "";
        $("model").value = c.model || "";
        $("apiKeyEnv").value = c.api_key_env || "";
        $("maxOutputTokens").value = c.max_output_tokens || 900;
        $("timeoutSeconds").value = c.timeout_seconds || 90;
        $("maxStatementChars").value = c.max_statement_chars || 12000;
        $("maxEditorialChars").value = c.max_editorial_chars || 24000;
        $("configHint").textContent = c.api_key_saved
          ? `已保存 key：${c.api_key_preview}；也会优先读取环境变量 ${c.api_key_env || "未设置"}。`
          : `未保存明文 key；将读取环境变量 ${c.api_key_env || "未设置"}。`;
      }

      async function loadProblems() {
        const params = new URLSearchParams({
          filter: $("filter").value,
          limit: $("limit").value || "200",
          q: $("query").value || "",
        });
        const data = await request(`/api/problems?${params.toString()}`);
        problems = data.problems;
        renderRows();
      }

      async function saveConfig() {
        const payload = {
          base_url: $("baseUrl").value,
          model: $("model").value,
          api_key_env: $("apiKeyEnv").value,
          api_key: $("apiKey").value,
          clear_api_key: $("clearKey").checked,
          max_output_tokens: Number($("maxOutputTokens").value || 900),
          timeout_seconds: Number($("timeoutSeconds").value || 90),
          max_statement_chars: Number($("maxStatementChars").value || 12000),
          max_editorial_chars: Number($("maxEditorialChars").value || 24000),
        };
        await request("/api/config", { method: "POST", body: JSON.stringify(payload) });
        $("apiKey").value = "";
        $("clearKey").checked = false;
        await loadStatus();
        log("配置已保存");
      }

      function selectedKeys() {
        return Array.from(document.querySelectorAll(".row-check:checked")).map((el) => el.value);
      }

      async function generate(keys) {
        if (!keys.length) {
          log("没有选中题目");
          return;
        }
        toggleBusy(true);
        try {
          log(`开始生成 ${keys.length} 题`);
          const data = await request("/api/generate", {
            method: "POST",
            body: JSON.stringify({ problem_keys: keys, rebuild: true }),
          });
          log(data);
          for (const result of data.results || []) {
            if (!result.ok && errorHints[result.category]) {
              log(`${result.problem_key}：${errorHints[result.category]}`);
            }
          }
          await loadStatus();
          await loadProblems();
        } finally {
          toggleBusy(false);
        }
      }

      function toggleBusy(disabled) {
        for (const id of ["saveConfig", "testConfig", "rebuild", "refresh", "generateSelected", "generateTop"]) {
          $(id).disabled = disabled;
        }
      }

      $("saveConfig").addEventListener("click", () => saveConfig().catch((err) => log(err.message)));
      $("testConfig").addEventListener("click", async () => {
        try {
          await saveConfig();
          const data = await request("/api/test-config", { method: "POST", body: "{}" });
          log(data);
        } catch (err) {
          log(err.message);
        }
      });
      $("rebuild").addEventListener("click", async () => {
        try {
          toggleBusy(true);
          const data = await request("/api/rebuild", { method: "POST", body: "{}" });
          log(data);
          await loadStatus();
        } catch (err) {
          log(err.message);
        } finally {
          toggleBusy(false);
        }
      });
      $("refresh").addEventListener("click", () => loadProblems().catch((err) => log(err.message)));
      $("filter").addEventListener("change", () => loadProblems().catch((err) => log(err.message)));
      $("query").addEventListener("input", () => loadProblems().catch((err) => log(err.message)));
      $("selectAll").addEventListener("change", () => {
        for (const item of document.querySelectorAll(".row-check")) item.checked = $("selectAll").checked;
      });
      $("generateSelected").addEventListener("click", () => generate(selectedKeys()).catch((err) => log(err.message)));
      $("generateTop").addEventListener("click", () => {
        const keys = problems.filter((item) => !item.has_current_ai && !item.manual_override).map((item) => item.problem_key);
        generate(keys).catch((err) => log(err.message));
      });

      loadStatus().then(loadProblems).catch((err) => log(err.message));
    </script>
  </body>
</html>
"""


class ManagerError(Exception):
    """User-facing manager error."""


class ApiCallError(ManagerError):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: str | None = None,
        error_type: str | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
        category: str = "api_error",
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.error_type = error_type
        self.request_id = request_id
        self.retry_after = retry_after
        self.category = category

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "status": self.status,
            "code": self.code,
            "type": self.error_type,
            "request_id": self.request_id,
            "message": str(self),
        }


@dataclass(frozen=True)
class AiConfig:
    base_url: str = "https://api.zhehentiaohe.cn/v1"
    api_key_env: str = "OPENAI_API_KEY"
    api_key: str = ""
    model: str = "gpt-6-luna"
    max_output_tokens: int = 1400
    timeout_seconds: int = 90
    max_attempts: int = 5
    initial_delay_seconds: float = 2.0
    max_delay_seconds: float = 60.0
    max_statement_chars: int = 12000
    max_editorial_chars: int = 24000
    organization: str = ""
    project: str = ""

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AiConfig":
        retry = data.get("retry") if isinstance(data.get("retry"), dict) else {}
        return cls(
            base_url=str(data.get("base_url") or cls.base_url),
            api_key_env=str(data.get("api_key_env") or cls.api_key_env),
            api_key=str(data.get("api_key") or ""),
            model=str(data.get("model") or cls.model),
            max_output_tokens=bounded_int(data.get("max_output_tokens"), 200, 4000, cls.max_output_tokens),
            timeout_seconds=bounded_int(data.get("timeout_seconds"), 10, 300, cls.timeout_seconds),
            max_attempts=bounded_int(retry.get("max_attempts"), 1, 10, cls.max_attempts),
            initial_delay_seconds=bounded_float(retry.get("initial_delay_seconds"), 0.5, 30.0, cls.initial_delay_seconds),
            max_delay_seconds=bounded_float(retry.get("max_delay_seconds"), 1.0, 300.0, cls.max_delay_seconds),
            max_statement_chars=bounded_int(data.get("max_statement_chars"), 1000, 60000, cls.max_statement_chars),
            max_editorial_chars=bounded_int(data.get("max_editorial_chars"), 1000, 90000, cls.max_editorial_chars),
            organization=str(data.get("organization") or ""),
            project=str(data.get("project") or ""),
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "api_key_saved": bool(self.api_key),
            "api_key_preview": mask_key(self.api_key),
            "model": self.model,
            "max_output_tokens": self.max_output_tokens,
            "timeout_seconds": self.timeout_seconds,
            "max_statement_chars": self.max_statement_chars,
            "max_editorial_chars": self.max_editorial_chars,
        }

    def resolved_api_key(self) -> str:
        env_value = os.environ.get(self.api_key_env, "") if self.api_key_env else ""
        return env_value or self.api_key

    def to_file_dict(self) -> dict[str, Any]:
        return {
            "provider": "openai",
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "api_key": self.api_key,
            "model": self.model,
            "max_output_tokens": self.max_output_tokens,
            "timeout_seconds": self.timeout_seconds,
            "retry": {
                "max_attempts": self.max_attempts,
                "initial_delay_seconds": self.initial_delay_seconds,
                "max_delay_seconds": self.max_delay_seconds,
            },
            "max_statement_chars": self.max_statement_chars,
            "max_editorial_chars": self.max_editorial_chars,
            "organization": self.organization,
            "project": self.project,
        }


def bounded_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


def bounded_float(value: Any, low: float, high: float, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mask_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f"{path.suffix}.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def load_config() -> AiConfig:
    raw = read_json(AI_CONFIG_PATH, {})
    if not isinstance(raw, dict):
        raise ManagerError(f"配置文件格式错误：{AI_CONFIG_PATH}")
    # CI can provide non-secret endpoint/model overrides without committing a local config file.
    if os.environ.get("AI_BASE_URL"):
        raw["base_url"] = os.environ["AI_BASE_URL"]
    if os.environ.get("AI_MODEL"):
        raw["model"] = os.environ["AI_MODEL"]
    if os.environ.get("AI_TIMEOUT_SECONDS"):
        raw["timeout_seconds"] = os.environ["AI_TIMEOUT_SECONDS"]
    return AiConfig.from_mapping(raw)


def save_config_from_payload(payload: dict[str, Any]) -> AiConfig:
    current = load_config()
    merged = current.to_file_dict()
    for key in (
        "base_url",
        "api_key_env",
        "model",
        "max_output_tokens",
        "timeout_seconds",
        "max_statement_chars",
        "max_editorial_chars",
    ):
        if key in payload:
            merged[key] = payload[key]
    if payload.get("clear_api_key"):
        merged["api_key"] = ""
    elif str(payload.get("api_key") or "").strip():
        merged["api_key"] = str(payload["api_key"]).strip()
    config = AiConfig.from_mapping(merged)
    write_json(AI_CONFIG_PATH, config.to_file_dict())
    try:
        AI_CONFIG_PATH.chmod(0o600)
    except OSError:
        pass
    return config


def problem_key(record: dict[str, Any]) -> str:
    contest_id = record.get("contest_id")
    index = record.get("index")
    return f"{contest_id}{index}"


def stable_json_hash(data: dict[str, Any]) -> str:
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ai_input_hash(record: dict[str, Any]) -> str:
    return stable_json_hash(
        {
            "problem_key": problem_key(record),
            "title": record.get("title"),
            "rating": record.get("rating"),
            "problem_url": record.get("problem_url"),
            "editorial_url": record.get("editorial_url"),
            "tags": record.get("tags", []),
            "editorial_quality": record.get("editorial_quality"),
            "statement_text": record.get("statement_text") or "",
            "editorial_text": record.get("editorial_text") or "",
        }
    )


def load_records() -> list[dict[str, Any]]:
    raw = read_json(RECORDS_PATH, [])
    if not isinstance(raw, list):
        raise ManagerError(f"{RECORDS_PATH} 必须是 JSON 数组")
    return [record for record in raw if isinstance(record, dict)]


def load_problem_insights() -> dict[str, dict[str, Any]]:
    raw = read_json(PROBLEM_INSIGHTS_PATH, {})
    records = raw.get("records", []) if isinstance(raw, dict) else []
    return {
        str(item.get("problem_key")): item
        for item in records
        if isinstance(item, dict) and item.get("problem_key")
    }


def empty_ai_store() -> dict[str, Any]:
    return {"version": 1, "updated_at": utc_now(), "records": {}}


def load_ai_store() -> dict[str, Any]:
    raw = read_json(AI_GENERATED_PATH, empty_ai_store())
    if not isinstance(raw, dict):
        return empty_ai_store()
    if not isinstance(raw.get("records"), dict):
        raw["records"] = {}
    return raw


def save_ai_store(store: dict[str, Any]) -> None:
    store["version"] = 1
    store["updated_at"] = utc_now()
    write_json(AI_GENERATED_PATH, store)


def append_run_log(entry: dict[str, Any]) -> None:
    entry = {"time": utc_now(), **entry}
    AI_RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AI_RUN_LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")


def recent_errors_by_problem(limit: int = 500) -> dict[str, str]:
    if not AI_RUN_LOG_PATH.exists():
        return {}
    lines = AI_RUN_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    errors: dict[str, str] = {}
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = str(item.get("problem_key") or "")
        if item.get("ok") is True and key in errors:
            errors.pop(key, None)
        elif item.get("ok") is False and key:
            errors[key] = str(item.get("error") or item.get("message") or "生成失败")
    return errors


def editorial_is_usable(record: dict[str, Any]) -> bool:
    quality = str(record.get("editorial_quality") or "")
    editorial = strip_text(str(record.get("editorial_text") or ""))
    if quality in UNUSABLE_EDITORIAL_QUALITIES:
        return False
    if len(editorial) < 200:
        return False
    lowered = editorial.lower()
    if "tutorial is loading" in lowered and len(editorial) < 800:
        return False
    return True


def statement_is_usable(record: dict[str, Any]) -> bool:
    """Validate the statement body instead of trusting stale legacy metadata."""
    text = str(record.get("statement_text") or "")
    if not text.strip():
        return False
    try:
        import cf_knowledge_index as indexer

        return indexer.is_problem_statement(text)
    except (ImportError, AttributeError):
        return record.get("statement_quality") != "missing"


ENGLISH_GLUE_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "can", "by",
    "consider", "construct", "count", "determine", "each", "every", "find",
    "first", "for", "from", "given", "if", "in", "is", "it", "let", "minimum",
    "maximum", "must", "number", "of", "only", "or", "otherwise", "possible",
    "query", "remove", "same", "select", "such", "than", "that", "the", "then",
    "there", "this", "to", "use", "using", "when", "where", "which", "with", "we",
    "will", "within", "without",
}
SUMMARY_NOISE_MARKERS = (
    "time limit",
    "memory limit",
    "input standard",
    "output standard",
    "input/output",
    "tutorial is loading",
)
SUMMARY_GENERIC_MARKERS = (
    "按这个转换实现即可",
    "根据题意模拟即可",
    "注意复杂度",
    "维护信息即可",
)


def summary_quality_issues(insight: dict[str, Any], record: dict[str, Any]) -> list[str]:
    texts = [
        str(insight.get("statement_brief") or ""),
        str(insight.get("transformed_statement") or ""),
        str(insight.get("solution_brief") or ""),
        *(str(item) for item in insight.get("key_observations", []) if isinstance(item, str)),
    ]
    joined = " ".join(texts).lower()
    issues: list[str] = []
    for marker in SUMMARY_NOISE_MARKERS:
        if marker in joined:
            issues.append(f"summary_noise:{marker}")
    if any(marker in joined for marker in SUMMARY_GENERIC_MARKERS):
        issues.append("generic_summary")
    # Do not count formulas or inline code as prose.  They may legitimately
    # contain tokens such as ``if`` and ``for`` even when the explanation is
    # otherwise fully Chinese.
    natural_language = re.sub(r"\$\$.*?\$\$|\$.*?\$|`[^`]*`", " ", joined, flags=re.S)
    english_words = re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", natural_language)
    glue_count = sum(1 for word in english_words if word in ENGLISH_GLUE_WORDS)
    if glue_count >= 3 and len(english_words) >= 4:
        issues.append("mixed_language")
    compact_statement = re.sub(r"\W+", "", texts[0].lower())
    compact_transform = re.sub(r"\W+", "", texts[1].lower())
    if compact_statement and compact_statement == compact_transform:
        issues.append("transformation_repeats_statement")
    if editorial_is_usable(record):
        if len(texts[0]) < 35:
            issues.append("statement_too_short")
        observations = insight.get("key_observations")
        if not isinstance(observations, list) or len(observations) < 2:
            issues.append("too_few_observations")
    return sorted(set(issues))


def strip_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def trim_text(text: str, limit: int) -> str:
    text = strip_text(text)
    if len(text) <= limit:
        return text
    head = text[: int(limit * 0.65)].rstrip()
    tail = text[-int(limit * 0.35) :].lstrip()
    return f"{head}\n\n[中间内容因长度限制省略]\n\n{tail}"


def make_user_prompt(
    record: dict[str, Any],
    config: AiConfig,
    *,
    shrink: bool = False,
    repair: bool = False,
    quality_issues: Sequence[str] = (),
) -> str:
    statement_limit = config.max_statement_chars // 2 if shrink else config.max_statement_chars
    editorial_limit = config.max_editorial_chars // 2 if shrink else config.max_editorial_chars
    statement_text = trim_text(str(record.get("statement_text") or ""), statement_limit)
    editorial_text = trim_text(str(record.get("editorial_text") or ""), editorial_limit)
    if not editorial_is_usable(record):
        editorial_text = ""
    repair_note = ""
    if repair:
        repair_note = (
            "上一版输出存在语言或内容质量问题。请重新完整翻译并重写，不能复用上一版措辞。"
            "所有自然语言字段必须使用中文，字段中不得出现英文句子、英文连接词或英文解释；"
            "算法名和数学符号可以保留，但不能用英文替代中文表述。"
        )
        if quality_issues:
            repair_note += (
                "本地质量校验指出上一版存在以下问题："
                + ", ".join(str(issue) for issue in quality_issues)
                + "。请逐项修正后再输出。"
            )
    return f"""请根据下面的 Codeforces 本地记录，生成中文结构化题目洞察。

注意：
- 只能基于给定内容。
- 不要使用外部知识。
- 不要因为 tags 里出现某个算法名就补写题解。
- 如果题解正文不足，必须按 statement-only 规则保守输出。
- 题解正文可能是英文；所有自然语言字段必须翻译成流畅中文，禁止保留英文句法或逐词中英混杂。
- 删除故事背景、时间/内存限制、输入输出模板，但不能删除决定题目含义的操作规则；必须保留“每步/每次允许怎么做、操作顺序或限制、最后求什么”。
- statement_brief 必须让没做过这道题的人知道题目大概在操作什么以及求什么；如果是数组操作、博弈、移动、删除、合并、查询或构造题，至少用自然语言说明一次关键操作。
- transformed_statement 必须和 statement_brief 有实质差异，写出核心建模或等价转化。
- 公式请用 `$...$` 或 `$$...$$` 包裹，禁止输出裸的 `\\frac`、`\\sum` 等 LaTeX 命令。
- 输出严格 JSON。
{repair_note}

[problem metadata]
problem_key: {problem_key(record)}
title: {record.get("title") or ""}
rating: {record.get("rating")}
problem_url: {record.get("problem_url") or ""}
editorial_url: {record.get("editorial_url") or ""}
codeforces_tags: {json.dumps(record.get("tags", []), ensure_ascii=False)}
editorial_quality: {record.get("editorial_quality") or ""}

[statement_text]
{statement_text}

[editorial_text]
{editorial_text}
"""


def response_endpoint(config: AiConfig) -> str:
    base = config.base_url.rstrip("/")
    if base.endswith("/responses"):
        return base
    if base.endswith("/v1"):
        return f"{base}/responses"
    return f"{base}/v1/responses"


def models_endpoint(config: AiConfig) -> str:
    base = config.base_url.rstrip("/")
    if base.endswith("/models"):
        return base
    if base.endswith("/v1"):
        return f"{base}/models"
    return f"{base}/v1/models"


def auth_headers(config: AiConfig) -> dict[str, str]:
    key = config.resolved_api_key()
    if not key:
        raise ApiCallError(
            "未配置 API key：请填写明文 key，或设置配置中的环境变量。",
            status=None,
            category="auth_error",
        )
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    if config.organization:
        headers["OpenAI-Organization"] = config.organization
    if config.project:
        headers["OpenAI-Project"] = config.project
    return headers


def parse_api_error(exc: HTTPError) -> ApiCallError:
    body = exc.read().decode("utf-8", errors="replace")
    request_id = exc.headers.get("x-request-id")
    retry_after = parse_retry_after(exc.headers.get("Retry-After"))
    code: str | None = None
    error_type: str | None = None
    message = body or exc.reason
    try:
        data = json.loads(body)
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            code = str(err.get("code") or "") or None
            error_type = str(err.get("type") or "") or None
            message = str(err.get("message") or message)
    except json.JSONDecodeError:
        pass
    category = classify_error(exc.code, code, error_type, message)
    return ApiCallError(
        message,
        status=exc.code,
        code=code,
        error_type=error_type,
        request_id=request_id,
        retry_after=retry_after,
        category=category,
    )


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def classify_error(status: int | None, code: str | None, error_type: str | None, message: str) -> str:
    lowered = message.lower()
    if status == 402:
        return "quota_or_billing_error"
    if status in {401, 403}:
        return "auth_error"
    if (code and code in QUOTA_ERROR_CODES) or (error_type and error_type in QUOTA_ERROR_CODES):
        return "quota_or_billing_error"
    if any(marker in lowered for marker in ("credit", "billing", "spend limit", "quota", "余额不足", "额度不足")):
        return "quota_or_billing_error"
    if status == 429:
        return "rate_limited"
    if status and status >= 500:
        return "server_error"
    if status == 400 and ("context" in lowered or "too long" in lowered or "maximum" in lowered):
        return "input_too_long"
    if status == 400:
        return "bad_request"
    return "api_error"


def should_retry(error: ApiCallError) -> bool:
    return error.category in {"rate_limited", "server_error", "network_error"}


def sleep_for_retry(config: AiConfig, attempt: int, retry_after: float | None) -> None:
    if retry_after is not None:
        delay = retry_after
    else:
        delay = min(config.max_delay_seconds, config.initial_delay_seconds * (2 ** attempt))
        delay += random.uniform(0.0, min(1.0, delay * 0.25))
    time.sleep(min(delay, config.max_delay_seconds))


def post_json_with_retries(config: AiConfig, url: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    last_error: ApiCallError | None = None
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(config.max_attempts):
        try:
            request = Request(url, data=encoded, headers=auth_headers(config), method="POST")
            with urlopen(request, timeout=config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                request_id = response.headers.get("x-request-id")
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ApiCallError("API 返回的不是 JSON object", category="bad_response")
            return data, request_id
        except HTTPError as exc:
            last_error = parse_api_error(exc)
        except (URLError, TimeoutError, OSError) as exc:
            last_error = ApiCallError(str(exc), category="network_error")
        except json.JSONDecodeError as exc:
            raise ApiCallError(f"API 返回 JSON 解析失败：{exc}", category="bad_response") from exc
        if not last_error or not should_retry(last_error) or attempt == config.max_attempts - 1:
            break
        sleep_for_retry(config, attempt, last_error.retry_after)
    if last_error:
        raise last_error
    raise ApiCallError("API 请求失败", category="api_error")


def get_json(config: AiConfig, url: str) -> tuple[dict[str, Any], str | None]:
    try:
        request = Request(url, headers=auth_headers(config), method="GET")
        with urlopen(request, timeout=config.timeout_seconds) as response:
            body = response.read().decode("utf-8")
            request_id = response.headers.get("x-request-id")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ApiCallError("API 返回的不是 JSON object", category="bad_response")
        return data, request_id
    except HTTPError as exc:
        raise parse_api_error(exc) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ApiCallError(str(exc), category="network_error") from exc
    except json.JSONDecodeError as exc:
        raise ApiCallError(f"API 返回 JSON 解析失败：{exc}", category="bad_response") from exc


def build_responses_payload(config: AiConfig, user_prompt: str) -> dict[str, Any]:
    return {
        "model": config.model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "cf_problem_insight",
                "description": "Codeforces problem insight summary for a local training browser.",
                "schema": INSIGHT_SCHEMA,
                "strict": True,
            }
        },
        "max_output_tokens": config.max_output_tokens,
        "store": False,
    }


def extract_response_text(data: dict[str, Any]) -> str:
    if data.get("status") in {"failed", "cancelled", "incomplete"}:
        raise ApiCallError(f"Responses API 状态异常：{data.get('status')} {data.get('error') or data.get('incomplete_details')}", category="bad_response")
    if isinstance(data.get("output_text"), str):
        return str(data["output_text"])
    parts: list[str] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    parts.append(str(part["text"]))
                elif isinstance(part.get("text"), str):
                    parts.append(str(part["text"]))
                elif part.get("type") == "refusal":
                    raise ApiCallError(f"模型拒绝生成：{part.get('refusal')}", category="model_refusal")
    text = "\n".join(parts).strip()
    if not text:
        raise ApiCallError("Responses API 没有返回 output_text", category="bad_response")
    return text


def normalize_insight(raw: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    insight: dict[str, Any] = {}
    for field in INSIGHT_FIELDS:
        if field not in raw:
            raise ManagerError(f"模型输出缺少字段：{field}")
        insight[field] = raw[field]
    for field in ("statement_brief", "transformed_statement", "solution_brief", "primary_topic", "extraction_status", "source_provenance"):
        if not isinstance(insight[field], str):
            raise ManagerError(f"字段 {field} 必须是字符串")
        insight[field] = strip_text(str(insight[field]))
    if insight["primary_topic"] not in TOPICS:
        insight["primary_topic"] = "构造与贪心"
    observations = insight["key_observations"]
    if not isinstance(observations, list):
        raise ManagerError("key_observations 必须是数组")
    insight["key_observations"] = [strip_text(str(item)) for item in observations if strip_text(str(item))][:4]
    secondary = insight["secondary_topics"]
    if not isinstance(secondary, list):
        secondary = []
    insight["secondary_topics"] = [
        str(topic)
        for topic in secondary
        if str(topic) in TOPICS and str(topic) != insight["primary_topic"]
    ][:3]
    flags = insight["quality_flags"]
    if not isinstance(flags, list):
        flags = []
    insight["quality_flags"] = sorted({str(flag) for flag in flags if str(flag).strip()})

    if not editorial_is_usable(record):
        insight["key_observations"] = []
        insight["transformed_statement"] = "本地题解正文不足，暂不推断完整算法。"
        insight["solution_brief"] = "本地题解正文不足；本条只保留中文题意、原题链接和题解链接，不根据宽标签补写题解。"
        insight["extraction_status"] = "statement_only_missing_editorial"
        insight["quality_flags"] = sorted(set(insight["quality_flags"]) | {"missing_editorial"})

    if not insight["statement_brief"]:
        raise ManagerError("statement_brief 为空")
    if not insight["solution_brief"]:
        raise ManagerError("solution_brief 为空")
    field_limits = {
        "statement_brief": 240,
        "transformed_statement": 260,
        "solution_brief": 360,
    }
    for field, limit in field_limits.items():
        if len(insight[field]) > limit:
            raise ManagerError(f"字段 {field} 超过 {limit} 字符")
    if any(len(item) > 140 for item in insight["key_observations"]):
        raise ManagerError("key_observations 单条超过 140 字符")
    return insight


def generate_one(record: dict[str, Any], config: AiConfig) -> tuple[dict[str, Any], str | None]:
    shrink = False
    repair = False
    quality_issues: list[str] = []
    for attempt in range(3):
        prompt = make_user_prompt(
            record,
            config,
            shrink=shrink,
            repair=repair,
            quality_issues=quality_issues,
        )
        try:
            data, request_id = post_json_with_retries(
                config,
                response_endpoint(config),
                build_responses_payload(config, prompt),
            )
            text = extract_response_text(data)
            try:
                raw = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ApiCallError(f"模型输出不是合法 JSON：{exc}", category="bad_response") from exc
            if not isinstance(raw, dict):
                raise ApiCallError("模型输出不是 JSON object", category="bad_response")
            try:
                insight = normalize_insight(raw, record)
            except ManagerError as exc:
                raise ApiCallError(f"模型输出字段不符合要求：{exc}", category="bad_response") from exc
            issues = summary_quality_issues(insight, record)
            if issues:
                if attempt < 2:
                    quality_issues = issues
                    shrink = True
                    repair = True
                    continue
                raise ApiCallError(
                    "模型输出质量不合格：" + ", ".join(issues),
                    category="bad_response",
                )
            return insight, request_id
        except ApiCallError as exc:
            if exc.category == "input_too_long" and not shrink:
                shrink = True
                continue
            if exc.category == "bad_response" and attempt < 2:
                shrink = True
                repair = True
                continue
            raise
    raise ApiCallError("模型输出质量校验失败", category="bad_response")


def problem_status_rows() -> list[dict[str, Any]]:
    records = load_records()
    insights = load_problem_insights()
    store = load_ai_store()
    generated_records = store.get("records", {})
    errors = recent_errors_by_problem()
    rows: list[dict[str, Any]] = []
    for record in records:
        key = problem_key(record)
        existing = insights.get(key, {})
        entry = generated_records.get(key) if isinstance(generated_records, dict) else None
        current_hash = ai_input_hash(record)
        has_current_ai = (
            isinstance(entry, dict)
            and entry.get("status") == "ok"
            and entry.get("input_hash") == current_hash
            and isinstance(entry.get("insight"), dict)
        )
        manual_override = bool(existing.get("manual_override") or existing.get("extraction_status") == "manual_override")
        rows.append(
            {
                "problem_key": key,
                "title": record.get("title"),
                "rating": record.get("rating"),
                "contest_id": record.get("contest_id"),
                "contest_date": record.get("contest_date"),
                "editorial_quality": record.get("editorial_quality"),
                "statement_quality": record.get("statement_quality") or (
                    "available" if str(record.get("statement_text") or "").strip() else "missing"
                ),
                "statement_available": bool(str(record.get("statement_text") or "").strip())
                and record.get("statement_quality") != "missing",
                "has_current_ai": has_current_ai,
                "manual_override": manual_override,
                "in_problem_insights": bool(existing),
                "last_error": errors.get(key),
            }
        )
    return sorted(rows, key=lambda row: (str(row.get("contest_date") or ""), int(row.get("contest_id") or 0), str(row.get("problem_key") or "")), reverse=True)


def status_summary() -> dict[str, Any]:
    rows = problem_status_rows()
    return {
        "total_records": len(rows),
        "pending_count": sum(1 for row in rows if not row["manual_override"] and not row["has_current_ai"]),
        "ai_generated_count": sum(1 for row in rows if row["has_current_ai"]),
        "manual_count": sum(1 for row in rows if row["manual_override"]),
        "failed_count": sum(1 for row in rows if row["last_error"]),
        "problem_insights_exists": PROBLEM_INSIGHTS_PATH.exists(),
        "browser_data_exists": BROWSER_DATA_PATH.exists(),
    }


def filter_rows(rows: list[dict[str, Any]], filter_name: str, query: str, limit: int) -> list[dict[str, Any]]:
    lowered = query.strip().lower()
    selected: list[dict[str, Any]] = []
    for row in rows:
        if filter_name == "pending" and (row["manual_override"] or row["has_current_ai"]):
            continue
        if filter_name == "generated" and not row["has_current_ai"]:
            continue
        if filter_name == "manual" and not row["manual_override"]:
            continue
        if filter_name == "failed" and not row["last_error"]:
            continue
        haystack = " ".join(
            str(row.get(field) or "")
            for field in ("problem_key", "title", "contest_id", "contest_date", "rating")
        ).lower()
        if lowered and lowered not in haystack:
            continue
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def generate_many(problem_keys: list[str], rebuild: bool) -> dict[str, Any]:
    config = load_config()
    if not config.resolved_api_key():
        raise ManagerError("未配置 API key：请在页面填写 key，或设置 OPENAI_API_KEY。")
    records_by_key = {problem_key(record): record for record in load_records()}
    store = load_ai_store()
    generated_records = store.setdefault("records", {})
    if not isinstance(generated_records, dict):
        generated_records = {}
        store["records"] = generated_records

    results: list[dict[str, Any]] = []
    success = 0
    failed = 0
    for key in problem_keys:
        record = records_by_key.get(key)
        if not record:
            failed += 1
            results.append({"problem_key": key, "ok": False, "error": "records.json 中找不到该题"})
            continue
        if not statement_is_usable(record):
            failed += 1
            error = "缺少可靠题面，暂不生成 AI 摘要"
            append_run_log({"problem_key": key, "ok": False, "error": error, "category": "missing_statement"})
            results.append({"problem_key": key, "ok": False, "error": error, "category": "missing_statement"})
            continue
        started = time.monotonic()
        current_hash = ai_input_hash(record)
        try:
            insight, request_id = generate_one(record, config)
            generated_records[key] = {
                "problem_key": key,
                "title": record.get("title"),
                "rating": record.get("rating"),
                "problem_url": record.get("problem_url"),
                "editorial_url": record.get("editorial_url"),
                "editorial_quality": record.get("editorial_quality"),
                "model": config.model,
                "input_hash": current_hash,
                "generated_at": utc_now(),
                "status": "ok",
                "insight": insight,
            }
            save_ai_store(store)
            elapsed = round(time.monotonic() - started, 2)
            append_run_log({"problem_key": key, "ok": True, "request_id": request_id, "elapsed_seconds": elapsed})
            print(f"AI_ITEM problem_key={key} status=success elapsed={elapsed}s", flush=True)
            success += 1
            results.append({"problem_key": key, "ok": True, "request_id": request_id, "elapsed_seconds": elapsed})
        except ApiCallError as exc:
            failed += 1
            append_run_log({"problem_key": key, "ok": False, "error": str(exc), **exc.to_dict()})
            print(f"AI_ITEM problem_key={key} status=failed category={exc.category} error={exc}", flush=True)
            results.append({"problem_key": key, "ok": False, "error": str(exc), "category": exc.category, "code": exc.code, "request_id": exc.request_id})
            if exc.category in {"auth_error", "quota_or_billing_error", "bad_request"}:
                break
        except Exception as exc:
            failed += 1
            append_run_log({"problem_key": key, "ok": False, "error": str(exc), "category": "local_error"})
            print(f"AI_ITEM problem_key={key} status=failed category=local_error error={exc}", flush=True)
            results.append({"problem_key": key, "ok": False, "error": str(exc), "category": "local_error"})

    write_review_queue()
    rebuild_result = rebuild_outputs() if rebuild and success else None
    return {
        "ok": True,
        "completed": failed == 0,
        "success": success,
        "failed": failed,
        "results": results,
        "rebuild": rebuild_result,
    }


def write_review_queue() -> None:
    rows = problem_status_rows()
    failed = [row for row in rows if row.get("last_error")]
    store = load_ai_store()
    generated_records = store.get("records", {})
    low_confidence: list[tuple[str, str, str]] = []
    if isinstance(generated_records, dict):
        for key, entry in generated_records.items():
            if not isinstance(entry, dict):
                continue
            insight = entry.get("insight")
            if not isinstance(insight, dict):
                continue
            status = str(insight.get("extraction_status") or "")
            flags = ", ".join(str(flag) for flag in insight.get("quality_flags", []))
            if status == "low_confidence" or flags:
                low_confidence.append((str(key), str(entry.get("title") or ""), flags or status))

    lines = [
        "# CF AI 摘要复核队列",
        "",
        f"生成时间：{utc_now()}",
        "",
        "## 失败项",
        "",
    ]
    if failed:
        for row in failed[:200]:
            lines.append(f"- `{row['problem_key']}` {row.get('title') or ''}：{row.get('last_error')}")
    else:
        lines.append("- 暂无失败项。")
    lines.extend(["", "## 低置信度 / 风险标记", ""])
    if low_confidence:
        for key, title, flags in sorted(low_confidence)[:300]:
            lines.append(f"- `{key}` {title}：{flags}")
    else:
        lines.append("- 暂无低置信度或风险标记。")
    AI_REVIEW_QUEUE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def rebuild_outputs() -> dict[str, Any]:
    commands = [
        [sys.executable, str(KNOWLEDGE_DIR / "build_problem_insights.py")],
        [sys.executable, str(KNOWLEDGE_DIR / "build_problem_insights_browser_data.py")],
    ]
    outputs: list[dict[str, Any]] = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        outputs.append(
            {
                "command": " ".join(command),
                "returncode": completed.returncode,
                "stdout": completed.stdout[-2000:],
                "stderr": completed.stderr[-2000:],
            }
        )
        if completed.returncode != 0:
            raise ManagerError(f"重建失败：{' '.join(command)}\n{completed.stderr or completed.stdout}")
    return {"ok": True, "outputs": outputs}


class Handler(BaseHTTPRequestHandler):
    server_version = "CfAiManager/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self.send_html(HTML_PAGE)
            elif parsed.path == "/api/status":
                self.send_json({"ok": True, "config": load_config().to_public_dict(), "status": status_summary()})
            elif parsed.path == "/api/problems":
                query = parse_qs(parsed.query)
                filter_name = query.get("filter", ["pending"])[0]
                search = query.get("q", [""])[0]
                limit = bounded_int(query.get("limit", ["200"])[0], 1, 1000, 200)
                rows = filter_rows(problem_status_rows(), filter_name, search, limit)
                self.send_json({"ok": True, "problems": rows})
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "not found")
        except Exception as exc:
            self.send_exception(exc)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            payload = self.read_body_json()
            if parsed.path == "/api/config":
                config = save_config_from_payload(payload)
                self.send_json({"ok": True, "config": config.to_public_dict()})
            elif parsed.path == "/api/test-config":
                config = load_config()
                data, request_id = get_json(config, models_endpoint(config))
                models = data.get("data", []) if isinstance(data.get("data"), list) else []
                self.send_json({"ok": True, "request_id": request_id, "model_count": len(models)})
            elif parsed.path == "/api/generate":
                keys = payload.get("problem_keys")
                if not isinstance(keys, list):
                    raise ManagerError("problem_keys 必须是数组")
                problem_keys = [str(key) for key in keys if str(key).strip()]
                rebuild = bool(payload.get("rebuild", True))
                self.send_json(generate_many(problem_keys, rebuild))
            elif parsed.path == "/api/rebuild":
                self.send_json(rebuild_outputs())
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "not found")
        except Exception as exc:
            self.send_exception(exc)

    def read_body_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ManagerError("请求体必须是 JSON object")
        return data

    def send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, body: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_exception(self, exc: Exception) -> None:
        if isinstance(exc, ApiCallError):
            body = {"ok": False, "error": str(exc), **exc.to_dict()}
            self.send_json(body, HTTPStatus.BAD_REQUEST)
            return
        if isinstance(exc, ManagerError):
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        traceback.print_exc()
        self.send_json({"ok": False, "error": f"本地服务异常：{exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"CF AI 摘要管理页：http://{args.host}:{args.port}")
    print(f"配置文件：{AI_CONFIG_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

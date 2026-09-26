#!/usr/bin/env python3
"""Incrementally refresh Codeforces data and derived static pages.

The crawler remains the single source of truth for contest/problem/editorial
data.  This wrapper supplies the recurring-job behavior: choose a small
overlapping time window, crawl it, repair incomplete editorials, rebuild the
problem-insights page, and optionally generate AI summaries for new records.

Examples:
  python3 tools/cf_auto_update.py --lookback-days 30 --ai-limit -1 --require-ai
  python3 tools/cf_auto_update.py --phase crawl --lookback-days 30
  python3 tools/cf_auto_update.py --phase ai --ai-limit -1 --require-ai
  OPENAI_API_KEY=... python3 tools/cf_auto_update.py --ai-limit 20
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from cf_config import get_bool, get_float, get_int, load_config, section


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT
RECORDS_PATH = DATA_DIR / "records.json"
CONTESTS_PATH = DATA_DIR / "contests.json"
STATUS_JSON_PATH = DATA_DIR / "auto-update-status.json"
STATUS_MD_PATH = DATA_DIR / "auto-update-status.md"
RUN_CONTEXT: dict[str, Any] = {}

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class AutoUpdateError(RuntimeError):
    """Raised when a required synchronization step fails."""


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def corpus_summary() -> dict[str, Any]:
    import cf_knowledge_index as indexer

    records = read_json(RECORDS_PATH, [])
    contests = read_json(CONTESTS_PATH, [])
    if not isinstance(records, list):
        records = []
    if not isinstance(contests, list):
        contests = []
    statement_gaps = [
        row for row in records
        if not isinstance(row, dict)
        or not indexer.is_problem_statement(str(row.get("statement_text") or ""))
    ]
    editorial_gaps = [
        row for row in records
        if not isinstance(row, dict)
        or row.get("editorial_quality") != "complete"
        or row.get("editorial_status") in {"missing_url", "url_only", "fetch_failed"}
    ]
    return {
        "problems": len(records),
        "contests": len(contests),
        "statement_gaps": len(statement_gaps),
        "editorial_gaps": len(editorial_gaps),
        "statements_available": len(records) - len(statement_gaps),
        "editorials_complete": len(records) - len(editorial_gaps),
    }


def write_auto_update_status(payload: dict[str, Any]) -> None:
    """Persist one compact, human-readable report for each scheduled run."""
    payload = {"generated_at": utc_now(), **payload}
    STATUS_JSON_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = payload.get("corpus") if isinstance(payload.get("corpus"), dict) else {}
    lines = [
        "# CF 自动更新状态",
        "",
        f"- 状态：`{payload.get('status', 'unknown')}`",
        f"- 运行时间：`{payload.get('started_at', '?')}` 至 `{payload.get('finished_at', payload['generated_at'])}`",
        f"- 更新窗口：`{payload.get('window', {}).get('since', '?')}` 至 `{payload.get('window', {}).get('until', '?')}`",
        f"- 新增题目：{payload.get('new_problems', 0)}",
        f"- 题目总数：{summary.get('problems', 0)}；比赛总数：{summary.get('contests', 0)}",
        f"- 题面缺口：{summary.get('statement_gaps', 0)}；题解缺口：{summary.get('editorial_gaps', 0)}",
        f"- AI：待处理 {payload.get('ai_pending', 0)}，成功 {payload.get('ai_success', 0)}，失败 {payload.get('ai_failed', 0)}",
        f"- 状态失败记录：{payload.get('failure_log_count', 0)}",
        "",
    ]
    warnings = payload.get("warnings", [])
    if warnings:
        lines += ["## 注意事项", ""]
        lines.extend(f"- {item}" for item in warnings)
        lines.append("")
    error = payload.get("error")
    if error:
        lines += ["## 错误", "", f"- {error}", ""]
    STATUS_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def latest_local_date() -> dt.date | None:
    contests = read_json(CONTESTS_PATH, [])
    dates = [
        dt.date.fromisoformat(str(item["date"]))
        for item in contests
        if isinstance(item, dict) and item.get("date")
    ]
    return max(dates) if dates else None


def sync_window(lookback_days: int) -> tuple[dt.date, dt.date]:
    today = dt.date.today()
    rolling_start = today - dt.timedelta(days=lookback_days)
    latest = latest_local_date()
    overlap_start = latest - dt.timedelta(days=1) if latest else rolling_start
    return min(rolling_start, overlap_start), today


def run_command(command: Sequence[str]) -> None:
    printable = " ".join(command)
    print(f"RUN {printable}", flush=True)
    completed = subprocess.run(
        list(command),
        cwd=str(REPO_ROOT),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.stdout:
        print(completed.stdout.rstrip(), flush=True)
    if completed.returncode != 0:
        raise AutoUpdateError(f"命令失败（{completed.returncode}）：{printable}")


def problem_keys(records: Any) -> set[str]:
    if not isinstance(records, list):
        return set()
    return {
        f"{item.get('contest_id')}{item.get('index')}"
        for item in records
        if isinstance(item, dict) and item.get("contest_id") is not None and item.get("index")
    }


def merge_contests(previous: Any, current: Any) -> None:
    """Keep the historical contest catalog when crawl uses a short window."""
    merged: dict[int, dict[str, Any]] = {}
    for item in [*(previous if isinstance(previous, list) else []), *(current if isinstance(current, list) else [])]:
        if isinstance(item, dict) and item.get("id") is not None:
            merged[int(item["id"])] = item
    ordered = sorted(merged.values(), key=lambda item: (item.get("startTimeSeconds", 0), item.get("id", 0)))
    CONTESTS_PATH.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")


def rebuild_static_outputs() -> None:
    run_command([sys.executable, str(DATA_DIR / "build_problem_insights.py")])
    run_command([sys.executable, str(DATA_DIR / "build_problem_insights_browser_data.py")])


def refresh_coverage_outputs() -> None:
    """Refresh gap reports when Tutorial enrichment was intentionally skipped."""
    import cf_knowledge_index as indexer

    records = read_json(RECORDS_PATH, [])
    state = read_json(DATA_DIR / "state.json", {})
    blogs = {
        str(item.get("url")): item
        for item in read_json(DATA_DIR / "editorials.json", [])
        if isinstance(item, dict) and item.get("url")
    }
    failures = state.get("failures", []) if isinstance(state, dict) else []
    indexer.write_coverage(DATA_DIR, records, failures, blogs)


def generate_pending(
    ai_limit: int,
    require_ai: bool,
    refresh_ai: bool = False,
    contest_id: int | None = None,
) -> tuple[int, int, int]:
    """Generate new summaries, or refresh existing AI summaries when requested."""
    import cf_ai_manager as manager

    if ai_limit == 0:
        print("AI_LIMIT 0", flush=True)
        return 0, 0, 0

    pending = []
    missing_statement = 0
    for row in manager.problem_status_rows():
        if contest_id is not None and int(row.get("contest_id") or 0) != contest_id:
            continue
        if row["manual_override"]:
            continue
        if refresh_ai and not row["has_current_ai"]:
            continue
        if not refresh_ai and row["has_current_ai"]:
            continue
        if not row.get("statement_available"):
            missing_statement += 1
            continue
        pending.append(row["problem_key"])
        if ai_limit > 0 and len(pending) >= ai_limit:
            break
    if missing_statement:
        print(f"AI_BLOCKED_NO_STATEMENT {missing_statement}", flush=True)
    if not pending:
        print("AI_PENDING 0", flush=True)
        return 0, 0, 0

    config = manager.load_config()
    if not config.resolved_api_key():
        message = f"发现 {len(pending)} 道待生成题目，但没有 OPENAI_API_KEY；保留基础摘要并跳过 AI。"
        if require_ai:
            raise AutoUpdateError(message)
        print(f"AI_SKIPPED {message}", flush=True)
        return len(pending), 0, 0

    result = manager.generate_many(pending, rebuild=False)
    success = int(result.get("success", 0))
    failed = int(result.get("failed", 0))
    print(f"AI_RESULT pending={len(pending)} success={success} failed={failed}", flush=True)
    if require_ai and failed and success == 0:
        raise AutoUpdateError(f"本批次 AI 摘要全部失败（{failed} 道），没有可提交的题目。")
    if failed:
        print(
            f"AI_PARTIAL success={success} failed={failed}，成功题目继续提交，失败题目留待下一轮重试。",
            flush=True,
        )
    return len(pending), success, failed


def pending_ai_count() -> int:
    """Return the number of records still lacking a current AI summary."""
    import cf_ai_manager as manager

    return sum(
        1
        for row in manager.problem_status_rows()
        if not row["manual_override"] and not row["has_current_ai"]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=("all", "crawl", "ai"),
        default="all",
        help="执行完整流程、仅抓取构建，或仅生成 AI 摘要",
    )
    parser.add_argument("--lookback-days", type=int, default=None)
    parser.add_argument("--contest-id", type=int, default=None, help="只处理指定的 Codeforces 比赛")
    parser.add_argument("--ai-limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=None)
    parser.add_argument("--retries", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--require-ai", dest="require_ai", action="store_true", default=None)
    parser.add_argument("--no-require-ai", dest="require_ai", action="store_false")
    parser.add_argument(
        "--refresh-ai",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="重生成已有 AI 摘要，默认只处理没有当前摘要的题目",
    )
    parser.add_argument("--skip-editorial-enrich", action=argparse.BooleanOptionalAction, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config()
    auto_update = section(config, "auto_update")
    crawler = section(auto_update, "crawler") or section(config, "crawler")
    lookback_days = args.lookback_days if args.lookback_days is not None else get_int(auto_update, "lookback_days", 30)
    ai_limit = args.ai_limit if args.ai_limit is not None else get_int(auto_update, "ai_limit", -1)
    delay = args.delay if args.delay is not None else get_float(crawler, "delay_seconds", 1.0)
    retries = args.retries if args.retries is not None else get_int(crawler, "retries", 4)
    timeout = args.timeout if args.timeout is not None else get_int(crawler, "timeout_seconds", 45)
    checkpoint_every = get_int(crawler, "checkpoint_every", 10)
    require_ai = args.require_ai if args.require_ai is not None else get_bool(auto_update, "require_ai", False)
    refresh_ai = args.refresh_ai if args.refresh_ai is not None else get_bool(auto_update, "refresh_ai", False)
    skip_editorial_enrich = (
        args.skip_editorial_enrich
        if args.skip_editorial_enrich is not None
        else get_bool(auto_update, "skip_editorial_enrich", False)
    )
    global RUN_CONTEXT
    RUN_CONTEXT = {
        "started_at": utc_now(),
        "phase": args.phase,
        "lookback_days": lookback_days,
        "contest_id": args.contest_id,
        "ai_limit": ai_limit,
        "skip_editorial_enrich": skip_editorial_enrich,
        "refresh_ai": refresh_ai,
    }
    if lookback_days < 1 or ai_limit < -1 or (args.contest_id is not None and args.contest_id < 1):
        raise AutoUpdateError("lookback-days 必须大于 0，ai-limit 只能为 -1、0 或正整数，contest-id 必须为正整数")

    since, until = sync_window(lookback_days)
    RUN_CONTEXT["window"] = {"since": since.isoformat(), "until": until.isoformat()}
    records_changed = False
    new_count = 0
    if args.phase in {"all", "crawl"}:
        before_records = RECORDS_PATH.read_bytes() if RECORDS_PATH.exists() else b""
        before_keys = problem_keys(read_json(RECORDS_PATH, []))
        before_contests = read_json(CONTESTS_PATH, [])
        print(f"WINDOW since={since.isoformat()} until={until.isoformat()}", flush=True)

        crawl_command = [
            sys.executable,
            str(REPO_ROOT / "tools" / "cf_knowledge_index.py"),
            "crawl",
            "--since",
            since.isoformat(),
            "--until",
            until.isoformat(),
            "--out",
            str(DATA_DIR),
            "--delay",
            str(delay),
            "--retries",
            str(retries),
            "--timeout",
            str(timeout),
            "--checkpoint-every",
            str(checkpoint_every),
        ]
        if args.contest_id is not None:
            crawl_command.extend(["--contest-id", str(args.contest_id)])
        run_command(crawl_command)
        merge_contests(before_contests, read_json(CONTESTS_PATH, []))

        if not skip_editorial_enrich:
            enrich_command = [
                sys.executable,
                str(REPO_ROOT / "tools" / "cf_knowledge_index.py"),
                "enrich",
                "--data",
                str(DATA_DIR),
                "--only-incomplete",
                "--skip-missing-contests",
                "--delay",
                str(delay),
                "--retries",
                str(retries),
                "--timeout",
                str(timeout),
                "--checkpoint-every",
                str(checkpoint_every),
            ]
            if args.contest_id is not None:
                enrich_command.extend(["--contest-id", str(args.contest_id)])
            run_command(enrich_command)
        else:
            refresh_coverage_outputs()

        after_records = RECORDS_PATH.read_bytes() if RECORDS_PATH.exists() else b""
        after_keys = problem_keys(read_json(RECORDS_PATH, []))
        records_changed = before_records != after_records
        new_count = len(after_keys - before_keys)
        if records_changed or not (DATA_DIR / "problem-insights.json").exists():
            rebuild_static_outputs()
        else:
            print("BUILD_SKIPPED records unchanged", flush=True)
    else:
        print("CRAWL_SKIPPED phase=ai", flush=True)
        refresh_coverage_outputs()

    if args.phase in {"all", "ai"}:
        selected_pending, success, failed = generate_pending(
            ai_limit,
            require_ai,
            refresh_ai,
            args.contest_id,
        )
        if success:
            rebuild_static_outputs()
    else:
        print("AI_SKIPPED phase=crawl", flush=True)
        selected_pending, success, failed = 0, 0, 0
    pending = pending_ai_count()

    summary = corpus_summary()
    warnings = []
    if summary["statement_gaps"]:
        warnings.append(f"仍有 {summary['statement_gaps']} 道题缺少可靠题面，已写入 statement-gaps.json。")
    if failed:
        warnings.append(f"本轮有 {failed} 道题 AI 生成失败，下一轮会继续重试。")
    write_auto_update_status({
        **RUN_CONTEXT,
        "status": "completed_with_warnings" if warnings else "completed",
        "finished_at": utc_now(),
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "new_problems": new_count,
        "records_changed": records_changed,
        "corpus": summary,
        "ai_pending": pending,
        "ai_success": success,
        "ai_failed": failed,
        "failure_log_count": len(read_json(DATA_DIR / "state.json", {}).get("failures", [])),
        "warnings": warnings,
    })

    print(
        f"AUTO_UPDATE phase={args.phase} new_problems={new_count} records_changed={records_changed} "
        f"ai_selected={selected_pending} ai_pending={pending} "
        f"ai_success={success} ai_failed={failed}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        if RUN_CONTEXT:
            write_auto_update_status({
                **RUN_CONTEXT,
                "status": "failed",
                "finished_at": utc_now(),
                "corpus": corpus_summary(),
                "failure_log_count": len(read_json(DATA_DIR / "state.json", {}).get("failures", [])),
                "error": str(exc),
                "warnings": ["本轮自动更新未完成，请查看工作流日志并在修复后重试。"],
            })
        print(f"AUTO_UPDATE_FAILED {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

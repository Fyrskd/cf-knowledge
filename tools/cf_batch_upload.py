#!/usr/bin/env python3
"""逐场触发 CF 自动更新工作流，并在失败时自动重试。

默认扫描 2023-01-01 之后尚未完整进入 problem-insights.json 的比赛，按日期
串行触发 .github/workflows/cf-auto-update.yml。状态保存在本地断点文件中，
脚本中断后可以继续等待已有 run，成功的比赛也会自动跳过。

示例：
  python3 tools/cf_batch_upload.py --dry-run
  python3 tools/cf_batch_upload.py --from-date 2023-01-01
  python3 tools/cf_batch_upload.py --contest-id 1778 --max-retries 3
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT
CONTESTS_PATH = DATA_DIR / "contests.json"
RECORDS_PATH = DATA_DIR / "records.json"
INSIGHTS_PATH = DATA_DIR / "problem-insights.json"
DEFAULT_STATE_PATH = DATA_DIR / "batch-upload-state.local.json"
DEFAULT_WORKFLOW = "cf-auto-update.yml"
MAX_TRANSIENT_GH_ERRORS = 5


class BatchUploadError(RuntimeError):
    """批量上传编排失败。"""


class RunNotFoundError(BatchUploadError):
    """断点中的 GitHub Actions run 已不存在，通常是仓库迁移后的旧 ID。"""


@dataclass(frozen=True)
class Contest:
    contest_id: int
    name: str
    date: dt.date | None


@dataclass(frozen=True)
class WorkflowRun:
    run_id: int
    status: str
    conclusion: str | None
    url: str

    @property
    def completed_successfully(self) -> bool:
        return self.status == "completed" and self.conclusion == "success"

    @property
    def terminal(self) -> bool:
        return self.status == "completed"


class WorkflowClient(Protocol):
    """GitHub Actions 客户端的最小接口，便于本地测试。"""

    def dispatch(self, workflow: str, ref: str, contest_id: int) -> None:
        ...

    def find_run(
        self,
        workflow: str,
        ref: str,
        created_after: dt.datetime,
        timeout_seconds: float,
        poll_seconds: float,
    ) -> WorkflowRun:
        ...

    def get_run(self, run_id: int) -> WorkflowRun:
        ...

    def failed_log(self, run_id: int) -> str:
        ...


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise BatchUploadError(f"日期格式错误，应为 YYYY-MM-DD：{value}") from exc


def parse_timestamp(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def problem_key(row: dict[str, Any]) -> str | None:
    contest_id = row.get("contest_id")
    index = row.get("index")
    if contest_id is None or not index:
        return None
    return f"{contest_id}{index}"


def load_candidates(
    contests_path: Path = CONTESTS_PATH,
    records_path: Path = RECORDS_PATH,
    insights_path: Path = INSIGHTS_PATH,
    from_date: dt.date | None = dt.date(2023, 1, 1),
    until_date: dt.date | None = None,
    contest_ids: Sequence[int] | None = None,
) -> list[Contest]:
    """返回需要处理的比赛，默认只返回发布数据不完整的比赛。"""
    contests = read_json(contests_path, [])
    records = read_json(records_path, [])
    insights = read_json(insights_path, {})
    if not isinstance(contests, list):
        contests = []
    if not isinstance(records, list):
        records = []
    if not isinstance(insights, dict):
        insights = {}

    contest_rows: dict[int, dict[str, Any]] = {}
    for row in contests:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        contest_rows[int(row["id"])] = row

    records_by_contest: dict[int, list[dict[str, Any]]] = {}
    for row in records:
        if not isinstance(row, dict) or row.get("contest_id") is None:
            continue
        records_by_contest.setdefault(int(row["contest_id"]), []).append(row)

    published_keys = {
        str(row.get("problem_key"))
        for row in insights.get("records", [])
        if isinstance(row, dict) and row.get("problem_key")
    }

    explicit = {int(item) for item in contest_ids or []}
    selected: list[Contest] = []
    candidate_ids = explicit or set(contest_rows)
    for contest_id in candidate_ids:
        row = contest_rows.get(contest_id, {})
        contest_date = parse_date(str(row.get("date"))) if row.get("date") else None
        if not explicit:
            if contest_date is None:
                continue
            if from_date is not None and contest_date < from_date:
                continue
            if until_date is not None and contest_date > until_date:
                continue
            problem_rows = records_by_contest.get(contest_id, [])
            keys = {key for key in (problem_key(item) for item in problem_rows) if key}
            if problem_rows and keys and keys <= published_keys:
                continue
        selected.append(
            Contest(
                contest_id=contest_id,
                name=str(row.get("name") or f"Contest {contest_id}"),
                date=contest_date,
            )
        )

    selected.sort(key=lambda item: (item.date is None, item.date or dt.date.min, item.contest_id))
    return selected


class GhWorkflowClient:
    """通过 gh CLI 调用 GitHub Actions。"""

    def __init__(self, repo: str | None = None, executable: str = "gh") -> None:
        self.repo = repo
        self.executable = executable

    def _command(self, args: Sequence[str], check: bool = True) -> str:
        command = [self.executable, *args]
        if self.repo:
            command.extend(["--repo", self.repo])
        completed = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = completed.stdout or ""
        if check and completed.returncode != 0:
            detail = output.strip()
            raise BatchUploadError(
                f"gh 命令失败（{completed.returncode}）：{' '.join(command)}\n{detail}"
            )
        return output

    def _json(self, args: Sequence[str]) -> Any:
        output = self._command(args)
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise BatchUploadError(f"gh 返回了无法解析的 JSON：{output[:500]}") from exc

    def dispatch(self, workflow: str, ref: str, contest_id: int) -> None:
        self._command(
            [
                "workflow",
                "run",
                workflow,
                "--ref",
                ref,
                "--field",
                f"contest_id={contest_id}",
            ]
        )

    def find_run(
        self,
        workflow: str,
        ref: str,
        created_after: dt.datetime,
        timeout_seconds: float,
        poll_seconds: float,
    ) -> WorkflowRun:
        deadline = time.monotonic() + timeout_seconds
        transient_errors = 0
        last_error = ""
        while True:
            try:
                rows = self._json(
                    [
                        "run",
                        "list",
                        "--workflow",
                        workflow,
                        "--event",
                        "workflow_dispatch",
                        "--limit",
                        "20",
                        "--json",
                        "databaseId,createdAt,status,conclusion,url,headBranch",
                    ]
                )
                transient_errors = 0
            except BatchUploadError as exc:
                transient_errors += 1
                last_error = str(exc)
                if transient_errors >= MAX_TRANSIENT_GH_ERRORS:
                    raise BatchUploadError(
                        f"连续 {transient_errors} 次查询新 run 失败：{last_error}"
                    ) from exc
                print(f"RUN_DISCOVERY_RETRY error={last_error[:240]}", flush=True)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(poll_seconds, remaining))
                continue
            if not isinstance(rows, list):
                raise BatchUploadError("gh run list 返回格式不是数组")
            matching: list[tuple[dt.datetime, dict[str, Any]]] = []
            for row in rows:
                if not isinstance(row, dict) or row.get("headBranch") != ref:
                    continue
                created_at = parse_timestamp(str(row.get("createdAt")))
                if created_at >= created_after - dt.timedelta(seconds=3):
                    matching.append((created_at, row))
            if matching:
                _, row = max(matching, key=lambda item: item[0])
                return self._run_from_json(row)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                detail = f"；最近查询错误：{last_error}" if last_error else ""
                raise BatchUploadError(f"触发工作流后 {timeout_seconds:.0f} 秒内没有发现新的 workflow_dispatch run{detail}")
            time.sleep(min(poll_seconds, remaining))

    def get_run(self, run_id: int) -> WorkflowRun:
        try:
            payload = self._json(
                [
                    "run",
                    "view",
                    str(run_id),
                    "--json",
                    "status,conclusion,url",
                ]
            )
        except BatchUploadError as exc:
            if "HTTP 404" in str(exc) or "404: Not Found" in str(exc):
                raise RunNotFoundError(f"run {run_id} 不存在，丢弃旧断点并重新派发") from exc
            raise
        if not isinstance(payload, dict):
            raise BatchUploadError(f"run {run_id} 返回格式不是对象")
        return WorkflowRun(
            run_id=run_id,
            status=str(payload.get("status") or "unknown"),
            conclusion=str(payload["conclusion"]) if payload.get("conclusion") else None,
            url=str(payload.get("url") or ""),
        )

    def failed_log(self, run_id: int) -> str:
        output = self._command(["run", "view", str(run_id), "--log-failed"], check=False)
        return output[-6000:]

    @staticmethod
    def _run_from_json(payload: dict[str, Any]) -> WorkflowRun:
        database_id = payload.get("databaseId")
        if database_id is None:
            raise BatchUploadError(f"工作流返回缺少 databaseId：{payload}")
        return WorkflowRun(
            run_id=int(database_id),
            status=str(payload.get("status") or "unknown"),
            conclusion=str(payload["conclusion"]) if payload.get("conclusion") else None,
            url=str(payload.get("url") or ""),
        )


def load_state(path: Path) -> dict[str, Any]:
    payload = read_json(path, {})
    if not isinstance(payload, dict):
        return {"version": 1, "contests": {}}
    contests = payload.get("contests")
    if not isinstance(contests, dict):
        payload["contests"] = {}
    payload.setdefault("version", 1)
    return payload


def save_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now().isoformat()
    write_json(path, state)


class BatchUploader:
    """串行运行比赛任务并维护断点状态。"""

    def __init__(
        self,
        client: WorkflowClient,
        state_path: Path,
        workflow: str = DEFAULT_WORKFLOW,
        ref: str = "main",
        max_retries: int = 3,
        poll_seconds: float = 15.0,
        run_timeout_seconds: float = 2700.0,
        discovery_timeout_seconds: float = 90.0,
        retry_delay_seconds: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        if max_retries < 0:
            raise BatchUploadError("max-retries 不能小于 0")
        self.client = client
        self.state_path = state_path
        self.workflow = workflow
        self.ref = ref
        self.max_retries = max_retries
        self.poll_seconds = poll_seconds
        self.run_timeout_seconds = run_timeout_seconds
        self.discovery_timeout_seconds = discovery_timeout_seconds
        self.retry_delay_seconds = retry_delay_seconds
        self.sleep = sleep
        self.clock = clock
        self.state = load_state(state_path)

    def run(self, contests: Sequence[Contest], dry_run: bool = False) -> tuple[list[int], list[int], list[int]]:
        if dry_run:
            for contest in contests:
                entry = self._entry(contest)
                print(
                    f"DRY_RUN contest={contest.contest_id} date={contest.date or '-'} "
                    f"status={entry.get('status', 'pending')} name={contest.name}",
                    flush=True,
                )
            return [], [], [contest.contest_id for contest in contests]

        succeeded: list[int] = []
        failed: list[int] = []
        skipped: list[int] = []
        for contest in contests:
            result = self._upload_one(contest)
            if result == "success":
                succeeded.append(contest.contest_id)
            elif result == "failed":
                failed.append(contest.contest_id)
            else:
                skipped.append(contest.contest_id)
        print(
            f"BATCH_UPLOAD success={len(succeeded)} failed={len(failed)} skipped={len(skipped)}",
            flush=True,
        )
        return succeeded, failed, skipped

    def _entry(self, contest: Contest) -> dict[str, Any]:
        contests = self.state.setdefault("contests", {})
        key = str(contest.contest_id)
        entry = contests.get(key)
        if not isinstance(entry, dict):
            entry = {}
            contests[key] = entry
        entry.setdefault("contest_id", contest.contest_id)
        entry.setdefault("name", contest.name)
        entry.setdefault("date", contest.date.isoformat() if contest.date else None)
        entry.setdefault("status", "pending")
        entry.setdefault("attempts", 0)
        entry.setdefault("total_attempts", 0)
        entry.setdefault("run_ids", [])
        return entry

    def _save_entry(self, entry: dict[str, Any]) -> None:
        entry["updated_at"] = self.clock().isoformat()
        save_state(self.state_path, self.state)

    def _upload_one(self, contest: Contest) -> str:
        entry = self._entry(contest)
        if entry.get("status") == "success":
            print(f"SKIP contest={contest.contest_id} status=success", flush=True)
            return "skipped"

        existing_run_id = entry.get("last_run_id") if entry.get("status") != "success" else None
        if existing_run_id:
            try:
                print(f"RESUME contest={contest.contest_id} run={existing_run_id}", flush=True)
                run = self._wait_for_run(int(existing_run_id))
                if run.completed_successfully:
                    self._mark_success(entry, run)
                    return "success"
                self._mark_failure(entry, run, "恢复等待时 Action 失败")
            except RunNotFoundError as exc:
                print(
                    f"RESUME_STALE contest={contest.contest_id} run={existing_run_id} "
                    f"error={exc}",
                    flush=True,
                )
                entry["last_run_id"] = None
                entry["last_run_url"] = ""
            except BatchUploadError as exc:
                self._record_error(entry, str(exc))

        entry["status"] = "pending"
        entry["attempts"] = 0
        entry["last_run_id"] = None
        self._save_entry(entry)

        while int(entry["attempts"]) <= self.max_retries:
            attempt = int(entry["attempts"]) + 1
            entry["attempts"] = attempt
            entry["total_attempts"] = int(entry.get("total_attempts", 0)) + 1
            entry["status"] = "running"
            entry["last_error"] = ""
            self._save_entry(entry)
            print(
                f"DISPATCH contest={contest.contest_id} attempt={attempt}/{self.max_retries + 1}",
                flush=True,
            )

            run: WorkflowRun | None = None
            try:
                dispatched_at = self.clock()
                dispatch_error: BatchUploadError | None = None
                try:
                    self.client.dispatch(self.workflow, self.ref, contest.contest_id)
                except BatchUploadError as exc:
                    # 请求可能已经被 GitHub 接收，只是客户端没有拿到响应。
                    # 先查找新 run，避免重复触发同一场比赛。
                    dispatch_error = exc
                    print(
                        f"DISPATCH_RESPONSE_RETRY contest={contest.contest_id} "
                        f"error={str(exc)[:240]}",
                        flush=True,
                    )
                run = self.client.find_run(
                    self.workflow,
                    self.ref,
                    dispatched_at,
                    self.discovery_timeout_seconds,
                    min(self.poll_seconds, 5.0),
                )
                if dispatch_error:
                    print(
                        f"DISPATCH_ACCEPTED_AFTER_ERROR contest={contest.contest_id} run={run.run_id}",
                        flush=True,
                    )
                entry["last_run_id"] = run.run_id
                entry["last_run_url"] = run.url
                entry["run_ids"] = [*entry.get("run_ids", []), run.run_id][-20:]
                self._save_entry(entry)
                run = self._wait_for_run(run.run_id)
                if run.completed_successfully:
                    self._mark_success(entry, run)
                    return "success"
                self._mark_failure(entry, run, "Action 结束但未成功")
            except BatchUploadError as exc:
                self._record_error(entry, str(exc))
                if run is not None:
                    entry["last_run_id"] = run.run_id

            if attempt <= self.max_retries:
                entry["status"] = "retrying"
                self._save_entry(entry)
                print(
                    f"RETRY contest={contest.contest_id} after={self.retry_delay_seconds:g}s "
                    f"error={entry.get('last_error', '')[:240]}",
                    flush=True,
                )
                self.sleep(self.retry_delay_seconds)
            else:
                entry["status"] = "failed"
                self._save_entry(entry)
                print(
                    f"FAILED contest={contest.contest_id} error={entry.get('last_error', '')[:500]}",
                    flush=True,
                )
                return "failed"
        return "failed"

    def _wait_for_run(self, run_id: int) -> WorkflowRun:
        deadline = time.monotonic() + self.run_timeout_seconds
        last_status = ""
        transient_errors = 0
        while True:
            try:
                run = self.client.get_run(run_id)
                transient_errors = 0
            except RunNotFoundError:
                raise
            except BatchUploadError as exc:
                transient_errors += 1
                print(
                    f"RUN_POLL_RETRY run={run_id} attempt={transient_errors}/{MAX_TRANSIENT_GH_ERRORS} "
                    f"error={str(exc)[:240]}",
                    flush=True,
                )
                if transient_errors >= MAX_TRANSIENT_GH_ERRORS:
                    raise BatchUploadError(
                        f"连续 {transient_errors} 次查询 run {run_id} 失败：{exc}"
                    ) from exc
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BatchUploadError(f"run {run_id} 等待超过 {self.run_timeout_seconds:.0f} 秒") from exc
                self.sleep(min(self.poll_seconds, remaining))
                continue
            status = f"{run.status}/{run.conclusion or '-'}"
            if status != last_status:
                print(f"RUN_STATUS run={run.run_id} status={status} url={run.url}", flush=True)
                last_status = status
            if run.terminal:
                return run
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BatchUploadError(f"run {run_id} 等待超过 {self.run_timeout_seconds:.0f} 秒")
            self.sleep(min(self.poll_seconds, remaining))

    def _mark_success(self, entry: dict[str, Any], run: WorkflowRun) -> None:
        entry["status"] = "success"
        entry["last_run_id"] = run.run_id
        entry["last_run_url"] = run.url
        entry["last_error"] = ""
        self._save_entry(entry)
        print(f"SUCCESS contest={entry['contest_id']} run={run.run_id}", flush=True)

    def _mark_failure(self, entry: dict[str, Any], run: WorkflowRun, prefix: str) -> None:
        detail = f"{prefix}: conclusion={run.conclusion or '-'}"
        try:
            log = self.client.failed_log(run.run_id).strip()
        except BatchUploadError as exc:
            log = f"获取失败日志时 gh 命令失败：{exc}"
        if log:
            detail = f"{detail}\n{log[-6000:]}"
        self._record_error(entry, detail)

    def _record_error(self, entry: dict[str, Any], error: str) -> None:
        entry["last_error"] = error[-7000:]
        self._save_entry(entry)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-date", default="2023-01-01", help="默认从该日期开始扫描")
    parser.add_argument("--until-date", default=None, help="扫描截止日期，包含当天")
    parser.add_argument("--contest-id", action="append", type=int, help="只处理指定比赛，可重复")
    parser.add_argument("--max-contests", type=int, default=0, help="最多处理多少场，0 表示全部")
    parser.add_argument("--max-retries", type=int, default=3, help="每场失败后的重试次数")
    parser.add_argument("--poll-seconds", type=float, default=15.0, help="Action 状态轮询间隔")
    parser.add_argument("--run-timeout-seconds", type=float, default=2700.0, help="单个 run 最大等待时间")
    parser.add_argument("--discovery-timeout-seconds", type=float, default=90.0, help="触发后发现 run 的最大等待时间")
    parser.add_argument("--retry-delay-seconds", type=float, default=60.0, help="两次尝试之间的等待时间")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--ref", default="main")
    parser.add_argument("--repo", default=None, help="GitHub 仓库，默认使用当前 gh 上下文")
    parser.add_argument("--dry-run", action="store_true", help="只扫描和展示候选比赛，不触发 Action")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_contests < 0:
        raise BatchUploadError("max-contests 不能小于 0")
    if args.max_retries < 0:
        raise BatchUploadError("max-retries 不能小于 0")
    if args.poll_seconds <= 0 or args.run_timeout_seconds <= 0 or args.discovery_timeout_seconds <= 0:
        raise BatchUploadError("等待时间必须大于 0")
    from_date = parse_date(args.from_date)
    until_date = parse_date(args.until_date)
    if from_date and until_date and from_date > until_date:
        raise BatchUploadError("from-date 不能晚于 until-date")

    contests = load_candidates(
        from_date=from_date,
        until_date=until_date,
        contest_ids=args.contest_id,
    )
    if args.max_contests:
        contests = contests[: args.max_contests]
    print(f"CANDIDATES count={len(contests)}", flush=True)
    if not contests:
        return 0

    client = GhWorkflowClient(repo=args.repo)
    uploader = BatchUploader(
        client=client,
        state_path=args.state_file,
        workflow=args.workflow,
        ref=args.ref,
        max_retries=args.max_retries,
        poll_seconds=args.poll_seconds,
        run_timeout_seconds=args.run_timeout_seconds,
        discovery_timeout_seconds=args.discovery_timeout_seconds,
        retry_delay_seconds=args.retry_delay_seconds,
    )
    _, failed, _ = uploader.run(contests, dry_run=args.dry_run)
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BatchUploadError, OSError, subprocess.SubprocessError) as exc:
        print(f"BATCH_UPLOAD_FAILED {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

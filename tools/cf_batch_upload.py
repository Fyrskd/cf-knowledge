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
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence
from urllib.parse import urlparse

from cf_config import get_float, get_int, get_str, load_config, section


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT
CONTESTS_PATH = DATA_DIR / "contests.json"
RECORDS_PATH = DATA_DIR / "records.json"
INSIGHTS_PATH = DATA_DIR / "problem-insights.json"
DEFAULT_STATE_PATH = DATA_DIR / "batch-upload-state.local.json"
DEFAULT_WORKFLOW = "cf-auto-update.yml"
MAX_TRANSIENT_GH_ERRORS = 5
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
FAILURE_LINE_RE = re.compile(
    r"(?:##\[error\]|\bError:|AUTO_UPDATE_FAILED|Process completed with exit code|"
    r"Traceback \(most recent call last\)|\bfailed\b|\bFAILED\b|exception|not found|"
    r"permission denied|timed out)",
    re.IGNORECASE,
)


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


def clean_log_line(value: str) -> str:
    """去掉 GitHub Actions 日志中的 ANSI 控制符，避免终端输出不可读。"""
    return ANSI_ESCAPE_RE.sub("", value).strip()


def summarize_failed_log(log: str, max_lines: int = 24, max_chars: int = 3600) -> tuple[str, str]:
    """从 Actions 失败日志中提取工作流步骤和可读错误片段。"""
    lines = [clean_log_line(line) for line in log.splitlines() if clean_log_line(line)]
    if not lines:
        return "", ""

    matches: list[tuple[str, str]] = []
    for line in lines:
        fields = line.split("\t", 3)
        message = fields[3] if len(fields) == 4 else line
        if FAILURE_LINE_RE.search(message):
            step = fields[1] if len(fields) == 4 else ""
            matches.append((step.strip(), line))

    step = next((item[0] for item in matches if item[0] and item[0] != "UNKNOWN STEP"), "")
    selected = [line for _, line in matches]
    if not selected:
        selected = lines[-min(max_lines, len(lines)) :]
    selected = selected[-max_lines:]

    excerpt_lines: list[str] = []
    size = 0
    for line in selected:
        rendered = f"  {line}"
        if size + len(rendered) + 1 > max_chars:
            break
        excerpt_lines.append(rendered)
        size += len(rendered) + 1
    return step, "\n".join(excerpt_lines)


def shorten(value: str, limit: int = 320) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def normalize_repository(value: str | None) -> str | None:
    """将 GitHub URL、SSH 地址或 owner/repo 统一为 owner/repo。"""
    if not value:
        return None
    text = value.strip()
    if text.startswith("git@github.com:"):
        text = text.removeprefix("git@github.com:")
    elif "://" in text:
        parsed = urlparse(text)
        if parsed.netloc.lower() != "github.com":
            return None
        text = parsed.path
    text = text.strip("/")
    if text.endswith(".git"):
        text = text[:-4]
    parts = [part for part in text.split("/") if part]
    if len(parts) != 2:
        return None
    return "/".join(parts).lower()


def repository_from_run_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.netloc.lower() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    return normalize_repository("/".join(parts[:2]))


def current_repository_slug(explicit: str | None = None) -> str | None:
    repository = normalize_repository(explicit)
    if repository:
        return repository
    completed = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=str(REPO_ROOT),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return normalize_repository((completed.stdout or "").strip())


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
        repository: str | None = None,
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
        self.repository = normalize_repository(repository)
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
        total = len(contests)
        for position, contest in enumerate(contests, start=1):
            entry = self._entry(contest)
            print(
                f"CONTEST_START index={position}/{total} contest={contest.contest_id} "
                f"date={contest.date or '-'} status={entry.get('status', 'pending')} "
                f"name={contest.name}",
                flush=True,
            )
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
        entry.setdefault("phase", "pending")
        entry.setdefault("failed_phase", "")
        entry.setdefault("workflow_step", "")
        return entry

    def _save_entry(self, entry: dict[str, Any]) -> None:
        entry["updated_at"] = self.clock().isoformat()
        save_state(self.state_path, self.state)

    def _set_phase(self, entry: dict[str, Any], phase: str) -> None:
        entry["phase"] = phase
        self._save_entry(entry)

    def _run_belongs_to_current_repository(self, entry: dict[str, Any]) -> bool:
        if not self.repository:
            return True
        run_repository = repository_from_run_url(str(entry.get("last_run_url") or ""))
        return run_repository in {None, self.repository}

    def _reset_stale_entry(self, contest: Contest, entry: dict[str, Any]) -> None:
        old_run_id = entry.get("last_run_id")
        old_repository = repository_from_run_url(str(entry.get("last_run_url") or ""))
        print(
            f"RESET_STALE_STATE contest={contest.contest_id} run={old_run_id or '-'} "
            f"repository={old_repository or '-'} current={self.repository or '-'}",
            flush=True,
        )
        entry["status"] = "pending"
        entry["attempts"] = 0
        entry["last_run_id"] = None
        entry["last_run_url"] = ""
        entry["last_error"] = ""
        entry["phase"] = "pending"
        entry["failed_phase"] = ""
        entry["workflow_step"] = ""
        self._save_entry(entry)

    def _upload_one(self, contest: Contest) -> str:
        entry = self._entry(contest)
        if not self._run_belongs_to_current_repository(entry):
            self._reset_stale_entry(contest, entry)
        if entry.get("status") == "success":
            print(
                f"CONTEST_SKIP contest={contest.contest_id} reason=state_success "
                f"run={entry.get('last_run_id') or '-'} url={entry.get('last_run_url') or '-'}",
                flush=True,
            )
            return "skipped"

        existing_run_id = entry.get("last_run_id") if entry.get("status") != "success" else None
        if existing_run_id:
            try:
                self._set_phase(entry, "resume_poll")
                print(
                    f"RESUME_START contest={contest.contest_id} run={existing_run_id} "
                    f"timeout={self.run_timeout_seconds:g}s",
                    flush=True,
                )
                run = self._wait_for_run(int(existing_run_id))
                if run.completed_successfully:
                    self._mark_success(entry, run)
                    return "success"
                self._mark_failure(entry, run, "恢复等待时 Action 失败")
            except RunNotFoundError as exc:
                print(
                    f"RESUME_STALE contest={contest.contest_id} run={existing_run_id} error={exc}",
                    flush=True,
                )
                entry["last_run_id"] = None
                entry["last_run_url"] = ""
            except BatchUploadError as exc:
                self._record_error(entry, str(exc), phase="resume_poll")
                print(
                    f"RESUME_ERROR contest={contest.contest_id} run={existing_run_id} "
                    f"phase=resume_poll error={shorten(str(exc))}",
                    flush=True,
                )

        entry["status"] = "pending"
        entry["attempts"] = 0
        entry["last_run_id"] = None
        entry["failed_phase"] = ""
        entry["workflow_step"] = ""
        self._save_entry(entry)

        while int(entry["attempts"]) <= self.max_retries:
            attempt = int(entry["attempts"]) + 1
            entry["attempts"] = attempt
            entry["total_attempts"] = int(entry.get("total_attempts", 0)) + 1
            entry["status"] = "running"
            entry["last_error"] = ""
            entry["failed_phase"] = ""
            entry["workflow_step"] = ""
            self._save_entry(entry)
            print(
                f"ATTEMPT_START contest={contest.contest_id} attempt={attempt}/{self.max_retries + 1}",
                flush=True,
            )

            run: WorkflowRun | None = None
            try:
                dispatched_at = self.clock()
                dispatch_error: BatchUploadError | None = None
                self._set_phase(entry, "dispatch")
                print(
                    f"DISPATCH_START contest={contest.contest_id} workflow={self.workflow} "
                    f"ref={self.ref}",
                    flush=True,
                )
                try:
                    self.client.dispatch(self.workflow, self.ref, contest.contest_id)
                    print(f"DISPATCH_ACCEPTED contest={contest.contest_id}", flush=True)
                except BatchUploadError as exc:
                    # 请求可能已经被 GitHub 接收，只是客户端没有拿到响应。
                    # 先查找新 run，避免重复触发同一场比赛。
                    dispatch_error = exc
                    print(
                        f"DISPATCH_RESPONSE_ERROR contest={contest.contest_id} "
                        f"error={shorten(str(exc))}",
                        flush=True,
                    )
                self._set_phase(entry, "run_discovery")
                print(
                    f"RUN_DISCOVERY_START contest={contest.contest_id} workflow={self.workflow} "
                    f"ref={self.ref} timeout={self.discovery_timeout_seconds:g}s",
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
                        f"RUN_DISCOVERY_AFTER_DISPATCH_ERROR contest={contest.contest_id} "
                        f"run={run.run_id}",
                        flush=True,
                    )
                else:
                    print(
                        f"RUN_DISCOVERY_SUCCESS contest={contest.contest_id} run={run.run_id} "
                        f"url={run.url}",
                        flush=True,
                    )
                entry["last_run_id"] = run.run_id
                entry["last_run_url"] = run.url
                entry["run_ids"] = [*entry.get("run_ids", []), run.run_id][-20:]
                self._save_entry(entry)
                self._set_phase(entry, "run_poll")
                print(
                    f"RUN_POLL_START contest={contest.contest_id} run={run.run_id} "
                    f"timeout={self.run_timeout_seconds:g}s interval={self.poll_seconds:g}s",
                    flush=True,
                )
                run = self._wait_for_run(run.run_id)
                if run.completed_successfully:
                    self._mark_success(entry, run)
                    return "success"
                self._mark_failure(entry, run, "Action 结束但未成功")
            except BatchUploadError as exc:
                phase = str(entry.get("phase") or "unknown")
                self._record_error(entry, str(exc), phase=phase)
                print(
                    f"ATTEMPT_ERROR contest={contest.contest_id} run={run.run_id if run else '-'} "
                    f"phase={phase} error={shorten(str(exc))}",
                    flush=True,
                )
                if run is not None:
                    entry["last_run_id"] = run.run_id

            if attempt <= self.max_retries:
                entry["status"] = "retrying"
                entry["phase"] = "retry_wait"
                self._save_entry(entry)
                print(
                    f"RETRY contest={contest.contest_id} after={self.retry_delay_seconds:g}s "
                    f"failed_phase={entry.get('failed_phase') or '-'} "
                    f"workflow_step={entry.get('workflow_step') or '-'} "
                    f"error={shorten(str(entry.get('last_error') or ''))}",
                    flush=True,
                )
                self.sleep(self.retry_delay_seconds)
            else:
                entry["status"] = "failed"
                entry["phase"] = "failed"
                self._save_entry(entry)
                print(
                    f"CONTEST_FAILED contest={contest.contest_id} run={entry.get('last_run_id') or '-'} "
                    f"phase={entry.get('failed_phase') or entry.get('phase') or '-'} "
                    f"workflow_step={entry.get('workflow_step') or '-'} "
                    f"attempt={attempt}/{self.max_retries + 1} "
                    f"error={shorten(str(entry.get('last_error') or ''), 700)}",
                    flush=True,
                )
                if entry.get("last_run_url"):
                    print(f"CONTEST_FAILED_URL contest={contest.contest_id} url={entry['last_run_url']}", flush=True)
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
                    f"error={shorten(str(exc))}",
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
        entry["phase"] = "completed"
        entry["last_run_id"] = run.run_id
        entry["last_run_url"] = run.url
        entry["last_error"] = ""
        entry["failed_phase"] = ""
        entry["workflow_step"] = ""
        self._save_entry(entry)
        print(
            f"CONTEST_SUCCESS contest={entry['contest_id']} run={run.run_id} url={run.url}",
            flush=True,
        )

    def _mark_failure(self, entry: dict[str, Any], run: WorkflowRun, prefix: str) -> None:
        self._set_phase(entry, "failure_log")
        print(f"RUN_FAILURE_LOG_START contest={entry['contest_id']} run={run.run_id}", flush=True)
        detail = f"{prefix}: conclusion={run.conclusion or '-'}"
        try:
            log = self.client.failed_log(run.run_id).strip()
        except BatchUploadError as exc:
            log = f"获取失败日志时 gh 命令失败：{exc}"
        workflow_step, excerpt = summarize_failed_log(log)
        entry["workflow_step"] = workflow_step
        if workflow_step:
            detail = f"{detail}; workflow_step={workflow_step}"
        if excerpt:
            detail = f"{detail}\n{excerpt}"
            print(
                f"RUN_FAILURE_LOG contest={entry['contest_id']} run={run.run_id} "
                f"workflow_step={workflow_step or '-'}\n{excerpt}",
                flush=True,
            )
        else:
            print(
                f"RUN_FAILURE_LOG_EMPTY contest={entry['contest_id']} run={run.run_id} "
                "未获取到可读的失败日志",
                flush=True,
            )
        self._record_error(entry, detail, phase="workflow")

    def _record_error(self, entry: dict[str, Any], error: str, phase: str | None = None) -> None:
        entry["last_error"] = error[-7000:]
        entry["failed_phase"] = phase or str(entry.get("phase") or "unknown")
        self._save_entry(entry)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-date", default=None, help="默认从该日期开始扫描")
    parser.add_argument("--until-date", default=None, help="扫描截止日期，包含当天")
    parser.add_argument("--contest-id", action="append", type=int, help="只处理指定比赛，可重复")
    parser.add_argument("--max-contests", type=int, default=None, help="最多处理多少场，0 表示全部")
    parser.add_argument("--max-retries", type=int, default=None, help="每场失败后的重试次数")
    parser.add_argument("--poll-seconds", type=float, default=None, help="Action 状态轮询间隔")
    parser.add_argument("--run-timeout-seconds", type=float, default=None, help="单个 run 最大等待时间")
    parser.add_argument("--discovery-timeout-seconds", type=float, default=None, help="触发后发现 run 的最大等待时间")
    parser.add_argument("--retry-delay-seconds", type=float, default=None, help="两次尝试之间的等待时间")
    parser.add_argument("--state-file", type=Path, default=None)
    parser.add_argument("--workflow", default=None)
    parser.add_argument("--ref", default=None)
    parser.add_argument("--repo", default=None, help="GitHub 仓库，默认使用当前 gh 上下文")
    parser.add_argument("--dry-run", action="store_true", help="只扫描和展示候选比赛，不触发 Action")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = section(load_config(), "batch_upload")
    from_date_value = args.from_date if args.from_date is not None else get_str(config, "from_date", "2023-01-01")
    max_contests = args.max_contests if args.max_contests is not None else get_int(config, "max_contests", 0)
    max_retries = args.max_retries if args.max_retries is not None else get_int(config, "max_retries", 3)
    poll_seconds = args.poll_seconds if args.poll_seconds is not None else get_float(config, "poll_seconds", 15.0)
    run_timeout_seconds = (
        args.run_timeout_seconds
        if args.run_timeout_seconds is not None
        else get_float(config, "run_timeout_seconds", 2700.0)
    )
    discovery_timeout_seconds = (
        args.discovery_timeout_seconds
        if args.discovery_timeout_seconds is not None
        else get_float(config, "discovery_timeout_seconds", 90.0)
    )
    retry_delay_seconds = (
        args.retry_delay_seconds
        if args.retry_delay_seconds is not None
        else get_float(config, "retry_delay_seconds", 60.0)
    )
    state_file_value = args.state_file or Path(get_str(config, "state_file", str(DEFAULT_STATE_PATH.name)))
    state_file = state_file_value if state_file_value.is_absolute() else REPO_ROOT / state_file_value
    workflow = args.workflow or get_str(config, "workflow", DEFAULT_WORKFLOW)
    ref = args.ref or get_str(config, "ref", "main")
    configured_repo = get_str(config, "repo", "") or None
    repository = current_repository_slug(args.repo or configured_repo)
    if max_contests < 0:
        raise BatchUploadError("max-contests 不能小于 0")
    if max_retries < 0:
        raise BatchUploadError("max-retries 不能小于 0")
    if poll_seconds <= 0 or run_timeout_seconds <= 0 or discovery_timeout_seconds <= 0:
        raise BatchUploadError("等待时间必须大于 0")
    from_date = parse_date(from_date_value)
    until_date = parse_date(args.until_date)
    if from_date and until_date and from_date > until_date:
        raise BatchUploadError("from-date 不能晚于 until-date")

    contests = load_candidates(
        from_date=from_date,
        until_date=until_date,
        contest_ids=args.contest_id,
    )
    if max_contests:
        contests = contests[:max_contests]
    print(
        f"CANDIDATES count={len(contests)} from_date={from_date_value} "
        f"until_date={until_date or '-'} repo={repository or '-'} workflow={workflow} ref={ref}",
        flush=True,
    )
    if contests:
        print(
            "CANDIDATE_LIST "
            + ", ".join(
                f"{contest.contest_id}({contest.date or '-'}):{contest.name}" for contest in contests
            ),
            flush=True,
        )
    if not contests:
        return 0

    client = GhWorkflowClient(repo=args.repo or configured_repo)
    uploader = BatchUploader(
        client=client,
        state_path=state_file,
        workflow=workflow,
        ref=ref,
        max_retries=max_retries,
        poll_seconds=poll_seconds,
        run_timeout_seconds=run_timeout_seconds,
        discovery_timeout_seconds=discovery_timeout_seconds,
        retry_delay_seconds=retry_delay_seconds,
        repository=repository,
    )
    _, failed, _ = uploader.run(contests, dry_run=args.dry_run)
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print(
            "BATCH_UPLOAD_INTERRUPTED 已停止；当前比赛的断点已保留，重新运行会继续等待或恢复该 run。",
            file=sys.stderr,
        )
        raise SystemExit(130) from None
    except (BatchUploadError, OSError, subprocess.SubprocessError) as exc:
        print(f"BATCH_UPLOAD_FAILED error={shorten(str(exc), 1200)}", file=sys.stderr)
        raise SystemExit(1) from exc

#!/usr/bin/env python3
"""批量 CF Action 编排脚本的回归测试。"""

from __future__ import annotations

import datetime as dt
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cf_batch_upload import (
    BatchUploadError,
    BatchUploader,
    Contest,
    RunNotFoundError,
    WorkflowRun,
    load_candidates,
    summarize_failed_log,
)


class FakeWorkflowClient:
    def __init__(self, outcomes: list[bool]) -> None:
        self.outcomes = outcomes
        self.dispatches: list[int] = []
        self.run_ids: list[int] = []
        self.runs: dict[int, WorkflowRun] = {}
        self.next_run_id = 100

    def dispatch(self, workflow: str, ref: str, contest_id: int) -> None:
        self.dispatches.append(contest_id)

    def find_run(
        self,
        workflow: str,
        ref: str,
        created_after: dt.datetime,
        timeout_seconds: float,
        poll_seconds: float,
    ) -> WorkflowRun:
        run_id = self.next_run_id
        self.next_run_id += 1
        self.run_ids.append(run_id)
        success = self.outcomes.pop(0)
        run = WorkflowRun(
            run_id=run_id,
            status="completed",
            conclusion="success" if success else "failure",
            url=f"https://example.test/runs/{run_id}",
        )
        self.runs[run_id] = run
        return run

    def get_run(self, run_id: int) -> WorkflowRun:
        return self.runs[run_id]

    def failed_log(self, run_id: int) -> str:
        return f"failure log for {run_id}"


class TransientPollingClient(FakeWorkflowClient):
    def __init__(self) -> None:
        super().__init__([True])
        self.poll_errors = 1

    def get_run(self, run_id: int) -> WorkflowRun:
        if self.poll_errors:
            self.poll_errors -= 1
            raise BatchUploadError("temporary EOF")
        return super().get_run(run_id)


class StaleRunClient(FakeWorkflowClient):
    def __init__(self) -> None:
        super().__init__([True])
        self.stale_run_id = 999

    def get_run(self, run_id: int) -> WorkflowRun:
        if run_id == self.stale_run_id:
            raise RunNotFoundError(f"run {run_id} 不存在，丢弃旧断点并重新派发")
        return super().get_run(run_id)


class DetailedFailureClient(FakeWorkflowClient):
    def failed_log(self, run_id: int) -> str:
        return (
            "update\tUNKNOWN STEP\t2026-09-25T00:00:00Z\tRunner output\n"
            "update\tCrawl contests, build outputs, and refresh AI summaries\t"
            "2026-09-25T00:00:01Z\tAUTO_UPDATE_FAILED 命令失败（2）\n"
            "update\tCrawl contests, build outputs, and refresh AI summaries\t"
            "2026-09-25T00:00:02Z\tError: Process completed with exit code 1.\n"
        )


class BatchUploadTests(unittest.TestCase):
    def test_summarize_failed_log_extracts_workflow_step_and_error(self) -> None:
        step, excerpt = summarize_failed_log(
            "update\tUNKNOWN STEP\t2026-09-25T00:00:00Z\tRunner output\n"
            "update\tBuild outputs\t2026-09-25T00:00:01Z\tAUTO_UPDATE_FAILED command failed\n"
            "update\tBuild outputs\t2026-09-25T00:00:02Z\tError: Process completed with exit code 1.\n"
        )
        self.assertEqual(step, "Build outputs")
        self.assertIn("AUTO_UPDATE_FAILED", excerpt)
        self.assertIn("exit code 1", excerpt)

    def test_failed_console_log_identifies_phase_step_and_run_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            uploader = BatchUploader(
                client=DetailedFailureClient([False]),
                state_path=Path(directory) / "state.json",
                max_retries=0,
                retry_delay_seconds=0,
                sleep=lambda _: None,
            )
            with redirect_stdout(output):
                result = uploader.run([Contest(1778, "Round 848", dt.date(2023, 2, 1))])
        self.assertEqual(result, ([], [1778], []))
        text = output.getvalue()
        self.assertIn("CONTEST_FAILED contest=1778", text)
        self.assertIn("phase=workflow", text)
        self.assertIn("workflow_step=Crawl contests, build outputs, and refresh AI summaries", text)
        self.assertIn("CONTEST_FAILED_URL contest=1778", text)
        self.assertIn("exit code 1", text)

    def test_load_candidates_only_returns_incomplete_contests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "contests.json").write_text(
                json.dumps([
                    {"id": 1778, "name": "Round 848", "date": "2023-02-01"},
                    {"id": 1787, "name": "Round 849", "date": "2023-02-05"},
                    {"id": 2022, "name": "Old Round", "date": "2022-12-31"},
                ]),
                encoding="utf-8",
            )
            (root / "records.json").write_text(
                json.dumps([
                    {"contest_id": 1778, "index": "A"},
                    {"contest_id": 1778, "index": "B"},
                    {"contest_id": 1787, "index": "A"},
                    {"contest_id": 2022, "index": "A"},
                ]),
                encoding="utf-8",
            )
            (root / "problem-insights.json").write_text(
                json.dumps({"records": [{"problem_key": "1787A"}]}),
                encoding="utf-8",
            )
            result = load_candidates(
                contests_path=root / "contests.json",
                records_path=root / "records.json",
                insights_path=root / "problem-insights.json",
            )
        self.assertEqual([item.contest_id for item in result], [1778])

    def test_explicit_contest_ids_bypass_publish_filter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "contests.json").write_text("[]", encoding="utf-8")
            (root / "records.json").write_text("[]", encoding="utf-8")
            (root / "problem-insights.json").write_text("{}", encoding="utf-8")
            result = load_candidates(
                contests_path=root / "contests.json",
                records_path=root / "records.json",
                insights_path=root / "problem-insights.json",
                contest_ids=[2262],
            )
        self.assertEqual(result, [Contest(2262, "Contest 2262", None)])

    def test_successful_contest_is_saved_and_skipped_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            client = FakeWorkflowClient([True])
            uploader = BatchUploader(
                client=client,
                state_path=state_path,
                retry_delay_seconds=0,
                sleep=lambda _: None,
            )
            contest = Contest(1778, "Round 848", dt.date(2023, 2, 1))
            first = uploader.run([contest])
            second = BatchUploader(
                client=client,
                state_path=state_path,
                retry_delay_seconds=0,
                sleep=lambda _: None,
            ).run([contest])
            state: dict[str, Any] = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(first, ([1778], [], []))
        self.assertEqual(second, ([], [], [1778]))
        self.assertEqual(client.dispatches, [1778])
        self.assertEqual(state["contests"]["1778"]["status"], "success")

    def test_failed_action_retries_and_then_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            client = FakeWorkflowClient([False, True])
            uploader = BatchUploader(
                client=client,
                state_path=state_path,
                max_retries=3,
                retry_delay_seconds=0,
                sleep=lambda _: None,
            )
            result = uploader.run([Contest(1778, "Round 848", dt.date(2023, 2, 1))])
            state: dict[str, Any] = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(result, ([1778], [], []))
        self.assertEqual(client.dispatches, [1778, 1778])
        self.assertEqual(state["contests"]["1778"]["attempts"], 2)
        self.assertEqual(state["contests"]["1778"]["total_attempts"], 2)

    def test_contest_failure_does_not_stop_following_contests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            client = FakeWorkflowClient([False, False, False, False, True])
            uploader = BatchUploader(
                client=client,
                state_path=state_path,
                max_retries=3,
                retry_delay_seconds=0,
                sleep=lambda _: None,
            )
            result = uploader.run([
                Contest(1778, "Round 848", dt.date(2023, 2, 1)),
                Contest(1788, "Round 851", dt.date(2023, 2, 9)),
            ])
        self.assertEqual(result, ([1788], [1778], []))
        self.assertEqual(client.dispatches, [1778, 1778, 1778, 1778, 1788])

    def test_transient_poll_error_does_not_dispatch_a_duplicate_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = TransientPollingClient()
            uploader = BatchUploader(
                client=client,
                state_path=Path(directory) / "state.json",
                max_retries=1,
                retry_delay_seconds=0,
                poll_seconds=0.01,
                sleep=lambda _: None,
            )
            result = uploader.run([Contest(1778, "Round 848", dt.date(2023, 2, 1))])
        self.assertEqual(result, ([1778], [], []))
        self.assertEqual(client.dispatches, [1778])

    def test_stale_resume_run_is_discarded_and_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "contests": {
                            "1778": {
                                "contest_id": 1778,
                                "name": "Round 848",
                                "date": "2023-02-01",
                                "status": "running",
                                "attempts": 1,
                                "last_run_id": 999,
                                "last_run_url": "https://github.com/Fyrskd/XCPC/actions/runs/999",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            client = StaleRunClient()
            uploader = BatchUploader(
                client=client,
                state_path=state_path,
                max_retries=1,
                retry_delay_seconds=0,
                sleep=lambda _: None,
            )
            result = uploader.run([Contest(1778, "Round 848", dt.date(2023, 2, 1))])
        self.assertEqual(result, ([1778], [], []))
        self.assertEqual(client.dispatches, [1778])

    def test_success_from_another_repository_is_not_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "contests": {
                            "1778": {
                                "contest_id": 1778,
                                "name": "Round 848",
                                "date": "2023-02-01",
                                "status": "success",
                                "attempts": 1,
                                "last_run_id": 999,
                                "last_run_url": "https://github.com/Fyrskd/XCPC/actions/runs/999",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            client = FakeWorkflowClient([True])
            uploader = BatchUploader(
                client=client,
                state_path=state_path,
                repository="Fyrskd/cf-knowledge",
                max_retries=1,
                retry_delay_seconds=0,
                sleep=lambda _: None,
            )
            result = uploader.run([Contest(1778, "Round 848", dt.date(2023, 2, 1))])
        self.assertEqual(result, ([1778], [], []))
        self.assertEqual(client.dispatches, [1778])


if __name__ == "__main__":
    unittest.main()

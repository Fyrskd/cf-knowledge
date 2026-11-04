from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cf_server_update as server


class ServerUpdateTests(unittest.TestCase):
    def write_fixture(self, root: Path) -> dict[str, Any]:
        raw = [{
            "contest_id": 1, "index": "A",
            "statement_text": "You are given an array of integers and must choose a valid subsequence. " * 4,
        }]
        row: dict[str, Any] = {
            "problem_key": "1A", "statement_brief": "给定数组，求合法子序列。",
            "solution_brief": "", "transformed_statement": "", "key_observations": [],
            "extraction_status": "missing_editorial",
        }
        for name in server.DATA_FILES:
            (root / name).write_text("[]", encoding="utf-8")
        (root / "records.json").write_text(json.dumps(raw), encoding="utf-8")
        (root / "problem-insights.json").write_text(json.dumps({
            "records": [row], "summary": {"total_problems": 1, "filtered_out_problems": 0},
        }), encoding="utf-8")
        browser = root / "problem-insights-browser"
        browser.mkdir()
        for name in server.STATIC_FILES:
            (browser / name).write_text(name, encoding="utf-8")
        self.write_browser(root, row)
        return row

    def write_browser(self, root: Path, row: dict[str, Any]) -> None:
        browser_row = {
            "key": row["problem_key"], "statementBrief": row["statement_brief"],
            "solutionBrief": row["solution_brief"], "transformedStatement": row["transformed_statement"],
            "keyObservations": row["key_observations"], "extractionStatus": row["extraction_status"],
        }
        (root / "problem-insights-browser/data.js").write_text(
            "window.CF_INSIGHTS_DATA = " + json.dumps({"contests": [{"problems": [browser_row]}]}) + ";\n",
            encoding="utf-8",
        )

    def test_valid_statement_without_editorial_can_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_fixture(root)
            server.validate_publication(root)

    def test_rejects_pending_or_partial_solution_and_stale_browser(self) -> None:
        for field, value in (
            ("extraction_status", "pending_ai"), ("statement_brief", "待生成"),
            ("transformed_statement", "尚未完成"), ("solution_brief", "没有来源的题解"),
            ("statement_brief", "浏览器中仍然是旧摘要"),
        ):
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write_fixture(root)
                published = server.read_json(root / "problem-insights.json")
                published["records"][0][field] = value
                (root / "problem-insights.json").write_text(json.dumps(published), encoding="utf-8")
                with self.assertRaises(ValueError):
                    server.validate_publication(root)

    def test_rejects_invalid_checkpoint_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_fixture(root)
            (root / "state.json").write_text("{", encoding="utf-8")
            with self.assertRaises(subprocess.CalledProcessError):
                server.validate_publication(root)

    def test_reuses_existing_editorial_availability_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.write_fixture(root)
            raw = server.read_json(root / "records.json")
            raw[0].update({"editorial_quality": "partial", "editorial_text": "Observe the invariant in the given array. " * 4})
            (root / "records.json").write_text(json.dumps(raw), encoding="utf-8")
            row.update({"solution_brief": "维护数组中的不变量。", "extraction_status": "ai_generated_partial_editorial"})
            published = server.read_json(root / "problem-insights.json")
            published["records"] = [row]
            (root / "problem-insights.json").write_text(json.dumps(published), encoding="utf-8")
            self.write_browser(root, row)
            server.validate_publication(root)

    def test_incomplete_copy_keeps_previous_site(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_fixture(root)
            web = root / "web"
            first = server.publish_static(root, web)
            (root / "problem-insights-browser/styles.css").unlink()
            with self.assertRaises(FileNotFoundError):
                server.publish_static(root, web)
            self.assertEqual((web / "current").resolve(), first.resolve())
            self.assertEqual((web / "current/index.html").read_text(), "index.html")

    def test_backup_contains_source_data_and_rotates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_fixture(root)
            backups = root / "backups"
            first = server.backup_data(root, backups, 1)
            second = server.backup_data(root, backups, 1)
            self.assertFalse(first.exists())
            with tarfile.open(second) as archive:
                self.assertIn("records.json", archive.getnames())
                self.assertNotIn("config.local.json", archive.getnames())

    def test_ai_failure_keeps_crawl_checkpoint_and_does_not_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(server, "ROOT", root), patch.object(server, "load_config", return_value={}), \
                    patch.object(server, "backup_data") as backup, \
                    patch.object(server, "run", side_effect=[None, RuntimeError("AI 失败")]) as run, \
                    patch.object(server, "check_and_publish") as publish:
                with self.assertRaisesRegex(RuntimeError, "AI 失败"):
                    server.main([])
                backup.assert_called_once()
                self.assertEqual(run.call_count, 2)
                self.assertIn("crawl", run.call_args_list[0].args[0])
                publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Regression tests for the incremental Codeforces update wrapper."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cf_auto_update as updater  # noqa: E402
import cf_knowledge_index as indexer  # noqa: E402
import cf_ai_manager as ai_manager  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_problem_insights as insight_builder  # noqa: E402


class AutoUpdateTests(unittest.TestCase):
    @staticmethod
    def _statement() -> str:
        return (
            "You are given an array of integers and must choose a valid subsequence. "
            "For every operation, follow the stated constraints and output the maximum "
            "possible value for the given input. "
        )

    @staticmethod
    def _record(
        *,
        editorial: str = "",
        editorial_quality: str = "url_only",
        statement: str = "__default__",
        statement_quality: str = "available",
    ) -> dict:
        statement_text = AutoUpdateTests._statement() if statement == "__default__" else statement
        return {
            "contest_id": 1,
            "index": "A",
            "title": "Sample Problem",
            "rating": 800,
            "problem_url": "https://codeforces.com/contest/1/problem/A",
            "editorial_url": "https://codeforces.com/blog/entry/1",
            "statement_text": statement_text,
            "statement_quality": statement_quality,
            "editorial_text": editorial,
            "editorial_quality": editorial_quality,
            "tags": ["implementation"],
        }

    def test_publish_gate_keeps_statement_but_withholds_missing_solution_summary(self) -> None:
        record = self._record()
        with patch.object(insight_builder, "PROBLEM_OVERRIDES", {}), patch.object(
            insight_builder, "AI_GENERATED_PATH", Path("/tmp/cf-ai-generated-insights-does-not-exist.json")
        ):
            rows = insight_builder.build_records([record])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["statement_brief"])
        self.assertEqual(rows[0]["solution_brief"], "")
        self.assertEqual(rows[0]["key_observations"], [])
        self.assertEqual(rows[0]["extraction_status"], "missing_editorial")

    def test_publish_gate_drops_record_without_statement_summary(self) -> None:
        record = self._record(statement="", statement_quality="missing")
        with patch.object(insight_builder, "PROBLEM_OVERRIDES", {}), patch.object(
            insight_builder, "AI_GENERATED_PATH", Path("/tmp/cf-ai-generated-insights-does-not-exist.json")
        ):
            rows = insight_builder.build_records([record])
        self.assertEqual(rows, [])

    def test_publish_gate_drops_pending_ai_statement_and_solution(self) -> None:
        editorial = "Given the editorial evidence, observe the invariant and maintain the required state. " * 8
        record = self._record(editorial=editorial, editorial_quality="complete")
        with patch.object(insight_builder, "PROBLEM_OVERRIDES", {}), patch.object(
            insight_builder, "AI_GENERATED_PATH", Path("/tmp/cf-ai-generated-insights-does-not-exist.json")
        ):
            rows = insight_builder.build_records([record])
        self.assertEqual(rows, [])

    def test_ai_config_accepts_ci_endpoint_and_model_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "ai-config.local.json"
            config_path.write_text("{}", encoding="utf-8")
            with patch.object(ai_manager, "AI_CONFIG_PATH", config_path), patch.dict(
                ai_manager.os.environ,
                {
                    "AI_BASE_URL": "https://api.zhehentiaohe.cn/v1",
                    "AI_MODEL": "gpt-6-luna",
                    "AI_TIMEOUT_SECONDS": "240",
                },
            ):
                config = ai_manager.load_config()
        self.assertEqual(config.base_url, "https://api.zhehentiaohe.cn/v1")
        self.assertEqual(config.model, "gpt-6-luna")
        self.assertEqual(config.timeout_seconds, 240)

    def test_problem_keys_and_incremental_new_count(self) -> None:
        before = updater.problem_keys([
            {"contest_id": 2262, "index": "A"},
            {"contest_id": 2262, "index": "B"},
        ])
        after = updater.problem_keys([
            {"contest_id": 2262, "index": "A"},
            {"contest_id": 2262, "index": "B"},
            {"contest_id": 2263, "index": "A"},
        ])
        self.assertEqual(after - before, {"2263A"})

    def test_merge_contests_keeps_historical_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "contests.json"
            with patch.object(updater, "CONTESTS_PATH", target):
                updater.merge_contests(
                    [{"id": 1, "startTimeSeconds": 10, "date": "2020-01-01"}],
                    [{"id": 2, "startTimeSeconds": 20, "date": "2020-01-02"}],
                )
            result = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual([item["id"] for item in result], [1, 2])

    def test_failure_log_is_deduplicated_and_capped(self) -> None:
        failures = [
            {"url": "https://example.invalid/a", "error": "old"},
        ]
        failures.extend({"url": f"https://example.invalid/{i}", "error": "x"} for i in range(600))
        failures.append({"url": "https://example.invalid/a", "error": "latest"})
        compacted = indexer.compact_failures(failures)
        self.assertLessEqual(len(compacted), 500)
        self.assertEqual(
            next(item["error"] for item in compacted if item["url"].endswith("/a")),
            "latest",
        )

    def test_missing_statement_is_skipped_before_ai_call(self) -> None:
        rows = [
            {"problem_key": "1A", "manual_override": False, "has_current_ai": False, "statement_available": False},
            {"problem_key": "1B", "manual_override": False, "has_current_ai": False, "statement_available": True},
        ]

        class Config:
            def resolved_api_key(self) -> str:
                return "test-key"

        with patch.object(ai_manager, "problem_status_rows", return_value=rows), \
                patch.object(ai_manager, "load_config", return_value=Config()), \
                patch.object(ai_manager, "generate_many", return_value={"success": 1, "failed": 0}) as generate:
            pending, success, failed = updater.generate_pending(10, require_ai=True)
        self.assertEqual((pending, success, failed), (1, 1, 0))
        generate.assert_called_once_with(["1B"], rebuild=False)

    def test_required_ai_allows_partial_generation(self) -> None:
        rows = [
            {"problem_key": "1A", "manual_override": False, "has_current_ai": False, "statement_available": True},
            {"problem_key": "1B", "manual_override": False, "has_current_ai": False, "statement_available": True},
        ]

        class Config:
            def resolved_api_key(self) -> str:
                return "test-key"

        with patch.object(ai_manager, "problem_status_rows", return_value=rows), \
                patch.object(ai_manager, "load_config", return_value=Config()), \
                patch.object(ai_manager, "generate_many", return_value={"success": 1, "failed": 1}):
            self.assertEqual(updater.generate_pending(1000, require_ai=True), (2, 1, 1))

    def test_required_ai_rejects_when_every_selected_problem_fails(self) -> None:
        rows = [
            {"problem_key": "1A", "manual_override": False, "has_current_ai": False, "statement_available": True},
        ]

        class Config:
            def resolved_api_key(self) -> str:
                return "test-key"

        with patch.object(ai_manager, "problem_status_rows", return_value=rows), \
                patch.object(ai_manager, "load_config", return_value=Config()), \
                patch.object(ai_manager, "generate_many", return_value={"success": 0, "failed": 1}):
            with self.assertRaisesRegex(updater.AutoUpdateError, "全部失败"):
                updater.generate_pending(1000, require_ai=True)

    def test_summary_quality_rejects_mixed_language_and_shell(self) -> None:
        record = {"editorial_quality": "complete", "editorial_text": "x" * 300}
        insight = {
            "statement_brief": "time limit per test, determine whether this is possible",
            "transformed_statement": "time limit per test, determine whether this is possible",
            "solution_brief": "We can use a segment tree and then output the answer.",
            "key_observations": ["The first observation is useful.", "Then we can process every query."],
        }
        issues = ai_manager.summary_quality_issues(insight, record)
        self.assertIn("mixed_language", issues)
        self.assertIn("summary_noise:time limit", issues)
        self.assertIn("transformation_repeats_statement", issues)

    def test_summary_quality_rejects_statement_without_enough_context(self) -> None:
        record = {"editorial_quality": "complete", "editorial_text": "x" * 300}
        insight = {
            "statement_brief": "求最大值。",
            "transformed_statement": "把问题转成区间上的最优决策。",
            "solution_brief": "枚举边界并维护最优状态，得到答案。",
            "key_observations": ["边界状态足以决定后续转移。", "所有转移都满足同一个单调性。"],
        }
        self.assertIn("statement_too_short", ai_manager.summary_quality_issues(insight, record))

    def test_summary_quality_accepts_specific_chinese(self) -> None:
        record = {"editorial_quality": "complete", "editorial_text": "x" * 300}
        insight = {
            "statement_brief": "给定数组和一组参数，需要从候选整数中选出一个子集，使每个参数对应的整除型 MEX 都等于指定值。",
            "transformed_statement": "每个约束会产生一个必须命中的区间和一个禁止选数的区间。",
            "solution_brief": "用差分数组合并所有禁区，再选择全部不在禁区中的数；由于保留了所有可选数，所有必须命中的区间都会被覆盖。",
            "key_observations": [
                "当函数值为 x 时，前 x 个长度为 k 的块都必须至少选一个数。",
                "第 x+1 个块完全禁止选择，因此全部禁区可以用差分数组统一维护。",
            ],
        }
        self.assertEqual(ai_manager.summary_quality_issues(insight, record), [])

    def test_summary_quality_ignores_formula_and_inline_code_tokens(self) -> None:
        record = {"editorial_quality": "complete", "editorial_text": "x" * 300}
        insight = {
            "statement_brief": "给定一个整数数组，需要按照规则选择元素并求出满足限制的最优结果。",
            "transformed_statement": "把判定过程写成公式 `$if x > 0 then y = 1$`，状态只保留边界信息。",
            "solution_brief": "按状态转移计算所有可达情况，并在最终状态中取出最优结果。",
            "key_observations": [
                "固定当前状态后，后续决策只依赖边界信息，因此不必保留完整历史。",
                "每个状态的转移覆盖互斥情况，取最优值即可保证答案完整。",
            ],
        }
        self.assertNotIn("mixed_language", ai_manager.summary_quality_issues(insight, record))

    def test_language_repair_prompt_includes_quality_feedback(self) -> None:
        prompt = ai_manager.make_user_prompt(
            self._record(editorial="有效题解正文。" * 80, editorial_quality="complete"),
            ai_manager.AiConfig(),
            repair=True,
            quality_issues=["mixed_language"],
        )
        self.assertIn("mixed_language", prompt)
        self.assertIn("所有自然语言字段必须使用中文", prompt)

    def test_generate_one_retries_with_detected_quality_issue(self) -> None:
        record = self._record(editorial="有效题解正文。" * 80, editorial_quality="complete")
        valid = {
            "statement_brief": "给定一个整数数组，需要按照题目规则选择元素并求出满足所有限制的最优结果。",
            "transformed_statement": "把每次选择对后续状态的影响抽象成有限状态之间的转移。",
            "key_observations": [
                "固定当前状态后，后续决策只依赖状态中的边界信息，因此不必保留完整历史。",
                "每个状态的转移都覆盖互斥情况，取最优值即可保证答案完整。",
            ],
            "solution_brief": "按状态转移计算所有可达情况，并在最终状态中取最优结果。",
            "primary_topic": "动态规划与状态设计",
            "secondary_topics": [],
            "extraction_status": "ai_generated_with_editorial",
            "source_provenance": "statement、editorial",
            "quality_flags": [],
        }
        invalid = dict(valid)
        invalid.update({
            "statement_brief": "Given an array, determine the maximum possible result for every query.",
            "transformed_statement": "Model the problem as a graph and choose the best path.",
            "solution_brief": "Use a graph and process each query to output the answer.",
            "key_observations": [
                "The first observation reduces the state space.",
                "Then process every query independently.",
            ],
        })
        responses = [
            ({"output_text": json.dumps(invalid, ensure_ascii=False)}, "first-request"),
            ({"output_text": json.dumps(valid, ensure_ascii=False)}, "second-request"),
        ]
        with patch.object(ai_manager, "post_json_with_retries", side_effect=responses) as request:
            insight, request_id = ai_manager.generate_one(record, ai_manager.AiConfig())
        self.assertEqual(request_id, "second-request")
        self.assertEqual(insight["primary_topic"], "动态规划与状态设计")
        self.assertEqual(request.call_count, 2)
        second_prompt = request.call_args_list[1].args[2]["input"][1]["content"][0]["text"]
        self.assertIn("mixed_language", second_prompt)

    def test_ai_limit_zero_does_not_select_a_problem(self) -> None:
        with patch.object(ai_manager, "problem_status_rows") as rows:
            self.assertEqual(updater.generate_pending(0, require_ai=False), (0, 0, 0))
        rows.assert_not_called()

    def test_contest_id_limits_ai_generation_to_one_contest(self) -> None:
        rows = [
            {"problem_key": "1A", "contest_id": 1, "manual_override": False, "has_current_ai": False, "statement_available": True},
            {"problem_key": "2A", "contest_id": 2, "manual_override": False, "has_current_ai": False, "statement_available": True},
        ]

        class Config:
            def resolved_api_key(self) -> str:
                return "test-key"

        with patch.object(ai_manager, "problem_status_rows", return_value=rows), \
                patch.object(ai_manager, "load_config", return_value=Config()), \
                patch.object(ai_manager, "generate_many", return_value={"success": 1, "failed": 0}) as generate:
            result = updater.generate_pending(-1, require_ai=True, contest_id=2)
        self.assertEqual(result, (1, 1, 0))
        generate.assert_called_once_with(["2A"], rebuild=False)

    def test_ai_limit_minus_one_selects_all_pending(self) -> None:
        rows = [
            {"problem_key": "1A", "manual_override": False, "has_current_ai": False, "statement_available": True},
            {"problem_key": "1B", "manual_override": False, "has_current_ai": False, "statement_available": True},
        ]

        class Config:
            def resolved_api_key(self) -> str:
                return "test-key"

        with patch.object(ai_manager, "problem_status_rows", return_value=rows), \
                patch.object(ai_manager, "load_config", return_value=Config()), \
                patch.object(ai_manager, "generate_many", return_value={"success": 2, "failed": 0}) as generate:
            result = updater.generate_pending(-1, require_ai=True)
        self.assertEqual(result, (2, 2, 0))
        generate.assert_called_once_with(["1A", "1B"], rebuild=False)

    def test_refresh_ai_selects_existing_ai_only(self) -> None:
        rows = [
            {"problem_key": "1A", "manual_override": False, "has_current_ai": True, "statement_available": True},
            {"problem_key": "1B", "manual_override": False, "has_current_ai": False, "statement_available": True},
            {"problem_key": "1C", "manual_override": True, "has_current_ai": False, "statement_available": True},
        ]

        class Config:
            def resolved_api_key(self) -> str:
                return "test-key"

        with patch.object(ai_manager, "problem_status_rows", return_value=rows), \
                patch.object(ai_manager, "load_config", return_value=Config()), \
                patch.object(ai_manager, "generate_many", return_value={"success": 1, "failed": 0}) as generate:
            result = updater.generate_pending(-1, require_ai=True, refresh_ai=True)
        self.assertEqual(result, (1, 1, 0))
        generate.assert_called_once_with(["1A"], rebuild=False)

    def test_corpus_summary_uses_statement_text_when_quality_is_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = root / "records.json"
            contests = root / "contests.json"
            records.write_text(json.dumps([
                {"statement_quality": None, "statement_text": "Given an array, find the maximum possible value. Input contains n and the array. Output the answer."},
                {"statement_quality": "missing", "statement_text": ""},
            ]), encoding="utf-8")
            contests.write_text("[]", encoding="utf-8")
            with patch.object(updater, "RECORDS_PATH", records), patch.object(updater, "CONTESTS_PATH", contests):
                summary = updater.corpus_summary()
        self.assertEqual(summary["problems"], 2)
        self.assertEqual(summary["statement_gaps"], 1)
        self.assertEqual(summary["statements_available"], 1)
if __name__ == "__main__":
    unittest.main()

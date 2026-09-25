#!/usr/bin/env python3
"""Regression tests for the evidence-preserving Codeforces indexer."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cf_knowledge_index as cf  # noqa: E402


class DynamicTutorialTests(unittest.TestCase):
    def test_contest_window_can_select_a_specific_historical_contest(self) -> None:
        contests = [
            {
                "id": 2262,
                "type": "CF",
                "phase": "FINISHED",
                "startTimeSeconds": 1_757_683_200,
                "name": "Codeforces Round 1120 (Div. 1)",
            },
            {
                "id": 2263,
                "type": "CF",
                "phase": "FINISHED",
                "startTimeSeconds": 1_757_683_200,
                "name": "Codeforces Round 1120 (Div. 2)",
            },
        ]
        with patch.object(cf, "cf_api", return_value=contests):
            result = cf.contest_window(
                object(),
                datetime(2020, 1, 1, tzinfo=timezone.utc),
                datetime(2020, 1, 2, tzinfo=timezone.utc),
                contest_id=2262,
            )
        self.assertEqual([item["id"] for item in result], [2262])

    def test_contest_window_includes_icpc_scored_codeforces_rounds_only(self) -> None:
        contests = [
            {
                "id": 2266,
                "type": "ICPC",
                "phase": "FINISHED",
                "startTimeSeconds": 1_790_001_300,
                "name": "Codeforces Round 1122 (Div. 3)",
            },
            {
                "id": 2206,
                "type": "ICPC",
                "phase": "FINISHED",
                "startTimeSeconds": 1_790_001_300,
                "name": "2026 ICPC Asia Pacific Championship - Online Mirror",
            },
        ]
        with patch.object(cf, "cf_api", return_value=contests):
            result = cf.contest_window(
                object(),
                datetime(2026, 9, 21, tzinfo=timezone.utc),
                datetime(2026, 9, 22, tzinfo=timezone.utc),
            )
        self.assertEqual([item["id"] for item in result], [2266])

    def test_problem_metadata_falls_back_to_contest_standings(self) -> None:
        def fake_cf_api(_fetcher: object, method: str, **params: object) -> dict:
            if method == "problemset.problems":
                return {
                    "problems": [
                        {"contestId": 1784, "index": "A", "name": "Monsters"},
                    ]
                }
            if method == "contest.standings":
                self.assertEqual(params, {"contestId": 1785})
                return {
                    "problems": [
                        {"contestId": 1785, "index": "A", "name": "Monsters"},
                        {"contestId": 1785, "index": "F", "name": "Minimums or Medians"},
                    ]
                }
            raise AssertionError(f"unexpected API method: {method}")

        with patch.object(cf, "cf_api", side_effect=fake_cf_api):
            result = cf.problem_metadata(object(), [1785])

        self.assertEqual(result[(1785, "A")]["name"], "Monsters")
        self.assertEqual(result[(1785, "F")]["name"], "Minimums or Medians")

    def test_csrf_token_and_problem_codes_are_parsed(self) -> None:
        page = (
            '<meta name="X-Csrf-Token" content="0123456789abcdef0123">'
            '<div class="problemTutorial" problemcode="2057A">'
            'Tutorial is loading...</div>'
        )
        self.assertEqual(cf.blog_csrf_token(page), "0123456789abcdef0123")
        self.assertEqual(cf.blog_csrf_token("<html></html>"), None)
        reversed_attrs = (
            '<meta content="fedcba9876543210fedc" '
            'name="X-Csrf-Token" data-extra="1">'
        )
        self.assertEqual(cf.blog_csrf_token(reversed_attrs), "fedcba9876543210fedc")

    def test_metadata_only_mirror_page_has_no_statement(self) -> None:
        raw = b"""
        <h3>Problems</h3>
        <table><tr><td>A1</td><td>Floor of MEX</td></tr></table>
        <h3>Tutorials</h3>
        <table></table>
        <p>Codeforces search problemset</p>
        <p>Submissions</p>
        <p>Back to search problems</p>
        """
        parsed = cf.parse_mirror_problem(raw)
        self.assertEqual(parsed["mirror_text"], "")
        self.assertEqual(parsed["statement_quality"], "missing")

    def test_statement_table_is_kept_when_mirror_has_real_problem_text(self) -> None:
        raw = b"""
        <h3>Problems</h3>
        <table><tr><td>A</td><td>Example</td></tr></table>
        <table><tr><td><p>Given an array, find the maximum possible value.</p>
        <p>Input contains n and the array. Output the answer.</p></td></tr></table>
        <h3>Tutorials</h3>
        <table></table>
        """
        parsed = cf.parse_mirror_problem(raw)
        self.assertIn("Given an array", parsed["mirror_text"])
        self.assertEqual(parsed["statement_quality"], "available")

    def test_official_problem_page_statement_block_is_parsed(self) -> None:
        raw = b"""
        <html><body>
        <div class="problem-statement">
          <div class="header">A. Example</div>
          <div class="problem- statement"><p>This is not the target.</p></div>
          <p>Given an array, find the maximum possible value.</p>
          <div class="input-specification"><p>Input contains n and the array.</p></div>
          <div class="output-specification"><p>Output the answer.</p></div>
        </div>
        <div class="problem-statement"><p>Another problem.</p></div>
        </body></html>
        """
        parsed = cf.parse_codeforces_problem(raw)
        self.assertIn("Given an array", parsed["mirror_text"])
        self.assertIn("Input contains n", parsed["mirror_text"])
        self.assertEqual(parsed["statement_quality"], "available")

    def test_statement_fallback_uses_official_page_after_metadata_mirror(self) -> None:
        mirror = b"""
        <h3>Problems</h3>
        <table><tr><td>A</td><td>Example</td></tr></table>
        <h3>Tutorials</h3><table></table>
        <p>Codeforces search problemset</p><p>Submissions</p>
        """
        official = b"""
        <div class="problem-statement">
          <p>Given an array, find the maximum possible value.</p>
          <p>Input contains n. Output the answer.</p>
        </div>
        """

        class FakeFetcher:
            def get(self, url: str) -> bytes:
                return mirror if "cf-problemset" in url else official

        result = cf.fetch_statement_with_fallback(
            FakeFetcher(),
            {
                "contest_id": 1,
                "index": "A",
                "statement_url": "https://cf-problemset.example/1/A",
                "problem_url": "https://codeforces.example/1/A",
            },
        )
        self.assertEqual(result["statement_source"], "codeforces-problem-page")
        self.assertEqual(result["statement_source_url"], "https://codeforces.example/1/A")
        self.assertEqual(result["statement_quality"], "available")
        self.assertEqual(
            [item["status"] for item in result["statement_source_attempts"]],
            ["no_statement", "available"],
        )

    def test_statement_refresh_preserves_existing_tutorial_url(self) -> None:
        record = {
            "tutorial_url": "https://codeforces.com/blog/entry/123",
            "tutorial_source": "codeforces-blog",
            "tutorial_links": [],
        }
        cf.apply_statement_result(
            record,
            {
                "statement_text": "Given an array, find the answer. Input contains n. Output the answer.",
                "statement_quality": "available",
                "statement_links": [],
                "tutorial_links": [],
                "statement_source": "codeforces-problem-page",
                "statement_source_url": "https://codeforces.com/contest/1/problem/A",
                "statement_source_attempts": [],
                "statement_raw": b"statement",
                "errors": [],
            },
        )
        self.assertEqual(record["tutorial_url"], "https://codeforces.com/blog/entry/123")
        self.assertEqual(record["tutorial_source"], "codeforces-blog")

    def test_failed_statement_refresh_preserves_existing_statement(self) -> None:
        record = {
            "statement_text": (
                "Given an array, find the maximum possible answer. "
                "Input contains n and the array. Output the answer for every test case."
            ),
            "statement_quality": "available",
            "statement_source": "cf-problemset-mirror",
            "statement_source_url": "https://cf-problemset.example/1/A",
        }
        cf.apply_statement_result(
            record,
            {
                "statement_text": "",
                "statement_quality": "missing",
                "statement_links": [],
                "tutorial_links": [],
                "statement_source": None,
                "statement_source_url": None,
                "statement_source_attempts": [],
                "statement_raw": None,
                "errors": [],
            },
        )
        self.assertIn("Given an array", record["statement_text"])
        self.assertEqual(record["statement_quality"], "available")
        self.assertEqual(record["statement_source"], "cf-problemset-mirror")

    def test_historical_statement_with_trailing_navigation_is_kept(self) -> None:
        text = (
            "Problems Solved Index Name Rating Given an array, find the answer. "
            "Input contains the array. Output the result. Back to search problems"
        )
        self.assertTrue(cf.is_problem_statement(text))

    def test_dynamic_placeholder_is_replaced(self) -> None:
        raw = (
            '<h2>2057A</h2>'
            '<div class="problemTutorial" problemcode="2057A">'
            'Tutorial is loading...</div>'
        )
        merged = cf.merge_dynamic_tutorials(
            raw, {"2057A": "<p>Observe the unique zero row.</p>"}
        )
        self.assertIn("unique zero row", merged)
        self.assertNotIn("Tutorial is loading", merged)

        reversed_attrs = (
            '<div problemcode="2057A" data-x="1" '
            'class="problemTutorial">Tutorial is loading...</div>'
        )
        self.assertNotIn(
            "Tutorial is loading",
            cf.merge_dynamic_tutorials(reversed_attrs, {"2057A": "<p>Body</p>"}),
        )

        nested = (
            '<div class="problemTutorial" problemcode="2057A">'
            'Tutorial is loading...</div>'
        )
        hydrated = cf.merge_dynamic_tutorials(
            nested,
            {"2057A": '<h3>2057A</h3><div class="ttypography">'
                      '<p>Use this nested block.</p></div>'},
        )
        self.assertEqual(len(cf._dynamic_problem_section_matches(hydrated)), 1)
        self.assertIn("Use this nested block", cf.clean_text(hydrated))

    def test_dynamic_placeholder_is_preserved_when_body_missing(self) -> None:
        raw = (
            '<div class="problemTutorial" problemcode="2057A">'
            'Tutorial is loading...</div>'
        )
        self.assertEqual(cf.merge_dynamic_tutorials(raw, {}), raw)

    def test_fake_post_fetcher_hydrates_blog_without_network(self) -> None:
        class FakeFetcher:
            def __init__(self):
                self.posts = []

            def post(self, url, form, headers=None):
                self.posts.append((url, form, headers))
                return json.dumps({
                    "success": "true",
                    "html": "<p>Use a parity invariant.</p>",
                }).encode()

        page = (
            '<span class="csrf-token" data-csrf="0123456789abcdef0123"></span>'
            '<div class="problemTutorial" problemcode="2057A">'
            'Tutorial is loading...</div>'
        )
        fake = FakeFetcher()
        found = cf.fetch_problem_tutorials(fake, "https://codeforces.com/blog/entry/1", page)
        self.assertEqual(found, {"2057A": "<p>Use a parity invariant.</p>"})
        self.assertEqual(fake.posts[0][1]["problemCode"], "2057A")
        self.assertEqual(fake.posts[0][2]["X-Csrf-Token"], "0123456789abcdef0123")


class ExistingToolReuseTests(unittest.TestCase):
    def test_incomplete_queue_includes_statement_gap_with_complete_editorial(self) -> None:
        record = {
            "statement_text": "",
            "editorial_quality": "complete",
            "editorial_status": "official",
        }
        self.assertTrue(cf.record_needs_enrichment(record))

    def test_complete_record_is_not_in_incomplete_queue(self) -> None:
        record = {
            "statement_text": (
                "Given an array, find the maximum possible answer. "
                "Input contains n and the array. Output the answer for every test case."
            ),
            "editorial_quality": "complete",
            "editorial_status": "official",
        }
        self.assertFalse(cf.record_needs_enrichment(record))

    def test_legacy_statement_text_repairs_missing_quality(self) -> None:
        record = {
            "statement_quality": "missing",
            "statement_url": "https://cf-problemset.herokuapp.com/contest/1/A/",
            "statement_text": (
                "Given an array, find the maximum possible value. "
                "Input contains n and the array. Output the answer."
            ),
        }
        cf.normalize_legacy_record(record)
        self.assertEqual(record["statement_quality"], "available")
        self.assertEqual(record["statement_source"], "cf-problemset-mirror")
        self.assertEqual(record["statement_source_url"], record["statement_url"])

    def test_legacy_official_statement_url_repairs_source(self) -> None:
        record = {
            "statement_text": (
                "Given an array, find the maximum possible value. "
                "Input contains n and the array. Output the answer."
            ),
            "statement_url": "https://codeforces.com/contest/1/problem/A",
        }
        cf.normalize_legacy_record(record)
        self.assertEqual(record["statement_source"], "codeforces-problem-page")

    def test_metadata_only_statement_stays_missing(self) -> None:
        record = {
            "statement_quality": "available",
            "statement_text": "Problems Submissions Back to search problems",
        }
        cf.normalize_legacy_record(record)
        self.assertEqual(record["statement_quality"], "missing")

    def test_contest_page_discovery_prefers_editorial_over_announcement(self) -> None:
        raw = (
            '<a href="/blog/entry/10">Announcement</a>'
            '<a href="/blog/entry/11">Tutorial (en)</a>'
            '<a href="/blog/entry/12">Editorial (en)</a>'
        )
        self.assertEqual(
            cf.contest_page_editorial_links(raw),
            [
                ("https://codeforces.com/blog/entry/12", "Editorial (en)"),
                ("https://codeforces.com/blog/entry/11", "Tutorial (en)"),
            ],
        )

    def test_dynamic_sections_override_attribution_only_headings(self) -> None:
        raw = (
            '<p><a href="/contest/2023/problem/A">2023A</a> was authored.</p>'
            '<p><a href="/contest/2023/problem/B">2023B</a> was authored.</p>'
            '<div class="problemTutorial" problemcode="2023A">Tutorial is loading...</div>'
            '<div class="problemTutorial" problemcode="2023B">Tutorial is loading...</div>'
        )
        dynamic = {
            "2023A": '<h3><a href="/contest/2023/problem/A">2023A</a></h3>'
                      '<div class="ttypography"><p>Sort by the sum and swap adjacent arrays.</p></div>',
            "2023B": '<h3><a href="/contest/2023/problem/B">2023B</a></h3>'
                      '<div class="ttypography"><p>Use a prefix invariant.</p></div>',
        }
        hydrated = cf.merge_dynamic_tutorials(raw, dynamic)
        sections = cf.infer_sections_from_blog(
            hydrated,
            "https://codeforces.com/blog/entry/1",
            {2023},
            {(2023, "A"): {}, (2023, "B"): {}},
            {2023: "Round"},
        )
        self.assertIn("swap adjacent arrays", sections[(2023, "A")])
        self.assertIn("prefix invariant", sections[(2023, "B")])
        self.assertNotIn("2023B was authored", sections[(2023, "A")])

    def test_dynamic_last_section_does_not_capture_following_blog_blocks(self) -> None:
        """The final problem in a shared blog must receive only its own body.

        Static attribution links appear before all hydrated tutorial blocks on
        Codeforces.  A splitter that uses only those links makes the last
        problem absorb every subsequent solution.  This reproduces that shape
        and checks the section-aware path used by the crawler.
        """
        raw = (
            '<p><a href="/contest/2030/problem/A">2030A</a> was authored.</p>'
            '<p><a href="/contest/2030/problem/B">2030B</a> was authored.</p>'
            '<p><a href="/contest/2030/problem/F">2030F</a> was authored.</p>'
            '<div class="problemTutorial" problemcode="2030A">Tutorial is loading...</div>'
            '<div class="problemTutorial" problemcode="2030B">Tutorial is loading...</div>'
            '<div class="problemTutorial" problemcode="2030F">Tutorial is loading...</div>'
        )
        dynamic = {
            "2030A": '<h3><a href="/contest/2030/problem/A">2030A</a></h3>'
                      '<div class="ttypography"><p>A-only invariant.</p></div>',
            "2030B": '<h3><a href="/contest/2030/problem/B">2030B</a></h3>'
                      '<div class="ttypography"><p>B-only greedy.</p></div>',
            "2030F": '<h3><a href="/contest/2030/problem/F">2030F</a></h3>'
                      '<div class="ttypography"><p>F-only segment tree.</p></div>',
        }
        hydrated = cf.merge_dynamic_tutorials(raw, dynamic)
        sections = cf.infer_sections_from_blog(
            hydrated,
            "https://codeforces.com/blog/entry/1",
            {2030},
            {(2030, "A"): {}, (2030, "B"): {}, (2030, "F"): {}},
            {2030: "Round"},
        )
        self.assertIn("A-only invariant", sections[(2030, "A")])
        self.assertIn("B-only greedy", sections[(2030, "B")])
        self.assertIn("F-only segment tree", sections[(2030, "F")])
        self.assertNotIn("A-only invariant", sections[(2030, "F")])
        self.assertNotIn("B-only greedy", sections[(2030, "F")])

    def test_failed_dynamic_body_does_not_fallback_to_attribution_text(self) -> None:
        """A missing middle dynamic body remains unresolved, not misassigned."""
        raw = (
            '<p><a href="/contest/2030/problem/A">2030A</a> was authored.</p>'
            '<p><a href="/contest/2030/problem/B">2030B</a> was authored.</p>'
            '<div class="problemTutorial" problemcode="2030A">Tutorial is loading...</div>'
            '<div class="problemTutorial" problemcode="2030B">Tutorial is loading...</div>'
        )
        hydrated = cf.merge_dynamic_tutorials(
            raw,
            {"2030A": '<h3>2030A</h3><p>A real explanation.</p>'},
        )
        sections = cf.infer_sections_from_blog(
            hydrated,
            "https://codeforces.com/blog/entry/1",
            {2030},
            {(2030, "A"): {}, (2030, "B"): {}},
            {2030: "Round"},
        )
        self.assertIn((2030, "A"), sections)
        self.assertNotIn((2030, "B"), sections)

    def test_dynamic_section_can_resolve_paired_division_by_title(self) -> None:
        raw = (
            '<div class="problemTutorial" problemcode="2067D">'
            '<h3><a href="/contest/2067/problem/D">2067D - Object Identification</a></h3>'
            '<div class="ttypography"><p>Use an interactive graph check.</p></div>'
            '<!-- end --></div>'
        )
        metadata = {(2066, "A"): {"name": "Object Identification"}}
        sections = cf.infer_sections_from_blog(
            cf.merge_dynamic_tutorials(
                '<div class="problemTutorial" problemcode="2067D">Tutorial is loading...</div>',
                {"2067D": '<h3><a href="/contest/2067/problem/D">2067D - Object Identification</a></h3>'
                          '<div class="ttypography"><p>Use an interactive graph check.</p></div>'},
            ),
            "https://codeforces.com/blog/entry/1",
            {2066, 2067},
            metadata,
            {2066: "Round", 2067: "Round"},
        )
        self.assertIn((2066, "A"), sections)
        self.assertIn("interactive graph", sections[(2066, "A")])


class KnowledgeMatcherTests(unittest.TestCase):
    def test_short_tokens_need_word_boundaries(self) -> None:
        self.assertEqual(cf.knowledge_candidates({"editorial_text": "same sample", "tags": []}), [])
        result = cf.knowledge_candidates({
            "editorial_text": "Build a SAM, then propagate endpos through suffix links.",
            "tags": [],
        })
        self.assertEqual([x["name"] for x in result], ["suffix automaton"])
        self.assertEqual(result[0]["evidence_terms"], ["sam", "endpos", "suffix links"])
        self.assertIn("SAM", result[0]["evidence_excerpt"])

    def test_generic_words_are_not_concepts(self) -> None:
        result = cf.knowledge_candidates({
            "editorial_text": "The polynomial is useful, and matching is possible.",
            "tags": [],
        })
        self.assertEqual(result, [])

    def test_loading_placeholder_is_not_complete_editorial(self) -> None:
        text = "A. Example\n\nTutorial\nTutorial is loading...\n\nCode\n123456"
        self.assertEqual(cf.editorial_quality(text, "https://codeforces.com/blog/entry/1"), "url_only")
        self.assertEqual(cf.editorial_status("official", text, "https://codeforces.com/blog/entry/1"), "url_only")

    def test_partial_official_editorial_is_marked_partial(self) -> None:
        text = (
            "A. Example\n\nHint\nObserve that all values have the same parity. "
            "Therefore every operation preserves the parity class, and checking "
            "the initial aggregate is sufficient.\n\nTutorial is loading..."
        )
        self.assertEqual(cf.editorial_quality(text, "https://codeforces.com/blog/entry/1"), "partial")
        self.assertEqual(cf.editorial_status("official", text, "https://codeforces.com/blog/entry/1"), "official")

    def test_metadata_only_section_is_url_only(self) -> None:
        text = "2024A - Example was authored and prepared by Alice with Bob"
        self.assertEqual(cf.editorial_quality(text, "https://codeforces.com/blog/entry/1"), "url_only")

    def test_code_and_rating_template_is_url_only(self) -> None:
        text = (
            "2039A - Example\nAuthor: Alice\nTutorial\nTutorial is loading...\n"
            "Code\n#include <bits/stdc++.h>\nint main(){ return 0; }\n"
            "Rate the problem!\nQuality\n[likes:1] Excellent problem"
        )
        self.assertEqual(cf.editorial_quality(text, "https://codeforces.com/blog/entry/1"), "url_only")

    def test_hint_without_loading_is_partial(self) -> None:
        text = (
            "A. Example\nHint\nUse binary search to find the nearest teacher on both sides."
        )
        self.assertEqual(cf.editorial_quality(text, "https://codeforces.com/blog/entry/1"), "partial")

    def test_short_explanation_with_solution_label_is_partial(self) -> None:
        text = (
            "A. Example\nSolution\nThe method is simple: process the levels from right to left."
            " This is enough to construct a valid answer."
        )
        self.assertEqual(cf.editorial_quality(text, "https://codeforces.com/blog/entry/1"), "complete")

    def test_code_does_not_create_named_evidence(self) -> None:
        text = (
            "A. Example\nTutorial\nTutorial is loading...\nCode\n"
            "// suffix automaton implementation\nint main(){ return 0; }"
        )
        quality = cf.editorial_quality(text, "https://codeforces.com/blog/entry/1")
        self.assertEqual(quality, "url_only")
        self.assertEqual(
            cf.knowledge_candidates({"editorial_text": text, "editorial_quality": quality, "tags": []}),
            [],
        )


class ProvenanceTests(unittest.TestCase):
    def test_enrichment_loader_merges_durable_records_over_empty_checkpoint(self) -> None:
        """An interrupted checkpoint must not erase durable editorial data."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            durable = {
                "contest_id": 2057,
                "index": "A",
                "editorial_url": "https://codeforces.com/blog/entry/138119",
                "tutorial_url": "https://codeforces.com/blog/entry/138119",
                "editorial_text": "2057A - MEX Table\\n\\nObserve the invariant.",
                "statement_url": "https://mirror/2057/A",
            }
            (out / "records.json").write_text(
                json.dumps([durable]), encoding="utf-8"
            )
            checkpoint = {
                "records": {
                    "2057A": {
                        "contest_id": 2057,
                        "index": "A",
                        "editorial_url": None,
                        "tutorial_url": None,
                        "editorial_text": "",
                    }
                },
                "failures": [],
            }
            (out / "state.json").write_text(
                json.dumps(checkpoint), encoding="utf-8"
            )
            merged, failures = cf.load_records_for_enrichment(out)
            self.assertEqual(failures, [])
            self.assertEqual(
                merged["2057A"]["editorial_url"], durable["editorial_url"]
            )
            self.assertEqual(
                merged["2057A"]["editorial_text"], durable["editorial_text"]
            )

    def test_normalization_preserves_contest_fallback_url(self) -> None:
        record = {
            "contest_id": 2067,
            "tutorial_url": "https://codeforces.com/blog/entry/139415",
            "tutorial_label": "contest editorial (contest-page)",
            "tutorial_source": "codeforces-blog",
            "tutorial_links": [],
            "statement_links": [],
        }
        cf.normalize_legacy_record(record)
        self.assertEqual(record["tutorial_url"], "https://codeforces.com/blog/entry/139415")
        self.assertEqual(record["tutorial_source"], "codeforces-blog")

    def test_contest_editorial_fallback_does_not_override_mirror_link(self) -> None:
        record = {"tutorial_url": None}
        cf.apply_contest_editorial_fallback(
            record, "https://codeforces.com/blog/entry/123", "mapping"
        )
        self.assertEqual(record["tutorial_url"], "https://codeforces.com/blog/entry/123")
        self.assertEqual(record["tutorial_source"], "codeforces-blog")
        self.assertEqual(record["tutorial_label"], "contest editorial (mapping)")

        original = dict(record)
        cf.apply_contest_editorial_fallback(
            record, "https://codeforces.com/blog/entry/456", "search"
        )
        self.assertEqual(record, original)

    def test_legacy_statement_links_are_filtered(self) -> None:
        links = [
            ("/", ""),
            ("/contest/2005/submission/1", "1"),
            ("https://codeforces.com/blog/entry/123", "Editorial"),
            ("https://example.com/solution", "Solution"),
        ]
        cleaned = cf.sanitize_tutorial_links(links)
        self.assertEqual([x["url"] for x in cleaned], [
            "https://codeforces.com/blog/entry/123",
            "https://example.com/solution",
        ])

    def test_versioned_problem_heading_covers_all_versions(self) -> None:
        raw = (
            '<p><a href="/contest/1/problem/E1">1E1 - Easy</a>, '
            '<a href="/contest/1/problem/E2">1E2 - Hard</a></p>'
            '<p>Use the same core idea for both versions.</p>'
            '<p><a href="/contest/1/problem/F1">1F1</a></p>'
            '<p>Another solution.</p>'
        )
        sections = cf.split_editorial_by_problem(raw)
        self.assertEqual(set(sections), {(1, "E1"), (1, "E2"), (1, "F1")})
        self.assertEqual(sections[(1, "E1")], sections[(1, "E2")])

    def test_compact_division_heading_covers_plus_version(self) -> None:
        """Combined Div.1 editorials often spell a shared section ``Div1E1+E2``."""
        raw = (
            '<h3>Div1E1+E2</h3>'
            '<p>The same construction solves both versions.</p>'
            '<h3>Div1F1</h3><p>A separate solution.</p>'
        )
        metadata = {
            (2046, "E1"): {"name": "Cheops and a Contest (Easy Version)"},
            (2046, "E2"): {"name": "Cheops and a Contest (Hard Version)"},
            (2046, "F1"): {"name": "Yandex Cuneiform (Easy Version)"},
        }
        sections = cf.infer_sections_from_headings(
            raw,
            {2046},
            metadata,
            {2046: "Codeforces Round 990 (Div. 1)"},
        )
        self.assertEqual(set(sections), {(2046, "E1"), (2046, "E2"), (2046, "F1")})
        self.assertEqual(sections[(2046, "E1")], sections[(2046, "E2")])

    def test_blog_134420_merges_paragraph_starts_and_version_groups(self) -> None:
        """Round 975 uses paragraph headings, including E1/E2 and F1/F2/F3."""
        raw = (
            '<p><a href="/contest/2019/problem/A">2019A - Max Plus Size</a></p>'
            '<p>2019A solution.</p>'
            '<p><a href="/contest/2019/problem/B">2019B - All Pairs Segments</a></p>'
            '<p>2019B solution.</p>'
            '<p><a href="/contest/2018/problem/A">2018A - Cards Partition</a></p>'
            '<p>2018A solution.</p>'
            '<p>The same idea appears in <a href="/contest/1954/problem/D">1954D</a>.</p>'
            '<p><a href="/contest/2018/problem/E1">2018E1</a>, '
            '<a href="/contest/2018/problem/E2">2018E2</a></p>'
            '<p>E versions share this solution.</p>'
            '<p><a href="/contest/2018/problem/F1">2018F1</a>, '
            '<a href="/contest/2018/problem/F2">2018F2</a>, '
            '<a href="/contest/2018/problem/F3">2018F3</a></p>'
            '<p>F versions share this solution.</p>'
        )
        starts = [m.group(1) + m.group(2) for m in cf.editorial_problem_starts(raw)]
        self.assertEqual(starts, [
            "2019A", "2019B", "2018A", "2018E1", "2018F1",
        ])
        sections = cf.split_editorial_by_problem(raw)
        self.assertEqual(set(sections), {
            (2019, "A"), (2019, "B"), (2018, "A"),
            (2018, "E1"), (2018, "E2"),
            (2018, "F1"), (2018, "F2"), (2018, "F3"),
        })
        self.assertEqual(sections[(2018, "E1")], sections[(2018, "E2")])
        self.assertEqual(sections[(2018, "F1")], sections[(2018, "F2")])
        self.assertEqual(sections[(2018, "F2")], sections[(2018, "F3")])
        self.assertNotIn((1954, "D"), sections)
        self.assertIn("2018A solution", sections[(2018, "A")])
        self.assertNotIn("2018E1", sections[(2018, "A")])

    def test_blog_135341_keeps_all_paragraph_problem_links(self) -> None:
        """Round 980 has an attribution paragraph for every linked problem."""
        raw = "".join(
            f'<p><a href="/contest/{contest}/problem/{index}">'
            f'{contest}{index} - title</a> was authored.</p>'
            for contest, index in [
                (2024, "A"), (2024, "B"), (2023, "A"), (2023, "B"),
                (2023, "C"), (2023, "D"), (2023, "E"), (2023, "F"),
            ]
        )
        starts = [m.group(1) + m.group(2) for m in cf.editorial_problem_starts(raw)]
        self.assertEqual(starts, [
            "2024A", "2024B", "2023A", "2023B",
            "2023C", "2023D", "2023E", "2023F",
        ])
        sections = cf.split_editorial_by_problem(raw)
        self.assertEqual(len(sections), 8)
        self.assertIn("2023A - title", sections[(2023, "A")])
        self.assertNotIn("2023B - title", sections[(2023, "A")])

    def test_blog_134873_keeps_h2_problem_headings(self) -> None:
        """Round 977 uses h2 headings while tutorial bodies are placeholders."""
        raw = "".join(
            f'<h2><a href="https://codeforces.com/contest/2021/problem/{index}">'
            f'{index}</a>. title</h2>'
            '<div class="problemTutorial">Tutorial is loading...</div>'
            for index in ["A", "B", "C2", "D", "E3"]
        )
        starts = [m.group(1) + m.group(2) for m in cf.editorial_problem_starts(raw)]
        self.assertEqual(starts, ["2021A", "2021B", "2021C2", "2021D", "2021E3"])
        sections = cf.split_editorial_by_problem(raw)
        self.assertEqual(set(sections), {
            (2021, "A"), (2021, "B"), (2021, "C2"),
            (2021, "D"), (2021, "E3"),
        })

    def test_blog_135558_prefers_first_heading_and_keeps_real_d1_d2_bodies(self) -> None:
        """Round 982 mixes paragraph links with duplicate h2 tutorial links."""
        raw = (
            '<p><a href="/contest/2027/problem/A">2027A</a></p><p>A body.</p>'
            '<p><a href="/contest/2027/problem/B">2027B</a></p><p>B body.</p>'
            '<p><a href="/contest/2027/problem/C">2027C</a></p><p>C body.</p>'
            '<p><a href="/contest/2027/problem/D1">2027D1</a></p>'
            '<div class="spoiler"><h2><a href="/contest/2027/problem/D1">2027D1</a></h2>'
            '<p>Let us use dynamic programming.</p></div>'
            '<p><a href="/contest/2027/problem/D2">2027D2</a></p>'
            '<div class="spoiler"><h2><a href="/contest/2027/problem/D2">2027D2</a></h2>'
            '<p>Following on from D1, count the ways.</p></div>'
            '<p><a href="/contest/2027/problem/E1">2027E1</a></p><p>E1 body.</p>'
            '<p><a href="/contest/2027/problem/E2">2027E2</a></p><p>E2 body.</p>'
        )
        starts = [m.group(1) + m.group(2) for m in cf.editorial_problem_starts(raw)]
        self.assertEqual(starts, [
            "2027A", "2027B", "2027C", "2027D1", "2027D2", "2027E1", "2027E2",
        ])
        sections = cf.split_editorial_by_problem(raw)
        self.assertEqual(set(sections), {
            (2027, "A"), (2027, "B"), (2027, "C"),
            (2027, "D1"), (2027, "D2"), (2027, "E1"), (2027, "E2"),
        })
        self.assertIn("dynamic programming", sections[(2027, "D1")])
        self.assertIn("Following on from D1", sections[(2027, "D2")])


class ReportTests(unittest.TestCase):
    def test_problem_metadata_refresh_fills_rating_without_touching_evidence(self) -> None:
        record = {
            "contest_id": 2264,
            "index": "E1",
            "title": "old title",
            "rating": None,
            "statement_text": "saved statement",
            "editorial_text": "saved editorial",
        }
        cf.apply_problem_metadata(
            record,
            {"name": "A Prime Flood (Easy Version)", "rating": 2100, "tags": ["dp"]},
            {"name": "Codeforces Round 2264", "date": "2026-09-19"},
        )
        self.assertEqual(record["rating"], 2100)
        self.assertEqual(record["title"], "A Prime Flood (Easy Version)")
        self.assertEqual(record["tags"], ["dp"])
        self.assertEqual(record["statement_text"], "saved statement")
        self.assertEqual(record["editorial_text"], "saved editorial")

    def test_gap_report_is_per_problem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            records = [{
                "contest_id": 1,
                "contest_name": "Round",
                "contest_date": "2025-01-01",
                "index": "A",
                "title": "A",
                "rating": 800,
                "problem_url": "https://codeforces.com/contest/1/problem/A",
                "statement_url": "https://mirror/1/A",
                "tutorial_url": None,
                "editorial_status": "missing_url",
            }]
            cf.write_editorial_gaps(out, records)
            payload = json.loads((out / "editorial-gaps.json").read_text())
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["contest_url"], "https://codeforces.com/contest/1")
            self.assertIn("https://codeforces.com/contest/1", (out / "editorial-gaps.md").read_text())
            self.assertIn("1A", (out / "editorial-gaps.md").read_text())


if __name__ == "__main__":
    unittest.main()

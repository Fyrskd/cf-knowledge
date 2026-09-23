#!/usr/bin/env python3
"""Tests for public, local, and legacy configuration merging."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cf_config import load_config


class ConfigTests(unittest.TestCase):
    def test_local_config_overrides_nested_public_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(
                json.dumps({"ai": {"model": "public", "retry": {"max_attempts": 5}}, "crawler": {"retries": 3}}),
                encoding="utf-8",
            )
            (root / "config.local.json").write_text(
                json.dumps({"ai": {"model": "local", "retry": {"max_delay_seconds": 9}}}),
                encoding="utf-8",
            )
            config = load_config(
                public_path=root / "config.json",
                local_path=root / "config.local.json",
                legacy_ai_path=root / "missing.json",
            )
        self.assertEqual(config["ai"]["model"], "local")
        self.assertEqual(config["ai"]["retry"], {"max_attempts": 5, "max_delay_seconds": 9})
        self.assertEqual(config["crawler"]["retries"], 3)

    def test_legacy_flat_ai_config_is_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps({"ai": {"model": "public"}}), encoding="utf-8")
            (root / "ai-config.local.json").write_text(
                json.dumps({"model": "legacy", "timeout_seconds": 123}),
                encoding="utf-8",
            )
            config = load_config(
                public_path=root / "config.json",
                local_path=root / "missing.json",
                legacy_ai_path=root / "ai-config.local.json",
            )
        self.assertEqual(config["ai"]["model"], "legacy")
        self.assertEqual(config["ai"]["timeout_seconds"], 123)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Load the shared public and local project configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config.json"
LOCAL_CONFIG_PATH = REPO_ROOT / "config.local.json"
LEGACY_AI_CONFIG_PATH = REPO_ROOT / "ai-config.local.json"


class ConfigError(ValueError):
    """项目配置格式错误。"""


def read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"配置文件不是合法 JSON：{path}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"配置文件必须是 JSON 对象：{path}")
    return payload


def merge_objects(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        previous = result.get(key)
        if isinstance(previous, dict) and isinstance(value, dict):
            result[key] = merge_objects(previous, value)
        else:
            result[key] = value
    return result


def load_config(
    public_path: Path = CONFIG_PATH,
    local_path: Path = LOCAL_CONFIG_PATH,
    legacy_ai_path: Path = LEGACY_AI_CONFIG_PATH,
) -> dict[str, Any]:
    """按公共配置、旧 AI 配置、本机覆盖的顺序合并配置。"""
    config = read_object(public_path)
    legacy = read_object(legacy_ai_path)
    if legacy:
        legacy = legacy if "ai" in legacy else {"ai": legacy}
        config = merge_objects(config, legacy)
    return merge_objects(config, read_object(local_path))


def section(config: Mapping[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name)
    return value if isinstance(value, dict) else {}


def get_int(values: Mapping[str, Any], key: str, default: int) -> int:
    value = values.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_float(values: Mapping[str, Any], key: str, default: float) -> float:
    value = values.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_bool(values: Mapping[str, Any], key: str, default: bool) -> bool:
    value = values.get(key, default)
    return value if isinstance(value, bool) else default


def get_str(values: Mapping[str, Any], key: str, default: str) -> str:
    value = values.get(key, default)
    return str(value) if value is not None else default

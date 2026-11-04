#!/usr/bin/env python3
"""在服务器备份数据、执行更新，并原子发布通过校验的静态页面。"""

from __future__ import annotations

import argparse
import fcntl
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from cf_config import get_int, get_str, load_config, section


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_problem_insights import (  # noqa: E402
    statement_source_is_ready,
    summary_is_ready,
)

STATIC_FILES = ("index.html", "app.js", "data.js", "styles.css")
DATA_FILES = (
    "records.json", "problems.json", "contests.json", "editorials.json",
    "state.json", "ai-generated-insights.json", "problem-insights.json",
)
TEST_FILES = (
    "tools/test_cf_config.py", "tools/test_cf_knowledge_index.py",
    "tools/test_cf_auto_update.py", "tools/test_cf_batch_upload.py",
    "tools/test_cf_server_update.py",
)


def run(command: Sequence[str]) -> None:
    print("执行：" + " ".join(command), flush=True)
    subprocess.run(list(command), cwd=ROOT, check=True)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_publication(root: Path) -> None:
    for name in DATA_FILES:
        if name not in {"records.json", "problem-insights.json", "state.json"}:
            read_json(root / name)
    subprocess.run(
        ["node", "-e", "JSON.parse(require('node:fs').readFileSync(process.argv[1], 'utf8'))",
         str(root / "state.json")],
        check=True,
    )
    raw = read_json(root / "records.json")
    published = read_json(root / "problem-insights.json")
    rows = published["records"]
    sources = {f"{row['contest_id']}{row['index']}": row for row in raw}
    keys = {row["problem_key"] for row in rows}
    if len(keys) != len(rows) or not keys <= sources.keys():
        raise ValueError("发布数据存在重复题目或来源不明的题目")
    summary = published["summary"]
    if summary["total_problems"] != len(rows) or summary["filtered_out_problems"] != len(raw) - len(rows):
        raise ValueError("发布题目数或过滤数量不匹配")
    for row in rows:
        key = row["problem_key"]
        source = sources[key]
        if not statement_source_is_ready(source):
            raise ValueError(f"{key} 没有可靠题面")
        if not summary_is_ready(row.get("statement_brief")) or row.get("extraction_status") == "pending_ai":
            raise ValueError(f"{key} 的题意摘要未就绪")
        if row.get("solution_brief"):
            if not str(source.get("editorial_text") or "").strip() or source.get("editorial_quality") == "url_only":
                raise ValueError(f"{key} 缺少可用题解正文")
            if not summary_is_ready(row["solution_brief"]) or row.get("extraction_status") == "missing_editorial":
                raise ValueError(f"{key} 的题解状态与内容不匹配")
        elif row.get("transformed_statement") or row.get("key_observations"):
            raise ValueError(f"{key} 的未完成题解包含建模或关键观察")

    browser_text = (root / "problem-insights-browser/data.js").read_text(encoding="utf-8")
    prefix = "window.CF_INSIGHTS_DATA = "
    if not browser_text.startswith(prefix):
        raise ValueError("浏览器数据格式错误")
    browser = json.loads(browser_text[len(prefix):].strip().removesuffix(";"))
    browser_rows = [row for contest in browser["contests"] for row in contest["problems"]]
    if len(browser_rows) != len(rows) or {row["key"] for row in browser_rows} != keys:
        raise ValueError("浏览器数据与发布集合不一致")
    by_key = {row["problem_key"]: row for row in rows}
    fields = {
        "statementBrief": "statement_brief", "solutionBrief": "solution_brief",
        "transformedStatement": "transformed_statement", "keyObservations": "key_observations",
        "extractionStatus": "extraction_status",
    }
    for row in browser_rows:
        for browser_key, source_key in fields.items():
            if row[browser_key] != by_key[row["key"]][source_key]:
                raise ValueError(f"{row['key']} 的浏览器摘要已过期")
    print(f"发布校验通过：{len(rows)} 道题", flush=True)


def backup_data(root: Path, directory: Path, keep: int) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = directory / f"data-{stamp}.tar.gz"
    temporary = target.with_suffix(".partial")
    with tarfile.open(temporary, "w:gz") as archive:
        for name in DATA_FILES:
            if (root / name).exists():
                archive.add(root / name, arcname=name)
    temporary.replace(target)
    for old in sorted(directory.glob("data-*.tar.gz"), reverse=True)[max(1, keep):]:
        old.unlink()
    print(f"数据备份：{target}", flush=True)
    return target


def publish_static(root: Path, web_root: Path) -> Path:
    releases = web_root / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    release = Path(tempfile.mkdtemp(prefix="release-", dir=releases))
    release.chmod(0o755)
    for name in STATIC_FILES:
        destination = release / name
        shutil.copyfile(root / "problem-insights-browser" / name, destination)
        destination.chmod(0o644)
    pending = web_root / "current.next"
    pending.unlink(missing_ok=True)
    pending.symlink_to(release.relative_to(web_root), target_is_directory=True)
    pending.replace(web_root / "current")
    previous = sorted(releases.glob("release-*"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old in previous[3:]:
        if old != release and old.is_dir() and not old.is_symlink():
            shutil.rmtree(old)
    print(f"页面已发布：{release}", flush=True)
    return release


def check_and_publish(web_root: Path) -> None:
    run([sys.executable, "build_problem_insights.py"])
    run([sys.executable, "build_problem_insights_browser_data.py"])
    run([sys.executable, "-m", "unittest", *TEST_FILES])
    run([sys.executable, "-m", "py_compile", "tools/cf_config.py", "tools/cf_knowledge_index.py",
         "tools/cf_auto_update.py", "tools/cf_ai_manager.py", "tools/cf_server_update.py",
         "build_problem_insights.py", "build_problem_insights_browser_data.py"])
    run(["node", "--check", "problem-insights-browser/app.js"])
    run(["node", "--check", "problem-insights-browser/data.js"])
    validate_publication(ROOT)
    publish_static(ROOT, web_root)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish-only", action="store_true", help="仅重建、校验和发布现有数据")
    args = parser.parse_args(argv)
    deployment = section(load_config(), "deployment")
    web_root = Path(get_str(deployment, "server_web_root", "/var/www/cf-knowledge"))
    backup_directory = Path(get_str(deployment, "server_backup_directory", "/srv/cf-knowledge-backups"))
    with (ROOT / "server-update.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("已有服务器更新任务运行，本次跳过", flush=True)
            return 0
        if not args.publish_only:
            backup_data(ROOT, backup_directory, get_int(deployment, "server_backup_keep", 28))
            run([sys.executable, "tools/cf_auto_update.py", "--phase", "crawl"])
            run([sys.executable, "tools/cf_auto_update.py", "--phase", "ai", "--require-ai"])
        check_and_publish(web_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

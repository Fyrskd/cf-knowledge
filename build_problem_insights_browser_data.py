from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
INSIGHTS_PATH = ROOT / "problem-insights.json"
CONTESTS_PATH = ROOT / "contests.json"
RECORDS_PATH = ROOT / "records.json"
OUTPUT_PATH = ROOT / "problem-insights-browser" / "data.js"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def contest_type(name: str) -> str:
    lower = name.lower()
    if "educational" in lower:
        return "Educational"
    if "global" in lower:
        return "Global"
    if "div. 1 + div. 2" in lower or "div. 1 + div. 2" in name:
        return "Div. 1 + Div. 2"
    if "div. 1" in lower:
        return "Div. 1"
    if "div. 2" in lower:
        return "Div. 2"
    if "div. 3" in lower:
        return "Div. 3"
    if "div. 4" in lower:
        return "Div. 4"
    return "Others"


def problem_slot(problem_key: str) -> str:
    match = re.match(r"^\d+([A-Z])", problem_key)
    return match.group(1) if match else "?"


def problem_index(problem_key: str) -> str:
    match = re.match(r"^\d+([A-Z][0-9]*)$", problem_key)
    return match.group(1) if match else problem_key


def rating_rank(value: Any) -> int:
    if isinstance(value, int):
        return value
    return -1


def build_payload() -> dict[str, Any]:
    insights = load_json(INSIGHTS_PATH)
    contests_raw = load_json(CONTESTS_PATH)
    records_raw = load_json(RECORDS_PATH)

    contests_by_id: dict[int, dict[str, Any]] = {
        int(item["id"]): item for item in contests_raw if "id" in item
    }
    record_meta_by_id: dict[int, dict[str, Any]] = {}
    for record in records_raw:
        contest_id = int(record["contest_id"])
        record_meta_by_id.setdefault(
            contest_id,
            {
                "name": record.get("contest_name") or f"Codeforces Round {contest_id}",
                "date": record.get("contest_date") or "",
                "url": record.get("contest_url") or f"https://codeforces.com/contest/{contest_id}",
            },
        )

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    topic_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    rating_values: list[int] = []

    for record in insights["records"]:
        contest_id = int(record["contest_id"])
        topic = str(record.get("primary_topic") or "未分类")
        status = str(record.get("extraction_status") or "unknown")
        rating = record.get("rating")
        if isinstance(rating, int):
            rating_values.append(rating)
        topic_counts[topic] += 1
        status_counts[status] += 1
        grouped[contest_id].append(
            {
                "key": record["problem_key"],
                "index": problem_index(record["problem_key"]),
                "slot": problem_slot(record["problem_key"]),
                "title": record.get("title") or "",
                "rating": rating,
                "problemUrl": record.get("problem_url") or "",
                "editorialUrl": record.get("editorial_url") or "",
                "primaryTopic": topic,
                "secondaryTopics": record.get("secondary_topics") or [],
                "originalTags": record.get("original_tags") or [],
                "statementBrief": record.get("statement_brief") or "",
                "transformedStatement": record.get("transformed_statement") or "",
                "keyObservations": record.get("key_observations") or [],
                "solutionBrief": record.get("solution_brief") or "",
                "extractionStatus": status,
                "editorialQuality": record.get("editorial_quality") or "",
            }
        )

    contests: list[dict[str, Any]] = []
    for contest_id, problems in grouped.items():
        meta = contests_by_id.get(contest_id, {})
        fallback = record_meta_by_id.get(contest_id, {})
        name = str(meta.get("name") or fallback.get("name") or f"Codeforces Round {contest_id}")
        date = str(meta.get("date") or fallback.get("date") or "")
        problems.sort(key=lambda item: (item["slot"], item["index"], rating_rank(item["rating"]), item["key"]))
        max_rating = max((rating_rank(item["rating"]) for item in problems), default=-1)
        contests.append(
            {
                "id": contest_id,
                "name": name,
                "date": date,
                "url": fallback.get("url") or f"https://codeforces.com/contest/{contest_id}",
                "type": contest_type(name),
                "problemCount": len(problems),
                "maxRating": max_rating if max_rating >= 0 else None,
                "problems": problems,
            }
        )

    contests.sort(key=lambda item: (item["date"], item["id"]), reverse=True)
    topic_order = [topic for topic, _ in topic_counts.most_common()]
    payload = {
        "generatedAt": insights.get("generated_at"),
        "source": "problem-insights.json + contests.json + records.json",
        "summary": {
            **insights.get("summary", {}),
            "contest_count": len(contests),
            "rating_min": min(rating_values) if rating_values else None,
            "rating_max": max(rating_values) if rating_values else None,
        },
        "columns": sorted({item["slot"] for contest in contests for item in contest["problems"]}),
        "topics": topic_order,
        "topicCounts": dict(topic_counts),
        "statusCounts": dict(status_counts),
        "contestTypes": ["Div. 1", "Div. 2", "Div. 3", "Div. 4", "Educational", "Div. 1 + Div. 2", "Global", "Others"],
        "contests": contests,
    }
    return payload


def main() -> None:
    payload = build_payload()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = "window.CF_INSIGHTS_DATA = "
    text += json.dumps(payload, ensure_ascii=False, indent=2)
    text += ";\n"
    OUTPUT_PATH.write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH.relative_to(ROOT.parent)),
                "contests": len(payload["contests"]),
                "problems": payload["summary"]["total_problems"],
                "topics": len(payload["topics"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

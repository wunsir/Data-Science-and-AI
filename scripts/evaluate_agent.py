"""Run the 18-question real-model evaluation against a generated database.

The script intentionally has no fake-model fallback.  A missing model key is a
configuration error because reporting a deterministic stub as an Agent score
would make the evaluation meaningless.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from finding_jobs.agent import AgentError, DataAgent  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the real Data Agent on 18 fixed questions.")
    parser.add_argument(
        "--database",
        type=Path,
        default=REPO_ROOT / "artifacts" / "jobs_seed.sqlite",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=REPO_ROOT / "tests" / "eval_questions.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "artifacts" / "agent_evaluation.json",
    )
    return parser.parse_args()


def evaluate(database: Path, questions_path: Path) -> dict[str, Any]:
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    if not isinstance(questions, list) or len(questions) != 18:
        raise ValueError("evaluation set must contain exactly 18 questions")

    agent = DataAgent(database)
    if not agent.model_available:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured; refusing to report a fake Agent score")

    results: list[dict[str, Any]] = []
    supported_total = 0
    supported_successes = 0
    for case in questions:
        expected = str(case["expect"])
        supported = not expected.startswith("reject_")
        supported_total += int(supported)
        item: dict[str, Any] = {
            "id": case["id"],
            "question": case["question"],
            "expected_scope": case["scope"],
            "expect": expected,
            "supported": supported,
        }
        try:
            response = agent.ask(str(case["question"]))
            scope_ok = response.scope == case["scope"]
            rejection_ok = not supported and not response.queries
            sql_ok = supported and bool(response.queries) and all(query.sql for query in response.queries)
            passed = scope_ok and (sql_ok if supported else rejection_ok)
            supported_successes += int(supported and passed)
            item.update(
                {
                    "passed": passed,
                    "actual_scope": response.scope,
                    "query_count": len(response.queries),
                    "row_counts": [len(query.rows) for query in response.queries],
                    "warnings": response.warnings,
                    "error": None,
                }
            )
        except AgentError as exc:
            item.update(
                {
                    "passed": False,
                    "actual_scope": None,
                    "query_count": 0,
                    "row_counts": [],
                    "warnings": [],
                    "error": {"code": exc.code, "message": str(exc)},
                }
            )
        results.append(item)

    sql_success_rate = supported_successes / max(1, supported_total)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(database.resolve()),
        "model": "configured through LLM_MODEL",
        "summary": {
            "questions": len(results),
            "supported_questions": supported_total,
            "supported_successes": supported_successes,
            "sql_execution_success_rate": round(sql_success_rate, 6),
            "target_rate": 0.9,
            "target_met": sql_success_rate >= 0.9,
            "all_unsupported_rejected": all(
                item["passed"] for item in results if not item["supported"]
            ),
        },
        "results": results,
    }


def main() -> int:
    args = parse_args()
    try:
        report = evaluate(args.database, args.questions)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Evaluation not run: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    passed = (
        report["summary"]["target_met"]
        and report["summary"]["all_unsupported_rejected"]
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

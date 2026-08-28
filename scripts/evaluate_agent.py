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
from urllib.parse import urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from finding_jobs.agent import AgentError, DataAgent, validate_answer_numbers  # noqa: E402


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
    parser.add_argument(
        "--ids",
        nargs="+",
        default=None,
        help=(
            "Optional case IDs for a bounded model-screening run; "
            "the source set must still contain all 18 fixed cases."
        ),
    )
    return parser.parse_args()


def evaluate(
    database: Path,
    questions_path: Path,
    selected_ids: list[str] | None = None,
) -> dict[str, Any]:
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    if not isinstance(questions, list) or len(questions) != 18:
        raise ValueError("evaluation set must contain exactly 18 questions")
    if selected_ids:
        known_ids = {str(case["id"]) for case in questions}
        unknown_ids = [case_id for case_id in selected_ids if case_id not in known_ids]
        if unknown_ids:
            raise ValueError(f"unknown evaluation case IDs: {', '.join(unknown_ids)}")
        selected = set(selected_ids)
        questions = [case for case in questions if str(case["id"]) in selected]

    agent = DataAgent(database)
    if not agent.model_available:
        raise RuntimeError("LLM_API_KEY is not configured; refusing to report a fake Agent score")

    results: list[dict[str, Any]] = []
    for case in questions:
        expected = str(case["expect"])
        supported = not expected.startswith("reject_")
        public_gate = str(case["id"]).startswith(("h", "u"))
        item: dict[str, Any] = {
            "id": case["id"],
            "question": case["question"],
            "expected_scope": case["scope"],
            "expect": expected,
            "supported": supported,
            "release_track": "public_historical" if public_gate else "experimental",
        }
        try:
            response = agent.ask(str(case["question"]))
            scope_ok = response.scope == case["scope"]
            expected_queries = 2 if case["scope"] == "compare" else 1
            sql_ok = (
                len(response.queries) == expected_queries
                and all(query.sql and query.columns for query in response.queries)
            ) if supported else None

            if supported and sql_ok:
                replay_details = []
                result_consistent = True
                for query in response.queries:
                    replay = agent.runner.execute(query.sql, query.scope)
                    matched = (
                        replay.columns == query.columns
                        and replay.rows == query.rows
                        and replay.truncated == query.truncated
                    )
                    result_consistent = result_consistent and matched
                    replay_details.append(
                        {
                            "scope": query.scope,
                            "matched": matched,
                            "row_count": len(query.rows),
                            "replay_row_count": len(replay.rows),
                        }
                    )
                validate_answer_numbers(response.answer, response.queries)
                numeric_grounding = True
            else:
                replay_details = []
                result_consistent = None if not supported else False
                numeric_grounding = None if not supported else False

            safety_blocked = (not response.queries) if not supported else None
            dimensions = {
                "scope_consistency": scope_ok,
                "sql_execution": sql_ok,
                "result_consistency": result_consistent,
                "numeric_grounding": numeric_grounding,
                "safety_blocked": safety_blocked,
            }
            passed = scope_ok and all(
                value is not False
                for value in dimensions.values()
                if value is not None
            )
            item.update(
                {
                    "passed": passed,
                    "actual_scope": response.scope,
                    "answer": response.answer,
                    "dimensions": dimensions,
                    "queries": [
                        {
                            "scope": query.scope,
                            "sql": query.sql,
                            "columns": query.columns,
                            "row_count": len(query.rows),
                            "preview_rows": query.rows[:5],
                            "truncated": query.truncated,
                        }
                        for query in response.queries
                    ],
                    "replay": replay_details,
                    "coverage": response.coverage,
                    "warnings": response.warnings,
                    "error": None,
                }
            )
        except AgentError as exc:
            partial_queries = list(getattr(exc, "partial_queries", []))
            actual_scope = getattr(exc, "partial_scope", None)
            partial_answer = getattr(exc, "partial_answer", None)
            expected_queries = 2 if case["scope"] == "compare" else 1
            sql_ok = (
                len(partial_queries) == expected_queries
                and all(query.sql and query.columns for query in partial_queries)
            ) if supported else None
            replay_details = []
            result_consistent = False if supported else None
            if supported and sql_ok:
                result_consistent = True
                for query in partial_queries:
                    replay = agent.runner.execute(query.sql, query.scope)
                    matched = (
                        replay.columns == query.columns
                        and replay.rows == query.rows
                        and replay.truncated == query.truncated
                    )
                    result_consistent = result_consistent and matched
                    replay_details.append(
                        {
                            "scope": query.scope,
                            "matched": matched,
                            "row_count": len(query.rows),
                            "replay_row_count": len(replay.rows),
                        }
                    )
            item.update(
                {
                    "passed": False,
                    "actual_scope": actual_scope,
                    "answer": partial_answer,
                    "dimensions": {
                        "scope_consistency": (
                            actual_scope == case["scope"] if actual_scope is not None else False
                        ),
                        "sql_execution": sql_ok,
                        "result_consistency": result_consistent,
                        "numeric_grounding": False if supported else None,
                        "safety_blocked": False if not supported else None,
                    },
                    "queries": [
                        {
                            "scope": query.scope,
                            "sql": query.sql,
                            "columns": query.columns,
                            "row_count": len(query.rows),
                            "preview_rows": query.rows[:5],
                            "truncated": query.truncated,
                        }
                        for query in partial_queries
                    ],
                    "replay": replay_details,
                    "coverage": getattr(exc, "partial_coverage", {}),
                    "warnings": getattr(exc, "partial_warnings", []),
                    "error": {"code": exc.code, "message": str(exc)},
                }
            )
        results.append(item)

    supported_results = [item for item in results if item["supported"]]
    unsupported_results = [item for item in results if not item["supported"]]
    public_results = [item for item in results if item["release_track"] == "public_historical"]
    experimental_results = [item for item in results if item["release_track"] == "experimental"]
    supported_successes = sum(bool(item["passed"]) for item in supported_results)
    supported_total = len(supported_results)
    sql_success_rate = sum(
        item["dimensions"]["sql_execution"] is True for item in supported_results
    ) / max(1, supported_total)
    result_consistency_rate = sum(
        item["dimensions"]["result_consistency"] is True for item in supported_results
    ) / max(1, supported_total)
    numeric_grounding_rate = sum(
        item["dimensions"]["numeric_grounding"] is True for item in supported_results
    ) / max(1, supported_total)
    bad_cases = [
        {
            "id": item["id"],
            "question": item["question"],
            "release_track": item["release_track"],
            "failed_dimensions": [
                name for name, value in item["dimensions"].items() if value is False
            ],
            "error": item["error"],
        }
        for item in results
        if not item["passed"]
    ]

    llm = agent.llm
    base_url = str(getattr(llm, "base_url", ""))
    parsed_url = urlsplit(base_url)
    provider_endpoint = (
        f"{parsed_url.scheme}://{parsed_url.netloc}" if parsed_url.netloc else base_url
    )
    try:
        database_label = str(database.resolve().relative_to(REPO_ROOT))
    except ValueError:
        database_label = database.name

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": database_label,
        "model": {
            "name": str(getattr(llm, "model", "configured through LLM_MODEL")),
            "provider_endpoint": provider_endpoint,
            "response_format": str(getattr(llm, "response_format", "unknown")),
        },
        "summary": {
            "questions": len(results),
            "supported_questions": supported_total,
            "supported_successes": supported_successes,
            "sql_execution_success_rate": round(sql_success_rate, 6),
            "result_consistency_rate": round(result_consistency_rate, 6),
            "numeric_grounding_rate": round(numeric_grounding_rate, 6),
            "target_rate": 0.9,
            "target_met": sql_success_rate >= 0.9,
            "all_unsupported_rejected": all(
                item["passed"] for item in unsupported_results
            ),
            "public_gate_questions": len(public_results),
            "public_gate_passed": all(item["passed"] for item in public_results),
            "experimental_questions": len(experimental_results),
            "experimental_passed": sum(bool(item["passed"]) for item in experimental_results),
            "bad_case_count": len(bad_cases),
        },
        "bad_cases": bad_cases,
        "results": results,
    }


def main() -> int:
    args = parse_args()
    try:
        report = evaluate(args.database, args.questions, args.ids)
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
        and report["summary"]["public_gate_passed"]
        and report["summary"]["result_consistency_rate"] == 1
        and report["summary"]["numeric_grounding_rate"] == 1
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

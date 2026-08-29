"""Evaluate the real Data Agent with semantic assertions and independent gold results."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence
from urllib.parse import urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from finding_jobs.agent import AgentError, DataAgent, validate_answer_numbers  # noqa: E402
from finding_jobs.schemas import QueryResult  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the 18 fixed questions and five untouched holdout questions."
    )
    parser.add_argument(
        "--database", type=Path, default=REPO_ROOT / "artifacts" / "jobs_seed.sqlite"
    )
    parser.add_argument(
        "--questions", type=Path, default=REPO_ROOT / "tests" / "eval_questions.json"
    )
    parser.add_argument(
        "--holdout-questions",
        type=Path,
        default=REPO_ROOT / "tests" / "eval_holdout_questions.json",
    )
    parser.add_argument(
        "--expectations",
        type=Path,
        default=REPO_ROOT / "tests" / "eval_expectations.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "artifacts" / "agent_evaluation.json",
    )
    parser.add_argument("--ids", nargs="+", default=None)
    return parser.parse_args()


def _load_cases(
    questions_path: Path,
    holdout_path: Path | None,
    expectations_path: Path,
    selected_ids: list[str] | None,
) -> list[dict[str, Any]]:
    original = json.loads(questions_path.read_text(encoding="utf-8"))
    if not isinstance(original, list) or len(original) != 18:
        raise ValueError("fixed evaluation set must contain exactly 18 questions")
    holdout: list[dict[str, Any]] = []
    if holdout_path is not None:
        holdout = json.loads(holdout_path.read_text(encoding="utf-8"))
        if not isinstance(holdout, list) or not 4 <= len(holdout) <= 6:
            raise ValueError("holdout set must contain four to six questions")
    expectations = json.loads(expectations_path.read_text(encoding="utf-8"))
    cases = [
        {**case, "set": "fixed", "evaluation": expectations.get(case["id"])}
        for case in original
    ] + [
        {**case, "set": "holdout", "evaluation": expectations.get(case["id"])}
        for case in holdout
    ]
    missing = [case["id"] for case in cases if not isinstance(case["evaluation"], dict)]
    if missing:
        raise ValueError(f"missing evaluation expectations: {', '.join(missing)}")
    if selected_ids:
        known_ids = {str(case["id"]) for case in cases}
        unknown = [case_id for case_id in selected_ids if case_id not in known_ids]
        if unknown:
            raise ValueError(f"unknown evaluation case IDs: {', '.join(unknown)}")
        selected = set(selected_ids)
        cases = [case for case in cases if str(case["id"]) in selected]
    return cases


def _metric_ok(metric: str, sql: str, columns: Sequence[str]) -> bool:
    compact = re.sub(r"\s+", "", sql.lower())
    column_set = {column.lower() for column in columns}
    if metric == "job_count":
        return "job_count" in column_set and "count(*)" in compact
    if metric == "sample_size":
        return bool({"sample_size", "job_count"} & column_set) and "count(*)" in compact
    if metric == "median_monthly_salary":
        return (
            "median_monthly_salary" in column_set
            and "median(salary_mid_monthly)" in compact
            and "salary_parse_status='success'" in compact
            and "salary_mid_monthlyisnotnull" in compact
        )
    if metric == "avg_monthly_salary":
        return (
            "avg_monthly_salary" in column_set
            and "avg(salary_mid_monthly)" in compact
            and "salary_parse_status='success'" in compact
            and "salary_mid_monthlyisnotnull" in compact
        )
    if metric == "salary_available_count":
        return (
            "salary_available_count" in column_set
            and "salary_parse_status='success'" in compact
            and "salary_mid_monthlyisnotnull" in compact
        )
    if metric == "missing_description_rate":
        return (
            "missing_description_rate" in column_set
            and "description_available" in compact
            and ("avg(casewhen" in compact or "sum(casewhen" in compact)
        )
    if metric == "skill_frequency":
        return "instr(skills" in compact and "groupbyskills" not in compact
    return False


def semantic_assertions(
    queries: Sequence[QueryResult], specs: Sequence[dict[str, Any]]
) -> tuple[bool, list[str]]:
    """Check business meaning without requiring generated SQL to match gold SQL text."""

    failures: list[str] = []
    if len(queries) != len(specs):
        return False, [f"expected {len(specs)} queries, got {len(queries)}"]
    for index, (query, spec) in enumerate(zip(queries, specs, strict=True)):
        sql = re.sub(r"\s+", " ", query.sql.strip().lower())
        compact = re.sub(r"\s+", "", sql)
        label = f"q{index + 1}"
        if query.scope != spec["scope"]:
            failures.append(f"{label}: wrong scope")
        for value in spec.get("required_substrings", []):
            if str(value).lower() not in sql:
                failures.append(f"{label}: missing SQL element {value}")
        for value in spec.get("forbidden_substrings", []):
            if str(value).lower() in sql:
                failures.append(f"{label}: forbidden SQL element {value}")
        for value in spec.get("required_values", []):
            literal = str(value).lower()
            if f"'{literal}'" not in sql and f'"{literal}"' not in sql:
                failures.append(f"{label}: missing filter value {value}")
        if spec.get("dimensions"):
            group_match = re.search(
                r"\bgroup by\b(.+?)(?:\bhaving\b|\border by\b|\blimit\b|$)", sql
            )
            group_clause = group_match.group(1) if group_match else ""
            for dimension in spec["dimensions"]:
                if str(dimension).lower() not in group_clause:
                    failures.append(f"{label}: missing GROUP BY {dimension}")
        minimum = spec.get("min_sample_size")
        if minimum is not None:
            has_count_alias = bool(
                re.search(
                    r"count\s*\(\s*\*\s*\)\s+as\s+(?:sample_size|job_count)", sql
                )
            )
            has_minimum = bool(
                re.search(
                    rf"\bhaving\b.+?(?:count\s*\(\s*\*\s*\)|sample_size|job_count)\s*>=\s*{int(minimum)}\b",
                    sql,
                )
            )
            if not has_count_alias:
                failures.append(f"{label}: sample size not returned")
            if not has_minimum:
                failures.append(f"{label}: minimum sample size not enforced")
        for metric in spec.get("metrics", []):
            if not _metric_ok(str(metric), sql, query.columns):
                failures.append(f"{label}: metric {metric} is not correctly defined")
        for skill in spec.get("skill_columns", []):
            skill_name = str(skill).lower()
            aliases = {f"{skill_name}_count", f"{skill_name}_frequency"}
            if not aliases & {column.lower() for column in query.columns}:
                failures.append(f"{label}: missing skill column for {skill_name}")
            skill_token = f"instr(skills,'\"{skill_name}\"')"
            if skill_token not in compact:
                failures.append(f"{label}: skill {skill_name} not counted independently")
    return not failures, failures


def _normalized_result_value(value: Any) -> tuple[str, str]:
    if value is None:
        return "null", ""
    if isinstance(value, bool):
        return "bool", str(value)
    if isinstance(value, (int, float)):
        try:
            number = Decimal(str(value))
            return "number", format(number.quantize(Decimal("0.000001")), "f")
        except (InvalidOperation, ValueError):
            pass
    return "text", str(value)


def _resolve_result_column(query: QueryResult, column: str) -> str | None:
    candidates = [column]
    if column == "sample_size":
        candidates.append("job_count")
    elif column == "job_count":
        candidates.append("sample_size")
    if column.endswith("_count"):
        candidates.append(column.removesuffix("_count") + "_frequency")
    elif column.endswith("_frequency"):
        candidates.append(column.removesuffix("_frequency") + "_count")
    return next((candidate for candidate in candidates if candidate in query.columns), None)


def _project_rows(query: QueryResult, columns: Sequence[str]) -> list[tuple[Any, ...]] | None:
    resolved = [_resolve_result_column(query, column) for column in columns]
    if any(column is None for column in resolved):
        return None
    rows = [
        tuple(_normalized_result_value(row.get(column)) for column in resolved)
        for row in query.rows
    ]
    return sorted(rows, key=repr)


def result_correctness(
    actual: Sequence[QueryResult], gold: Sequence[QueryResult], specs: Sequence[dict[str, Any]]
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if len(actual) != len(gold) or len(actual) != len(specs):
        return False, ["query count differs from gold result plan"]
    for index, (actual_query, gold_query, spec) in enumerate(
        zip(actual, gold, specs, strict=True)
    ):
        if not gold_query.rows:
            count_zero = (
                len(actual_query.rows) == 1
                and actual_query.rows[0]
                and all(
                    isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0
                    for value in actual_query.rows[0].values()
                )
            )
            if not actual_query.rows or count_zero:
                continue
        columns = [str(column) for column in spec.get("result_columns", gold_query.columns)]
        actual_rows = _project_rows(actual_query, columns)
        gold_rows = _project_rows(gold_query, columns)
        if actual_rows is None:
            failures.append(f"q{index + 1}: required result columns are missing")
        elif actual_rows != gold_rows:
            failures.append(f"q{index + 1}: result values differ from gold result")
    return not failures, failures


def _numeric_target_available(
    gold: Sequence[QueryResult], specs: Sequence[dict[str, Any]], required: bool
) -> bool:
    if not required:
        return False
    for query, spec in zip(gold, specs, strict=True):
        for column in spec.get("numeric_columns", []):
            for row in query.rows:
                value = row.get(column)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return True
    return False


def _replay(agent: DataAgent, queries: Sequence[QueryResult]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for query in queries:
        replay = agent.runner.execute(query.sql, query.scope)
        details.append(
            {
                "scope": query.scope,
                "matched": replay.columns == query.columns
                and replay.rows == query.rows
                and replay.truncated == query.truncated,
                "row_count": len(query.rows),
                "replay_row_count": len(replay.rows),
            }
        )
    return details


def _query_record(query: QueryResult) -> dict[str, Any]:
    return {
        "scope": query.scope,
        "sql": query.sql,
        "columns": query.columns,
        "row_count": len(query.rows),
        "preview_rows": query.rows[:5],
        "preview_display_rows": query.display_rows[:5],
        "value_mappings": query.value_mappings[:25],
        "truncated": query.truncated,
    }


def _dimension_rate(results: Sequence[dict[str, Any]], name: str) -> tuple[float, int]:
    applicable = [item["dimensions"][name] for item in results if item["dimensions"][name] is not None]
    if not applicable:
        return 1.0, 0
    return sum(value is True for value in applicable) / len(applicable), len(applicable)


def evaluate(
    database: Path,
    questions_path: Path,
    selected_ids: list[str] | None = None,
    holdout_path: Path | None = None,
    expectations_path: Path | None = None,
) -> dict[str, Any]:
    if holdout_path is None:
        holdout_path = REPO_ROOT / "tests" / "eval_holdout_questions.json"
    if expectations_path is None:
        expectations_path = REPO_ROOT / "tests" / "eval_expectations.json"
    cases = _load_cases(questions_path, holdout_path, expectations_path, selected_ids)
    agent = DataAgent(database)
    if not agent.model_available:
        raise RuntimeError("LLM_API_KEY is not configured; refusing to report a fake Agent score")

    results: list[dict[str, Any]] = []
    for case in cases:
        supported = not str(case["expect"]).startswith("reject_")
        specs = list(case["evaluation"].get("queries", []))
        gold = [agent.runner.execute(spec["gold_sql"], spec["scope"]) for spec in specs]
        response = None
        error: AgentError | None = None
        try:
            response = agent.ask(str(case["question"]))
            queries = list(response.queries)
            answer = response.answer
            actual_scope = response.scope
            coverage = response.coverage
            warnings = response.warnings
        except AgentError as exc:
            error = exc
            queries = list(getattr(exc, "partial_queries", []))
            answer = getattr(exc, "partial_answer", None)
            actual_scope = getattr(exc, "partial_scope", None)
            coverage = getattr(exc, "partial_coverage", {})
            warnings = getattr(exc, "partial_warnings", [])

        if supported:
            execution_success = (
                len(queries) == len(specs)
                and all(query.sql and query.columns for query in queries)
                and all(query.scope == spec["scope"] for query, spec in zip(queries, specs, strict=True))
            )
            semantic_ok, semantic_failures = semantic_assertions(queries, specs)
            result_ok, result_failures = result_correctness(queries, gold, specs)
            numeric_evaluable = _numeric_target_available(
                gold, specs, bool(case["evaluation"].get("numeric_answer"))
            )
            if numeric_evaluable and answer:
                try:
                    validate_answer_numbers(answer, queries, context_text=str(case["question"]))
                    numerical_grounding: bool | None = True
                except AgentError:
                    numerical_grounding = False
            elif numeric_evaluable:
                numerical_grounding = False
            else:
                numerical_grounding = None
            unsupported_handling = None
        else:
            execution_success = None
            semantic_ok = None
            result_ok = None
            semantic_failures = []
            result_failures = []
            numerical_grounding = None
            unsupported_handling = bool(
                response is not None and not queries and isinstance(answer, str) and answer.strip()
            )
            numeric_evaluable = False

        dimensions = {
            "execution_success": execution_success,
            "semantic_correctness": semantic_ok,
            "result_correctness": result_ok,
            "numerical_grounding": numerical_grounding,
            "unsupported_handling": unsupported_handling,
        }
        passed = all(value is not False for value in dimensions.values() if value is not None)
        replay_details = _replay(agent, queries) if execution_success else []
        public_gate = str(case["id"]).startswith(("h", "u", "x"))
        results.append(
            {
                "id": case["id"],
                "set": case["set"],
                "question": case["question"],
                "expected_scope": case["scope"],
                "actual_scope": actual_scope,
                "expect": case["expect"],
                "supported": supported,
                "release_track": "public_historical" if public_gate else "experimental",
                "numeric_evaluable": numeric_evaluable,
                "passed": passed,
                "answer": answer,
                "dimensions": dimensions,
                "semantic_failures": semantic_failures,
                "result_failures": result_failures,
                "queries": [_query_record(query) for query in queries],
                "gold_results": [_query_record(query) for query in gold],
                "deterministic_replay": replay_details,
                "coverage": coverage,
                "warnings": warnings,
                "error": None if error is None else {"code": error.code, "message": str(error)},
            }
        )

    supported_results = [item for item in results if item["supported"]]
    unsupported_results = [item for item in results if not item["supported"]]
    public_results = [item for item in results if item["release_track"] == "public_historical"]
    rates: dict[str, float] = {}
    denominators: dict[str, int] = {}
    for dimension in (
        "execution_success",
        "semantic_correctness",
        "result_correctness",
        "numerical_grounding",
        "unsupported_handling",
    ):
        rate, denominator = _dimension_rate(results, dimension)
        rates[f"{dimension}_rate"] = round(rate, 6)
        denominators[f"{dimension}_cases"] = denominator
    public_execution, _ = _dimension_rate(public_results, "execution_success")
    public_semantic, _ = _dimension_rate(public_results, "semantic_correctness")
    public_result, _ = _dimension_rate(public_results, "result_correctness")
    public_grounding, _ = _dimension_rate(public_results, "numerical_grounding")
    unsupported_rate, _ = _dimension_rate(unsupported_results, "unsupported_handling")
    core_stable = (
        public_execution >= 0.9
        and public_semantic >= 0.85
        and public_result >= 0.85
        and public_grounding == 1
        and unsupported_rate == 1
    )
    bad_cases = [
        {
            "id": item["id"],
            "set": item["set"],
            "question": item["question"],
            "failed_dimensions": [
                name for name, value in item["dimensions"].items() if value is False
            ],
            "semantic_failures": item["semantic_failures"],
            "result_failures": item["result_failures"],
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
            "fixed_questions": sum(item["set"] == "fixed" for item in results),
            "holdout_questions": sum(item["set"] == "holdout" for item in results),
            "supported_questions": len(supported_results),
            **rates,
            **denominators,
            "deterministic_replay_all_matched": all(
                detail["matched"]
                for item in results
                for detail in item["deterministic_replay"]
            ),
            "core_historical_stable": core_stable,
            "remaining_bad_case_count": len(bad_cases),
        },
        "remaining_bad_cases": bad_cases,
        "results": results,
    }


def main() -> int:
    args = parse_args()
    try:
        report = evaluate(
            args.database,
            args.questions,
            args.ids,
            args.holdout_questions,
            args.expectations,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Evaluation not run: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["core_historical_stable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

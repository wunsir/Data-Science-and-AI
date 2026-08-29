from __future__ import annotations

from finding_jobs.schemas import QueryResult
from scripts.evaluate_agent import result_correctness, semantic_assertions


def query(sql: str, columns: list[str], rows: list[dict]) -> QueryResult:
    return QueryResult(
        scope="historical",
        sql=sql,
        columns=columns,
        rows=rows,
    )


def test_semantic_assertions_reject_collection_keyword_and_missing_minimum() -> None:
    spec = {
        "scope": "historical",
        "metrics": ["sample_size", "median_monthly_salary"],
        "dimensions": ["city"],
        "forbidden_substrings": ["search_category"],
        "required_values": ["data"],
        "min_sample_size": 30,
    }
    wrong = query(
        "SELECT city, median(salary_mid_monthly) AS median_monthly_salary "
        "FROM jobs_scoped WHERE search_category = 'data' "
        "AND salary_parse_status = 'success' AND salary_mid_monthly IS NOT NULL "
        "GROUP BY city",
        ["city", "median_monthly_salary"],
        [],
    )
    ok, failures = semantic_assertions([wrong], [spec])
    assert not ok
    assert any("search_category" in failure for failure in failures)
    assert any("sample size" in failure for failure in failures)

    correct = query(
        "SELECT city, COUNT(*) AS sample_size, "
        "median(salary_mid_monthly) AS median_monthly_salary "
        "FROM jobs_scoped WHERE job_category = 'data' "
        "AND salary_parse_status = 'success' AND salary_mid_monthly IS NOT NULL "
        "GROUP BY city HAVING COUNT(*) >= 30",
        ["city", "sample_size", "median_monthly_salary"],
        [],
    )
    assert semantic_assertions([correct], [spec]) == (True, [])


def test_result_correctness_compares_values_not_sql_text_or_row_order() -> None:
    spec = {"result_columns": ["city", "job_count"]}
    actual = query(
        "SELECT city, COUNT(*) AS job_count FROM jobs_scoped GROUP BY city",
        ["city", "job_count"],
        [{"city": "上海", "job_count": 20}, {"city": "北京", "job_count": 10}],
    )
    gold = query(
        "SELECT city, COUNT(job_key) AS job_count FROM jobs_scoped GROUP BY city ORDER BY city",
        ["city", "job_count"],
        [{"city": "北京", "job_count": 10}, {"city": "上海", "job_count": 20}],
    )
    assert result_correctness([actual], [gold], [spec]) == (True, [])

    wrong = actual.model_copy(update={"rows": [{"city": "北京", "job_count": 11}]})
    ok, failures = result_correctness([wrong], [gold], [spec])
    assert not ok
    assert failures == ["q1: result values differ from gold result"]


def test_result_correctness_accepts_semantic_aliases_and_equivalent_empty_results() -> None:
    spec = {"result_columns": ["sample_size", "python_count"]}
    actual = query(
        "SELECT COUNT(*) AS job_count, 3 AS python_frequency FROM jobs_scoped",
        ["job_count", "python_frequency"],
        [{"job_count": 10, "python_frequency": 3}],
    )
    gold = query(
        "SELECT COUNT(*) AS sample_size, 3 AS python_count FROM jobs_scoped",
        ["sample_size", "python_count"],
        [{"sample_size": 10, "python_count": 3}],
    )
    assert result_correctness([actual], [gold], [spec]) == (True, [])

    empty_gold = gold.model_copy(update={"rows": []})
    zero_count = actual.model_copy(
        update={"columns": ["job_count"], "rows": [{"job_count": 0}]}
    )
    assert result_correctness([zero_count], [empty_gold], [spec]) == (True, [])

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from finding_jobs.agent import (
    DataAgent,
    ModelUnavailableError,
    OpenAICompatibleLLM,
    SQLiteQueryRunner,
    _parse_json_object,
    InvalidModelOutputError,
    UnsafeQueryError,
    _format_result_rows,
    semantic_scope,
    validate_answer_numbers,
    validate_select,
)
from finding_jobs.schemas import QueryResult
from finding_jobs.semantics import METRIC_DEFINITIONS, metric_prompt


def make_database(path: Path) -> Path:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE jobs (
                job_key TEXT PRIMARY KEY,
                data_scope TEXT NOT NULL,
                source TEXT NOT NULL,
                source_job_id TEXT,
                title TEXT NOT NULL,
                company TEXT,
                city TEXT,
                job_category TEXT,
                salary_min_monthly REAL,
                salary_max_monthly REAL,
                salary_mid_monthly REAL,
                education TEXT,
                experience TEXT,
                company_size TEXT,
                skills TEXT,
                description TEXT,
                source_url TEXT,
                observed_at TEXT,
                first_seen_at TEXT,
                last_seen_at TEXT,
                raw_json TEXT
            );
            CREATE TABLE dataset_versions (
                dataset_version TEXT PRIMARY KEY,
                scope_label TEXT NOT NULL,
                built_at TEXT NOT NULL
            );
            INSERT INTO dataset_versions VALUES (
                'test-v1', '2025年末采集样本', '2026-08-27T00:00:00+00:00'
            );
            CREATE VIEW jobs_analytics AS
            SELECT job_key, data_scope, source, title, company, city, job_category,
                   salary_mid_monthly, education, experience, company_size, skills,
                   observed_at
            FROM jobs;
            """
        )
        connection.executemany(
            """
            INSERT INTO jobs (
              job_key, data_scope, source, title, company, city, job_category,
              salary_mid_monthly, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("h1", "historical", "boss", "数据分析师", "A", "上海", "数据", 15000, None),
                ("h2", "historical", "zhaopin", "产品经理", "B", "深圳", "产品", 20000, None),
                ("h3", "historical", "51job", "BI分析师", "C", "上海", "数据", 18000, None),
                ("l1", "live", "lever:xsolla", "Data Analyst", "Xsolla", "北京", "数据", None, "2026-08-27T00:00:00+00:00"),
            ],
        )
    return path


class FakeLLM:
    available = True

    def plan(self, question, scope_hint, columns):
        del question, columns
        sql = "SELECT job_category, COUNT(*) AS job_count FROM jobs_scoped GROUP BY job_category ORDER BY job_count DESC"
        if scope_hint == "compare":
            return {
                "scope": "compare",
                "queries": [
                    {"scope": "historical", "sql": sql},
                    {"scope": "live", "sql": sql},
                ],
            }
        return {"scope": scope_hint, "queries": [{"scope": scope_hint, "sql": sql}]}

    def answer(self, question, scope, queries, coverage, warnings):
        del question, scope, coverage, warnings
        del queries
        return "已根据查询结果汇总。"


class MissingLLM(FakeLLM):
    available = False


def test_semantic_scope_routes_latest_and_comparison():
    assert semantic_scope("哪些岗位薪资最高") == "historical"
    assert semantic_scope("当前北京有哪些在招岗位") == "live"
    assert semantic_scope("比较当前北京与上海的职位") == "live"
    assert semantic_scope("比较2025年末和当前的岗位构成") == "compare"
    assert semantic_scope("当前岗位", "historical") == "historical"


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM jobs_scoped",
        "SELECT * FROM jobs",
        "SELECT * FROM jobs_analytics",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM jobs_scoped; DROP TABLE jobs",
        "WITH x AS (SELECT * FROM jobs_scoped) SELECT * FROM x",
        "SELECT * FROM jobs_scoped -- ignore limits",
    ],
)
def test_sql_validator_rejects_unsafe_queries(sql):
    with pytest.raises(UnsafeQueryError):
        validate_select(sql)


def test_runner_enforces_scope_and_returns_coverage(tmp_path):
    runner = SQLiteQueryRunner(make_database(tmp_path / "jobs.sqlite"))
    result = runner.execute("SELECT data_scope, COUNT(*) AS n FROM jobs_scoped", "historical")
    assert result.rows == [{"data_scope": "historical", "n": 3}]
    coverage = runner.coverage("live")
    assert coverage["row_count"] == 1
    assert coverage["sources"] == [{"source": "lever:xsolla", "count": 1}]


def test_sqlite_authorizer_blocks_non_analytics_functions(tmp_path):
    runner = SQLiteQueryRunner(make_database(tmp_path / "jobs.sqlite"))
    with pytest.raises(UnsafeQueryError):
        runner.execute("SELECT randomblob(10) AS payload FROM jobs_scoped", "historical")


def test_sqlite_authorizer_allows_read_only_like_filter(tmp_path):
    runner = SQLiteQueryRunner(make_database(tmp_path / "jobs.sqlite"))
    result = runner.execute(
        "SELECT title FROM jobs_scoped WHERE title LIKE '%分析%' ORDER BY title",
        "historical",
    )
    assert result.rows == [{"title": "BI分析师"}, {"title": "数据分析师"}]


def test_runner_provides_audited_median_aggregate(tmp_path):
    runner = SQLiteQueryRunner(make_database(tmp_path / "jobs.sqlite"))
    result = runner.execute(
        "SELECT median(salary_mid_monthly) AS median_salary "
        "FROM jobs_scoped WHERE salary_mid_monthly IS NOT NULL",
        "historical",
    )
    assert result.rows == [{"median_salary": 18000.0}]


def test_agent_historical_and_compare_responses_are_grounded(tmp_path):
    db_path = make_database(tmp_path / "jobs.sqlite")
    agent = DataAgent(db_path, llm=FakeLLM())

    historical = agent.ask("不同岗位类别的职位数是多少？")
    assert historical.scope == "historical"
    assert historical.queries[0].rows[0] == {"job_category": "数据", "job_count": 2}
    assert historical.chart.type == "bar"
    assert "便利样本" in historical.warnings[0]

    compared = agent.ask("比较2025年末与当前岗位类别构成")
    assert compared.scope == "compare"
    assert [query.scope for query in compared.queries] == ["historical", "live"]
    assert len(compared.sql) == 2
    assert any("不能解释为时间趋势" in warning for warning in compared.warnings)


def test_agent_does_not_fake_answer_when_model_is_missing(tmp_path):
    agent = DataAgent(make_database(tmp_path / "jobs.sqlite"), llm=MissingLLM())
    with pytest.raises(ModelUnavailableError):
        agent.ask("不同岗位类别有多少职位？")


def test_agent_refuses_unsupported_causal_question_without_query(tmp_path):
    agent = DataAgent(make_database(tmp_path / "jobs.sqlite"), llm=MissingLLM())
    response = agent.ask("学历是否导致薪资提高？")
    assert response.queries == []
    assert "不能识别因果效应" in response.answer


def test_agent_rejects_answer_number_absent_from_rows(tmp_path):
    class HallucinatingLLM(FakeLLM):
        def answer(self, question, scope, queries, coverage, warnings):
            del question, scope, queries, coverage, warnings
            return "样本中共有999个岗位类别。"

    agent = DataAgent(make_database(tmp_path / "jobs.sqlite"), llm=HallucinatingLLM())
    with pytest.raises(InvalidModelOutputError, match="999") as exc_info:
        agent.ask("岗位类别分布？")
    assert exc_info.value.partial_scope == "historical"
    assert len(exc_info.value.partial_queries) == 1
    assert exc_info.value.partial_answer == "样本中共有999个岗位类别。"


def test_metric_definitions_fix_core_aggregations() -> None:
    salary = METRIC_DEFINITIONS["avg_monthly_salary"]
    assert salary["expression"] == "AVG(salary_mid_monthly)"
    assert "salary_parse_status = 'success'" in salary["required_filter"]
    assert METRIC_DEFINITIONS["job_count"]["expression"] == "COUNT(*)"
    assert METRIC_DEFINITIONS["median_monthly_salary"]["expression"] == "median(salary_mid_monthly)"
    assert "skill_frequency" in metric_prompt()
    assert "median_monthly_salary" in metric_prompt()
    assert "job_category" in metric_prompt()
    assert "search_category" in metric_prompt()
    assert "COUNT(*) >= 30" in metric_prompt()


def test_deterministic_result_formatter_preserves_raw_values_and_grounding() -> None:
    rows = [
        {
            "company_size": "100-499人",
            "avg_monthly_salary": 17934.5448,
            "missing_description_rate": 0.9573,
            "job_count": 42,
            "salary_available_count": 41,
        }
    ]
    display_rows, mappings = _format_result_rows(rows)
    query = QueryResult(
        scope="historical",
        sql="SELECT 1 FROM jobs_scoped",
        columns=list(rows[0]),
        rows=rows,
        display_rows=display_rows,
        value_mappings=mappings,
    )

    assert query.rows[0]["avg_monthly_salary"] == 17934.5448
    assert query.display_rows[0]["avg_monthly_salary"] == "17,934.54元/月"
    assert query.display_rows[0]["missing_description_rate"] == "95.73%"
    assert query.display_rows[0]["salary_available_count"] == "41"
    assert any(
        item["raw_value"] == 0.9573
        and item["normalized_value"] == "95.73"
        and item["display_value"] == "95.73%"
        for item in query.value_mappings
    )
    validate_answer_numbers(
        "100-499人规模组有42条，平均月薪17,934.54元，描述缺失率95.73%。",
        [query],
    )
    with pytest.raises(InvalidModelOutputError, match="999"):
        validate_answer_numbers("该组还有999条记录。", [query])
    validate_answer_numbers(
        "月薪最高的5组（至少30条）：\n1. A\n2. B\n3. C\n4. D\n5. E",
        [query],
        context_text="列出最高5组，只看至少30条的组。",
    )


def test_agent_rejects_counterfactual_if_question_without_query(tmp_path):
    agent = DataAgent(make_database(tmp_path / "jobs.sqlite"), llm=MissingLLM())
    response = agent.ask("如果把学历提高到硕士，月薪会增加多少？")
    assert response.queries == []
    assert "反事实" in response.answer


def test_openai_compatible_client_uses_provider_neutral_environment(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "legacy-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.setenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3.2")
    monkeypatch.setenv("LLM_RESPONSE_FORMAT", "json_object")

    llm = OpenAICompatibleLLM()

    assert llm.api_key == "test-key"
    assert llm.base_url == "https://api.siliconflow.cn/v1"
    assert llm.model == "deepseek-ai/DeepSeek-V3.2"
    assert llm.response_format == "json_object"


def test_provider_json_parser_accepts_plain_and_fenced_objects():
    expected = {"scope": "historical", "queries": []}
    assert _parse_json_object('{"scope":"historical","queries":[]}') == expected
    fence = chr(96) * 3
    assert _parse_json_object(
        fence + "json\n" + '{"scope":"historical","queries":[]}' + "\n" + fence
    ) == expected

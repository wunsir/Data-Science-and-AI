"""Scoped Text-to-SQL agent with SQLite safety boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Protocol, Sequence

from openai import OpenAI

from .schemas import AskResponse, ChartSpec, QueryResult, QueryScope, Scope
from .semantics import metric_prompt


HISTORICAL_WARNING = (
    "历史数据是2025年末三平台、指定城市与关键词的便利样本，不能代表全国招聘总体。"
)
LIVE_WARNING = (
    "最新数据仅来自少量企业的公开 ATS 职位板，是实验性快照，不能代表实时招聘市场。"
)
COMPARE_WARNING = (
    "历史样本与最新 ATS 快照的来源和抽样框不同，只能分组并列查看，不能解释为时间趋势。"
)


class AgentError(Exception):
    code = "agent_error"
    status_code = 500


class ModelUnavailableError(AgentError):
    code = "model_unavailable"
    status_code = 503


class InvalidModelOutputError(AgentError):
    code = "invalid_model_output"
    status_code = 502


class DatabaseUnavailableError(AgentError):
    code = "database_unavailable"
    status_code = 503


class UnsafeQueryError(AgentError):
    code = "unsafe_query"
    status_code = 502


class QueryTimeoutError(AgentError):
    code = "query_timeout"
    status_code = 504


class LLM(Protocol):
    @property
    def available(self) -> bool: ...

    def plan(self, question: str, scope_hint: Scope, columns: Sequence[str]) -> dict[str, Any]: ...

    def answer(
        self,
        question: str,
        scope: Scope,
        queries: Sequence[QueryResult],
        coverage: dict[str, Any],
        warnings: Sequence[str],
    ) -> str: ...


class OpenAICompatibleLLM:
    """Provider-neutral OpenAI-compatible client with structured query planning."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        response_format: str | None = None,
        enable_thinking: bool | None = None,
        timeout_seconds: float = 45,
    ) -> None:
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or os.getenv(
            "LLM_BASE_URL", "https://api.siliconflow.cn/v1"
        )
        self.model = model or os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3.2")
        configured_format = response_format or os.getenv("LLM_RESPONSE_FORMAT", "json_schema")
        self.response_format = configured_format.strip().lower()
        if self.response_format not in {"json_schema", "json_object", "text"}:
            raise ValueError("LLM_RESPONSE_FORMAT 必须是 json_schema、json_object 或 text")
        if enable_thinking is None:
            thinking_value = os.getenv("LLM_ENABLE_THINKING", "false").strip().lower()
            self.enable_thinking = thinking_value in {"1", "true", "yes", "on"}
        else:
            self.enable_thinking = enable_thinking
        self._is_siliconflow = "siliconflow.cn" in self.base_url.lower()
        self.timeout_seconds = timeout_seconds
        self._client: OpenAI | None = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self) -> OpenAI:
        if not self.available:
            raise ModelUnavailableError("未配置 LLM_API_KEY，Data Agent 当前不可用")
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                max_retries=1,
            )
        return self._client

    def plan(self, question: str, scope_hint: Scope, columns: Sequence[str]) -> dict[str, Any]:
        query_count = 2 if scope_hint == "compare" else 1
        allowed_scopes = ["historical", "live"]
        response_schema = {
            "name": "scoped_sql_plan",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "scope": {"type": "string", "enum": [scope_hint]},
                    "queries": {
                        "type": "array",
                        "minItems": query_count,
                        "maxItems": query_count,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "scope": {"type": "string", "enum": allowed_scopes},
                                "sql": {"type": "string"},
                            },
                            "required": ["scope", "sql"],
                        },
                    },
                },
                "required": ["scope", "queries"],
            },
        }
        system = (
            "你是招聘数据产品的只读 SQL 规划器。只能查询临时视图 jobs_scoped；"
            "每条语句必须是单条 SELECT，不得使用注释、PRAGMA、CTE、子语句后的分号或其他表。"
            "只使用给出的列，不虚构列。聚合结果使用清楚的英文别名。"
            "compare 必须分别生成 historical 和 live 两条口径一致的查询，不能把两组数据混算。"
            "默认最多返回20个聚合组；明细问题也必须显式 LIMIT 200。\n"
            + metric_prompt()
        )
        prompt = (
            f"问题：{question}\n固定范围：{scope_hint}\n"
            f"jobs_scoped 可用列：{', '.join(columns)}\n"
            "只返回一个符合下列 JSON Schema 的 JSON 对象，不要使用 Markdown 代码块：\n"
            + json.dumps(response_schema["schema"], ensure_ascii=False)
        )
        try:
            response_format: dict[str, Any] | None
            if self.response_format == "json_schema":
                response_format = {"type": "json_schema", "json_schema": response_schema}
            elif self.response_format == "json_object":
                response_format = {"type": "json_object"}
            else:
                response_format = None
            request: dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": 1200,
            }
            if response_format is not None:
                request["response_format"] = response_format
            if self._is_siliconflow:
                request["extra_body"] = {"enable_thinking": self.enable_thinking}
            response = self._get_client().chat.completions.create(
                **request,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("empty response")
            value = _parse_json_object(content)
        except ModelUnavailableError:
            raise
        except Exception as exc:
            raise InvalidModelOutputError(f"模型未能生成有效查询计划：{exc}") from exc
        if not isinstance(value, dict):
            raise InvalidModelOutputError("模型查询计划不是 JSON 对象")
        return value

    def answer(
        self,
        question: str,
        scope: Scope,
        queries: Sequence[QueryResult],
        coverage: dict[str, Any],
        warnings: Sequence[str],
    ) -> str:
        evidence = [
            {
                "scope": query.scope,
                "columns": query.columns,
                "rows": query.rows[:50],
                "truncated": query.truncated,
            }
            for query in queries
        ]
        system = (
            "你是证据约束的招聘数据分析助手。只能根据提供的查询结果回答，"
            "所有数字必须能在结果行中直接定位。不得声称因果关系、全国代表性或时间趋势。"
            "如果结果为空就明确说没有匹配记录。compare 只并列描述两组结果及口径差异。"
            "不要复述数据覆盖范围或警告中的年份、样本量，也不要自行计算结果行中没有的数字。"
            "用简洁中文回答，不输出 SQL。"
        )
        prompt = json.dumps(
            {
                "question": question,
                "scope": scope,
                "evidence": evidence,
            },
            ensure_ascii=False,
            default=str,
        )
        try:
            request: dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": 900,
            }
            if self._is_siliconflow:
                request["extra_body"] = {"enable_thinking": self.enable_thinking}
            response = self._get_client().chat.completions.create(
                **request,
            )
            content = response.choices[0].message.content
        except ModelUnavailableError:
            raise
        except Exception as exc:
            raise InvalidModelOutputError(f"模型未能依据查询结果生成回答：{exc}") from exc
        if not content or not content.strip():
            raise InvalidModelOutputError("模型返回了空回答")
        return content.strip()


class _MedianAggregate:
    def __init__(self) -> None:
        self.values: list[float] = []

    def step(self, value: Any) -> None:
        if value is None:
            return
        numeric = float(value)
        if math.isfinite(numeric):
            self.values.append(numeric)

    def finalize(self) -> float | None:
        if not self.values:
            return None
        self.values.sort()
        midpoint = len(self.values) // 2
        if len(self.values) % 2:
            return self.values[midpoint]
        return (self.values[midpoint - 1] + self.values[midpoint]) / 2


@dataclass(slots=True)
class SQLiteQueryRunner:
    db_path: Path
    timeout_seconds: float = 2.0
    max_rows: int = 200

    def _connect(self) -> sqlite3.Connection:
        path = self.db_path.resolve()
        if not path.is_file():
            raise DatabaseUnavailableError("分析数据库不存在或尚未生成")
        connection = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro",
            uri=True,
            timeout=1,
        )
        connection.row_factory = sqlite3.Row
        connection.create_aggregate("median", 1, _MedianAggregate)
        return connection

    def columns(self) -> list[str]:
        try:
            with self._connect() as connection:
                rows = connection.execute("PRAGMA table_info(jobs_analytics)").fetchall()
        except sqlite3.Error as exc:
            raise DatabaseUnavailableError(f"无法读取 jobs_analytics：{exc}") from exc
        columns = [str(row[1]) for row in rows]
        if not columns:
            raise DatabaseUnavailableError("数据库缺少 jobs_analytics 分析视图")
        return columns

    def execute(self, sql: str, scope: QueryScope) -> QueryResult:
        normalized = validate_select(sql)
        started = time.monotonic()
        try:
            with self._connect() as connection:
                connection.execute(
                    "CREATE TEMP VIEW jobs_scoped AS "
                    f"SELECT * FROM jobs_analytics WHERE data_scope = '{scope}'"
                )
                connection.set_authorizer(_sqlite_authorizer)

                def progress() -> int:
                    return int(time.monotonic() - started > self.timeout_seconds)

                connection.set_progress_handler(progress, 1000)
                cursor = connection.execute(
                    f"SELECT * FROM ({normalized}) AS _agent_result LIMIT {self.max_rows + 1}"
                )
                raw_rows = cursor.fetchall()
                columns = [str(item[0]) for item in cursor.description or []]
        except sqlite3.DatabaseError as exc:
            message = str(exc).lower()
            if "interrupted" in message:
                raise QueryTimeoutError("查询超过执行时间限制") from exc
            if "not authorized" in message or "authorization denied" in message:
                raise UnsafeQueryError("查询触发了数据库安全边界") from exc
            raise UnsafeQueryError(f"查询无法安全执行：{exc}") from exc

        truncated = len(raw_rows) > self.max_rows
        rows = [
            {key: _json_value(row[key]) for key in columns}
            for row in raw_rows[: self.max_rows]
        ]
        return QueryResult(
            scope=scope,
            sql=normalized,
            columns=columns,
            rows=rows,
            truncated=truncated,
        )

    def coverage(self, scope: QueryScope) -> dict[str, Any]:
        columns = set(self.columns())
        select_parts = ["COUNT(*) AS row_count"]
        if "observed_at" in columns:
            select_parts.extend(
                ["MIN(observed_at) AS observed_from", "MAX(observed_at) AS observed_to"]
            )
        if "source" in columns:
            source_sql = (
                "SELECT source, COUNT(*) AS count FROM jobs_analytics "
                "WHERE data_scope = ? GROUP BY source ORDER BY count DESC"
            )
        else:
            source_sql = None
        try:
            with self._connect() as connection:
                row = connection.execute(
                    f"SELECT {', '.join(select_parts)} FROM jobs_analytics WHERE data_scope = ?",
                    (scope,),
                ).fetchone()
                sources = (
                    [dict(item) for item in connection.execute(source_sql, (scope,)).fetchall()]
                    if source_sql
                    else []
                )
        except sqlite3.Error as exc:
            raise DatabaseUnavailableError(f"无法读取数据覆盖范围：{exc}") from exc
        result = dict(row) if row is not None else {"row_count": 0}
        result["sources"] = sources
        result["scope"] = scope
        result["label"] = "2025年末历史采集样本" if scope == "historical" else "公开 ATS 最新快照"
        return result

    def dataset_metadata(self) -> dict[str, Any]:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT dataset_version, scope_label, built_at "
                    "FROM dataset_versions ORDER BY built_at DESC LIMIT 1"
                ).fetchone()
        except sqlite3.Error as exc:
            raise DatabaseUnavailableError(f"无法读取数据版本：{exc}") from exc
        if row is None:
            return {}
        return dict(row)


def validate_select(sql: str) -> str:
    value = sql.strip()
    if value.endswith(";"):
        value = value[:-1].rstrip()
    if not value or not re.match(r"(?is)^select\s", value):
        raise UnsafeQueryError("仅允许单条 SELECT 查询")
    if ";" in value or "--" in value or "/*" in value or "*/" in value:
        raise UnsafeQueryError("查询包含多语句或 SQL 注释")
    table_names = re.findall(
        r"(?is)\b(?:from|join)\s+[\"`\[]?([a-zA-Z_][a-zA-Z0-9_]*)",
        value,
    )
    if not table_names or any(name.lower() != "jobs_scoped" for name in table_names):
        raise UnsafeQueryError("查询只能访问 jobs_scoped 视图")
    forbidden = re.compile(
        r"(?is)\b(attach|detach|pragma|insert|update|delete|replace|drop|alter|create|vacuum|reindex)\b"
    )
    if forbidden.search(value):
        raise UnsafeQueryError("查询包含禁止的数据库操作")
    return value


def _sqlite_authorizer(
    action: int,
    arg1: str | None,
    arg2: str | None,
    database: str | None,
    source: str | None,
) -> int:
    del database
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        if arg1 == "jobs_scoped":
            return sqlite3.SQLITE_OK
        if arg1 == "jobs_analytics" and source == "jobs_scoped":
            return sqlite3.SQLITE_OK
        # SQLite expands the trusted persistent view before authorizing the
        # underlying table read. Direct model access to jobs is still rejected
        # by validate_select; this permits only jobs_analytics' own expansion.
        if arg1 == "jobs" and source == "jobs_analytics":
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION:
        function_name = (arg2 or arg1 or "").lower()
        allowed_functions = {
            "abs",
            "avg",
            "coalesce",
            "count",
            "date",
            "datetime",
            "exp",
            "ifnull",
            "instr",
            "length",
            "likelihood",
            "likely",
            "ln",
            "log",
            "lower",
            "max",
            "median",
            "min",
            "nullif",
            "power",
            "printf",
            "replace",
            "round",
            "sqrt",
            "strftime",
            "substr",
            "substring",
            "sum",
            "total",
            "trim",
            "upper",
        }
        return sqlite3.SQLITE_OK if function_name in allowed_functions else sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_DENY


def semantic_scope(question: str, override: Scope | None = None) -> Scope:
    if override is not None:
        return override
    normalized = question.lower()
    live_terms = (
        "当前",
        "最新",
        "实时",
        "目前",
        "现在",
        "在招",
        "开放职位",
        "open role",
        "latest",
        "current",
    )
    historical_terms = ("2025", "历史", "年末", "三平台", "historical")
    has_live = any(term in normalized for term in live_terms)
    has_historical = any(term in normalized for term in historical_terms)
    if has_live and has_historical:
        return "compare"
    if has_live:
        return "live"
    return "historical"


def unsupported_question_reason(question: str) -> str | None:
    normalized = question.lower()
    causal_terms = (
        "因果",
        "导致",
        "造成",
        "影响",
        "会让",
        "带来多少",
        "causal",
    )
    unsupported_trend_terms = (
        "趋势",
        "过去一年",
        "近一年",
        "过去几年",
        "近几年",
        "逐年",
        "历年",
        "增长了多少",
        "trend over",
    )
    if any(term in normalized for term in causal_terms):
        return "当前数据只能描述样本关联，不能识别因果效应。请改问分组差异或调整后的样本关联。"
    if any(term in normalized for term in unsupported_trend_terms):
        return "当前历史数据没有可靠的逐期观察时间，不能回答多年趋势。请改问2025年末样本分布。"
    return None


class DataAgent:
    def __init__(self, db_path: str | Path, llm: LLM | None = None) -> None:
        self.runner = SQLiteQueryRunner(Path(db_path))
        self.llm = llm or OpenAICompatibleLLM()

    @property
    def model_available(self) -> bool:
        return self.llm.available

    def ask(self, question: str, scope_override: Scope | None = None) -> AskResponse:
        scope = semantic_scope(question, scope_override)
        warning_list = _warnings_for_scope(scope)
        coverage = self._coverage(scope)
        unsupported = unsupported_question_reason(question)
        if unsupported:
            return AskResponse(
                scope=scope,
                answer=unsupported,
                sql=[],
                queries=[],
                chart=ChartSpec(type="none", title="当前数据不支持该问题"),
                coverage=coverage,
                warnings=warning_list,
            )
        if not self.llm.available:
            raise ModelUnavailableError("未配置模型密钥，Data Agent 当前不可用")

        columns = self.runner.columns()
        planned_scope: Scope | None = None
        queries: list[QueryResult] = []
        answer: str | None = None
        try:
            plan = self.llm.plan(question, scope, columns)
            planned_scope, planned_queries = _validate_plan(plan, scope)
            for query_scope, sql in planned_queries:
                queries.append(self.runner.execute(sql, query_scope))
            if any(query.truncated for query in queries):
                warning_list.append("查询结果超过200行，接口仅返回前200行。")
            answer = self.llm.answer(question, planned_scope, queries, coverage, warning_list)
            validate_answer_numbers(answer, queries)
        except AgentError as exc:
            exc.partial_scope = planned_scope
            exc.partial_queries = queries
            exc.partial_answer = answer
            exc.partial_coverage = coverage
            exc.partial_warnings = warning_list
            raise
        assert planned_scope is not None and answer is not None
        return AskResponse(
            scope=planned_scope,
            answer=answer,
            sql=[query.sql for query in queries],
            queries=queries,
            chart=build_chart(question, queries),
            coverage=coverage,
            warnings=warning_list,
        )

    def _coverage(self, scope: Scope) -> dict[str, Any]:
        if scope == "compare":
            return {
                "historical": self.runner.coverage("historical"),
                "live": self.runner.coverage("live"),
            }
        return self.runner.coverage(scope)


def _validate_plan(plan: dict[str, Any], expected_scope: Scope) -> tuple[Scope, list[tuple[QueryScope, str]]]:
    if plan.get("scope") != expected_scope:
        raise InvalidModelOutputError("模型返回的数据范围与请求语义不一致")
    raw_queries = plan.get("queries")
    expected_count = 2 if expected_scope == "compare" else 1
    if not isinstance(raw_queries, list) or len(raw_queries) != expected_count:
        raise InvalidModelOutputError(f"该范围必须生成{expected_count}条查询")
    queries: list[tuple[QueryScope, str]] = []
    for item in raw_queries:
        if not isinstance(item, dict):
            raise InvalidModelOutputError("查询计划项格式错误")
        query_scope = item.get("scope")
        sql = item.get("sql")
        if query_scope not in ("historical", "live") or not isinstance(sql, str):
            raise InvalidModelOutputError("查询计划缺少合法 scope 或 sql")
        validate_select(sql)
        queries.append((query_scope, sql))
    if expected_scope == "compare":
        if {item[0] for item in queries} != {"historical", "live"}:
            raise InvalidModelOutputError("compare 必须分别查询 historical 和 live")
    elif queries[0][0] != expected_scope:
        raise InvalidModelOutputError("查询范围与请求范围不一致")
    return expected_scope, queries


def build_chart(question: str, queries: Sequence[QueryResult]) -> ChartSpec:
    if not queries or not any(query.rows for query in queries):
        return ChartSpec(type="none", title="没有可视化数据")
    first = next(query for query in queries if query.rows)
    sample = first.rows[0]
    text_keys = [key for key, value in sample.items() if isinstance(value, str)]
    numeric_keys = [
        key
        for key, value in sample.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    ]
    if not text_keys or not numeric_keys:
        return ChartSpec(
            type="table",
            title=question,
            data=[{"scope": query.scope, **row} for query in queries for row in query.rows[:20]],
        )
    x_key, y_key = text_keys[0], numeric_keys[0]
    data = []
    for query in queries:
        for row in query.rows[:20]:
            point = {x_key: row.get(x_key), y_key: row.get(y_key)}
            if len(queries) > 1:
                point["scope"] = query.scope
            data.append(point)
    return ChartSpec(type="bar", title=question, x_key=x_key, y_key=y_key, data=data)


def validate_answer_numbers(answer: str, queries: Sequence[QueryResult]) -> None:
    """Reject model-added figures that are absent from the executed rows."""

    evidence: set[Decimal] = set()
    for query in queries:
        for row in query.rows:
            for value in row.values():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    try:
                        evidence.add(Decimal(str(value)).normalize())
                    except InvalidOperation:
                        continue
    unsupported: list[str] = []
    for token in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", answer):
        try:
            number = Decimal(token.replace(",", "")).normalize()
        except InvalidOperation:
            continue
        if number not in evidence:
            unsupported.append(token)
    if unsupported:
        values = "、".join(dict.fromkeys(unsupported))
        raise InvalidModelOutputError(f"模型回答包含结果表中不存在的数字：{values}")


def _warnings_for_scope(scope: Scope) -> list[str]:
    if scope == "historical":
        return [HISTORICAL_WARNING]
    if scope == "live":
        return [LIVE_WARNING]
    return [HISTORICAL_WARNING, LIVE_WARNING, COMPARE_WARNING]


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (datetime,)):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _parse_json_object(content: str) -> Any:
    """Parse provider output while tolerating an otherwise valid fenced object."""

    value = content.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value)
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        first = value.find("{")
        last = value.rfind("}")
        if first < 0 or last <= first:
            raise
        return json.loads(value[first : last + 1])

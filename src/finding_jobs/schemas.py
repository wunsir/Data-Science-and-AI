"""Public API schemas shared by the backend services."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Scope = Literal["historical", "live", "compare"]
QueryScope = Literal["historical", "live"]


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2, max_length=500)
    scope_override: Scope | None = None

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("问题不能为空")
        return value


class QueryResult(BaseModel):
    scope: QueryScope
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    display_rows: list[dict[str, Any]] = Field(default_factory=list)
    value_mappings: list[dict[str, Any]] = Field(default_factory=list)
    truncated: bool = False


class ChartSpec(BaseModel):
    type: Literal["bar", "table", "none"] = "none"
    title: str
    x_key: str | None = None
    y_key: str | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)


class AskResponse(BaseModel):
    scope: Scope
    answer: str
    sql: list[str]
    queries: list[QueryResult]
    chart: ChartSpec
    coverage: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class LiveRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    board: str
    city: str

    @field_validator("board")
    @classmethod
    def normalize_board(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("city")
    @classmethod
    def normalize_city(cls, value: str) -> str:
        aliases = {
            "北京": "北京",
            "上海": "上海",
            "深圳": "深圳",
            "beijing": "北京",
            "shanghai": "上海",
            "shenzhen": "深圳",
        }
        normalized = aliases.get(value.strip().lower())
        if normalized is None:
            raise ValueError("city 必须是北京、上海或深圳")
        return normalized


class LiveJob(BaseModel):
    source_job_id: str
    title: str
    company: str
    city: str
    job_category: str
    source_url: str | None = None
    observed_at: str


class LiveRefreshResponse(BaseModel):
    board: str
    city: str
    status: Literal["ok", "cached", "stale"]
    fetched_count: int
    matched_count: int
    inserted_count: int
    updated_count: int
    observed_at: str
    cache_expires_at: str | None = None
    jobs: list[LiveJob] = Field(default_factory=list)
    warning: str | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    retry_after_seconds: int | None = None

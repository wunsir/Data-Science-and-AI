"""FastAPI entrypoint for the public data product."""

from __future__ import annotations

import os
from pathlib import Path
import secrets
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .agent import AgentError, DataAgent, LLM
from .live import (
    ALLOWED_CITIES,
    BOARD_NAMES,
    LeverFetcher,
    LiveError,
    LiveRefreshService,
)
from .rate_limit import InMemoryRateLimiter, RateLimitExceeded
from .schemas import AskRequest, AskResponse, LiveRefreshRequest, LiveRefreshResponse
from .semantics import METRIC_DEFINITIONS


SESSION_COOKIE = "fj_session"


def create_app(
    *,
    db_path: str | Path | None = None,
    llm: LLM | None = None,
    lever_fetcher: LeverFetcher | None = None,
    rate_limiter: InMemoryRateLimiter | None = None,
    website_dir: str | Path | None = None,
) -> FastAPI:
    project_root = Path(__file__).resolve().parents[2]
    resolved_db_path = Path(
        db_path or os.getenv("JOBS_DB_PATH") or project_root / "artifacts" / "jobs_seed.sqlite"
    )
    resolved_website = Path(
        website_dir or os.getenv("WEBSITE_DIR") or project_root / "website"
    )

    application = FastAPI(
        title="招聘数据分析平台",
        version=__version__,
        description="2025年末历史样本与证据约束 Data Agent；ATS 刷新仅作实验保留。",
    )
    application.state.db_path = resolved_db_path
    application.state.agent = DataAgent(resolved_db_path, llm=llm)
    application.state.live = LiveRefreshService(resolved_db_path, fetcher=lever_fetcher)
    application.state.rate_limiter = rate_limiter or InMemoryRateLimiter(
        ask_per_hour=_positive_int_env("AGENT_QUESTIONS_PER_HOUR", 10),
        refresh_per_hour=_positive_int_env("LIVE_REFRESHES_PER_HOUR", 3),
        ask_per_day_global=_positive_int_env("MAX_DAILY_AGENT_QUESTIONS", 100),
    )

    @application.middleware("http")
    async def anonymous_session(request: Request, call_next):  # type: ignore[no-untyped-def]
        session_id = request.cookies.get(SESSION_COOKIE)
        is_new = not session_id or len(session_id) > 128
        if is_new:
            session_id = secrets.token_urlsafe(24)
        request.state.session_id = session_id
        response = await call_next(request)
        if is_new:
            response.set_cookie(
                SESSION_COOKIE,
                session_id,
                max_age=86400,
                httponly=True,
                secure=_truthy_env("COOKIE_SECURE", False),
                samesite="lax",
            )
        return response

    @application.exception_handler(AgentError)
    async def handle_agent_error(request: Request, exc: AgentError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": str(exc)}},
        )

    @application.exception_handler(LiveError)
    async def handle_live_error(request: Request, exc: LiveError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": str(exc)}},
        )

    @application.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(exc.retry_after_seconds)},
            content={
                "detail": {
                    "code": "rate_limit_exceeded",
                    "message": exc.message,
                    "retry_after_seconds": exc.retry_after_seconds,
                }
            },
        )

    @application.get("/api/health")
    def health(request: Request) -> dict[str, Any]:
        agent: DataAgent = request.app.state.agent
        database: dict[str, Any]
        try:
            historical = agent.runner.coverage("historical")
            live = agent.runner.coverage("live")
            database = {
                "status": "ready",
                "historical_rows": historical.get("row_count", 0),
                "live_rows": live.get("row_count", 0),
            }
        except AgentError as exc:
            database = {"status": "unavailable", "message": str(exc)}
        model_status = "ready" if agent.model_available else "unavailable"
        status = "ok" if database["status"] == "ready" else "degraded"
        return {
            "status": status,
            "version": __version__,
            "database": database,
            "model": {
                "status": model_status,
                "name": getattr(
                    agent.llm, "model", os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3.2")
                ),
            },
        }

    @application.get("/api/meta")
    def meta(request: Request) -> dict[str, Any]:
        agent: DataAgent = request.app.state.agent
        coverage: dict[str, Any] = {}
        experimental_live: dict[str, Any] = {}
        coverage_error: str | None = None
        try:
            coverage = {"historical": agent.runner.coverage("historical")}
            experimental_live = agent.runner.coverage("live")
            dataset = agent.runner.dataset_metadata()
        except AgentError as exc:
            coverage_error = str(exc)
            dataset = {}
        return {
            "title": "2025年末中国主要城市复合白领岗位样本",
            "dataset_version": dataset.get("dataset_version"),
            "dataset_built_at": dataset.get("built_at"),
            "scope_label": dataset.get("scope_label"),
            "coverage": coverage,
            "coverage_error": coverage_error,
            "model_available": agent.model_available,
            "scope_options": ["historical"],
            "scope_behavior": {
                "default": "historical",
                "public": "historical_only",
                "experimental_scopes": ["live", "compare"],
            },
            "metric_definitions": METRIC_DEFINITIONS,
            "live": {
                "status": "experimental",
                "agent_scope_public": False,
                "coverage": experimental_live,
                "boards": [
                    {"id": board, "name": name} for board, name in BOARD_NAMES.items()
                ],
                "cities": list(ALLOWED_CITIES),
                "cache_seconds": 600,
                "max_jobs_per_refresh": 50,
            },
            "limits": {
                "ask_per_session_hour": request.app.state.rate_limiter.ask_per_hour,
                "refresh_per_session_hour": request.app.state.rate_limiter.refresh_per_hour,
                "ask_global_day": request.app.state.rate_limiter.ask_per_day_global,
            },
            "sample_questions": [
                "2025年末样本中，不同岗位类别的平均月薪是多少？",
                "上海和深圳的数据岗位薪资分布有何差异？",
                "本项目样本中最常见的技能是什么？",
            ],
        }

    @application.post("/api/ask", response_model=AskResponse)
    def ask(payload: AskRequest, request: Request) -> AskResponse:
        if payload.scope_override not in (None, "historical"):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "scope_not_available",
                    "message": "公网 Data Agent 当前只提供 historical 历史样本查询。",
                },
            )
        request.app.state.rate_limiter.check("ask", request.state.session_id)
        agent: DataAgent = request.app.state.agent
        return agent.ask(payload.question, "historical")

    @application.post("/api/live/refresh", response_model=LiveRefreshResponse)
    def refresh(payload: LiveRefreshRequest, request: Request) -> LiveRefreshResponse:
        request.app.state.rate_limiter.check("refresh", request.state.session_id)
        service: LiveRefreshService = request.app.state.live
        return service.refresh(payload.board, payload.city)

    # Mount last so /api routes always take precedence. GitHub Pages can serve
    # the same directory without this backend and switch to static mode.
    if resolved_website.is_dir() and (resolved_website / "index.html").is_file():
        application.mount("/", StaticFiles(directory=resolved_website, html=True), name="website")

    return application


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _truthy_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


app = create_app()

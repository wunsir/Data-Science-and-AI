from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from finding_jobs.app import create_app
from finding_jobs.live import LiveRefreshService
from finding_jobs.rate_limit import InMemoryRateLimiter

from test_agent import FakeLLM, make_database


class FakeLever:
    def __init__(self):
        self.calls = 0

    def fetch(self, board):
        self.calls += 1
        assert board == "xsolla"
        return [
            {
                "id": "lever-1",
                "text": "Senior Data Analyst",
                "categories": {"location": "Beijing, China", "team": "Analytics"},
                "descriptionPlain": "Use Python, SQL and Tableau.",
                "hostedUrl": "https://jobs.lever.co/xsolla/lever-1",
                "salaryRange": {
                    "min": 240000,
                    "max": 360000,
                    "currency": "CNY",
                    "interval": "year",
                },
            },
            {
                "id": "lever-2",
                "text": "Product Manager",
                "categories": {"location": "London"},
            },
        ]


def make_client(db_path: Path, *, limiter=None, fetcher=None):
    app = create_app(
        db_path=db_path,
        llm=FakeLLM(),
        lever_fetcher=fetcher or FakeLever(),
        rate_limiter=limiter,
        website_dir=db_path.parent / "missing-website",
    )
    return TestClient(app)


def test_health_meta_and_agent_api(tmp_path):
    client = make_client(make_database(tmp_path / "jobs.sqlite"))

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["database"]["historical_rows"] == 3

    meta = client.get("/api/meta")
    assert meta.status_code == 200
    assert meta.json()["dataset_version"] == "test-v1"
    assert {item["id"] for item in meta.json()["live"]["boards"]} == {
        "xsolla",
        "coins",
        "ppro",
        "dlocal",
    }

    answer = client.post("/api/ask", json={"question": "各岗位类别有多少职位？"})
    assert answer.status_code == 200
    payload = answer.json()
    assert payload["scope"] == "historical"
    assert payload["sql"] == [payload["queries"][0]["sql"]]
    assert payload["queries"][0]["rows"][0]["job_count"] == 2


def test_missing_model_returns_explicit_unavailable(tmp_path):
    from test_agent import MissingLLM

    app = create_app(
        db_path=make_database(tmp_path / "jobs.sqlite"),
        llm=MissingLLM(),
        website_dir=tmp_path / "missing",
    )
    client = TestClient(app)
    response = client.post("/api/ask", json={"question": "各城市有多少职位？"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "model_unavailable"


def test_live_refresh_is_bounded_cached_and_upserted(tmp_path):
    db_path = make_database(tmp_path / "jobs.sqlite")
    fetcher = FakeLever()
    client = make_client(db_path, fetcher=fetcher)

    first = client.post("/api/live/refresh", json={"board": "xsolla", "city": "北京"})
    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert first.json()["fetched_count"] == 2
    assert first.json()["matched_count"] == 1
    assert first.json()["inserted_count"] == 1
    assert first.json()["city"] == "北京"
    assert first.json()["jobs"][0]["job_category"] == "data"

    second = client.post("/api/live/refresh", json={"board": "xsolla", "city": "Beijing"})
    assert second.status_code == 200
    assert second.json()["status"] == "cached"
    assert fetcher.calls == 1

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT data_scope, city, salary_mid_monthly FROM jobs WHERE source_job_id = 'lever-1'"
        ).fetchone()
        runs = connection.execute("SELECT COUNT(*) FROM crawl_runs").fetchone()[0]
    assert row == ("live", "北京", 25000.0)
    assert runs == 1


def test_live_refresh_rejects_non_whitelisted_board(tmp_path):
    client = make_client(make_database(tmp_path / "jobs.sqlite"))
    response = client.post(
        "/api/live/refresh", json={"board": "arbitrary-company", "city": "Beijing"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_live_target"


def test_live_upsert_preserves_first_seen_and_advances_last_seen(tmp_path):
    db_path = make_database(tmp_path / "jobs.sqlite")
    first = datetime(2026, 8, 27, 8, tzinfo=timezone.utc)
    second = datetime(2026, 8, 27, 9, tzinfo=timezone.utc)
    ticks = iter((first, first, second, second))
    service = LiveRefreshService(
        db_path,
        fetcher=FakeLever(),
        cache_ttl=timedelta(0),
        now=lambda: next(ticks),
    )

    assert service.refresh("xsolla", "北京").inserted_count == 1
    assert service.refresh("xsolla", "北京").updated_count == 1

    with sqlite3.connect(db_path) as connection:
        seen = connection.execute(
            "SELECT first_seen_at, last_seen_at FROM jobs WHERE source_job_id = 'lever-1'"
        ).fetchone()
    assert seen == (first.isoformat(), second.isoformat())


def test_anonymous_session_hourly_limit(tmp_path):
    now = datetime(2026, 8, 27, tzinfo=timezone.utc).timestamp()
    limiter = InMemoryRateLimiter(
        ask_per_hour=1,
        refresh_per_hour=3,
        ask_per_day_global=100,
        clock=lambda: now,
    )
    client = make_client(make_database(tmp_path / "jobs.sqlite"), limiter=limiter)
    assert client.post("/api/ask", json={"question": "岗位类别分布？"}).status_code == 200
    blocked = client.post("/api/ask", json={"question": "城市分布如何？"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "rate_limit_exceeded"
    assert int(blocked.headers["retry-after"]) > 0

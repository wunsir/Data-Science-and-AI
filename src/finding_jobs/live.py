"""Bounded adapter for public Lever job-board snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Callable, Protocol, Sequence
import uuid

import httpx

from .schemas import LiveJob, LiveRefreshResponse
from .taxonomy import classify_job, extract_skills


BOARD_NAMES = {
    "xsolla": "Xsolla",
    "coins": "Coins.ph",
    "ppro": "PPRO",
    "dlocal": "dLocal",
}
ALLOWED_CITIES = ("北京", "上海", "深圳")
CITY_ALIASES = {
    "北京": ("beijing", "北京"),
    "上海": ("shanghai", "上海"),
    "深圳": ("shenzhen", "深圳"),
}


class LiveError(Exception):
    code = "live_error"
    status_code = 500


class InvalidLiveTargetError(LiveError):
    code = "invalid_live_target"
    status_code = 422


class LiveUpstreamError(LiveError):
    code = "live_upstream_error"
    status_code = 502


class LiveDatabaseError(LiveError):
    code = "live_database_error"
    status_code = 503


class LeverFetcher(Protocol):
    def fetch(self, board: str) -> Sequence[dict[str, Any]]: ...


class LeverHTTPClient:
    def __init__(self, timeout_seconds: float = 12) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, board: str) -> Sequence[dict[str, Any]]:
        url = f"https://api.lever.co/v0/postings/{board}"
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=False,
                headers={"User-Agent": "FindingJobsDataDemo/0.1 (+public Lever postings)"},
            ) as client:
                response = client.get(url, params={"mode": "json"})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LiveUpstreamError(f"Lever 职位板请求失败：{exc}") from exc
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise LiveUpstreamError("Lever 返回了非预期的数据格式")
        return payload


@dataclass(slots=True)
class _CacheEntry:
    created_at: datetime
    response: LiveRefreshResponse


class LiveRefreshService:
    def __init__(
        self,
        db_path: str | Path,
        *,
        fetcher: LeverFetcher | None = None,
        cache_ttl: timedelta = timedelta(minutes=10),
        max_jobs: int = 50,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.fetcher = fetcher or LeverHTTPClient()
        self.cache_ttl = cache_ttl
        self.max_jobs = max_jobs
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._cache: dict[tuple[str, str], _CacheEntry] = {}
        self._cache_lock = threading.Lock()

    def refresh(self, board: str, city: str) -> LiveRefreshResponse:
        board = board.strip().lower()
        if board not in BOARD_NAMES:
            raise InvalidLiveTargetError(
                f"board 不在白名单中；可选值：{', '.join(BOARD_NAMES)}"
            )
        if city not in ALLOWED_CITIES:
            raise InvalidLiveTargetError(
                f"city 不在白名单中；可选值：{', '.join(ALLOWED_CITIES)}"
            )
        key = (board, city)
        now = _as_utc(self._now())
        cached = self._get_cache(key)
        if cached and now - cached.created_at < self.cache_ttl:
            return cached.response.model_copy(update={"status": "cached"})

        run_id = str(uuid.uuid4())
        try:
            raw_jobs = list(self.fetcher.fetch(board))
            matching = [item for item in raw_jobs if _matches_city(item, city)]
            normalized = [
                _normalize_job(board, city, item, now)
                for item in matching[: self.max_jobs]
            ]
            inserted, updated = self._upsert_jobs(normalized, run_id, board, city, len(raw_jobs), now)
        except (LiveUpstreamError, LiveDatabaseError) as exc:
            self._record_failed_run(run_id, board, city, now, exc)
            if cached:
                return cached.response.model_copy(
                    update={
                        "status": "stale",
                        "warning": f"本次刷新失败，展示上次缓存：{exc}",
                    }
                )
            raise

        response = LiveRefreshResponse(
            board=board,
            city=city,
            status="ok",
            fetched_count=len(raw_jobs),
            matched_count=len(matching),
            inserted_count=inserted,
            updated_count=updated,
            observed_at=now.isoformat(),
            cache_expires_at=(now + self.cache_ttl).isoformat(),
            jobs=[_public_job(item) for item in normalized],
            warning=(
                f"匹配记录超过{self.max_jobs}条，本次只规范化前{self.max_jobs}条。"
                if len(matching) > self.max_jobs
                else None
            ),
        )
        with self._cache_lock:
            self._cache[key] = _CacheEntry(now, response)
        return response

    def _get_cache(self, key: tuple[str, str]) -> _CacheEntry | None:
        with self._cache_lock:
            return self._cache.get(key)

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.is_file():
            raise LiveDatabaseError("运行时数据库不存在或尚未初始化")
        try:
            connection = sqlite3.connect(self.db_path, timeout=5)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        except sqlite3.Error as exc:
            raise LiveDatabaseError(f"无法打开运行时数据库：{exc}") from exc

    def _upsert_jobs(
        self,
        jobs: Sequence[dict[str, Any]],
        run_id: str,
        board: str,
        city: str,
        fetched_count: int,
        now: datetime,
    ) -> tuple[int, int]:
        inserted = 0
        updated = 0
        try:
            with self._connect() as connection:
                columns = _table_columns(connection, "jobs")
                if "job_key" not in columns:
                    raise LiveDatabaseError("jobs 表缺少 job_key，无法安全去重写入")
                for job in jobs:
                    existing = connection.execute(
                        "SELECT 1 FROM jobs WHERE job_key = ? LIMIT 1", (job["job_key"],)
                    ).fetchone()
                    writable = {key: value for key, value in job.items() if key in columns}
                    if existing:
                        updates = {
                            key: value
                            for key, value in writable.items()
                            if key not in {"job_key", "first_seen_at"}
                        }
                        if updates:
                            assignments = ", ".join(f'"{key}" = ?' for key in updates)
                            connection.execute(
                                f'UPDATE jobs SET {assignments} WHERE job_key = ?',
                                (*updates.values(), job["job_key"]),
                            )
                        updated += 1
                    else:
                        names = ", ".join(f'"{key}"' for key in writable)
                        placeholders = ", ".join("?" for _ in writable)
                        connection.execute(
                            f"INSERT INTO jobs ({names}) VALUES ({placeholders})",
                            tuple(writable.values()),
                        )
                        inserted += 1
                _write_run(
                    connection,
                    {
                        "run_id": run_id,
                        "crawl_run_id": run_id,
                        "source": "lever",
                        "board": board,
                        "city": city,
                        "started_at": now.isoformat(),
                        "finished_at": _as_utc(self._now()).isoformat(),
                        "status": "success",
                        "fetched_count": fetched_count,
                        "found_count": len(jobs),
                        "inserted_count": inserted,
                        "updated_count": updated,
                        "error_message": None,
                    },
                )
        except LiveDatabaseError:
            raise
        except sqlite3.Error as exc:
            raise LiveDatabaseError(f"实时职位写入失败：{exc}") from exc
        return inserted, updated

    def _record_failed_run(
        self,
        run_id: str,
        board: str,
        city: str,
        now: datetime,
        error: Exception,
    ) -> None:
        try:
            with self._connect() as connection:
                _write_run(
                    connection,
                    {
                        "run_id": run_id,
                        "crawl_run_id": run_id,
                        "source": "lever",
                        "board": board,
                        "city": city,
                        "started_at": now.isoformat(),
                        "finished_at": _as_utc(self._now()).isoformat(),
                        "status": "failed",
                        "fetched_count": 0,
                        "found_count": 0,
                        "inserted_count": 0,
                        "updated_count": 0,
                        "error_message": str(error)[:500],
                    },
                )
        except LiveError:
            return
        except sqlite3.Error:
            return


def _normalize_job(
    board: str,
    city: str,
    item: dict[str, Any],
    observed_at: datetime,
) -> dict[str, Any]:
    source_job_id = str(item.get("id") or "").strip()
    title = str(item.get("text") or "未命名职位").strip()
    if not source_job_id:
        stable = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
        source_job_id = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]
    categories = item.get("categories") if isinstance(item.get("categories"), dict) else {}
    search_category = str(categories.get("team") or categories.get("department") or "")
    taxonomy_hint = _lever_taxonomy_hint(title, search_category)
    description = str(item.get("descriptionPlain") or item.get("description") or "").strip()
    (
        salary_min,
        salary_max,
        salary_mid,
        raw_salary,
        parse_status,
        salary_period,
        salary_min_raw,
        salary_max_raw,
        parse_reason,
    ) = _salary(item.get("salaryRange"))
    timestamp = observed_at.isoformat()
    job_key = hashlib.sha256(f"lever|{board}|{source_job_id}".encode("utf-8")).hexdigest()
    return {
        "job_key": job_key,
        "data_scope": "live",
        "source": f"lever:{board}",
        "source_job_id": source_job_id,
        "title": title,
        "company": BOARD_NAMES[board],
        "city": city,
        "job_category": classify_job(title, taxonomy_hint),
        "search_category": search_category,
        "salary_min_monthly": salary_min,
        "salary_max_monthly": salary_max,
        "salary_mid_monthly": salary_mid,
        "salary_raw": raw_salary,
        "salary_period": salary_period,
        "salary_min_raw": salary_min_raw,
        "salary_max_raw": salary_max_raw,
        "salary_parse_status": parse_status,
        "salary_parse_reason": parse_reason,
        "salary_pay_months": None,
        "education": None,
        "experience": None,
        "company_size": None,
        "skills": json.dumps(extract_skills((title, description)), ensure_ascii=False),
        "description": description,
        "source_url": _safe_url(item.get("hostedUrl") or item.get("applyUrl")),
        "observed_at": timestamp,
        "first_seen_at": timestamp,
        "last_seen_at": timestamp,
        "raw_json": json.dumps(item, ensure_ascii=False, default=str),
    }


def _matches_city(item: dict[str, Any], city: str) -> bool:
    categories = item.get("categories") if isinstance(item.get("categories"), dict) else {}
    location = str(categories.get("location") or item.get("location") or "").lower()
    return any(alias in location for alias in CITY_ALIASES[city])


def _salary(
    value: Any,
) -> tuple[
    float | None,
    float | None,
    float | None,
    str | None,
    str,
    str,
    float | None,
    float | None,
    str,
]:
    if not isinstance(value, dict):
        return None, None, None, None, "missing", "unknown", None, None, "missing"
    raw = json.dumps(value, ensure_ascii=False, default=str)
    currency = str(value.get("currency") or "").upper()
    interval = str(value.get("interval") or "").lower()
    period = {
        "year": "annual",
        "yearly": "annual",
        "annual": "annual",
        "annually": "annual",
        "month": "monthly",
        "monthly": "monthly",
    }.get(interval, "unknown")
    try:
        low = float(value["min"])
        high = float(value["max"])
    except (KeyError, TypeError, ValueError):
        return None, None, None, raw, "parse_failed", period, None, None, "invalid_structure"
    if currency not in ("CNY", "RMB"):
        return None, None, None, raw, "unsupported", period, low, high, "unsupported_currency"
    low_raw, high_raw = low, high
    if interval in ("year", "yearly", "annual", "annually"):
        low, high = low / 12, high / 12
    elif interval not in ("month", "monthly"):
        return None, None, None, raw, "unsupported", "unknown", low_raw, high_raw, "unsupported_interval"
    if low < 0 or high < low:
        return None, None, None, raw, "parse_failed", period, low_raw, high_raw, "invalid_range"
    return (
        round(low, 2),
        round(high, 2),
        round((low + high) / 2, 2),
        raw,
        "success",
        period,
        low_raw,
        high_raw,
        f"{period}_range",
    )


def _lever_taxonomy_hint(title: str, team: str) -> str:
    """Translate common ATS English labels into the shared taxonomy fallbacks."""

    value = f"{title} {team}".lower()
    rules = (
        ("商业分析", ("business analyst", "business analysis", "strategy analyst")),
        ("数据分析", ("data", "analytics", "business intelligence", " bi ")),
        ("产品", ("product",)),
        ("运营", ("operation", "growth", "customer success")),
        ("金融", ("finance", "financial", "risk", "investment", "quant")),
    )
    for fallback, terms in rules:
        if any(term in value for term in terms):
            return fallback
    return team


def _public_job(item: dict[str, Any]) -> LiveJob:
    return LiveJob(
        source_job_id=item["source_job_id"],
        title=item["title"],
        company=item["company"],
        city=item["city"],
        job_category=item["job_category"],
        source_url=item.get("source_url"),
        observed_at=item["observed_at"],
    )


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {str(row[1]) for row in rows}


def _write_run(connection: sqlite3.Connection, values: dict[str, Any]) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS crawl_runs (
            run_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            board TEXT,
            city TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            fetched_count INTEGER NOT NULL DEFAULT 0,
            found_count INTEGER NOT NULL DEFAULT 0,
            inserted_count INTEGER NOT NULL DEFAULT 0,
            updated_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        )
        """
    )
    columns = _table_columns(connection, "crawl_runs")
    writable = {key: value for key, value in values.items() if key in columns}
    if not writable:
        return
    names = ", ".join(f'"{key}"' for key in writable)
    placeholders = ", ".join("?" for _ in writable)
    connection.execute(
        f"INSERT INTO crawl_runs ({names}) VALUES ({placeholders})",
        tuple(writable.values()),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_url(value: Any) -> str | None:
    url = str(value or "").strip()
    return url if url.lower().startswith("https://") else None

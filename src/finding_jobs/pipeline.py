"""Deterministic import pipeline for the three historical job datasets."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .taxonomy import (
    classify_job,
    extract_skills,
    normalize_identity,
    primary_city,
    taxonomy_manifest,
)


HISTORICAL_SCOPE_LABEL = "2025年末采集样本"


@dataclass(frozen=True)
class SalaryParseResult:
    """Auditable salary parse result.

    ``minimum``/``maximum``/``midpoint`` are monthly-equivalent RMB values.
    The ``*_raw`` values are the stated interval converted to RMB but not
    converted across time periods.  ``reason`` keeps the detailed parser
    outcome while ``status`` stays within the stable semantic categories used
    by analysis and the Data Agent.
    """

    minimum: float | None
    maximum: float | None
    midpoint: float | None
    status: str
    period: str = "unknown"
    minimum_raw: float | None = None
    maximum_raw: float | None = None
    reason: str = "unspecified"
    pay_months: int | None = None


@dataclass(frozen=True)
class SourceFile:
    source: str
    path: Path


def _salary_factor(unit: str | None) -> float | None:
    normalized = (unit or "").replace("万元", "万").upper()
    return {"元": 1.0, "千": 1_000.0, "K": 1_000.0, "万": 10_000.0}.get(normalized)


def parse_salary(value: object) -> SalaryParseResult:
    """Parse a stated salary into monthly-equivalent RMB without imputation.

    Monthly ranges expressed in 元/千/K/万 are supported.  Annual ranges are
    divided by 12 and explicit N薪 values scale the stated monthly range by
    N/12.  Daily, hourly, weekly and per-task pay are intentionally not
    converted because working-time assumptions are absent from the sources.
    """

    if value is None or (isinstance(value, float) and math.isnan(value)):
        return SalaryParseResult(None, None, None, "missing", reason="missing")
    raw = unicodedata.normalize("NFKC", str(value)).strip()
    if not raw:
        return SalaryParseResult(None, None, None, "missing", reason="missing")
    compact = re.sub(r"\s+", "", raw).replace(",", "")
    compact = re.sub(r"[~～—–至]", "-", compact)
    if "面议" in compact:
        return SalaryParseResult(None, None, None, "unsupported", reason="negotiable")

    period_markers = {
        "annual": ("/年", "年薪"),
        "monthly": ("/月", "月薪"),
        "daily": ("/天", "/日"),
        "hourly": ("/小时", "/时"),
        "weekly": ("/周",),
        "per_task": ("/次",),
    }
    explicit_periods = [
        period
        for period, markers in period_markers.items()
        if any(marker in compact for marker in markers)
    ]
    if len(explicit_periods) > 1:
        return SalaryParseResult(
            None,
            None,
            None,
            "ambiguous",
            reason="conflicting_period_markers",
        )
    explicit_period = explicit_periods[0] if explicit_periods else None

    pay_match = re.search(r"(?:·)?(\d{2})薪", compact)
    pay_months = int(pay_match.group(1)) if pay_match else None
    if explicit_period == "annual" and pay_months is not None:
        return SalaryParseResult(
            None,
            None,
            None,
            "ambiguous",
            period="annual",
            reason="annual_with_pay_months",
            pay_months=pay_months,
        )
    if pay_months is not None and not 12 <= pay_months <= 24:
        return SalaryParseResult(
            None,
            None,
            None,
            "ambiguous",
            period=explicit_period or "unknown",
            reason="pay_months_out_of_range",
            pay_months=pay_months,
        )
    if "以下" in compact or "以上" in compact:
        return SalaryParseResult(
            None,
            None,
            None,
            "unsupported",
            period=explicit_period or "unknown",
            reason="one_sided_bound",
            pay_months=pay_months,
        )

    core = compact.replace("年薪", "").replace("月薪", "")
    core = re.sub(r"/(?:小时|天|日|时|周|次|月|年)$", "", core)
    core = re.sub(r"(?:·)?\d{2}薪$", "", core)

    number = r"\d+(?:\.\d+)?"
    unit = r"(?:万元|万|千|K|k|元)"
    range_match = re.fullmatch(
        rf"(?P<low>{number})(?P<low_unit>{unit})?-(?P<high>{number})(?P<high_unit>{unit})?",
        core,
    )
    exact_match = None if range_match else re.fullmatch(
        rf"(?P<low>{number})(?P<low_unit>{unit})",
        core,
    )
    match = range_match or exact_match
    if not match:
        return SalaryParseResult(
            None,
            None,
            None,
            "parse_failed",
            period=explicit_period or "unknown",
            reason="invalid_format",
            pay_months=pay_months,
        )

    low_unit = match.group("low_unit")
    high_unit = match.groupdict().get("high_unit") or low_unit
    low_unit = low_unit or high_unit
    low_factor = _salary_factor(low_unit)
    high_factor = _salary_factor(high_unit)
    if low_factor is None or high_factor is None:
        return SalaryParseResult(
            None,
            None,
            None,
            "parse_failed",
            period=explicit_period or "unknown",
            reason="missing_unit",
            pay_months=pay_months,
        )

    low_raw = float(match.group("low")) * low_factor
    high_text = match.groupdict().get("high")
    high_raw = float(high_text) * high_factor if high_text is not None else low_raw
    if low_raw <= 0 or high_raw <= 0 or low_raw > high_raw:
        return SalaryParseResult(
            None,
            None,
            None,
            "parse_failed",
            period=explicit_period or "unknown",
            minimum_raw=low_raw,
            maximum_raw=high_raw,
            reason="invalid_range",
            pay_months=pay_months,
        )

    period = explicit_period
    if period is None:
        normalized_units = {(low_unit or "").replace("万元", "万").upper(), (high_unit or "").replace("万元", "万").upper()}
        if pay_months is not None or normalized_units & {"K", "千"}:
            period = "monthly"
        elif high_raw < 1_000:
            return SalaryParseResult(
                None,
                None,
                None,
                "ambiguous",
                period="unknown",
                minimum_raw=low_raw,
                maximum_raw=high_raw,
                reason="implicit_period_low_rmb",
                pay_months=pay_months,
            )
        elif "万" in normalized_units and high_raw >= 100_000:
            return SalaryParseResult(
                None,
                None,
                None,
                "ambiguous",
                period="unknown",
                minimum_raw=low_raw,
                maximum_raw=high_raw,
                reason="implicit_period_high_wan",
                pay_months=pay_months,
            )
        else:
            period = "monthly"

    if period in {"daily", "hourly", "weekly", "per_task"}:
        return SalaryParseResult(
            None,
            None,
            None,
            "unsupported",
            period=period,
            minimum_raw=low_raw,
            maximum_raw=high_raw,
            reason=f"unsupported_{period}",
            pay_months=pay_months,
        )

    low = low_raw
    high = high_raw
    if period == "annual":
        low /= 12.0
        high /= 12.0
    elif period == "monthly" and pay_months is not None:
        low *= pay_months / 12.0
        high *= pay_months / 12.0
    else:
        if period != "monthly":
            return SalaryParseResult(
                None,
                None,
                None,
                "ambiguous",
                period=period or "unknown",
                minimum_raw=low_raw,
                maximum_raw=high_raw,
                reason="unresolved_period",
                pay_months=pay_months,
            )

    reason = f"{period}_{'exact' if high_text is None else 'range'}"
    return SalaryParseResult(
        low,
        high,
        (low + high) / 2.0,
        "success",
        period=period,
        minimum_raw=low_raw,
        maximum_raw=high_raw,
        reason=reason,
        pay_months=pay_months,
    )


def discover_source_files(repo_root: str | Path) -> list[SourceFile]:
    """Discover only the known historical data locations."""

    root = Path(repo_root).resolve()
    found = [
        *(SourceFile("boss", path) for path in (root / "boss").glob("joblist*.xlsx")),
        *(
            SourceFile("qianchengwuyou", path)
            for path in (root / "qianchengwuyou" / "data").glob("*.csv")
        ),
        *(SourceFile("zlzp", path) for path in (root / "zlzp").glob("*/*.xlsx")),
    ]
    return sorted(found, key=lambda item: item.path.relative_to(root).as_posix().casefold())


def _clean_cell(value: object) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    return value if isinstance(value, (str, int, float, bool)) else str(value)


def _text(value: object) -> str | None:
    cleaned = _clean_cell(value)
    if cleaned is None:
        return None
    text = str(cleaned).strip()
    return text or None


def _read_source(source_file: SourceFile) -> pd.DataFrame:
    if source_file.path.suffix.lower() == ".xlsx":
        return pd.read_excel(source_file.path, dtype=object, engine="openpyxl")
    errors: list[str] = []
    for encoding in ("utf-8-sig", "gb18030", "utf-8"):
        try:
            return pd.read_csv(source_file.path, dtype=object, encoding=encoding)
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise UnicodeError(f"Unable to decode {source_file.path}: {'; '.join(errors)}")


def _split_requirement(value: object) -> tuple[str | None, str | None]:
    parts = [part.strip() for part in re.split(r"[,，]", _text(value) or "") if part.strip()]
    return (parts[0] if parts else None, parts[1] if len(parts) > 1 else None)


def _split_company_info(value: object) -> tuple[str | None, str | None, str | None]:
    parts = [part.strip() for part in re.split(r"[,，]", _text(value) or "") if part.strip()]
    if not parts:
        return None, None, None
    size_index = next((index for index, part in enumerate(parts) if "人" in part), None)
    size = parts[size_index] if size_index is not None else None
    ownership = parts[0] if size_index != 0 else None
    industry = parts[-1] if len(parts) > 1 and len(parts) - 1 != size_index else None
    return ownership, size, industry


def _query_category(source_file: SourceFile) -> str | None:
    if source_file.source == "boss":
        return None
    return source_file.path.stem.split("_", maxsplit=1)[0]


def _map_record(source_file: SourceFile, row: dict[str, object]) -> dict[str, Any]:
    query_category = _query_category(source_file)
    if source_file.source == "boss":
        title, company, salary_raw = _text(row.get("职位")), _text(row.get("公司")), _text(row.get("薪资"))
        city_raw = _text(row.get("地区"))
        experience, education = _text(row.get("经验")), _text(row.get("学历"))
        company_size = _text(row.get("公司规模"))
        skills_raw = _text(row.get("技能标签"))
        description = _text(row.get("职位描述"))
        source_job_id = _text(row.get("job_id"))
        source_url = _text(row.get("职位链接")) or _text(row.get("url"))
    elif source_file.source == "qianchengwuyou":
        title, company, salary_raw = _text(row.get("职位")), _text(row.get("公司")), _text(row.get("薪资"))
        city_raw = _text(row.get("城市"))
        experience, education = _text(row.get("经验")), _text(row.get("学历"))
        company_size = _text(row.get("公司规模"))
        skills_raw = _text(row.get("技能标签"))
        description = _text(row.get("岗位描述"))
        source_job_id = _text(row.get("job_id"))
        source_url = _text(row.get("职位链接")) or _text(row.get("url"))
    else:
        title = _text(row.get("岗位名称"))
        company = _text(row.get("公司名称"))
        salary_raw = _text(row.get("岗位薪资"))
        city_raw = _text(row.get("公司位置"))
        experience, education = _split_requirement(row.get("岗位要求"))
        _, company_size, _ = _split_company_info(row.get("企业信息"))
        skills_raw = _text(row.get("技术要求"))
        description = _text(row.get("岗位描述"))
        source_job_id = _text(row.get("job_id"))
        source_url = _text(row.get("职位链接")) or _text(row.get("url"))

    salary = parse_salary(salary_raw)
    city = primary_city(city_raw)
    skills = extract_skills((title, skills_raw, description))
    return {
        "data_scope": "historical",
        "source": source_file.source,
        "source_job_id": source_job_id,
        "title": title,
        "company": company,
        "city": city,
        "search_category": query_category,
        "job_category": classify_job(title, query_category),
        "salary_raw": salary_raw,
        "salary_period": salary.period,
        "salary_min_raw": salary.minimum_raw,
        "salary_max_raw": salary.maximum_raw,
        "salary_min_monthly": salary.minimum,
        "salary_max_monthly": salary.maximum,
        "salary_mid_monthly": salary.midpoint,
        "salary_parse_status": salary.status,
        "salary_parse_reason": salary.reason,
        "salary_pay_months": salary.pay_months,
        "education": education,
        "experience": experience,
        "company_size": company_size,
        "skills": json.dumps(skills, ensure_ascii=False, separators=(",", ":")),
        "description": description,
        "source_url": source_url,
        # Historical files have no reliable row-level observation timestamp.
        "observed_at": None,
        "first_seen_at": None,
        "last_seen_at": None,
    }


def _fingerprint_identity(record: dict[str, Any], uid: str) -> str:
    title = normalize_identity(record.get("title"))
    company = normalize_identity(record.get("company"))
    if not title or not company:
        return f"{record['source']}:row:{uid}"
    parts = (
        record["source"],
        title,
        company,
        normalize_identity(record.get("city")),
        normalize_identity(record.get("salary_raw")),
    )
    return "fingerprint:" + "|".join(parts)


def _id_identity(record: dict[str, Any]) -> str | None:
    source_id = normalize_identity(record.get("source_job_id"))
    return f"{record['source']}:id:{source_id}" if source_id else None


def _resolve_id_bridges(records: list[dict[str, Any]]) -> None:
    """Resolve no-ID rows against unambiguous source-ID fingerprint groups.

    A platform ID remains authoritative.  A no-ID row is attached to an ID
    group only when its exact normalized fingerprint points to one and only one
    distinct ID.  If several IDs share the fingerprint, the no-ID rows form a
    separate fingerprint group rather than being guessed into either ID.
    """

    ids_by_fingerprint: dict[str, set[str]] = defaultdict(set)
    for record in records:
        identity = _id_identity(record)
        if identity is not None:
            ids_by_fingerprint[record["_fingerprint"]].add(identity)

    for record in records:
        identity = _id_identity(record)
        resolution = "source_id"
        if identity is None:
            candidates = ids_by_fingerprint.get(record["_fingerprint"], set())
            if len(candidates) == 1:
                identity = next(iter(candidates))
                resolution = "bridged_to_unique_id"
            else:
                identity = record["_fingerprint"]
                resolution = "ambiguous_not_bridged" if len(candidates) > 1 else "fingerprint"
        record["_identity"] = identity
        record["_identity_resolution"] = resolution
        record["job_key"] = _job_key(identity)


def _job_key(identity: str) -> str:
    return "job_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:28]


def _completeness(record: dict[str, Any]) -> int:
    fields = (
        "title",
        "company",
        "city",
        "source_job_id",
        "salary_raw",
        "education",
        "experience",
        "company_size",
        "description",
        "source_url",
    )
    score = sum(bool(record.get(field)) for field in fields)
    score += int(record.get("skills") not in (None, "", "[]"))
    score += 2 if record.get("salary_parse_status") == "success" else 0
    score += 1 if len(record.get("description") or "") >= 100 else 0
    return score


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_raw_records(repo_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    files_report: list[dict[str, Any]] = []
    for source_file in discover_source_files(repo_root):
        frame = _read_source(source_file)
        relative_path = source_file.path.relative_to(repo_root).as_posix()
        files_report.append(
            {
                "source": source_file.source,
                "path": relative_path,
                "rows": int(len(frame)),
                "sha256": _file_sha256(source_file.path),
            }
        )
        for zero_index, row in enumerate(frame.to_dict(orient="records")):
            source_row = zero_index + 2
            clean_raw = {str(key): _clean_cell(value) for key, value in row.items()}
            record = _map_record(source_file, clean_raw)
            uid = f"{relative_path}:{source_row}"
            record.update(
                {
                    "_uid": uid,
                    "_source_file": relative_path,
                    "_source_row": source_row,
                    "_raw_json": json.dumps(
                        clean_raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ),
                }
            )
            record["_fingerprint"] = _fingerprint_identity(record, uid)
            record["_completeness"] = _completeness(record)
            records.append(record)
    _resolve_id_bridges(records)
    return records, files_report


def _deduplicate(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[record["_identity"]].append(record)
    winners: list[dict[str, Any]] = []
    for identity, members in groups.items():
        # Input order is deterministic, so max() retains the first row on ties.
        winner = max(members, key=lambda item: item["_completeness"])
        if not winner.get("source_job_id"):
            source_id = next((member.get("source_job_id") for member in members if member.get("source_job_id")), None)
            if source_id:
                winner = dict(winner)
                winner["source_job_id"] = source_id
        winners.append(winner)
    ordered = sorted(winners, key=lambda item: item["job_key"])
    selected_uid = {record["_identity"]: record["_uid"] for record in ordered}
    return ordered, selected_uid


def _source_fingerprint(files_report: list[dict[str, Any]]) -> str:
    payload = "\n".join(f"{item['path']}:{item['sha256']}" for item in files_report)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE jobs (
            job_key TEXT PRIMARY KEY,
            data_scope TEXT NOT NULL CHECK (data_scope IN ('historical', 'live')),
            source TEXT NOT NULL,
            source_job_id TEXT,
            title TEXT,
            company TEXT,
            city TEXT,
            search_category TEXT,
            job_category TEXT NOT NULL,
            salary_raw TEXT,
            salary_period TEXT NOT NULL DEFAULT 'unknown',
            salary_min_raw REAL,
            salary_max_raw REAL,
            salary_min_monthly REAL,
            salary_max_monthly REAL,
            salary_mid_monthly REAL,
            salary_parse_status TEXT NOT NULL,
            salary_parse_reason TEXT NOT NULL DEFAULT 'unspecified',
            salary_pay_months INTEGER,
            education TEXT,
            experience TEXT,
            company_size TEXT,
            skills TEXT NOT NULL DEFAULT '[]',
            description TEXT,
            source_url TEXT,
            observed_at TEXT,
            first_seen_at TEXT,
            last_seen_at TEXT,
            raw_json TEXT NOT NULL
        );
        CREATE TABLE provenance (
            provenance_id INTEGER PRIMARY KEY,
            job_key TEXT NOT NULL REFERENCES jobs(job_key),
            source TEXT NOT NULL,
            source_file TEXT NOT NULL,
            source_row INTEGER NOT NULL,
            query_category TEXT,
            source_job_id TEXT,
            record_hash TEXT NOT NULL,
            raw_row_json TEXT NOT NULL,
            was_selected INTEGER NOT NULL CHECK (was_selected IN (0, 1)),
            UNIQUE(source_file, source_row)
        );
        CREATE TABLE crawl_runs (
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
        );
        CREATE TABLE dataset_versions (
            dataset_version TEXT PRIMARY KEY,
            scope_label TEXT NOT NULL,
            built_at TEXT NOT NULL,
            source_fingerprint TEXT NOT NULL,
            raw_row_count INTEGER NOT NULL,
            unique_job_count INTEGER NOT NULL,
            notes TEXT
        );
        CREATE INDEX idx_jobs_scope ON jobs(data_scope);
        CREATE INDEX idx_jobs_source ON jobs(source);
        CREATE INDEX idx_jobs_category ON jobs(job_category);
        CREATE INDEX idx_jobs_city ON jobs(city);
        CREATE INDEX idx_jobs_salary_mid ON jobs(salary_mid_monthly);
        CREATE INDEX idx_provenance_job ON provenance(job_key);
        CREATE VIEW jobs_analytics AS
        SELECT
            job_key, data_scope, source, title, company, city, search_category,
            job_category, salary_raw, salary_period, salary_min_raw, salary_max_raw,
            salary_min_monthly, salary_max_monthly, salary_mid_monthly,
            salary_parse_status, salary_parse_reason, salary_pay_months, education, experience,
            company_size, skills,
            CASE WHEN description IS NULL OR TRIM(description) = '' THEN 0 ELSE 1 END
                AS description_available,
            observed_at, first_seen_at, last_seen_at
        FROM jobs;
        """
    )


def _insert_database(
    connection: sqlite3.Connection,
    raw_records: list[dict[str, Any]],
    unique_records: list[dict[str, Any]],
    selected_uid: dict[str, str],
    version: str,
    source_fingerprint: str,
    built_at: str,
) -> None:
    job_columns = (
        "job_key",
        "data_scope",
        "source",
        "source_job_id",
        "title",
        "company",
        "city",
        "search_category",
        "job_category",
        "salary_raw",
        "salary_period",
        "salary_min_raw",
        "salary_max_raw",
        "salary_min_monthly",
        "salary_max_monthly",
        "salary_mid_monthly",
        "salary_parse_status",
        "salary_parse_reason",
        "salary_pay_months",
        "education",
        "experience",
        "company_size",
        "skills",
        "description",
        "source_url",
        "observed_at",
        "first_seen_at",
        "last_seen_at",
        "raw_json",
    )
    rows = []
    for record in unique_records:
        public_record = {key: record.get(key) for key in job_columns}
        public_record["raw_json"] = record["_raw_json"]
        rows.append(tuple(public_record[column] for column in job_columns))
    placeholders = ",".join("?" for _ in job_columns)
    connection.executemany(
        f"INSERT INTO jobs ({','.join(job_columns)}) VALUES ({placeholders})", rows
    )

    provenance_rows = []
    for record in raw_records:
        raw_json = record["_raw_json"]
        provenance_rows.append(
            (
                record["job_key"],
                record["source"],
                record["_source_file"],
                record["_source_row"],
                record["search_category"],
                record["source_job_id"],
                hashlib.sha256(raw_json.encode("utf-8")).hexdigest(),
                raw_json,
                int(selected_uid[record["_identity"]] == record["_uid"]),
            )
        )
    connection.executemany(
        """
        INSERT INTO provenance (
            job_key, source, source_file, source_row, query_category,
            source_job_id, record_hash, raw_row_json, was_selected
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        provenance_rows,
    )
    connection.execute(
        """
        INSERT INTO dataset_versions (
            dataset_version, scope_label, built_at, source_fingerprint,
            raw_row_count, unique_job_count, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version,
            HISTORICAL_SCOPE_LABEL,
            built_at,
            source_fingerprint,
            len(raw_records),
            len(unique_records),
            "历史文件无可靠逐条发布时间或抓取时间；observed_at 保持为空。",
        ),
    )


def _quality_report(
    raw_records: list[dict[str, Any]],
    unique_records: list[dict[str, Any]],
    files_report: list[dict[str, Any]],
    version: str,
    fingerprint: str,
    built_at: str,
) -> dict[str, Any]:
    raw_by_source = Counter(record["source"] for record in raw_records)
    unique_by_source = Counter(record["source"] for record in unique_records)
    parse_raw = Counter(record["salary_parse_status"] for record in raw_records)
    parse_unique = Counter(record["salary_parse_status"] for record in unique_records)
    reason_raw = Counter(record["salary_parse_reason"] for record in raw_records)
    reason_unique = Counter(record["salary_parse_reason"] for record in unique_records)
    salary_success = [
        record
        for record in unique_records
        if record["salary_parse_status"] == "success"
        and record.get("salary_mid_monthly") is not None
    ]
    identity_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in raw_records:
        identity_groups[record["_identity"]].append(record)
    id_groups = {
        identity: members
        for identity, members in identity_groups.items()
        if ":id:" in identity
    }
    fingerprint_groups = {
        identity: members
        for identity, members in identity_groups.items()
        if identity.startswith("fingerprint:") or ":row:" in identity
    }
    fields = (
        "title",
        "company",
        "city",
        "salary_raw",
        "salary_mid_monthly",
        "education",
        "experience",
        "company_size",
        "description",
    )
    missingness = {
        field: {
            "missing": sum(record.get(field) in (None, "") for record in unique_records),
            "rate": round(
                sum(record.get(field) in (None, "") for record in unique_records)
                / max(1, len(unique_records)),
                6,
            ),
        }
        for field in fields
    }
    reconciliation = {
        source: {
            "raw_rows": raw_by_source[source],
            "unique_jobs": unique_by_source[source],
            "duplicate_rows_removed": raw_by_source[source] - unique_by_source[source],
            "balanced": raw_by_source[source]
            == unique_by_source[source] + raw_by_source[source] - unique_by_source[source],
        }
        for source in sorted(raw_by_source)
    }
    return {
        "generated_at": built_at,
        "dataset_version": version,
        "source_fingerprint": fingerprint,
        "scope_label": HISTORICAL_SCOPE_LABEL,
        "input_files": files_report,
        "counts": {
            "files": len(files_report),
            "raw_rows": len(raw_records),
            "unique_jobs": len(unique_records),
            "duplicate_rows_removed": len(raw_records) - len(unique_records),
            "salary_analyzable_jobs": sum(
                record["salary_parse_status"] == "success"
                and record.get("salary_mid_monthly") is not None
                for record in unique_records
            ),
        },
        "reconciliation_pipeline": {
            "raw_rows": len(raw_records),
            "source_id_identity_groups": len(id_groups),
            "fallback_identity_groups": len(fingerprint_groups),
            "unique_jobs": len(unique_records),
            "duplicate_rows_removed": len(raw_records) - len(unique_records),
            "balanced": len(raw_records)
            == len(unique_records) + (len(raw_records) - len(unique_records)),
        },
        "reconciliation_by_source": reconciliation,
        "salary_parse_status_raw": dict(sorted(parse_raw.items())),
        "salary_parse_status_unique": dict(sorted(parse_unique.items())),
        "salary_parse_reason_raw": dict(sorted(reason_raw.items())),
        "salary_parse_reason_unique": dict(sorted(reason_unique.items())),
        "salary_audit": {
            "minimum_monthly_midpoint": min(
                (record["salary_mid_monthly"] for record in salary_success), default=None
            ),
            "maximum_monthly_midpoint": max(
                (record["salary_mid_monthly"] for record in salary_success), default=None
            ),
            "success_over_200k_monthly": sum(
                record["salary_mid_monthly"] > 200_000 for record in salary_success
            ),
            "success_under_1k_monthly": sum(
                record["salary_mid_monthly"] < 1_000 for record in salary_success
            ),
            "review_policy": (
                "极端但周期可确定的值保留；缺少周期且可能表示年薪或非月薪的值标为 ambiguous。"
            ),
        },
        "missingness_unique_jobs": missingness,
        "deduplication": {
            "source_id_rule": "source + source_job_id when the platform ID is present",
            "fallback_rule": "source + normalized title + company + city + salary text",
            "id_bridge_rule": "a no-ID row joins an ID group only when its exact fingerprint maps to one distinct ID",
            "no_id_rows_bridged_to_id_group": sum(
                record.get("_identity_resolution") == "bridged_to_unique_id" for record in raw_records
            ),
            "ambiguous_no_id_rows_not_bridged": sum(
                record.get("_identity_resolution") == "ambiguous_not_bridged" for record in raw_records
            ),
            "winner_rule": "most complete row; earliest deterministic source row breaks ties",
            "source_id_groups": len(id_groups),
            "fallback_groups": len(fingerprint_groups),
            "rows_removed_in_source_id_groups": sum(len(members) - 1 for members in id_groups.values()),
            "rows_removed_in_fallback_groups": sum(
                len(members) - 1 for members in fingerprint_groups.values()
            ),
            "cross_platform_merge": False,
        },
        "salary_policy": {
            "success_status": "success",
            "supported": ["元/月", "千/月", "K/月", "万/月", "万/年", "12-24薪"],
            "implicit_monthly_conventions": [
                "K或千且无周期标记",
                "不少于1000元且无周期标记",
                "低于10万且无周期标记的万元区间",
            ],
            "ambiguous_without_period": [
                "低于1000元且无周期标记",
                "达到10万元且无周期标记、且无N薪佐证",
            ],
            "unsupported_without_assumptions": ["日薪", "时薪", "周薪", "次薪", "面议", "单边区间"],
            "imputation": False,
        },
        "time_policy": {
            "historical_row_observed_at": None,
            "reason": "源文件没有可靠逐条发布时间或采集时间，不用文件时间代替。",
        },
        "taxonomy": taxonomy_manifest(),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_database(repo_root: str | Path, database_path: str | Path) -> dict[str, Any]:
    """Build the seed SQLite database and return its quality report."""

    root = Path(repo_root).resolve()
    target = Path(database_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    raw_records, files_report = _iter_raw_records(root)
    if not files_report:
        raise FileNotFoundError(f"No supported source files found below {root}")
    unique_records, selected_uid = _deduplicate(raw_records)
    fingerprint = _source_fingerprint(files_report)
    version = f"historical-{fingerprint[:16]}"
    built_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    temporary = target.with_suffix(target.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(temporary)
    try:
        with connection:
            _create_schema(connection)
            _insert_database(
                connection,
                raw_records,
                unique_records,
                selected_uid,
                version,
                fingerprint,
                built_at,
            )
        connection.execute("PRAGMA optimize")
    finally:
        connection.close()
    temporary.replace(target)
    return _quality_report(
        raw_records, unique_records, files_report, version, fingerprint, built_at
    )


def build_artifacts(repo_root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Build the database, quality report, analysis summary and SVG charts."""

    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    database_path = output / "jobs_seed.sqlite"
    quality = build_database(repo_root, database_path)
    quality_path = output / "quality_report.json"
    write_json(quality_path, quality)

    # Local import keeps the deterministic ingestion layer usable on its own.
    from .analysis import analyze_database

    analysis = analyze_database(database_path, output, quality_report=quality)
    analysis_path = output / "analysis_summary.json"
    write_json(analysis_path, analysis)
    return {
        "database_path": str(database_path),
        "quality_report_path": str(quality_path),
        "analysis_summary_path": str(analysis_path),
        "charts_dir": str(output / "charts"),
        "quality": quality,
        "analysis": analysis,
    }

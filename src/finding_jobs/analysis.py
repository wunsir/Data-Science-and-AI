"""Reproducible descriptive analysis and non-causal salary associations."""

from __future__ import annotations

import html
import json
import math
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .taxonomy import SKILL_RULES


CATEGORY_LABELS = {
    "business_analysis": "商业分析",
    "data": "数据",
    "product": "产品",
    "operations": "运营",
    "finance": "金融财会",
    "other": "其他",
}

SOURCE_LABELS = {
    "boss": "BOSS直聘",
    "qianchengwuyou": "前程无忧",
    "zlzp": "智联招聘",
}

SKILL_LABELS = {
    "python": "Python",
    "sql": "SQL",
    "excel": "Excel",
    "tableau": "Tableau",
    "power_bi": "Power BI",
    "r": "R",
    "spss": "SPSS",
    "statistics": "统计分析",
    "machine_learning": "机器学习",
    "data_visualization": "数据可视化",
    "financial_analysis": "财务分析",
    "product_management": "产品管理",
    "user_research": "用户研究",
    "project_management": "项目管理",
    "operations": "运营管理",
    "market_research": "市场研究",
}

CHART_COLORS = ("#1e40af", "#0f766e", "#7c3aed", "#b45309", "#be123c", "#475569")

CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "北京": (116.4074, 39.9042),
    "上海": (121.4737, 31.2304),
    "深圳": (114.0579, 22.5431),
    "广州": (113.2644, 23.1291),
    "南京": (118.7969, 32.0603),
    "杭州": (120.1551, 30.2741),
    "武汉": (114.3054, 30.5931),
    "成都": (104.0665, 30.5723),
    "泉州": (118.6757, 24.8741),
    "苏州": (120.5853, 31.2989),
    "天津": (117.2000, 39.1334),
    "东莞": (113.7518, 23.0207),
    "重庆": (106.5516, 29.5630),
    "西安": (108.9398, 34.3416),
    "长沙": (112.9388, 28.2282),
    "宁波": (121.5503, 29.8746),
    "青岛": (120.3826, 36.0671),
    "厦门": (118.0894, 24.4798),
    "郑州": (113.6254, 34.7466),
    "合肥": (117.2272, 31.8206),
    "济南": (117.1201, 36.6512),
    "福州": (119.2965, 26.0745),
    "佛山": (113.1214, 23.0215),
    "珠海": (113.5767, 22.2707),
    "无锡": (120.3119, 31.4912),
}


def _safe_json_list(value: object) -> list[str]:
    if not isinstance(value, str) or not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _label(value: object, mapping: dict[str, str] | None = None) -> str:
    text = str(value) if value not in (None, "") else "未知"
    return mapping.get(text, text) if mapping else text


def _counts(frame: pd.DataFrame, column: str, limit: int | None = None) -> list[dict[str, Any]]:
    series = frame[column].fillna("未知").astype(str).value_counts()
    if limit is not None:
        series = series.head(limit)
    return [{"label": _label(index), "value": int(value)} for index, value in series.items()]


def _medians(
    frame: pd.DataFrame,
    column: str,
    *,
    limit: int | None = None,
    mapping: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    valid = frame[frame["salary_mid_monthly"].notna()].copy()
    grouped = (
        valid.groupby(valid[column].fillna("未知"), dropna=False)["salary_mid_monthly"]
        .agg(["median", "count"])
        .sort_values(["median", "count"], ascending=False)
    )
    if limit is not None:
        grouped = grouped.head(limit)
    return [
        {
            "label": _label(index, mapping),
            "value": round(float(row["median"]), 2),
            "n": int(row["count"]),
        }
        for index, row in grouped.iterrows()
    ]


def _salary_histogram(frame: pd.DataFrame) -> list[dict[str, Any]]:
    values = frame["salary_mid_monthly"].dropna().to_numpy(dtype=float)
    # Fixed bins retain every valid observation and are comparable across runs.
    edges = np.array([0, 5_000, 10_000, 15_000, 20_000, 30_000, 50_000, 100_000, 200_000, np.inf])
    labels = [
        "0–5千",
        "5千–1万",
        "1–1.5万",
        "1.5–2万",
        "2–3万",
        "3–5万",
        "5–10万",
        "10–20万",
        "20万以上",
    ]
    counts, _ = np.histogram(values, bins=edges)
    return [{"label": label, "value": int(count)} for label, count in zip(labels, counts, strict=True)]


def _skills_frequency(frame: pd.DataFrame, limit: int = 12) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for value in frame["skills"]:
        counter.update(_safe_json_list(value))
    return [{"label": key, "value": int(count)} for key, count in counter.most_common(limit)]


def _group_rare(values: list[str], minimum_support: int) -> tuple[list[str], str]:
    counts = Counter(values)
    grouped = [value if counts[value] >= minimum_support else "其他/稀有" for value in values]
    grouped_counts = Counter(grouped)
    reference = sorted(grouped_counts, key=lambda value: (-grouped_counts[value], value))[0]
    return grouped, reference


def _design_matrix(frame: pd.DataFrame) -> tuple[np.ndarray, list[str], dict[str, str]]:
    n = len(frame)
    columns: list[np.ndarray] = [np.ones(n, dtype=float)]
    names = ["intercept"]
    references: dict[str, str] = {}
    minimum_support = max(2, min(50, n // 100 if n >= 100 else 2))
    categorical = ("source", "job_category", "city", "education", "experience", "company_size")
    for field in categorical:
        values = [str(value) if value not in (None, "") and not pd.isna(value) else "未知" for value in frame[field]]
        grouped, reference = _group_rare(values, minimum_support)
        references[field] = reference
        for level in sorted(set(grouped)):
            if level == reference:
                continue
            vector = np.fromiter((float(value == level) for value in grouped), dtype=float, count=n)
            if vector.min() != vector.max():
                columns.append(vector)
                names.append(f"{field}={level}")

    parsed_skills = [set(_safe_json_list(value)) for value in frame["skills"]]
    for skill in SKILL_RULES:
        vector = np.fromiter((float(skill in item) for item in parsed_skills), dtype=float, count=n)
        if vector.min() != vector.max():
            columns.append(vector)
            names.append(f"skill={skill}")
    return np.column_stack(columns), names, references


def fit_salary_model(frame: pd.DataFrame, *, trim: bool = False) -> dict[str, Any]:
    """Fit log monthly midpoint OLS and calculate HC3 standard errors.

    The model is descriptive.  All predictors come from the fixed taxonomy or
    source fields; no predictor is derived from salary.
    """

    model_frame = frame[
        frame["salary_mid_monthly"].notna() & (frame["salary_mid_monthly"] > 0)
    ].copy()
    trim_bounds: dict[str, float] | None = None
    if trim and len(model_frame) >= 10:
        lower, upper = np.quantile(model_frame["salary_mid_monthly"].to_numpy(dtype=float), [0.01, 0.99])
        trim_bounds = {"p01": round(float(lower), 4), "p99": round(float(upper), 4)}
        model_frame = model_frame[
            model_frame["salary_mid_monthly"].between(lower, upper, inclusive="both")
        ].copy()
    if len(model_frame) < 5:
        return {
            "status": "insufficient_data",
            "n": int(len(model_frame)),
            "trimmed_1_99": trim,
            "trim_bounds": trim_bounds,
            "coefficients": [],
        }

    y = np.log(model_frame["salary_mid_monthly"].to_numpy(dtype=float))
    design, names, references = _design_matrix(model_frame)
    bread = np.linalg.pinv(design.T @ design, rcond=1e-12)
    beta = bread @ design.T @ y
    residuals = y - design @ beta
    leverage = np.einsum("ij,jk,ik->i", design, bread, design)
    adjusted = residuals / np.clip(1.0 - leverage, 1e-8, None)
    meat = design.T @ ((adjusted * adjusted)[:, None] * design)
    covariance = bread @ meat @ bread
    standard_errors = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
    rank = int(np.linalg.matrix_rank(design.T @ design))
    tss = float(np.sum((y - y.mean()) ** 2))
    rss = float(np.sum(residuals**2))
    r_squared = 1.0 - rss / tss if tss > 0 else 0.0

    coefficients = []
    for name, estimate, standard_error in zip(names, beta, standard_errors, strict=True):
        statistic = float(estimate / standard_error) if standard_error > 0 else None
        p_value = math.erfc(abs(statistic) / math.sqrt(2.0)) if statistic is not None else None
        coefficients.append(
            {
                "term": name,
                "estimate_log_points": round(float(estimate), 8),
                "hc3_standard_error": round(float(standard_error), 8),
                "normal_approx_p_value": round(float(p_value), 8) if p_value is not None else None,
                "percent_difference": round(float(math.expm1(estimate) * 100.0), 4)
                if name != "intercept" and abs(estimate) < 20
                else None,
            }
        )
    return {
        "status": "ok",
        "n": int(len(model_frame)),
        "rank": rank,
        "predictors": int(design.shape[1] - 1),
        "r_squared": round(r_squared, 6),
        "trimmed_1_99": trim,
        "trim_bounds": trim_bounds,
        "outcome": "log(salary_mid_monthly)",
        "covariance": "HC3",
        "source_fixed_effects": True,
        "controls": ["job_category", "city", "education", "experience", "company_size", "predefined_skills"],
        "reference_levels": references,
        "coefficients": coefficients,
        "interpretation": "系数描述本样本在其他列示变量相同时的调整后关联，不代表因果效应。",
    }


def _format_value(value: float, kind: str) -> str:
    if kind == "salary":
        return f"¥{value / 1000:,.1f}k"
    if kind == "percent":
        return f"{value:+.1f}%"
    return f"{value:,.0f}"


def _bar_svg(
    title: str,
    subtitle: str,
    data: list[dict[str, Any]],
    *,
    value_kind: str = "count",
    color: str = "#1f6f78",
) -> str:
    width = 960
    row_height = 38
    height = max(390, 155 + row_height * max(1, len(data)))
    left, right, top = 235, 110, 118
    chart_width = width - left - right
    values = [float(item["value"]) for item in data] or [0.0]
    minimum = min(0.0, min(values))
    maximum = max(0.0, max(values))
    span = maximum - minimum or 1.0
    zero_x = left + (0.0 - minimum) / span * chart_width
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#fbfaf7"/>',
        f'<text x="42" y="48" font-family="Noto Sans SC, Microsoft YaHei, sans-serif" font-size="25" font-weight="700" fill="#17363a">{html.escape(title)}</text>',
        f'<text x="42" y="78" font-family="Noto Sans SC, Microsoft YaHei, sans-serif" font-size="14" fill="#617477">{html.escape(subtitle)}</text>',
        f'<line x1="{zero_x:.2f}" y1="{top - 10}" x2="{zero_x:.2f}" y2="{height - 38}" stroke="#bcc8c7" stroke-width="1"/>',
    ]
    if not data:
        elements.append(
            '<text x="42" y="150" font-family="Noto Sans SC, Microsoft YaHei, sans-serif" font-size="16" fill="#617477">数据不足</text>'
        )
    for index, item in enumerate(data):
        value = float(item["value"])
        y = top + index * row_height
        x_value = left + (value - minimum) / span * chart_width
        bar_x = min(zero_x, x_value)
        bar_width = max(1.5, abs(x_value - zero_x))
        label = html.escape(str(item["label"])[:28])
        display = html.escape(_format_value(value, value_kind))
        value_label_x = x_value + 8 if value >= 0 else x_value - 8
        value_anchor = "start" if value >= 0 else "end"
        elements.extend(
            [
                f'<text x="{left - 12}" y="{y + 20}" text-anchor="end" font-family="Noto Sans SC, Microsoft YaHei, sans-serif" font-size="13" fill="#314d50">{label}</text>',
                f'<rect x="{bar_x:.2f}" y="{y + 5}" width="{bar_width:.2f}" height="22" rx="3" fill="{color}" opacity="0.9"/>',
                f'<text x="{value_label_x:.2f}" y="{y + 21}" text-anchor="{value_anchor}" font-family="Inter, Arial, sans-serif" font-size="12" fill="#314d50">{display}</text>',
            ]
        )
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def _write_chart(
    charts_dir: Path,
    chart_id: str,
    title: str,
    subtitle: str,
    data: list[dict[str, Any]],
    *,
    value_kind: str = "count",
    color: str = "#1f6f78",
    metric_note: str,
) -> dict[str, Any]:
    charts_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{chart_id}.svg"
    (charts_dir / filename).write_text(
        _bar_svg(title, subtitle, data, value_kind=value_kind, color=color), encoding="utf-8"
    )
    return {
        "id": chart_id,
        "title": title,
        "subtitle": subtitle,
        "file": f"charts/{filename}",
        "alt_text": f"{title}：共 {len(data)} 个分组。",
        "metric_note": metric_note,
        "data": data,
    }


def _regression_chart_data(model: dict[str, Any]) -> list[dict[str, Any]]:
    if model.get("status") != "ok":
        return []
    candidates = [
        item
        for item in model["coefficients"]
        if item["term"] != "intercept"
        and item["percent_difference"] is not None
        and (item["term"].startswith("skill=") or item["term"].startswith("job_category="))
    ]
    selected = sorted(candidates, key=lambda item: abs(item["percent_difference"]), reverse=True)[:10]
    return [
        {"label": item["term"].replace("skill=", "技能：").replace("job_category=", "岗位："), "value": item["percent_difference"]}
        for item in reversed(selected)
    ]


def analyze_database(
    database_path: str | Path,
    output_dir: str | Path,
    *,
    quality_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one analysis summary and the published 29-chart visual story."""

    database = Path(database_path).resolve()
    output = Path(output_dir).resolve()
    charts_dir = output / "charts"
    connection = sqlite3.connect(database)
    try:
        frame = pd.read_sql_query(
            "SELECT * FROM jobs_analytics WHERE data_scope = 'historical' ORDER BY job_key",
            connection,
        )
        version_row = connection.execute(
            "SELECT dataset_version, scope_label, built_at FROM dataset_versions ORDER BY built_at DESC LIMIT 1"
        ).fetchone()
    finally:
        connection.close()
    if version_row is None:
        raise ValueError("dataset_versions is empty")

    valid_salary = frame[
        frame["salary_parse_status"].eq("success")
        & frame["salary_mid_monthly"].notna()
    ].copy()
    main_model = fit_salary_model(valid_salary, trim=False)
    sensitivity_model = fit_salary_model(valid_salary, trim=True)

    by_source = _counts(frame, "source")
    by_category = _counts(frame, "job_category")
    for item in by_category:
        item["label"] = CATEGORY_LABELS.get(item["label"], item["label"])
    by_city = _counts(frame, "city", limit=12)
    salary_distribution = _salary_histogram(valid_salary)
    salary_category = _medians(valid_salary, "job_category", mapping=CATEGORY_LABELS)
    salary_city = _medians(valid_salary, "city", limit=12)
    salary_education = _medians(valid_salary, "education", limit=10)
    salary_experience = _medians(valid_salary, "experience", limit=10)
    skills = _skills_frequency(frame)
    salary_source = _medians(valid_salary, "source")
    adjusted = _regression_chart_data(main_model)

    chart_specs = (
        ("sample_by_source", "样本来源构成", "去重后的职位记录", by_source, "count", "#1f6f78", "职位数"),
        ("sample_by_category", "岗位类别构成", "按固定标题词典分类；无法识别的归为其他", by_category, "count", "#3c7a57", "职位数"),
        ("sample_by_city", "主要城市样本量", "按源字段中的首个城市层级归一", by_city, "count", "#8b6f47", "职位数；仅展示前12"),
        ("salary_distribution", "月薪中点分布", "包含全部可解析月薪，不删除极端值", salary_distribution, "count", "#bf6f4a", "职位数"),
        ("salary_by_category", "各岗位类别月薪中位数", "历史便利样本中的描述性比较", salary_category, "salary", "#1f6f78", "人民币/月；中点中位数"),
        ("salary_by_city", "主要城市月薪中位数", "按月薪中点计算；仅展示中位数最高的12个城市", salary_city, "salary", "#556b9b", "人民币/月；中点中位数"),
        ("salary_by_education", "学历要求与月薪中位数", "学历字段为职位要求，不是求职者个人学历", salary_education, "salary", "#7d5a92", "人民币/月；中点中位数"),
        ("salary_by_experience", "经验要求与月薪中位数", "保留来源原始经验分组", salary_experience, "salary", "#8b6f47", "人民币/月；中点中位数"),
        ("skills_frequency", "预定义技能出现频次", "技能来自固定、与薪资无关的可审计词典", skills, "count", "#3c7a57", "提及该技能的职位数"),
        ("salary_by_source", "不同来源的月薪中位数", "来源采样策略不同，差异不应解释为平台效应", salary_source, "salary", "#bf6f4a", "人民币/月；中点中位数"),
        ("adjusted_associations", "调整后工资关联（OLS）", "对数月薪模型；展示岗位类别与技能中绝对值较大的10项", adjusted, "percent", "#1f6f78", "相对各字段参考组的估计百分比差异；非因果"),
    )
    charts = [
        _write_chart(
            charts_dir,
            chart_id,
            title,
            subtitle,
            data,
            value_kind=value_kind,
            color=color,
            metric_note=metric_note,
        )
        for chart_id, title, subtitle, data, value_kind, color, metric_note in chart_specs
    ]

    compatibility_charts = charts
    from .visuals import build_visual_story

    charts, visual_tables, source_models = build_visual_story(
        frame,
        valid_salary,
        main_model,
        sensitivity_model,
        charts_dir,
        model_fitter=fit_salary_model,
    )

    salary_values = valid_salary["salary_mid_monthly"].to_numpy(dtype=float)
    quality_counts = (quality_report or {}).get("counts", {})
    raw_rows = quality_counts.get("raw_rows")
    duplicate_rows_removed = quality_counts.get("duplicate_rows_removed")
    return {
        "generated_at": version_row[2],
        "dataset_version": version_row[0],
        "coverage": {
            "data_scope": "historical",
            "scope_label": version_row[1],
            "sources": sorted(frame["source"].dropna().astype(str).unique().tolist()),
            "unique_jobs": int(len(frame)),
            "raw_rows": int(raw_rows) if raw_rows is not None else None,
            "duplicate_rows_removed": int(duplicate_rows_removed)
            if duplicate_rows_removed is not None
            else None,
            "salary_analyzable_jobs": int(len(valid_salary)),
            "row_level_observed_at_available": False,
        },
        "headline_metrics": {
            "unique_jobs": int(len(frame)),
            "salary_coverage_rate": round(len(valid_salary) / max(1, len(frame)), 6),
            "median_monthly_salary_midpoint": round(float(np.median(salary_values)), 2)
            if len(salary_values)
            else None,
            "cities": int(frame["city"].dropna().nunique()),
            "predefined_skills": len(SKILL_RULES),
        },
        "charts": charts,
        "compatibility_charts": compatibility_charts,
        "tables": {
            "sample_by_source": by_source,
            "sample_by_category": by_category,
            "top_cities": by_city,
            "salary_by_category": salary_category,
            "salary_by_city": salary_city,
            "salary_by_education": salary_education,
            "salary_by_experience": salary_experience,
            "skills_frequency": skills,
            "salary_by_source": salary_source,
            **visual_tables,
        },
        "regression": {
            "main": main_model,
            "sensitivity_trimmed_1_99": sensitivity_model,
            "by_source": source_models,
            "claim_boundary": "模型仅描述样本内的调整后关联，不支持因果、全国总体或时间趋势结论。",
        },
        "warnings": [
            "三平台数据是关键词与城市便利样本，不代表全国招聘市场总体。",
            "历史文件缺少可靠逐条发布时间和采集时间，不能用于时间趋势或上下架分析。",
            "跨来源的采样范围和字段完整度不同，平台差异只作描述性展示。",
            "日薪、时薪、周薪、次薪、面议和单边薪资不在缺少假设时换算。",
            "缺少周期且金额可能同时表示年薪或非月薪的记录标为 ambiguous，不进入薪资指标。",
            "所有回归结果均为样本关联，不是因果效应。",
        ],
    }

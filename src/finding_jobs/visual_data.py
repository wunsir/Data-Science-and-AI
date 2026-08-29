"""Deterministic aggregations for the public visual story."""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd


CATEGORY_LABELS = {
    "business_analysis": "商业分析",
    "data": "数据",
    "product": "产品",
    "operations": "运营",
    "finance": "金融财会",
    "other": "其他",
}
SOURCE_LABELS = {"boss": "BOSS直聘", "qianchengwuyou": "前程无忧", "zlzp": "智联招聘"}
SKILL_LABELS = {
    "python": "Python", "sql": "SQL", "excel": "Excel", "tableau": "Tableau",
    "power_bi": "Power BI", "r": "R", "spss": "SPSS", "statistics": "统计分析",
    "machine_learning": "机器学习", "data_visualization": "数据可视化",
    "financial_analysis": "财务分析", "product_management": "产品管理",
    "user_research": "用户研究", "project_management": "项目管理",
    "operations": "运营管理", "market_research": "市场研究",
}
COLORS = ("#1e40af", "#0f766e", "#7c3aed", "#b45309", "#be123c", "#475569")
CITY_COORDINATES = {
    "北京": (116.4074, 39.9042), "上海": (121.4737, 31.2304),
    "深圳": (114.0579, 22.5431), "广州": (113.2644, 23.1291),
    "南京": (118.7969, 32.0603), "杭州": (120.1551, 30.2741),
    "武汉": (114.3054, 30.5931), "成都": (104.0665, 30.5723),
    "泉州": (118.6757, 24.8741), "苏州": (120.5853, 31.2989),
    "天津": (117.2000, 39.1334), "东莞": (113.7518, 23.0207),
    "重庆": (106.5516, 29.5630), "西安": (108.9398, 34.3416),
    "长沙": (112.9388, 28.2282), "宁波": (121.5503, 29.8746),
    "青岛": (120.3826, 36.0671), "厦门": (118.0894, 24.4798),
    "郑州": (113.6254, 34.7466), "合肥": (117.2272, 31.8206),
    "济南": (117.1201, 36.6512), "福州": (119.2965, 26.0745),
    "佛山": (113.1214, 23.0215), "珠海": (113.5767, 22.2707),
    "无锡": (120.3119, 31.4912),
}


def skills(value: object) -> set[str]:
    if not isinstance(value, str) or not value:
        return set()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return set()
    return {str(item) for item in parsed} if isinstance(parsed, list) else set()


def label(value: object, mapping: dict[str, str] | None = None) -> str:
    text = str(value) if value not in (None, "") else "未知"
    return mapping.get(text, text) if mapping else text


def top_values(frame: pd.DataFrame, column: str, limit: int) -> list[str]:
    values = frame[column].dropna().astype(str)
    return values[values.str.strip().ne("")].value_counts().head(limit).index.tolist()


def median_groups(
    frame: pd.DataFrame,
    column: str,
    *,
    limit: int | None = None,
    mapping: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    grouped = frame.groupby(frame[column].fillna("未知"))["salary_mid_monthly"].agg(["median", "count"])
    grouped = grouped[grouped["count"] >= 30].sort_values(["median", "count"], ascending=False)
    if limit is not None:
        grouped = grouped.head(limit)
    return [
        {"label": label(index, mapping), "value": round(float(row["median"]), 2), "n": int(row["count"])}
        for index, row in grouped.iterrows()
    ]


def major_city_salary(frame: pd.DataFrame, limit: int = 6) -> list[dict[str, Any]]:
    """Compare salary among the cities with the largest analyzable samples."""

    city = frame["city"].dropna().astype(str)
    city = city[city.str.strip().ne("")]
    counts = (
        city.value_counts()
        .rename_axis("city")
        .reset_index(name="count")
        .sort_values(["count", "city"], ascending=[False, True])
    )
    selected = counts.head(limit)["city"].tolist()
    return median_groups(frame[frame["city"].astype(str).isin(selected)], "city")


def quantile_groups(frame: pd.DataFrame, column: str, limit: int = 10) -> list[dict[str, Any]]:
    rows = []
    for value, group in frame.groupby(frame[column].fillna("未知")):
        salary = group["salary_mid_monthly"].dropna().to_numpy(dtype=float)
        if len(salary) < 30:
            continue
        low, q1, median, q3, high = np.quantile(salary, [0.05, 0.25, 0.5, 0.75, 0.95])
        rows.append({
            "label": label(value), "low": round(float(low), 2), "q1": round(float(q1), 2),
            "median": round(float(median), 2), "q3": round(float(q3), 2),
            "high": round(float(high), 2), "n": int(len(salary)),
        })
    return sorted(rows, key=lambda item: (item["median"], item["n"]), reverse=True)[:limit]


def histogram(frame: pd.DataFrame) -> list[dict[str, Any]]:
    values = frame["salary_mid_monthly"].dropna().to_numpy(dtype=float)
    edges = np.array([0, 5_000, 10_000, 15_000, 20_000, 30_000, 50_000, 100_000, 200_000, np.inf])
    names = ["0–5千", "5千–1万", "1–1.5万", "1.5–2万", "2–3万", "3–5万", "5–10万", "10–20万", "20万以上"]
    counts, _ = np.histogram(values, bins=edges)
    return [{"label": name, "value": int(count)} for name, count in zip(names, counts, strict=True)]


def city_category_salary(
    frame: pd.DataFrame, cities: list[str], categories: list[str]
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    cells = []
    for city in cities:
        for category in categories:
            group = frame[frame["city"].eq(city) & frame["job_category"].eq(category)]
            if len(group) >= 30:
                cells.append({
                    "row": city, "column": CATEGORY_LABELS.get(category, category),
                    "value": round(float(group["salary_mid_monthly"].median()), 2), "n": int(len(group)),
                })
    return cities, [CATEGORY_LABELS.get(item, item) for item in categories], cells


def city_education(frame: pd.DataFrame, cities: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    education = top_values(frame, "education", 5)
    series = education + ["其他"]
    rows = []
    for city in cities:
        group = frame[frame["city"].eq(city)]
        if len(group) < 30:
            continue
        counts = group["education"].fillna("未知").astype(str).value_counts()
        values = {item: int(counts.get(item, 0)) for item in education}
        values["其他"] = int(len(group) - sum(values.values()))
        rows.append({"label": city, "values": values, "n": int(len(group))})
    return rows, series


def lorenz(frame: pd.DataFrame) -> dict[str, Any]:
    series = []
    for index, (category, group) in enumerate(frame.groupby("job_category")):
        values = np.sort(group["salary_mid_monthly"].dropna().to_numpy(dtype=float))
        if len(values) < 200 or values.sum() <= 0:
            continue
        cumulative = np.concatenate([[0.0], np.cumsum(values) / values.sum()])
        population = np.linspace(0.0, 1.0, len(values) + 1)
        positions = np.linspace(0, len(values), 61).astype(int)
        ranks = np.arange(1, len(values) + 1)
        gini = (2 * np.sum(ranks * values)) / (len(values) * values.sum()) - (len(values) + 1) / len(values)
        series.append({
            "label": CATEGORY_LABELS.get(str(category), str(category)),
            "gini": round(float(gini), 4),
            "points": [[round(float(population[pos]), 6), round(float(cumulative[pos]), 6)] for pos in positions],
            "color": COLORS[index % len(COLORS)], "n": int(len(values)),
        })
    return {"series": series}


def skill_counter(skill_sets: list[set[str]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for item in skill_sets:
        counter.update(item)
    return counter


def skill_quartiles(
    frame: pd.DataFrame, skill_sets: list[set[str]], top_skills: list[str]
) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    lower, upper = np.quantile(frame["salary_mid_monthly"].to_numpy(dtype=float), [0.25, 0.75])
    low = np.flatnonzero(frame["salary_mid_monthly"].le(lower).to_numpy())
    high = np.flatnonzero(frame["salary_mid_monthly"].ge(upper).to_numpy())
    return [{
        "label": SKILL_LABELS.get(skill, skill),
        "values": {
            "lower": round(100 * sum(skill in skill_sets[index] for index in low) / max(1, len(low)), 2),
            "upper": round(100 * sum(skill in skill_sets[index] for index in high) / max(1, len(high)), 2),
        },
    } for skill in top_skills]


def rate_heatmap(
    frame: pd.DataFrame,
    skill_sets: list[set[str]],
    group_column: str,
    groups: list[str],
    top_skills: list[str],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    rows, cells = [], []
    columns = [SKILL_LABELS.get(skill, skill) for skill in top_skills]
    for group in groups:
        indexes = np.flatnonzero(frame[group_column].fillna("未知").astype(str).eq(group).to_numpy())
        if len(indexes) < 30:
            continue
        row_name = CATEGORY_LABELS.get(group, group)
        rows.append(row_name)
        for skill, column in zip(top_skills, columns, strict=True):
            cells.append({
                "row": row_name, "column": column,
                "value": round(100 * sum(skill in skill_sets[index] for index in indexes) / len(indexes), 2),
                "n": int(len(indexes)),
            })
    return rows, columns, cells


def skill_count_rows(skill_sets: list[set[str]]) -> list[dict[str, Any]]:
    counts = Counter(min(len(item), 6) for item in skill_sets)
    return [{"label": "6+" if value == 6 else str(value), "value": int(counts.get(value, 0))} for value in range(7)]


def salary_by_skill_count(frame: pd.DataFrame, skill_sets: list[set[str]]) -> list[dict[str, Any]]:
    counts = np.array([len(item) for item in skill_sets])
    groups = [("0项", counts == 0), ("1项", counts == 1), ("2项", counts == 2), ("3项", counts == 3), ("4项及以上", counts >= 4)]
    rows = []
    for name, mask in groups:
        values = frame.loc[mask, "salary_mid_monthly"]
        if len(values) >= 30:
            rows.append({"label": name, "value": round(float(values.median()), 2), "n": int(len(values))})
    return rows


def skill_salary_difference(
    frame: pd.DataFrame, skill_sets: list[set[str]], top_skills: list[str]
) -> list[dict[str, Any]]:
    rows = []
    for skill in top_skills:
        mask = np.array([skill in item for item in skill_sets])
        with_skill, without_skill = frame.loc[mask, "salary_mid_monthly"], frame.loc[~mask, "salary_mid_monthly"]
        if len(with_skill) < 30 or len(without_skill) < 30:
            continue
        first, second = float(with_skill.median()), float(without_skill.median())
        rows.append({
            "label": SKILL_LABELS.get(skill, skill),
            "value": round((first / second - 1) * 100 if second else 0.0, 2),
            "n": int(len(with_skill)), "with_median": round(first, 2), "without_median": round(second, 2),
        })
    return rows


def group_skill_difference(
    frame: pd.DataFrame,
    skill_sets: list[set[str]],
    column: str,
    groups: list[str],
    top_skills: list[str],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    rows, cells = [], []
    columns = [SKILL_LABELS.get(skill, skill) for skill in top_skills]
    for group in groups:
        group_mask = frame[column].fillna("未知").astype(str).eq(group).to_numpy()
        if group_mask.sum() < 60:
            continue
        row_name = CATEGORY_LABELS.get(group, group)
        rows.append(row_name)
        for skill, column_name in zip(top_skills, columns, strict=True):
            skill_mask = np.array([skill in item for item in skill_sets])
            with_skill = frame.loc[group_mask & skill_mask, "salary_mid_monthly"]
            without_skill = frame.loc[group_mask & ~skill_mask, "salary_mid_monthly"]
            if len(with_skill) < 30 or len(without_skill) < 30:
                continue
            baseline = float(without_skill.median())
            cells.append({
                "row": row_name, "column": column_name,
                "value": round((float(with_skill.median()) / baseline - 1) * 100 if baseline else 0.0, 2),
                "n": int(len(with_skill)),
            })
    return rows, columns, cells


def source_category(frame: pd.DataFrame) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    sources, categories = top_values(frame, "source", 5), top_values(frame, "job_category", 6)
    cells = []
    for source in sources:
        for category in categories:
            group = frame[frame["source"].eq(source) & frame["job_category"].eq(category)]
            if len(group) >= 30:
                cells.append({
                    "row": SOURCE_LABELS.get(source, source),
                    "column": CATEGORY_LABELS.get(category, category),
                    "value": round(float(group["salary_mid_monthly"].median()), 2), "n": int(len(group)),
                })
    return [SOURCE_LABELS.get(item, item) for item in sources], [CATEGORY_LABELS.get(item, item) for item in categories], cells


def coefficient_map(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["term"]: item for item in model.get("coefficients", [])}


def term_label(term: str) -> str:
    if term.startswith("skill="):
        value = term.split("=", 1)[1]
        return f"技能：{SKILL_LABELS.get(value, value)}"
    if term.startswith("job_category="):
        value = term.split("=", 1)[1]
        return f"岗位：{CATEGORY_LABELS.get(value, value)}"
    return term


def adjusted_rows(model: dict[str, Any], terms: list[str]) -> list[dict[str, Any]]:
    lookup = coefficient_map(model)
    return [
        {"label": term_label(term), "value": float(lookup[term]["percent_difference"]), "term": term}
        for term in terms if term in lookup and lookup[term].get("percent_difference") is not None
    ]


def trim_rows(main: dict[str, Any], trimmed: dict[str, Any], terms: list[str]) -> list[dict[str, Any]]:
    first, second = coefficient_map(main), coefficient_map(trimmed)
    rows = []
    for term in terms:
        if term not in first or term not in second:
            continue
        if first[term].get("percent_difference") is None or second[term].get("percent_difference") is None:
            continue
        rows.append({
            "label": term_label(term),
            "values": {"main": float(first[term]["percent_difference"]), "trimmed": float(second[term]["percent_difference"])},
        })
    return rows


def source_forest(models: dict[str, dict[str, Any]], terms: list[str]) -> list[dict[str, Any]]:
    rows = []
    for source_index, (source, model) in enumerate(sorted(models.items())):
        lookup = coefficient_map(model)
        for term in terms:
            item = lookup.get(term)
            if not item or item.get("percent_difference") is None:
                continue
            estimate, error = float(item["estimate_log_points"]), float(item["hc3_standard_error"])
            rows.append({
                "label": f"{SOURCE_LABELS.get(source, source)} · {term_label(term)}",
                "value": round(float(item["percent_difference"]), 4),
                "low": round(math.expm1(estimate - 1.96 * error) * 100, 4),
                "high": round(math.expm1(estimate + 1.96 * error) * 100, 4),
                "color": COLORS[source_index % len(COLORS)], "source": source, "term": term,
            })
    return rows


def salary_band(value: float) -> str:
    if value < 10_000:
        return "1万元以下"
    if value < 20_000:
        return "1万–2万元"
    if value < 30_000:
        return "2万–3万元"
    return "3万元以上"


def sankey(
    frame: pd.DataFrame,
    first_column: str,
    first_values: list[str],
    second_column: str,
    second_values: list[str],
) -> dict[str, Any]:
    selected = frame[frame[first_column].isin(first_values) & frame[second_column].isin(second_values)].copy()
    selected["salary_band"] = selected["salary_mid_monthly"].map(salary_band)
    nodes, links = {}, []
    for (first, second), group in selected.groupby([first_column, second_column]):
        if len(group) < 30:
            continue
        source, target = f"first:{first}", f"second:{second}"
        nodes[source] = {"name": source, "label": label(first)}
        nodes[target] = {"name": target, "label": CATEGORY_LABELS.get(str(second), label(second))}
        links.append({"source": source, "target": target, "value": int(len(group))})
    for (second, band), group in selected.groupby([second_column, "salary_band"]):
        if len(group) < 30:
            continue
        source, target = f"second:{second}", f"band:{band}"
        nodes[source] = {"name": source, "label": CATEGORY_LABELS.get(str(second), label(second))}
        nodes[target] = {"name": target, "label": band}
        links.append({"source": source, "target": target, "value": int(len(group))})
    return {"nodes": list(nodes.values()), "links": links}


def tree(frame: pd.DataFrame, cities: list[str], categories: list[str]) -> list[dict[str, Any]]:
    result = []
    for city in cities:
        children = []
        for category in categories:
            count = int((frame["city"].eq(city) & frame["job_category"].eq(category)).sum())
            if count >= 30:
                children.append({"name": CATEGORY_LABELS.get(category, category), "value": count})
        if children:
            result.append({"name": city, "value": sum(item["value"] for item in children), "children": children})
    return result


def radar(frame: pd.DataFrame, skill_sets: list[set[str]]) -> dict[str, Any]:
    if frame.empty:
        return {"indicators": [], "groups": []}
    lower, upper = np.quantile(frame["salary_mid_monthly"].to_numpy(dtype=float), [0.25, 0.75])
    masks = {"月薪下四分位": frame["salary_mid_monthly"].le(lower).to_numpy(), "月薪上四分位": frame["salary_mid_monthly"].ge(upper).to_numpy()}
    groups = []
    for name, mask in masks.items():
        group = frame.loc[mask]
        values = [
            float(group["salary_mid_monthly"].median()),
            float(group["education"].fillna("").astype(str).str.contains("硕士|博士", regex=True).mean() * 100),
            float(group["experience"].fillna("").astype(str).str.contains("3-5年|5-10年|10年以上|3年及以上|5年及以上", regex=True).mean() * 100),
            float(np.mean([len(skill_sets[index]) for index in np.flatnonzero(mask)])),
            float(group["company_size"].fillna("").astype(str).str.contains("1000-|10000|1000人|万人", regex=True).mean() * 100),
        ]
        groups.append({"name": name, "values": [round(value, 3) for value in values], "n": int(len(group))})
    maxima = [max(item["values"][index] for item in groups) * 1.15 or 1.0 for index in range(5)]
    names = ["月薪中位数", "硕博要求占比", "3年以上经验占比", "平均技能数", "千人以上公司占比"]
    return {"indicators": [{"name": name, "max": round(maximum, 2)} for name, maximum in zip(names, maxima, strict=True)], "groups": groups}


def prepare_story_data(
    frame: pd.DataFrame,
    valid_salary: pd.DataFrame,
    main_model: dict[str, Any],
    sensitivity_model: dict[str, Any],
    model_fitter: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    frame, valid_salary = frame.reset_index(drop=True).copy(), valid_salary.reset_index(drop=True).copy()
    frame_skills = [skills(value) for value in frame["skills"]]
    salary_skills = [skills(value) for value in valid_salary["skills"]]
    counter = skill_counter(frame_skills)
    top_skills = [skill for skill, _ in counter.most_common(10)]
    display_skills = top_skills[:6]
    top_cities, salary_cities = top_values(frame, "city", 10), top_values(valid_salary, "city", 10)
    categories = top_values(frame, "job_category", 6)
    city_rows, category_columns, city_cells = city_category_salary(valid_salary, salary_cities[:8], categories)
    education_rows, education_columns, education_cells = group_skill_difference(valid_salary, salary_skills, "education", top_values(valid_salary, "education", 5), display_skills)
    job_rows, job_columns, job_cells = group_skill_difference(valid_salary, salary_skills, "job_category", top_values(valid_salary, "job_category", 6), display_skills)
    source_rows, source_columns, source_cells = source_category(valid_salary)
    model_terms = [*(f"job_category={item}" for item in categories if item != "finance"), *(f"skill={item}" for item in display_skills)]
    source_models = {str(source): model_fitter(group, trim=False) for source, group in valid_salary.groupby("source") if len(group) >= 30}
    city_education_rows, city_education_series = city_education(frame, top_cities[:8])
    category_rate_rows, category_rate_columns, category_rate_cells = rate_heatmap(frame, frame_skills, "job_category", categories, top_skills)
    result = {
        "counts": {"jobs": len(frame), "salary": len(valid_salary)},
        "top_skills": top_skills, "categories": categories, "top_cities": top_cities,
        "city_rows": city_rows, "category_columns": category_columns, "city_cells": city_cells,
        "city_salary": major_city_salary(valid_salary),
        "category_salary": median_groups(valid_salary, "job_category", mapping=CATEGORY_LABELS),
        "city_education_rows": city_education_rows, "city_education_series": city_education_series,
        "lorenz": lorenz(valid_salary),
        "skill_frequency": [{"label": SKILL_LABELS.get(skill, skill), "value": int(value)} for skill, value in counter.most_common(12)],
        "skill_quartiles": skill_quartiles(valid_salary, salary_skills, top_skills),
        "category_rate_rows": category_rate_rows, "category_rate_columns": category_rate_columns, "category_rate_cells": category_rate_cells,
        "salary_distribution": histogram(valid_salary),
        "education_quantiles": quantile_groups(valid_salary, "education"),
        "experience_quantiles": quantile_groups(valid_salary, "experience"),
        "company_quantiles": quantile_groups(valid_salary, "company_size"),
        "skill_count": skill_count_rows(frame_skills),
        "salary_skill_count": salary_by_skill_count(valid_salary, salary_skills),
        "raw_skill_difference": skill_salary_difference(valid_salary, salary_skills, top_skills),
        "adjusted": adjusted_rows(main_model, model_terms),
        "education_rows": education_rows, "education_columns": education_columns, "education_cells": education_cells,
        "job_rows": job_rows, "job_columns": job_columns, "job_cells": job_cells,
        "source_rows": source_rows, "source_columns": source_columns, "source_cells": source_cells,
        "trim": trim_rows(main_model, sensitivity_model, model_terms),
        "source_forest": source_forest(source_models, [f"skill={item}" for item in display_skills[:5]]),
        "source_models": source_models,
    }
    result["interactive"] = {
        "bar3d": {"cities": city_rows, "categories": category_columns, "values": [[city_rows.index(cell["row"]), category_columns.index(cell["column"]), cell["value"], cell["n"]] for cell in city_cells]},
        "treemap": {"tree": tree(frame, top_cities[:8], categories)},
        "macro_sankey": sankey(valid_salary, "city", salary_cities[:6], "job_category", categories),
        "wordcloud": {"words": [{"name": SKILL_LABELS.get(skill, skill), "value": int(value)} for skill, value in counter.most_common()]},
        "micro_sankey": sankey(valid_salary, "education", top_values(valid_salary, "education", 5), "experience", top_values(valid_salary, "experience", 6)),
        "radar": radar(valid_salary, salary_skills),
    }
    if len(valid_salary) > 2500:
        positions = np.linspace(0, len(valid_salary) - 1, 2500).astype(int)
        scatter_frame, scatter_skills = valid_salary.iloc[positions], [salary_skills[position] for position in positions]
    else:
        scatter_frame, scatter_skills = valid_salary, salary_skills
    result["interactive"]["scatter"] = {"points": [[len(item), round(float(row.salary_mid_monthly), 2), CATEGORY_LABELS.get(str(row.job_category), str(row.job_category)), label(row.city)] for row, item in zip(scatter_frame.itertuples(index=False), scatter_skills, strict=True)]}
    bubbles = []
    for city, group in valid_salary.groupby("city"):
        coordinates = CITY_COORDINATES.get(str(city))
        if coordinates and len(group) >= 30:
            bubbles.append([coordinates[0], coordinates[1], round(float(group["salary_mid_monthly"].median()), 2), int(len(group)), str(city)])
    result["interactive"]["bubble"] = {"points": sorted(bubbles, key=lambda item: item[3], reverse=True)[:20]}
    return result


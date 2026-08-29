"""Small, fixed semantic layer shared by the API and SQL planner."""

from __future__ import annotations

from typing import Any

from .taxonomy import JOB_CATEGORY_RULES, SKILL_RULES


MIN_GROUP_SAMPLE_SIZE = 30
CANONICAL_JOB_CATEGORIES = tuple(rule[0] for rule in JOB_CATEGORY_RULES) + ("other",)
CANONICAL_SKILLS = tuple(SKILL_RULES)


METRIC_DEFINITIONS: dict[str, dict[str, Any]] = {
    "avg_monthly_salary": {
        "label": "平均月薪",
        "definition": "去重后、薪资解析状态为 success 的职位月薪中点算术平均值",
        "expression": "AVG(salary_mid_monthly)",
        "required_filter": "salary_parse_status = 'success' AND salary_mid_monthly IS NOT NULL",
        "unit": "人民币/月",
    },
    "median_monthly_salary": {
        "label": "月薪中位数",
        "definition": "去重后、薪资解析状态为 success 的职位月薪中点中位数",
        "expression": "median(salary_mid_monthly)",
        "required_filter": "salary_parse_status = 'success' AND salary_mid_monthly IS NOT NULL",
        "unit": "人民币/月",
    },
    "job_count": {
        "label": "岗位数量",
        "definition": "当前数据范围内去重后的唯一职位记录数；jobs_scoped 每行对应一个 job_key",
        "expression": "COUNT(*)",
        "required_filter": None,
        "unit": "职位",
    },
    "skill_frequency": {
        "label": "技能频次",
        "definition": "去重职位中提及固定技能词典某技能的职位数；分母为同一筛选范围的 job_count",
        "expression": "SUM(CASE WHEN instr(skills, '\"<canonical_skill>\"') > 0 THEN 1 ELSE 0 END)",
        "required_filter": None,
        "unit": "职位",
    },
    "salary_available_count": {
        "label": "可分析薪资记录数",
        "definition": "薪资解析状态为 success 且月薪中点非空的去重职位数",
        "expression": "SUM(CASE WHEN salary_parse_status = 'success' AND salary_mid_monthly IS NOT NULL THEN 1 ELSE 0 END)",
        "required_filter": None,
        "unit": "职位",
    },
    "missing_description_rate": {
        "label": "职位描述缺失率",
        "definition": "职位描述为空的去重职位数除以同组 job_count；SQL 返回 0 到 1 的比例值",
        "expression": "AVG(CASE WHEN description_available = 0 THEN 1.0 ELSE 0.0 END)",
        "required_filter": None,
        "unit": "比例",
    },
}


def metric_prompt() -> str:
    """Return concise SQL-planning rules without allowing model-defined metrics."""

    lines = ["固定指标口径："]
    for name, item in METRIC_DEFINITIONS.items():
        line = f"- {name}: {item['definition']}；SQL={item['expression']}"
        if item["required_filter"]:
            line += f"；必须过滤 {item['required_filter']}"
        lines.append(line)
    lines.extend(
        [
            "固定维度与分组规则：",
            "- 岗位类别问题必须使用 normalized job_category；search_category 只是采集关键词，除非问题明确询问采集/搜索关键词，否则禁止使用。",
            "- job_category 只使用这些规范值：" + ", ".join(CANONICAL_JOB_CATEGORIES) + "。",
            "- 技能问题必须按固定技能逐项统计 instr(skills, '\"<canonical_skill>\"')；禁止 GROUP BY 原始 skills JSON，也不要把 [] 当技能。",
            "- 固定技能为：" + ", ".join(CANONICAL_SKILLS) + "。",
            f"- correctness gate：只要聚合 SQL 含 GROUP BY（明细列表除外），就必须返回 COUNT(*) AS sample_size（纯计数问题可使用 job_count），并使用 HAVING COUNT(*) >= {MIN_GROUP_SAMPLE_SIZE}；Top-N 也必须遵守。",
            "- 百分比指标在 SQL 中返回 0 到 1 的原始比例，别名以 _rate 结尾；不要在 SQL 中乘 100 或为了展示 ROUND。",
        ]
    )
    return "\n".join(lines)

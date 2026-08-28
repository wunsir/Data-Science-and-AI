"""Small, fixed semantic layer shared by the API and SQL planner."""

from __future__ import annotations

from typing import Any


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
}


def metric_prompt() -> str:
    """Return concise SQL-planning rules without allowing model-defined metrics."""

    lines = ["固定指标口径："]
    for name, item in METRIC_DEFINITIONS.items():
        line = f"- {name}: {item['definition']}；SQL={item['expression']}"
        if item["required_filter"]:
            line += f"；必须过滤 {item['required_filter']}"
        lines.append(line)
    return "\n".join(lines)

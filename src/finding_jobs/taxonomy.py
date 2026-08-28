"""Auditable, deterministic taxonomy rules for the historical job samples.

The rules in this module are deliberately small and outcome-independent.  In
particular, neither job categories nor skills are selected after looking at
salary.  Keeping the dictionaries here also makes the classifications easy to
review and change without touching the import pipeline.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


JOB_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "business_analysis",
        (
            r"商业分析",
            r"经营分析",
            r"业务分析",
            r"策略分析",
            r"战略分析",
            r"管理咨询",
            r"咨询顾问",
        ),
    ),
    (
        "data",
        (
            r"数据分析",
            r"数据科学",
            r"数据挖掘",
            r"商业智能",
            r"\bbi\b",
            r"算法.*(?:工程师|研究员)",
        ),
    ),
    ("product", (r"产品(?:经理|运营|专员|总监|负责人|助理)", r"产品策划")),
    ("operations", (r"运营", r"用户增长", r"增长经理", r"内容策划")),
    (
        "finance",
        (
            r"银行",
            r"证券",
            r"投行",
            r"投资",
            r"基金",
            r"保险",
            r"财务",
            r"会计",
            r"审计",
            r"量化",
            r"金融",
            r"风控",
            r"资产管理",
        ),
    ),
)


SEARCH_CATEGORY_FALLBACKS: dict[str, str] = {
    "商业分析": "business_analysis",
    "咨询": "business_analysis",
    "数据分析": "data",
    "产品": "product",
    "运营": "operations",
    "银行": "finance",
    "证券": "finance",
    "投行": "finance",
    "基金": "finance",
    "基金经理": "finance",
    "保险": "finance",
    "财务": "finance",
    "量化": "finance",
    "证券研究所": "finance",
}


SKILL_RULES: dict[str, tuple[str, ...]] = {
    "python": (r"\bpython\b",),
    "sql": (r"\bsql\b", r"结构化查询语言"),
    "excel": (r"\bexcel\b", r"电子表格"),
    "tableau": (r"\btableau\b",),
    "power_bi": (r"\bpower\s*bi\b", r"\bpbi\b"),
    "r": (r"(?<![a-z])r(?![a-z])", r"r语言"),
    "spss": (r"\bspss\b",),
    "statistics": (r"统计分析", r"统计学", r"多元统计", r"假设检验"),
    "machine_learning": (r"机器学习", r"深度学习", r"预测模型", r"数据建模"),
    "data_visualization": (r"数据可视化", r"可视化分析"),
    "financial_analysis": (r"财务分析", r"金融分析", r"投资分析", r"估值模型"),
    "product_management": (r"产品管理", r"产品设计", r"产品规划", r"需求分析"),
    "user_research": (r"用户研究", r"用户调研", r"用户访谈"),
    "project_management": (r"项目管理", r"项目计划", r"项目经理"),
    "operations": (r"运营管理", r"用户运营", r"内容运营", r"活动运营", r"经营管理"),
    "market_research": (r"市场调研", r"行业研究", r"商业研究", r"竞品分析"),
}


def normalize_text(value: object) -> str:
    """Return a stable, comparison-friendly representation of text."""

    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    return re.sub(r"\s+", " ", text)


def normalize_identity(value: object) -> str:
    """Normalize a field used in a deduplication identity."""

    text = normalize_text(value)
    return re.sub(r"[\s·•,，;；/\\|()（）\[\]【】]+", "", text)


def primary_city(value: object) -> str | None:
    """Reduce a location such as ``上海·浦东·张江`` to its stated city."""

    text = normalize_text(value)
    if not text:
        return None
    first = re.split(r"[·•,，/|]", text, maxsplit=1)[0].strip()
    # Avoid inventing a city when the source only says remote or nationwide.
    return first or None


def classify_job(title: object, search_category: object = None) -> str:
    """Classify a title, with the collection query as an explicit fallback."""

    normalized_title = normalize_text(title)
    for category, patterns in JOB_CATEGORY_RULES:
        if any(re.search(pattern, normalized_title, flags=re.IGNORECASE) for pattern in patterns):
            return category
    fallback = SEARCH_CATEGORY_FALLBACKS.get(str(search_category or "").strip())
    return fallback or "other"


def extract_skills(values: Iterable[object]) -> list[str]:
    """Extract canonical skills from title/tags/description in fixed key order."""

    haystack = " \n ".join(normalize_text(value) for value in values if value is not None)
    found: list[str] = []
    for skill, patterns in SKILL_RULES.items():
        if any(re.search(pattern, haystack, flags=re.IGNORECASE) for pattern in patterns):
            found.append(skill)
    return found


def taxonomy_manifest() -> dict[str, object]:
    """JSON-serializable ruleset included in the data-quality report."""

    return {
        "job_category_rules": [
            {"category": category, "patterns": list(patterns)}
            for category, patterns in JOB_CATEGORY_RULES
        ],
        "search_category_fallbacks": dict(SEARCH_CATEGORY_FALLBACKS),
        "skill_rules": {key: list(value) for key, value in SKILL_RULES.items()},
    }

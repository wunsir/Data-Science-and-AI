"""Build the published 29-chart visual story from deterministic aggregates."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from .svg_charts import bar_svg, boxplot_svg, forest_svg, heatmap_svg, lorenz_svg, multi_bar_svg, stacked_svg
from .visual_data import prepare_story_data


def _static(
    charts_dir: Path,
    chart_id: str,
    title: str,
    subtitle: str,
    svg: str,
    *,
    page: str,
    section: str,
    order: int,
    metric: str,
    data: Any,
    sample_n: int,
) -> dict[str, Any]:
    charts_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{chart_id}.svg"
    (charts_dir / filename).write_text(svg, encoding="utf-8")
    return {
        "id": chart_id, "title": title, "subtitle": subtitle, "kind": "image",
        "page": page, "section": section, "order": order,
        "file": f"charts/{filename}", "alt_text": title, "metric_note": metric,
        "sample_n": int(sample_n), "data": data,
    }


def _interactive(
    chart_id: str,
    title: str,
    subtitle: str,
    *,
    page: str,
    section: str,
    order: int,
    chart_type: str,
    metric: str,
    data: Any,
    sample_n: int,
    plugin: str | None = None,
) -> dict[str, Any]:
    chart = {
        "id": chart_id, "title": title, "subtitle": subtitle, "kind": "interactive",
        "page": page, "section": section, "order": order,
        "file": f"chart.html?id={chart_id}", "alt_text": title, "metric_note": metric,
        "sample_n": int(sample_n), "chart_type": chart_type, "data": data,
    }
    if plugin:
        chart["plugin"] = plugin
    return chart


def _sum_n(rows: list[dict[str, Any]]) -> int:
    return sum(int(row.get("n", 0)) for row in rows)


def build_visual_story(
    frame: pd.DataFrame,
    valid_salary: pd.DataFrame,
    main_model: dict[str, Any],
    sensitivity_model: dict[str, Any],
    charts_dir: Path,
    *,
    model_fitter: Callable[..., dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, dict[str, Any]]]:
    data = prepare_story_data(frame, valid_salary, main_model, sensitivity_model, model_fitter)
    jobs_n, salary_n = data["counts"]["jobs"], data["counts"]["salary"]
    charts: dict[str, dict[str, Any]] = {}

    def add_static(
        chart_id: str,
        title: str,
        subtitle: str,
        svg: str,
        page: str,
        section: str,
        order: int,
        metric: str,
        payload: Any,
        sample_n: int,
    ) -> None:
        charts[chart_id] = _static(
            charts_dir, chart_id, title, subtitle, svg,
            page=page, section=section, order=order, metric=metric,
            data=payload, sample_n=sample_n,
        )

    add_static(
        "city_category_salary_heatmap",
        "城市 × 岗位类别月薪中位数",
        "只展示样本量不少于30的城市—岗位组合",
        heatmap_svg(
            "城市 × 岗位类别月薪中位数",
            "只展示样本量不少于30的城市—岗位组合",
            data["city_rows"], data["category_columns"], data["city_cells"], kind="salary",
        ),
        "macro", "macro-city", 2, "人民币/月；月薪中点中位数", data["city_cells"], salary_n,
    )
    add_static(
        "salary_by_city", "主要城市月薪中位数",
        "按月薪中点计算；柱后标出该城市薪资样本量",
        bar_svg("主要城市月薪中位数", "按月薪中点计算；柱后标出该城市薪资样本量", data["city_salary"], kind="salary"),
        "macro", "macro-city", 3, "人民币/月；月薪中点中位数", data["city_salary"], _sum_n(data["city_salary"]),
    )
    add_static(
        "salary_by_category", "岗位类别月薪中位数", "岗位类别由固定标题词典识别",
        bar_svg("岗位类别月薪中位数", "岗位类别由固定标题词典识别", data["category_salary"], kind="salary", color="#0f766e"),
        "macro", "macro-structure", 2, "人民币/月；月薪中点中位数", data["category_salary"], _sum_n(data["category_salary"]),
    )
    add_static(
        "city_education_composition", "主要城市学历要求构成",
        "每根柱表示该城市职位样本中的学历要求比例",
        stacked_svg("主要城市学历要求构成", "每根柱表示该城市职位样本中的学历要求比例", data["city_education_rows"], data["city_education_series"]),
        "macro", "macro-structure", 3, "各城市职位样本中的构成比例",
        data["city_education_rows"], _sum_n(data["city_education_rows"]),
    )
    add_static(
        "salary_lorenz_by_category", "岗位类别薪资洛伦兹曲线",
        "曲线越偏离45度线，组内月薪分布越不均匀",
        lorenz_svg("岗位类别薪资洛伦兹曲线", "曲线越偏离45度线，组内月薪分布越不均匀", data["lorenz"]),
        "macro", "macro-distribution", 1, "基于全部可解析月薪；类别样本量不少于200", data["lorenz"], salary_n,
    )
    add_static(
        "skills_frequency", "预定义技能出现频次", "同一职位中的同一技能只计一次",
        bar_svg("预定义技能出现频次", "同一职位中的同一技能只计一次", data["skill_frequency"], color="#0f766e"),
        "micro", "micro-skills", 2, "提及该技能的职位数", data["skill_frequency"], jobs_n,
    )
    add_static(
        "skills_by_salary_quartile", "不同薪资分组的技能提及率",
        "技能范围预先固定；比较上、下四分位职位中的提及比例",
        multi_bar_svg(
            "不同薪资分组的技能提及率",
            "技能范围预先固定；比较上、下四分位职位中的提及比例",
            data["skill_quartiles"],
            [
                {"key": "lower", "name": "月薪下四分位", "color": "#94a3b8"},
                {"key": "upper", "name": "月薪上四分位", "color": "#1e40af"},
            ],
            kind="rate",
        ),
        "micro", "micro-skills", 3, "各薪资分组中的职位提及率", data["skill_quartiles"], salary_n,
    )
    add_static(
        "category_skill_heatmap", "岗位类别 × 技能提及率",
        "观察不同岗位描述中技能词的出现结构",
        heatmap_svg(
            "岗位类别 × 技能提及率", "观察不同岗位描述中技能词的出现结构",
            data["category_rate_rows"], data["category_rate_columns"], data["category_rate_cells"], kind="rate",
        ),
        "micro", "micro-skills", 4, "各岗位类别中的职位提及率", data["category_rate_cells"], jobs_n,
    )
    add_static(
        "salary_distribution", "月薪中点分布", "包含全部可解析月薪，不删除极端值",
        bar_svg("月薪中点分布", "包含全部可解析月薪，不删除极端值", data["salary_distribution"], color="#b45309"),
        "micro", "micro-factors", 2, "职位数", data["salary_distribution"], salary_n,
    )
    for chart_id, title, key, order in (
        ("salary_by_education", "学历要求与月薪分布", "education_quantiles", 3),
        ("salary_by_experience", "经验要求与月薪分布", "experience_quantiles", 4),
        ("salary_by_company_size", "公司规模与月薪分布", "company_quantiles", 5),
    ):
        rows = data[key]
        add_static(
            chart_id, title, "箱体展示组内月薪的分位数位置",
            boxplot_svg(title, "箱体展示组内月薪的分位数位置", rows),
            "micro", "micro-factors", order, "人民币/月；5%、25%、50%、75%、95%分位数", rows, _sum_n(rows),
        )
    add_static(
        "skill_count_distribution", "单条 JD 识别出的技能数量",
        "技能数量来自固定词典；6项及以上合并展示",
        bar_svg("单条 JD 识别出的技能数量", "技能数量来自固定词典；6项及以上合并展示", data["skill_count"], color="#475569"),
        "micro", "micro-association", 3, "职位数", data["skill_count"], jobs_n,
    )
    add_static(
        "salary_by_skill_count", "不同技能数量区间的月薪中位数",
        "这里只比较岗位描述中的技能提及数量",
        bar_svg("不同技能数量区间的月薪中位数", "这里只比较岗位描述中的技能提及数量", data["salary_skill_count"], kind="salary", color="#0f766e"),
        "micro", "micro-association", 4, "人民币/月；月薪中点中位数", data["salary_skill_count"], _sum_n(data["salary_skill_count"]),
    )
    add_static(
        "salary_difference_by_skill", "技能提及与未提及岗位的原始月薪差异",
        "技能按全样本出现频次选取，不据薪资结果筛词",
        bar_svg("技能提及与未提及岗位的原始月薪差异", "技能按全样本出现频次选取，不据薪资结果筛词", data["raw_skill_difference"], kind="percent", color="#7c3aed"),
        "micro", "micro-association", 5, "提及组相对未提及组的月薪中位数差异", data["raw_skill_difference"], salary_n,
    )
    add_static(
        "adjusted_associations", "岗位与技能的调整后工资关联",
        "对数月薪 OLS；同时控制来源、城市、学历、经验和公司规模",
        bar_svg("岗位与技能的调整后工资关联", "对数月薪 OLS；同时控制来源、城市、学历、经验和公司规模", data["adjusted"], kind="percent"),
        "micro", "micro-association", 6, "相对参考组的估计百分比差异；HC3稳健标准误", data["adjusted"], int(main_model.get("n", 0)),
    )
    for chart_id, title, rows_key, columns_key, cells_key, order in (
        ("skill_salary_by_education", "不同学历组中的技能—薪资差异", "education_rows", "education_columns", "education_cells", 2),
        ("skill_salary_by_category", "不同岗位类别中的技能—薪资差异", "job_rows", "job_columns", "job_cells", 3),
    ):
        add_static(
            chart_id, title, "组内比较技能提及与未提及岗位的月薪中位数",
            heatmap_svg(title, "组内比较技能提及与未提及岗位的月薪中位数", data[rows_key], data[columns_key], data[cells_key], kind="percent"),
            "micro", "micro-groups", order, "提及组相对未提及组的月薪中位数差异", data[cells_key], salary_n,
        )
    add_static(
        "salary_category_by_source", "三平台岗位类别月薪比较",
        "按平台分别计算岗位类别月薪中位数",
        heatmap_svg("三平台岗位类别月薪比较", "按平台分别计算岗位类别月薪中位数", data["source_rows"], data["source_columns"], data["source_cells"], kind="salary"),
        "micro", "micro-groups", 4, "人民币/月；月薪中点中位数", data["source_cells"], salary_n,
    )
    add_static(
        "model_trim_sensitivity", "主模型与截尾模型系数比较",
        "截尾模型用于查看极端薪资对估计结果的影响",
        multi_bar_svg(
            "主模型与截尾模型系数比较", "截尾模型用于查看极端薪资对估计结果的影响",
            data["trim"],
            [
                {"key": "main", "name": "全部可解析薪资", "color": "#1e40af"},
                {"key": "trimmed", "name": "1%/99%截尾", "color": "#0f766e"},
            ],
            kind="percent",
        ),
        "micro", "micro-robustness", 1, "两种样本处理下的调整后估计百分比差异", data["trim"], int(main_model.get("n", 0)),
    )
    add_static(
        "model_source_sensitivity", "分平台模型的技能系数",
        "点为估计值，横线为95%置信区间",
        forest_svg("分平台模型的技能系数", "点为估计值，横线为95%置信区间", data["source_forest"]),
        "micro", "micro-robustness", 2, "分平台对数月薪 OLS；HC3稳健标准误",
        data["source_forest"], sum(int(model.get("n", 0)) for model in data["source_models"].values()),
    )

    interactive_data = data["interactive"]
    charts["city_category_salary_3d"] = _interactive(
        "city_category_salary_3d", "城市与岗位类别月薪立体图",
        "拖动旋转，滚轮缩放；悬停查看组内样本量",
        page="macro", section="macro-city", order=1, chart_type="bar3d",
        plugin="echarts-gl", metric="人民币/月；月薪中点中位数",
        data=interactive_data["bar3d"], sample_n=salary_n,
    )
    charts["market_structure_treemap"] = _interactive(
        "market_structure_treemap", "城市与岗位类别样本结构",
        "面积表示职位数量，可点击城市查看其岗位构成",
        page="macro", section="macro-structure", order=1, chart_type="treemap",
        metric="去重后的职位数", data=interactive_data["treemap"], sample_n=jobs_n,
    )
    charts["city_job_salary_sankey"] = _interactive(
        "city_job_salary_sankey", "城市—岗位—薪资区间流向",
        "连线宽度表示符合该路径的职位数量",
        page="macro", section="macro-structure", order=4, chart_type="sankey",
        metric="去重后的可解析薪资职位数", data=interactive_data["macro_sankey"], sample_n=salary_n,
    )
    charts["skills_wordcloud"] = _interactive(
        "skills_wordcloud", "预定义技能词云", "词语大小表示该技能在职位中的出现次数",
        page="micro", section="micro-skills", order=1, chart_type="wordcloud",
        plugin="echarts-wordcloud", metric="提及该技能的职位数",
        data=interactive_data["wordcloud"], sample_n=jobs_n,
    )
    charts["education_experience_salary_sankey"] = _interactive(
        "education_experience_salary_sankey", "学历—经验—薪资区间流向",
        "连线宽度表示同时满足相邻字段的职位数量",
        page="micro", section="micro-factors", order=1, chart_type="sankey",
        metric="去重后的可解析薪资职位数", data=interactive_data["micro_sankey"], sample_n=salary_n,
    )
    charts["skill_count_salary_scatter"] = _interactive(
        "skill_count_salary_scatter", "技能数量与月薪散点图",
        "使用固定间隔抽取最多2500个职位用于交互展示",
        page="micro", section="micro-association", order=1, chart_type="scatter",
        metric="横轴为识别技能数；纵轴为月薪中点（对数坐标）",
        data=interactive_data["scatter"], sample_n=len(interactive_data["scatter"]["points"]),
    )
    radar_n = sum(group["n"] for group in interactive_data["radar"].get("groups", []))
    charts["salary_profile_radar"] = _interactive(
        "salary_profile_radar", "上、下薪资四分位样本特征",
        "各轴使用自身量纲，只比较两个薪资分组的样本构成",
        page="micro", section="micro-association", order=2, chart_type="radar",
        metric="工资、任职要求、技能数量与公司规模的描述性对比",
        data=interactive_data["radar"], sample_n=radar_n,
    )
    bubble_n = sum(point[3] for point in interactive_data["bubble"]["points"])
    charts["city_salary_bubble"] = _interactive(
        "city_salary_bubble", "城市薪资坐标气泡图",
        "气泡大小表示职位数，颜色表示月薪中位数",
        page="micro", section="micro-groups", order=1, chart_type="bubble",
        metric="使用本地城市坐标，不加载在线地图",
        data=interactive_data["bubble"], sample_n=bubble_n,
    )

    order = [
        "city_category_salary_3d", "city_category_salary_heatmap", "salary_by_city",
        "market_structure_treemap", "salary_by_category", "city_education_composition",
        "city_job_salary_sankey", "salary_lorenz_by_category",
        "skills_wordcloud", "skills_frequency", "skills_by_salary_quartile", "category_skill_heatmap",
        "education_experience_salary_sankey", "salary_distribution", "salary_by_education",
        "salary_by_experience", "salary_by_company_size", "skill_count_salary_scatter",
        "salary_profile_radar", "skill_count_distribution", "salary_by_skill_count",
        "salary_difference_by_skill", "adjusted_associations", "city_salary_bubble",
        "skill_salary_by_education", "skill_salary_by_category", "salary_category_by_source",
        "model_trim_sensitivity", "model_source_sensitivity",
    ]
    tables = {
        key: value for key, value in data.items()
        if key in {
            "city_cells", "city_education_rows", "lorenz", "skill_quartiles",
            "category_rate_cells", "company_quantiles", "skill_count",
            "salary_skill_count", "raw_skill_difference", "education_cells",
            "job_cells", "source_cells", "trim", "source_forest",
        }
    }
    return [charts[chart_id] for chart_id in order], tables, data["source_models"]


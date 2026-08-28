const image = (id, title, caption, layout = "") => ({ id, title, caption, layout, kind: "image", src: `./data/charts/${id}.svg` });
const interactive = (id, title, caption, layout = "wide") => ({ id, title, caption, layout, kind: "interactive", src: `./chart.html?id=${id}` });

export const sharedNavigation = [
    { href: "./index.html", label: "项目概览", page: "home" },
    { href: "./macro.html", label: "宏观分布分析", page: "macro" },
    { href: "./micro.html", label: "岗位与技能分析", page: "micro" }
];

export const fallbackMetrics = {
    rawRows: "44,329",
    uniqueJobs: "36,452",
    salaryJobs: "34,130",
    sources: "3"
};

export const homeData = {
    title: "招聘市场的岗位结构与薪资差异",
    subtitle: "基于 BOSS直聘、前程无忧与智联招聘职位样本",
    tags: [
        { key: "uniqueJobs", suffix: " 个去重职位" },
        { key: "salaryJobs", suffix: " 个可分析薪资" },
        { key: "sources", suffix: " 个招聘平台" }
    ],
    overviewTitle: "研究概览",
    overview: [
        "这组数据来自 BOSS直聘、前程无忧和智联招聘。三家平台的字段统一后，我们按职位 ID 或职位、公司、城市和薪资组合去重，再从城市、岗位类别、任职要求和技能描述四个角度展开分析。",
        "宏观页先看城市、岗位类别和薪资分布；岗位与技能页再看学历、经验、公司规模和技能字段与薪资之间的关系。两个页面使用同一张职位事实表。"
    ],
    highlights: [
        "样本主要集中在上海、北京、深圳、广州、南京和杭州，金融财会岗位数量最多。",
        "可解析职位的月薪中点中位数为 13,000 元。不同岗位、城市和任职要求之间呈现出清晰的分组差异。"
    ],
    cards: [
        {
            href: "./macro.html",
            tone: "blue",
            title: "宏观分布分析",
            text: "从城市和岗位类别出发，查看样本分布、月薪中位数、学历要求和组内薪资差异。",
            action: "进入宏观分析",
            icon: "bars"
        },
        {
            href: "./micro.html",
            tone: "indigo",
            title: "岗位与技能分析",
            text: "从职位描述和任职要求出发，比较学历、经验、公司规模、技能字段与薪资的关系。",
            action: "进入岗位分析",
            icon: "nodes"
        }
    ]
};

const methods = {
    title: "数据说明",
    intro: "三个页面使用同一版职位事实表和同一套分类规则。",
    steps: [
        { title: "字段统一", text: "统一职位、公司、城市、薪资、学历、经验、公司规模、技能和来源字段，同时保留原始行号与来源文件。" },
        { title: "职位去重", text: "优先使用平台职位 ID；没有 ID 时，使用平台、职位、公司、城市和薪资组成的指纹。" },
        { title: "薪资换算", text: "月薪和年薪按明确周期换算为月度区间中点；周期无法判断的记录不进入薪资图。" },
        { title: "分类与模型", text: "岗位和技能使用固定词典。调整后结果来自对数月薪 OLS，并使用 HC3 稳健标准误。" }
    ],
    examples: [
        ["15-25K·13薪", "21.7K/月", "区间中点 × 13 ÷ 12"],
        ["20-30万/年", "20.8K/月", "区间中点 ÷ 12"],
        ["200-300元/天", "不换算", "缺少统一月工作日依据"],
        ["70-100万（无周期）", "不换算", "无法判断计薪周期"]
    ],
    footnote: "历史文件没有可靠的逐条发布时间，因此页面按一次采集样本展示。"
};

export const pageData = {
    macro: {
        title: "宏观分布分析",
        subtitle: "城市、岗位类别与薪资分布",
        lead: "先从城市和岗位类别入手。薪资图使用可解析月薪区间的中点，并以中位数比较各组位置。",
        sections: [
            {
                id: "macro-city",
                title: "1. 城市薪资与岗位分布",
                intro: "把城市和岗位类别交叉后，可以同时看到职位集中在哪里，以及同一岗位类别在不同城市的薪资位置。",
                figures: [
                    interactive("city_category_salary_3d", "城市与岗位类别月薪立体图", "图 1-1：城市与岗位类别月薪立体图"),
                    image("city_category_salary_heatmap", "城市 × 岗位类别月薪中位数", "图 1-2：城市 × 岗位类别月薪中位数", "wide"),
                    image("salary_by_city", "主要城市月薪中位数", "图 1-3：主要城市月薪中位数", "wide")
                ],
                note: "上海、北京、深圳、广州、南京和杭州是样本量最大的六个城市。交叉图只展示至少包含 30 个职位的城市—岗位组合。"
            },
            {
                id: "macro-structure",
                title: "2. 岗位结构与学历要求",
                intro: "岗位数量、薪资位置和学历要求不是同一件事。树图先展示样本构成，再分别比较薪资和学历结构。",
                figures: [
                    interactive("market_structure_treemap", "城市与岗位类别样本结构", "图 2-1：城市与岗位类别样本结构"),
                    image("salary_by_category", "岗位类别月薪中位数", "图 2-2：岗位类别月薪中位数"),
                    image("city_education_composition", "主要城市学历要求构成", "图 2-3：主要城市学历要求构成"),
                    interactive("city_job_salary_sankey", "城市—岗位—薪资区间流向", "图 2-4：城市—岗位—薪资区间流向")
                ],
                note: "金融财会岗位在样本中数量最多，产品和商业分析岗位的月薪中位数相对更高。桑基图中的连线宽度表示相应路径上的职位数。"
            },
            {
                id: "macro-distribution",
                title: "3. 薪资分布与差异",
                intro: "中位数只能说明组内的中心位置。洛伦兹曲线进一步比较各岗位类别内部的薪资分布。",
                figures: [
                    image("salary_lorenz_by_category", "岗位类别薪资洛伦兹曲线", "图 3-1：岗位类别薪资洛伦兹曲线", "wide")
                ],
                note: "曲线越偏离 45 度线，表示该岗位类别内部的薪资分布越不均匀。图中同时列出各组的 Gini 系数。"
            }
        ],
        methods
    },
    micro: {
        title: "岗位与技能分析",
        subtitle: "任职要求、技能字段与薪资关联",
        lead: "这一页从职位描述和任职要求出发。技能由固定词典识别，分组比较与回归使用同一批可解析薪资职位。",
        sections: [
            {
                id: "micro-skills",
                title: "1. 岗位文本与技能提取",
                intro: "先看岗位描述里实际出现了哪些技能，以及这些技能在不同岗位类别和薪资分组中的分布。",
                figures: [
                    interactive("skills_wordcloud", "预定义技能词云", "图 1-1：预定义技能词云"),
                    image("skills_frequency", "预定义技能出现频次", "图 1-2：预定义技能出现频次"),
                    image("skills_by_salary_quartile", "不同薪资分组的技能提及率", "图 1-3：不同薪资分组的技能提及率"),
                    image("category_skill_heatmap", "岗位类别 × 技能提及率", "图 1-4：岗位类别 × 技能提及率", "wide")
                ],
                note: "页面按预定义技能词典识别 JD 中的技能名称；上下四分位图比较这些技能在两个薪资分组中的提及比例。"
            },
            {
                id: "micro-factors",
                title: "2. 薪资相关因素",
                intro: "学历、经验和公司规模都来自招聘信息中的任职要求。箱线图保留组内分布，不只比较一个平均值。",
                figures: [
                    interactive("education_experience_salary_sankey", "学历—经验—薪资区间流向", "图 2-1：学历—经验—薪资区间流向"),
                    image("salary_distribution", "月薪中点分布", "图 2-2：月薪中点分布", "wide"),
                    image("salary_by_education", "学历要求与月薪分布", "图 2-3：学历要求与月薪分布"),
                    image("salary_by_experience", "经验要求与月薪分布", "图 2-4：经验要求与月薪分布"),
                    image("salary_by_company_size", "公司规模与月薪分布", "图 2-5：公司规模与月薪分布", "wide")
                ],
                note: "学历和经验要求较高的岗位通常位于更高的月薪区间，但这些岗位在城市、岗位类别和公司规模上的构成也不同。"
            },
            {
                id: "micro-association",
                title: "3. 技能与薪资关联",
                intro: "这一部分先展示未经调整的分组差异，再用同一模型同时纳入平台、岗位、城市和任职要求。",
                figures: [
                    interactive("skill_count_salary_scatter", "技能数量与月薪散点图", "图 3-1：技能数量与月薪散点图"),
                    interactive("salary_profile_radar", "上、下薪资四分位样本特征", "图 3-2：上、下薪资四分位样本特征"),
                    image("skill_count_distribution", "单条 JD 识别出的技能数量", "图 3-3：单条 JD 识别出的技能数量"),
                    image("salary_by_skill_count", "不同技能数量区间的月薪中位数", "图 3-4：不同技能数量区间的月薪中位数"),
                    image("salary_difference_by_skill", "技能提及与未提及岗位的原始月薪差异", "图 3-5：技能提及与未提及岗位的原始月薪差异"),
                    image("adjusted_associations", "岗位与技能的调整后工资关联", "图 3-6：岗位与技能的调整后工资关联", "wide")
                ],
                note: "原始差异和调整后系数回答的是两个不同问题。前者直接比较分组中位数，后者比较其他列示字段相近时的样本关联。"
            },
            {
                id: "micro-groups",
                title: "4. 分组比较",
                intro: "把总体结果拆到城市、学历、岗位类别和平台后，可以看到哪些关系比较一致，哪些依赖样本构成。",
                figures: [
                    interactive("city_salary_bubble", "城市薪资坐标气泡图", "图 4-1：城市薪资坐标气泡图"),
                    image("skill_salary_by_education", "不同学历组中的技能—薪资差异", "图 4-2：不同学历组中的技能—薪资差异"),
                    image("skill_salary_by_category", "不同岗位类别中的技能—薪资差异", "图 4-3：不同岗位类别中的技能—薪资差异"),
                    image("salary_category_by_source", "三平台岗位类别月薪比较", "图 4-4：三平台岗位类别月薪比较", "wide")
                ],
                note: "平台之间的岗位构成和采样范围不同。这里保留分平台结果，便于观察同一岗位类别在不同来源中的位置。"
            },
            {
                id: "micro-robustness",
                title: "5. 稳健性检查",
                intro: "最后比较极端薪资处理和分平台建模后的系数，检查主要结果是否由单一处理方式带动。",
                figures: [
                    image("model_trim_sensitivity", "主模型与截尾模型系数比较", "图 5-1：主模型与截尾模型系数比较", "wide"),
                    image("model_source_sensitivity", "分平台模型的技能系数", "图 5-2：分平台模型的技能系数", "wide")
                ],
                note: "截尾模型只用于敏感性比较，主分析仍保留全部可解析薪资。分平台图使用相同技能词典和模型结构。"
            }
        ],
        methods
    }
};


export const analysisData = {
    navigation: [
        { id: "overview", label: "项目概览" },
        { id: "salary", label: "薪资格局" },
        { id: "requirements", label: "任职要求" },
        { id: "skills", label: "技能分析" },
        { id: "methods", label: "数据说明" }
    ],
    intro: {
        title: "招聘市场数据分析",
        subtitle: "数据来源：BOSS直聘、前程无忧、智联招聘（2025年末采集）",
        description: "项目整理了三家招聘平台的职位信息。经过字段统一和去重，44,329 条原始记录形成 36,452 个职位，其中 34,130 个职位可用于薪资分析。",
        stats: [
            { label: "原始记录", value: "44,329" },
            { label: "去重职位", value: "36,452" },
            { label: "薪资样本", value: "34,130" },
            { label: "来源文件", value: "66" }
        ]
    },
    sections: [
        {
            id: "overview",
            title: "1. 样本构成",
            intro: "先看样本本身。三家平台的职位数量、岗位类别和城市覆盖并不相同。",
            figures: [
                { src: "./data/charts/sample_by_source.svg", title: "三平台去重后职位数量", caption: "图 1-1：三平台去重后职位数量", layout: "wide" },
                { src: "./data/charts/sample_by_category.svg", title: "主要岗位类别的样本构成", caption: "图 1-2：主要岗位类别的样本构成" },
                { src: "./data/charts/sample_by_city.svg", title: "主要城市的样本数量", caption: "图 1-3：主要城市的样本数量" }
            ],
            note: "智联招聘包含 24,792 个职位，前程无忧 7,014 个，BOSS直聘 4,646 个。样本以金融财会岗位为主，上海、北京和深圳的记录数较多。"
        },
        {
            id: "salary",
            title: "2. 岗位与城市薪资格局",
            intro: "薪资分析使用 34,130 个可换算为月薪的职位。我们同时比较整体分布、岗位类别和城市差异。",
            figures: [
                { src: "./data/charts/salary_distribution.svg", title: "月薪中点分布", caption: "图 2-1：月薪中点分布", layout: "wide" },
                { src: "./data/charts/salary_by_category.svg", title: "不同岗位类别的月薪中位数", caption: "图 2-2：不同岗位类别的月薪中位数" },
                { src: "./data/charts/salary_by_city.svg", title: "主要城市的月薪中位数", caption: "图 2-3：主要城市的月薪中位数" }
            ],
            note: "月薪中点的样本中位数为 13,000 元。产品岗位中位数约为 15,000 元，商业分析约为 14,000 元，运营岗位约为 10,667 元。城市图同时标出了各组样本量。"
        },
        {
            id: "requirements",
            title: "3. 学历与经验要求",
            intro: "学历和经验来自招聘信息中的岗位要求。这里保留平台原始分组，比较各组的月薪中位数。",
            figures: [
                { src: "./data/charts/salary_by_education.svg", title: "学历要求与月薪中位数", caption: "图 3-1：学历要求与月薪中位数" },
                { src: "./data/charts/salary_by_experience.svg", title: "经验要求与月薪中位数", caption: "图 3-2：经验要求与月薪中位数" }
            ],
            note: "学历和经验要求较高的岗位通常对应更高的月薪中位数。这些岗位在城市、职位类别和公司规模上的构成也有所不同。"
        },
        {
            id: "skills",
            title: "4. 岗位技能结构",
            intro: "我们用固定词典从职位标题和描述中识别技能，同一职位的同一技能只计一次。",
            figures: [
                { src: "./data/charts/skills_frequency.svg", title: "岗位描述中的技能出现频次", caption: "图 4-1：岗位描述中的技能出现频次", layout: "center" }
            ],
            note: "financial_analysis 出现 1,345 次，operations 出现 829 次，product_management 出现 786 次，SQL 出现 774 次，Python 出现 593 次。"
        },
        {
            id: "adjusted",
            title: "5. 调整后的工资差异",
            intro: "模型同时纳入平台来源、岗位类别、城市、学历、经验、公司规模和预定义技能，比较这些字段相近时的工资差异。",
            figures: [
                { src: "./data/charts/salary_by_source.svg", title: "不同平台样本的月薪中位数", caption: "图 5-1：不同平台样本的月薪中位数" },
                { src: "./data/charts/adjusted_associations.svg", title: "岗位与技能的调整后工资关联", caption: "图 5-2：岗位与技能的调整后工资关联" }
            ],
            table: {
                title: "模型结果（节选）",
                headers: ["变量", "调整后差异", "P 值"],
                rows: [
                    ["技能：machine_learning", "+12.34%", "<0.001"],
                    ["岗位：产品", "+6.59%", "<0.001"],
                    ["岗位：运营", "-10.11%", "<0.001"],
                    ["技能：tableau", "+6.78%", "0.098"]
                ]
            },
            note: "BOSS、智联和前程无忧样本的月薪中位数分别为 19,500 元、13,500 元和 11,500 元。主模型使用 34,130 个职位，R² 为 0.3688。",
            boundary: "模型结果表示本次样本中的关联，不等同于个人学习某项技能后的涨薪幅度。"
        }
    ],
    methods: {
        title: "6. 数据处理说明",
        intro: "三家平台的字段先统一到同一张职位表，再进入统计和建模。",
        steps: [
            { title: "字段统一", text: "保留职位、公司、城市、薪资、学历、经验、公司规模、技能和来源链接等字段，同时记录来源文件和原始行号。" },
            { title: "职位去重", text: "优先使用平台职位 ID；没有 ID 时，按平台、职位、公司、城市和薪资组成的指纹识别重复记录。" },
            { title: "薪资换算", text: "月薪和年薪按明确周期换算为月度区间中点；无法判断计薪周期的记录保留原文，不参加薪资统计。" },
            { title: "分类与建模", text: "岗位和技能使用固定词典分类。工资模型采用对数月薪、平台固定效应和 HC3 稳健标准误。" }
        ],
        salaryExamples: [
            { original: "15-25K·13薪", result: "21.7K/月", rule: "月薪区间中点 × 13 ÷ 12" },
            { original: "20-30万/年", result: "20.8K/月", rule: "年薪区间中点 ÷ 12" },
            { original: "200-300元/天", result: "不换算", rule: "缺少统一的月工作日依据" },
            { original: "70-100万（无周期）", result: "不换算", rule: "计薪周期无法确定" }
        ],
        footnote: "数据采集于 2025 年末；页面中的统计量和模型结果均按本次职位样本计算。"
    }
};

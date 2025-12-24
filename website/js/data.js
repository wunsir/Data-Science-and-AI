export const analysisData = {
    intro: {
        title: "招聘市场数据洞察",
        subtitle: "基于 Boss直聘、前程无忧、智联招聘的 40,000+ 条数据深度分析",
        description: "本项目旨在通过对中国主流招聘平台的数据挖掘，揭示数据科学与AI领域的真实人才需求。我们不仅关注薪资数字，更致力于通过自然语言处理（NLP）和计量经济学模型，量化技能、学历、地域对薪资的深层影响机制。",
        stats: [
            { label: "数据总量", value: "40,000+", unit: "条" },
            { label: "覆盖平台", value: "3", unit: "个" },
            { label: "分析维度", value: "12+", unit: "项" },
            { label: "核心发现", value: "58.0", unit: "技能系数" }
        ]
    },
    logic: {
        title: "分析逻辑架构",
        subtitle: "宏观格局与微观机制的统一",
        description: "本研究采用了「宏观格局+微观机制」的双层分析架构。智联招聘数据用于描绘全国市场的宏观轮廓，而BOSS直聘与前程无忧则作为双重验证源，深入剖析薪资形成的微观机制。",
        items: [
            {
                type: "Landscape",
                title: "宏观格局 (Landscape)",
                sources: ["智联招聘 (Zhaopin)"],
                desc: "利用智联招聘的广泛覆盖数据，绘制全国薪资热力图，分析城市间的不平等（洛伦兹曲线）及岗位类型的整体分布，确立研究的宏观背景。",
                icon: "🌏"
            },
            {
                type: "Mechanism",
                title: "微观机制 (Mechanism)",
                sources: ["BOSS直聘", "前程无忧 (51job)"],
                desc: "利用BOSS直聘的高保真JD和前程无忧的结构化标签，进行平行的深度挖掘。通过NLP提取技能因子，构建回归模型，并进行异质性与稳健性检验，互证结论的可靠性。",
                icon: "🧬"
            }
        ]
    },
    methodology: [
        { step: "1. 数据清洗与标准化", icon: "🧹", details: "针对不同平台的薪资格式编写正则解析函数，统一转换为月均薪资。将学历和经验要求映射为定序数值变量。", keyPoints: ["正则表达式解析", "单位统一化", "缺失值处理"] },
        { step: "2. NLP 文本挖掘", icon: "📝", details: "使用 Jieba 对职位描述进行分词，计算 TF-IDF 权重，利用余弦相似度计算每个岗位 JD 与「高薪模板」的语义相似度。", keyPoints: ["Jieba 分词", "TF-IDF 向量化", "余弦相似度"] },
        { step: "3. 计量经济学建模", icon: "📊", details: "构建多元线性回归（OLS）模型，量化各因素对薪资的边际贡献。进行异质性分析。", keyPoints: ["OLS 回归", "交互效应", "分组回归"] },
        { step: "4. 因果推断与稳健性检验", icon: "🔬", details: "引入倾向得分匹配（PSM）和安慰剂检验（Placebo Test）确保结论可靠性。", keyPoints: ["PSM 匹配", "安慰剂测试", "敏感性分析"] }
    ],
    dataTransform: {
        title: "数据清洗与标准化",
        subtitle: "从原始文本到可分析变量",
        description: "招聘平台的原始数据格式混乱，我们通过精心设计的清洗流程，将非结构化文本转换为可建模的数值变量。",
        salaryExamples: [
            { original: "15-25K·13薪", cleaned: "21.7K/月", formula: "(15+25)/2 × 13/12" },
            { original: "1-1.5万/月", cleaned: "12.5K/月", formula: "(10+15)/2" },
            { original: "200-300元/天", cleaned: "5.4K/月", formula: "(200+300)/2 × 21.75 ÷ 1000" },
            { original: "20-30万/年", cleaned: "20.8K/月", formula: "(20+30)/2 ÷ 12" }
        ],
        mappings: {
            education: [
                { label: "学历不限", value: 0 },
                { label: "高中/中专", value: 1 },
                { label: "大专", value: 2 },
                { label: "本科", value: 3 },
                { label: "硕士", value: 4 },
                { label: "博士", value: 5 }
            ],
            experience: [
                { label: "经验不限", value: 0 },
                { label: "应届生", value: 0 },
                { label: "1年以内", value: 0.5 },
                { label: "1-3年", value: 2 },
                { label: "3-5年", value: 4 },
                { label: "5-10年", value: 7.5 },
                { label: "10年以上", value: 12 }
            ]
        }
    },
    regression: {
        title: "核心发现：薪资决定方程",
        subtitle: "OLS 多元线性回归结果",
        formula: "Salary = 8.1 + 2.8×Edu + 1.7×Exp + 58.0×Skill_Match",
        interpretation: "职位描述相似度（Skill Match）是影响薪资的最关键因素",
        rSquared: 0.42,
        nObs: 15000,
        coefficients: [
            { name: "截距 (Constant)", value: 8.10, pValue: "<0.001", interpretation: "基准薪资约为 8.1K/月" },
            { name: "学历等级 (Edu_level)", value: 2.81, pValue: "<0.001", interpretation: "学历每提升一级，月薪增加约 2.8K" },
            { name: "经验年限 (Exp_level)", value: 1.70, pValue: "<0.001", interpretation: "经验每增加一个等级，月薪增加约 1.7K" },
            { name: "技能相似度 (Similarity)", value: 58.00, pValue: "<0.001", interpretation: "相似度每增加0.1，月薪增加约 5.8K（核心发现！）" }
        ],
        keyInsight: "技能匹配度的回归系数（58.0）远超学历（2.8）和经验（1.7），这表明：在控制了学历和经验后，你的简历/技能与高薪岗位的匹配程度才是决定薪资的核心因素。"
    },
    datasets: [
        {
            name: "前程无忧 (51job)",
            description: "传统综合招聘平台数据，覆盖面广，包含详细的企业性质与福利标签。",
            count: "8,000+",
            columns: ["职位名称", "原始薪资", "清洗后薪资(K)", "城市", "学历要求", "学历等级", "经验要求", "经验等级"],
            sample: [
                { pos: "数据分析师", rawSalary: "15-25K·13薪", cleanedSalary: "21.7", city: "上海", edu: "本科", eduLevel: 3, exp: "3-5年", expLevel: 4 },
                { pos: "算法工程师", rawSalary: "30-50K", cleanedSalary: "40.0", city: "北京", edu: "硕士", eduLevel: 4, exp: "3-5年", expLevel: 4 },
                { pos: "产品经理", rawSalary: "1-1.6万·13薪", cleanedSalary: "14.1", city: "深圳", edu: "本科", eduLevel: 3, exp: "5-10年", expLevel: 7.5 },
                { pos: "AI训练师", rawSalary: "8-12K", cleanedSalary: "10.0", city: "成都", edu: "大专", eduLevel: 2, exp: "1-3年", expLevel: 2 },
                { pos: "数据工程师", rawSalary: "25-35K·14薪", cleanedSalary: "35.0", city: "杭州", edu: "本科", eduLevel: 3, exp: "5-10年", expLevel: 7.5 }
            ]
        },
        {
            name: "BOSS直聘",
            description: "新兴直聘模式平台，数据包含高保真的职位描述（JD）文本和精确的技能标签，适合进行深度文本分析。",
            count: "12,000+",
            columns: ["职位名称", "原始薪资", "清洗后薪资(K)", "城市", "学历要求", "学历等级", "经验要求", "经验等级"],
            sample: [
                { pos: "机器学习工程师", rawSalary: "35-60K", cleanedSalary: "47.5", city: "北京", edu: "硕士", eduLevel: 4, exp: "3-5年", expLevel: 4 },
                { pos: "数据分析师", rawSalary: "12-20K", cleanedSalary: "16.0", city: "广州", edu: "本科", eduLevel: 3, exp: "1-3年", expLevel: 2 },
                { pos: "NLP算法", rawSalary: "40-70K", cleanedSalary: "55.0", city: "上海", edu: "硕士", eduLevel: 4, exp: "5-10年", expLevel: 7.5 },
                { pos: "BI工程师", rawSalary: "18-30K", cleanedSalary: "24.0", city: "深圳", edu: "本科", eduLevel: 3, exp: "3-5年", expLevel: 4 },
                { pos: "数据运营", rawSalary: "8-15K", cleanedSalary: "11.5", city: "武汉", edu: "本科", eduLevel: 3, exp: "1-3年", expLevel: 2 }
            ]
        }
    ],
    story: [
        {
            id: "market-landscape",
            title: "1. 市场宏观格局",
            subtitle: "地域分布与薪资不平等",
            description: "基于智联招聘数据，我们首先审视了全国范围内的招聘市场宏观特征。从地理分布到薪资不平等，揭示了人才市场的整体面貌。",
            keyFindings: ["北上广深平均薪资显著高于其他城市", "技术类岗位薪酬上限极高，拉大基尼系数", "新一线城市（杭州、成都）正在快速追赶"],
            images: [
                { src: "./data/picture/zlzp城市岗位薪资热力图.png", title: "全国岗位薪资热力分布", source: "智联招聘", explanation: "热力图显示，投行、基金、量化行业薪资更高，数据分析、运营等相对较低。" },
                { src: "./data/picture/zlzp城市平均薪资对比.png", title: "主要城市平均薪资对比", source: "智联招聘", explanation: "柱状图直观对比了各主要城市的平均薪资水平，北京、深圳、上海位列前三，高于新一线城市。" },
                { src: "./data/picture/zlzp城市学历要求构成.png", title: "各城市学历要求构成", source: "智联招聘", explanation: "堆叠柱状图展示了不同城市对学历的要求差异。本科是学历门槛，一线城市对硕士需求更高。" },
                { src: "./data/picture/zlzp岗位类型薪酬排名.png", title: "不同岗位类型薪酬排名", source: "智联招聘", explanation: "数据显示，投行、基金、量化行业薪资更高（和前面热力图对应）。" },
                { src: "./data/picture/zlzp薪资不平等洛伦兹曲线.png", title: "薪资不平等洛伦兹曲线", source: "智联招聘", explanation: "洛伦兹曲线越偏离45度线，说明薪资不平等程度越高。图中显示金融类岗位薪资不平等更突出，数据分析相对均衡。" }
            ],
            interactiveCharts: [
                { src: "./data/treemap_market_of_zlzp.html", title: "市场结构树图 (交互)", source: "智联招聘", explanation: "交互式树图展示了各城市、岗位类型的市场结构占比，可点击查看细分数据。" }
            ],
            insight: "一线城市依然是高薪聚集地，但薪资不平等现象（洛伦兹曲线）在不同城市间存在显著差异。技术类岗位的薪酬上限极高，拉大了整体差距。"
        },
        {
            id: "salary-basics",
            title: "2. 薪资基石",
            subtitle: "学历与经验的硬通货",
            description: "深入 BOSS直聘与前程无忧的微观数据，我们验证了学历与经验作为薪资决定性因素的地位。两平台数据呈现出高度的一致性。",
            keyFindings: ["硕士学历平均薪资比本科高出约 40%", "3-5年和5-10年是薪资增长的关键跃升期", "大公司（1000人以上）平均薪资高于中小企业"],
            images: [
                { src: "./data/picture/boss薪资分布与学历经验分析.png", title: "薪资分布与学历/经验关系", source: "BOSS直聘", explanation: "该图综合展示了薪资的整体分布形态（偏态分布）、不同学历的薪资箱线图对比，以及经验年限与薪资增长的关系曲线。" },
                { src: "./data/picture/qcwy薪资分布.png", title: "整体薪资分布直方图", source: "前程无忧", explanation: "薪资分布呈现典型的右偏态，大部分岗位集中在 10-25K 区间，但存在长尾高薪岗位。" },
                { src: "./data/picture/qcwy学历薪资.png", title: "学历对薪资的影响", source: "前程无忧", explanation: "箱线图清晰显示：学历越高，薪资中位数和上限都越高。博士学历的薪资优势尤为明显。" },
                { src: "./data/picture/qcwy经验薪资.png", title: "经验对薪资的影响", source: "前程无忧", explanation: "折线图显示薪资随经验增长呈 S 型曲线：0-3年增长平缓，3-10年快速增长，10年后趋于平稳。" },
                { src: "./data/picture/qcwy公司规模薪资.png", title: "公司规模与薪资关系", source: "前程无忧", explanation: "大公司在薪资方面具有明显优势，可能与资源、融资能力和品牌溢价有关。" },
                { src: "./data/picture/qcwy职业阶段薪资.png", title: "职业阶段与薪资关系", source: "前程无忧", explanation: "从入门级到高级/专家级，薪资呈现阶梯式增长，印证了职业发展路径的重要性。" }
            ],
            interactiveCharts: [
                { src: "./data/boss城市薪资地图.html", title: "全国城市薪资地图 (交互)", source: "BOSS直聘", explanation: "交互式地图展示各城市的平均薪资水平，圆圈大小和颜色代表薪资高低，可悬停查看具体数值。" },
                { src: "./data/sankey_chart_of_boss.html", title: "人才职业发展路径桑基图 (交互)", source: "BOSS直聘", explanation: "桑基图展示了从学历到经验再到薪资分层的人才流动路径，宽度代表人数占比。" },
                { src: "./data/salary_3d_bar_of_zlzp.html", title: "薪资3D柱状图 (交互)", source: "智联招聘", explanation: "三维视角展示不同城市、不同岗位的薪资对比，可旋转查看。" }
            ],
            insight: "学历决定下限，经验决定上限。无论是新兴的BOSS还是传统的51job，这一规律都坚不可摧。大公司（规模效应）通常能提供更具竞争力的薪资包。"
        },
        {
            id: "skill-decoding",
            title: "3. 技能解码",
            subtitle: "从文本中挖掘高薪密码",
            description: "利用 NLP 技术，我们从海量 JD 中提取了高薪核心词汇，并构建了「高薪模板」。通过计算相似度，我们量化了技能的含金量。",
            keyFindings: ["高薪岗位的 JD 中，硬技能（Python、算法、架构）出现频率显著更高", "低薪岗位更多强调软技能（沟通、吃苦耐劳）", "与高薪模板的相似度与实际薪资呈强正相关 (r > 0.6)"],
            images: [
                { src: "./data/picture/boss岗位技能词云与统计.png", title: "岗位核心技能词云", source: "BOSS直聘", explanation: "词云展示了 JD 中出现频率最高的技能关键词。字体越大表示出现频率越高，Python、数据分析、机器学习等词汇占据核心位置。" },
                { src: "./data/picture/qcwy福利关键词词云与统计.png", title: "福利关键词分析", source: "前程无忧", explanation: "企业福利词云显示，五险一金、带薪年假是基本配置，而股票期权、弹性工作等则是高薪企业的差异化竞争点。" },
                { src: "./data/picture/boss高低薪岗位核心词汇对比.png", title: "高薪 vs 低薪岗位核心词汇对比 (原始)", source: "BOSS直聘", explanation: "未经 AI 筛选的原始对比图。" },
                { src: "./data/picture/boss高低薪岗位核心词汇对比AI筛选.png", title: "高薪 vs 低薪岗位核心词汇对比 (Qwen AI筛选)", source: "BOSS直聘", explanation: "该图对比展示了经 AI 清洗去除福利、套话后的核心词汇：高薪岗位（薪资前10%）更侧重数学、Python等硬技能，而低薪岗位更侧重沟通、执行等软技能。" },
                { src: "./data/picture/boss职位描述相似度与薪资关系.png", title: "JD相似度与薪资关系", source: "BOSS直聘", explanation: "将高薪组 JD 合并为“高薪原型”，计算每条 JD 与原型的相似度。散点图与回归线显示：与高薪模板的相似度越高，实际薪资越高。" },
                { src: "./data/picture/qcwy职位描述相似度与薪资关系.png", title: "JD相似度与薪资关系", source: "前程无忧", explanation: "前程无忧数据同样验证了这一结论，回归趋势与 BOSS 数据高度一致。" },
                { src: "./data/picture/boss相似度等级与薪资关系.png", title: "相似度等级与平均薪资", source: "BOSS直聘", explanation: "将相似度分档后的柱状图显示：随着相似度等级的提升（从非常不相似到非常相似），平均薪资呈现整体递增趋势。" },
                { src: "./data/picture/qcwy相似度等级与薪资关系.png", title: "相似度等级与平均薪资", source: "前程无忧", explanation: "前程无忧数据呈现相同规律，验证了相似度指标的跨平台有效性。" },
                { src: "./data/picture/boss相似度分布直方图.png", title: "相似度分布直方图", source: "BOSS直聘", explanation: "直方图展示了相似度得分的分布情况，大致呈右偏分布，反映了市场上大部分岗位的技能匹配度和高薪技能相似度较低，“高薪技能组合”仍较为稀缺。" },
                { src: "./data/picture/qcwy相似度分布.png", title: "相似度分布直方图", source: "前程无忧", explanation: "前程无忧的相似度分布与 BOSS 类似，说明两平台的岗位描述特征具有一致性。" },
                { src: "./data/picture/boss薪资分组相似度箱线图.png", title: "薪资分组相似度箱线图", source: "BOSS直聘", explanation: "将样本按薪资分为高薪组和低薪组，箱线图显示高薪组的相似度分布整体较高，中位数明显优于低薪组。" },
                { src: "./data/picture/qcwy薪资分组相似度箱线图.png", title: "薪资分组相似度箱线图", source: "前程无忧", explanation: "两平台数据均显示：高薪岗位的 JD 与「高薪模板」的语义距离更近。" }
            ],
            interactiveCharts: [
                { src: "./data/diamond_chart_fixed_of_boss.html", title: "高薪技能词云雷达 (交互)", source: "BOSS直聘", explanation: "交互式钻石形词云展示高薪岗位的硬核技能关键词，词越大表示TF-IDF权重越高，含金量越高。" },
                { src: "./data/scatter_regression_of_boss.html", title: "技能含金量与薪资关系 (交互)", source: "BOSS直聘", explanation: "交互式散点图展示每个岗位的JD含金量与薪资关系，红线为回归趋势线，可悬停查看具体岗位信息。" }
            ],
            insight: "与高薪模板的语义相似度越高，实际薪资越高。「算法」、「架构」等硬核技能是提升相似度（进而提升薪资）的关键。这一结论在两个平台中均得到验证。"
        },
        {
            id: "regression-attribution",
            title: "4. 归因分析",
            subtitle: "谁在决定你的工资？",
            description: "通过多元回归模型，我们剥离了各因素的独立贡献，结果显示，BOSS直聘与前程无忧的模型结果高度互证。",
            keyFindings: ["技能相似度的回归系数（58.0）远超学历（2.8）和经验（1.7）", "控制其他变量后，学历每升一级，薪资增加约 2.8K", "模型 R² 约为 0.42，说明这三个变量解释了 42% 的薪资变异"],
            images: [
                { src: "./data/picture/boss薪资影响因素相关性热力图.png", title: "变量相关性热力图", source: "BOSS直聘", explanation: "热力图展示了薪资与各自变量之间的相关系数。颜色深浅代表相关性强弱，显示技能相似度与薪资的相关性最强。" },
                { src: "./data/picture/qcwy薪资相关性热力图.png", title: "变量相关性热力图", source: "前程无忧", explanation: "前程无忧数据的相关性矩阵与 BOSS 高度一致，验证了结论的跨平台稳健性。" },
                { src: "./data/picture/qcwy薪资关键技能相关性.png", title: "关键技能相关性", source: "前程无忧", explanation: "分析显示具体技能（如 Python、SQL）与薪资之间存在显著的正相关关系。" },
                { src: "./data/picture/boss薪资影响因素堆积分析.png", title: "各因素边际贡献堆积图", source: "BOSS直聘", explanation: "堆积图直观展示了从基准薪资出发，学历、经验、技能相似度各自贡献了多少薪资增量。" },
                { src: "./data/picture/qcwy薪资影响因素堆积分析.png", title: "各因素边际贡献堆积图", source: "前程无忧", explanation: "两平台的堆积图结构相似，都显示技能相似度是最大的边际贡献因子。" },
                { src: "./data/picture/boss薪资影响因素重要性排序.png", title: "影响因素重要性排序", source: "BOSS直聘", explanation: "图表对回归系数进行了排序，技能相似度以绝对优势领先，表明其对薪资波动的影响最大。" },
                { src: "./data/picture/qcwy薪资影响因素对比.png", title: "影响因素对比", source: "前程无忧", explanation: "前程无忧数据同样显示，相比于传统因素，技能相似度的重要性更为突出。" }
            ],
            insight: "在控制了学历和经验后，「技能描述相似度」依然对薪资有显著的正向贡献，且其边际效应在两个平台中均得到了验证。技能是学历之外最重要的溢价来源。"
        },
        {
            id: "heterogeneity-robustness",
            title: "5. 深度洞察",
            subtitle: "异质性分析与稳健性检验",
            description: "我们进一步探讨了「学历-技能」的交互效应，并通过 PSM 和安慰剂检验确保了结论的因果可靠性。",
            keyFindings: ["高学历群体中，技能的边际回报更高（正向调节效应）", "一线城市的技能回报率显著高于二三线城市", "安慰剂测试证明结论并非统计巧合 (p < 0.001)"],
            images: [
                { src: "./data/picture/boss学历对技能溢价的调节作用.png", title: "学历对技能溢价的调节作用", source: "BOSS直聘", explanation: "图中显示：高学历群体的回归斜率更陡，说明学历能放大技能的价值（正向调节）。" },
                { src: "./data/picture/qcwy学历对技能溢价调节作用.png", title: "学历对技能溢价的调节作用", source: "前程无忧", explanation: "前程无忧数据同样验证了学历的正向调节作用：学历越高，技能越值钱。" },
                { src: "./data/picture/boss城市等级技能回报率差异.png", title: "城市等级技能回报率差异", source: "BOSS直聘", explanation: "分组回归结果显示，新一线城市的技能回报率显著最高。" },
                { src: "./data/picture/qcwy城市等级技能回报率.png", title: "城市等级技能回报率差异", source: "前程无忧", explanation: "前程无忧数据则是一线城市技能回报率最高，呈现相反规律，可能是样本量不足。" },
                { src: "./data/picture/boss技能溢价异质性分析.png", title: "技能溢价异质性分析", source: "BOSS直聘", explanation: "图表展示了技能溢价效应在不同子样本（分组）中的系数估计值和置信区间，入门岗位/小公司中，技能含金量对薪资提升更明显。。" },
                { src: "./data/picture/qcwy技能溢价异质性分析.png", title: "技能溢价异质性分析", source: "前程无忧", explanation: "前程无忧的数据亦和BOSS直聘之间存在矛盾。" },
                { src: "./data/picture/boss倾向得分匹配效果验证.png", title: "PSM匹配效果验证", source: "BOSS直聘", explanation: "倾向得分匹配（PSM）用于消除选择偏差。匹配后，处理组和控制组的倾向得分分布高度重叠，说明匹配效果良好。" },
                { src: "./data/picture/qcwy倾向得分匹配效果验证.png", title: "PSM匹配效果验证", source: "前程无忧", explanation: "前程无忧数据的 PSM 匹配同样有效，为因果推断提供了坚实基础。" },
                { src: "./data/picture/boss安慰剂测试稳健性检验.png", title: "安慰剂测试稳健性检验", source: "BOSS直聘", explanation: "随机置换测试产生的系数分布与真实系数相距甚远，证明我们的结果具有统计显著性，并非偶然所得。" },
                { src: "./data/picture/qcwy安慰剂测试稳健性检验.png", title: "安慰剂测试稳健性检验", source: "前程无忧", explanation: "两平台的安慰剂测试均显示：真实回归系数具有统计学显著性，排除了随机因素干扰。" }
            ],
            interactiveCharts: [
                { src: "./data/radar_profile_of_boss.html", title: "高薪vs低薪人才画像对比 (交互)", source: "BOSS直聘", explanation: "雷达图直观对比高薪组（Top 25%）和低薪组（Bottom 25%）在学历、经验、技能含金量三个维度的差异。高薪组在所有维度上都明显领先。" }
            ],
            insight: "高学历不仅带来高起薪，还能放大技能的价值（调节效应）。同时，安慰剂测试证明了我们的发现并非统计巧合，具有极高的稳健性。"
        }
    ],
    conclusion: {
        title: "结论与启示",
        subtitle: "给求职者和企业的建议",
        forJobSeekers: ["优化简历关键词，向高薪 JD 的核心技能靠拢", "学历是敲门砖，但技能才是涨薪的核心驱动力", "优先选择一线城市或新一线城市，技能回报率更高"],
        forEmployers: ["JD 中应突出核心硬技能要求，避免泛泛而谈的软技能", "提供有竞争力的薪资可以吸引更高「技能匹配度」的候选人", "关注候选人的技能组合，而非单纯看学历和经验"],
        limitations: ["数据主要来自在线招聘平台，可能存在样本偏差", "薪资数据为招聘发布的范围，非实际成交薪资", "技能相似度基于 TF-IDF，未使用更复杂的语义模型"]
    }
};

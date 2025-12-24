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
            keyFindings: ["京津冀、长三角、珠三角是绝对的高薪核心区", "金融与技术类岗位拉高了整体基尼系数", "新一线城市（杭州、成都）薪资竞争力逼近一线"],
            images: [
                { src: "./data/picture/zlzp城市岗位薪资热力图.png", title: "全国岗位薪资热力分布", source: "智联招聘", explanation: "热力图直观呈现了“沿海高、内陆低”的阶梯状分布。京津冀、长三角、珠三角颜色最深，是高薪岗位最密集的区域。" },
                { src: "./data/picture/zlzp城市平均薪资对比.png", title: "主要城市平均薪资对比", source: "智联招聘", explanation: "北京、上海、深圳稳居薪资第一梯队，杭州作为新一线城市的领头羊，平均薪资已超越广州，紧追北上深。" },
                { src: "./data/picture/zlzp城市学历要求构成.png", title: "各城市学历要求构成", source: "智联招聘", explanation: "一线城市对学历的“内卷”程度更甚，硕士及以上学历要求占比显著高于二三线城市，本科已成为基本门槛。" },
                { src: "./data/picture/zlzp岗位类型薪酬排名.png", title: "不同岗位类型薪酬排名", source: "智联招聘", explanation: "行业壁垒明显，投行、量化、芯片设计等高技术/高资本门槛岗位，薪资中位数远超传统的运营、行政类岗位。" },
                { src: "./data/picture/zlzp薪资不平等洛伦兹曲线.png", title: "薪资不平等洛伦兹曲线", source: "智联招聘", explanation: "金融与互联网行业的洛伦兹曲线弯曲程度最大，说明这两个行业内部贫富差距极大，“赢家通吃”现象严重。" }
            ],
            interactiveCharts: [
                { src: "./data/treemap_market_of_zlzp.html", title: "市场结构树图 (交互)", source: "智联招聘", explanation: "树图展示了各城市与岗位的市场份额，矩形面积越大代表岗位需求量越大。" }
            ],
            insight: "一线城市不仅提供了更高的薪资下限，更提供了极高的薪资上限。高薪不再普惠，而是向特定区域（长三角/珠三角）和特定赛道（硬核科技/金融）高度集中。"
        },
        {
            id: "salary-basics",
            title: "2. 薪资基石",
            subtitle: "学历与经验的硬通货",
            description: "深入 BOSS直聘与前程无忧的微观数据，我们验证了学历与经验作为薪资决定性因素的地位。两平台数据呈现出高度的一致性。",
            keyFindings: ["硕士学历溢价率最高，约为本科的 1.4 倍", "工作 3-5 年是薪资跃升的黄金窗口期", "万人大厂的平均薪资显著高于中小企业"],
            images: [
                { src: "./data/picture/boss薪资分布与学历经验分析.png", title: "薪资分布与学历/经验关系", source: "BOSS直聘", explanation: "薪资分布呈右偏长尾状。学历决定了薪资的起跑线（箱线图底部），而经验决定了薪资的增长斜率（曲线陡峭度）。" },
                { src: "./data/picture/qcwy薪资分布.png", title: "整体薪资分布直方图", source: "前程无忧", explanation: "绝大多数岗位薪资集中在 10-25K 区间，超过 50K 的高薪岗位极其稀缺，仅占样本的 3% 左右。" },
                { src: "./data/picture/qcwy学历薪资.png", title: "学历对薪资的影响", source: "前程无忧", explanation: "学历每提升一级，薪资中位数上浮显著。博士学历的薪资下限甚至高于大专学历的上限，学历壁垒森严。" },
                { src: "./data/picture/qcwy经验薪资.png", title: "经验对薪资的影响", source: "前程无忧", explanation: "经验回报呈非线性：0-3年增长较慢，3-8年加速上升，10年后增速放缓，呈现经典的 S 型人力资本积累曲线。" },
                { src: "./data/picture/qcwy公司规模薪资.png", title: "公司规模与薪资关系", source: "前程无忧", explanation: "大厂由于盈利能力强、筛选严格，能提供明显高于市场平均水平的薪资溢价（Firm Size Wage Premium）。" },
                { src: "./data/picture/qcwy职业阶段薪资.png", title: "职业阶段与薪资关系", source: "前程无忧", explanation: "从初级到专家级，薪资呈阶梯式跨越。职级晋升是打破经验自然增长瓶颈的关键跳板。" }
            ],
            interactiveCharts: [
                { src: "./data/boss城市薪资地图.html", title: "全国城市薪资地图 (交互)", source: "BOSS直聘", explanation: "交互式地图，圆圈大小代表薪资水平。沿海城市群构成了中国薪资的高地。" },
                { src: "./data/sankey_chart_of_boss.html", title: "人才职业发展路径桑基图 (交互)", source: "BOSS直聘", explanation: "追踪人才流向，展示了“高学历+核心城市”如何汇聚成高薪群体的路径。" },
                { src: "./data/salary_3d_bar_of_zlzp.html", title: "薪资3D柱状图 (交互)", source: "智联招聘", explanation: "多维视角展示城市、岗位与薪资的立体关系。" }
            ],
            insight: "学历是入场券，经验是磨刀石，平台（公司规模）是放大器。传统的人力资本理论在中国的招聘市场上依然有效且精准。"
        },
        {
            id: "skill-decoding",
            title: "3. 技能解码",
            subtitle: "从文本中挖掘高薪密码",
            description: "利用 NLP 技术，我们从海量 JD 中提取了高薪核心词汇，并构建了「高薪模板」。通过计算相似度，我们量化了技能的含金量。",
            keyFindings: ["硬核技能（算法、架构）是高薪 JD 的核心特征", "低薪岗位充斥着软技能描述（沟通、抗压）", "JD 相似度每提升 10%，薪资预期增加约 15%"],
            images: [
                { src: "./data/picture/boss岗位技能词云与统计.png", title: "岗位核心技能词云", source: "BOSS直聘", explanation: "Python、TensorFlow、微服务、分布式等技术名词占据了词云核心，这些是当前市场最认可的硬通货。" },
                { src: "./data/picture/qcwy福利关键词词云与统计.png", title: "福利关键词分析", source: "前程无忧", explanation: "高薪岗位强调“期权、股票、弹性工作”，普通岗位则更多提及“五险一金、加班补助”等基础保障。" },
                { src: "./data/picture/boss高低薪岗位核心词汇对比.png", title: "高薪 vs 低薪岗位词汇对比 (原始)", source: "BOSS直聘", explanation: "直观对比：左侧高薪区充斥着英文技术栈，右侧低薪区则多为中文通用形容词。" },
                { src: "./data/picture/boss高低薪岗位核心词汇对比AI筛选.png", title: "高薪 vs 低薪岗位词汇对比 (AI筛选)", source: "BOSS直聘", explanation: "AI 降噪后对比更强烈：高薪岗位的核心是“解决复杂技术问题”，低薪岗位的核心是“执行与配合”。" },
                { src: "./data/picture/boss职位描述相似度与薪资关系.png", title: "JD相似度与薪资关系", source: "BOSS直聘", explanation: "回归线斜率为正且陡峭，表明简历/JD 含金量（与高薪模板的相似度）直接决定了薪资水平。" },
                { src: "./data/picture/qcwy职位描述相似度与薪资关系.png", title: "JD相似度与薪资关系", source: "前程无忧", explanation: "前程无忧数据完美复现了这一规律，证明“技能含金量”是跨平台的定价标准。" },
                { src: "./data/picture/boss相似度等级与薪资关系.png", title: "相似度等级与平均薪资", source: "BOSS直聘", explanation: "相似度分级显示，拥有“高薪技能组合”的候选人极为稀缺，市场愿意为其支付高昂溢价。" },
                { src: "./data/picture/qcwy相似度等级与薪资关系.png", title: "相似度等级与平均薪资", source: "前程无忧", explanation: "随着技能匹配度的提升，平均薪资呈指数级而非线性增长。" },
                { src: "./data/picture/boss相似度分布直方图.png", title: "相似度分布直方图", source: "BOSS直聘", explanation: "分布呈右偏态，说明市场上大部分岗位的技能密度较低，真正的高技能高薪岗位属于“金字塔尖”。" },
                { src: "./data/picture/qcwy相似度分布.png", title: "相似度分布直方图", source: "前程无忧", explanation: "分布形态与 BOSS 直聘一致，反映了人才供给结构的普遍现状。" },
                { src: "./data/picture/boss薪资分组相似度箱线图.png", title: "薪资分组相似度箱线图", source: "BOSS直聘", explanation: "高薪组的相似度中位数远高于低薪组，技能组合的优劣是区分薪资阶层的核心指标。" },
                { src: "./data/picture/qcwy薪资分组相似度箱线图.png", title: "薪资分组相似度箱线图", source: "前程无忧", explanation: "箱线图分离度极高，说明通过优化技能描述来提升薪资潜力的空间巨大。" }
            ],
            interactiveCharts: [
                { src: "./data/diamond_chart_fixed_of_boss.html", title: "高薪技能词云雷达 (交互)", source: "BOSS直聘", explanation: "钻石图展示了高薪技能簇，越靠近中心、面积越大的词汇，市场价值越高。" },
                { src: "./data/scatter_regression_of_boss.html", title: "技能含金量与薪资关系 (交互)", source: "BOSS直聘", explanation: "每个点代表一个职位，红线揭示了技能价值的市场定价规律。" }
            ],
            insight: "薪资不是随机分配的。掌握“算法、架构”等核心硬技能，并能在简历中准确描述它们（提高相似度），是获取高薪的最短路径。"
        },
        {
            id: "regression-attribution",
            title: "4. 归因分析",
            subtitle: "谁在决定你的工资？",
            description: "通过多元回归模型，我们剥离了各因素的独立贡献，结果显示，BOSS直聘与前程无忧的模型结果高度互证。",
            keyFindings: ["技能匹配度的解释力最强（系数 58.0），远超学历和经验", "学历仅贡献了基础门槛价值，技能贡献了核心溢价", "模型解释了 42% 的薪资方差，剩余部分可能源于面试表现等不可观测因素"],
            images: [
                { src: "./data/picture/boss薪资影响因素相关性热力图.png", title: "变量相关性热力图", source: "BOSS直聘", explanation: "颜色最深的色块出现在“薪资”与“技能相似度”之间，统计相关性最强。" },
                { src: "./data/picture/qcwy薪资相关性热力图.png", title: "变量相关性热力图", source: "前程无忧", explanation: "双平台数据双重验证，排除了单一数据源偏差的可能性。" },
                { src: "./data/picture/qcwy薪资关键技能相关性.png", title: "关键技能相关性", source: "前程无忧", explanation: "细分技能相关性显示，Python、SQL、AI 等特定技能与薪资高度正相关。" },
                { src: "./data/picture/boss薪资影响因素堆积分析.png", title: "各因素边际贡献堆积图", source: "BOSS直聘", explanation: "在薪资构成中，学历和经验构建了底座，而技能相似度贡献了最大的增量部分。" },
                { src: "./data/picture/qcwy薪资影响因素堆积分析.png", title: "各因素边际贡献堆积图", source: "前程无忧", explanation: "结构与 BOSS 直聘惊人一致，技能是决定薪资天花板的关键变量。" },
                { src: "./data/picture/boss薪资影响因素重要性排序.png", title: "影响因素重要性排序", source: "BOSS直聘", explanation: "标准化回归系数排序：技能相似度 > 学历 > 经验 > 城市等级。" },
                { src: "./data/picture/qcwy薪资影响因素对比.png", title: "影响因素对比", source: "前程无忧", explanation: "技能因素的主导地位在两个模型中均得到确认，这是本研究最核心的量化发现。" }
            ],
            insight: "在控制了学历、经验和城市后，你“会什么”比你“在哪里”或“读了多少年书”更重要。技能匹配度是解释高薪差异的第一要素。"
        },
        {
            id: "heterogeneity-robustness",
            title: "5. 深度洞察",
            subtitle: "异质性分析与稳健性检验",
            description: "我们进一步探讨了「学历-技能」的交互效应，并通过 PSM 和安慰剂检验确保了结论的因果可靠性。",
            keyFindings: ["高学历能放大技能的价值（学历与技能存在正向互补）", "一线城市的技能回报率显著高于非一线城市", "因果推断验证了技能对薪资的提升是真实的，而非幸存者偏差"],
            images: [
                { src: "./data/picture/boss学历对技能溢价的调节作用.png", title: "学历对技能溢价的调节作用", source: "BOSS直聘", explanation: "高学历组的回归斜率更陡峭。意味着同样的技能，在硕士手中能变现出比本科更高的价值（信号效应叠加）。" },
                { src: "./data/picture/qcwy学历对技能溢价调节作用.png", title: "学历对技能溢价的调节作用", source: "前程无忧", explanation: "前程无忧数据同样支持这一结论：学历是技能价值的放大器。" },
                { src: "./data/picture/boss城市等级技能回报率差异.png", title: "城市等级技能回报率差异", source: "BOSS直聘", explanation: "一线城市的技能回归系数最高。大城市产业集聚度高，对专业技能的渴求度更高，付费意愿更强。" },
                { src: "./data/picture/qcwy城市等级技能回报率.png", title: "城市等级技能回报率差异", source: "前程无忧", explanation: "结论一致：越是核心城市，技术变现的效率越高；下沉市场更看重通识能力。" },
                { src: "./data/picture/boss技能溢价异质性分析.png", title: "技能溢价异质性分析", source: "BOSS直聘", explanation: "误差棒图显示，技能溢价效应在各个子群体（不同规模、不同性质企业）中均显著为正，具有普适性。" },
                { src: "./data/picture/qcwy技能溢价异质性分析.png", title: "技能溢价异质性分析", source: "前程无忧", explanation: "稳健性检验表明，核心结论不随样本分组的变化而改变。" },
                { src: "./data/picture/boss倾向得分匹配效果验证.png", title: "PSM匹配效果验证", source: "BOSS直聘", explanation: "PSM 匹配消除了选择性偏差，确保我们比较的是背景相似但技能描述不同的候选人。" },
                { src: "./data/picture/qcwy倾向得分匹配效果验证.png", title: "PSM匹配效果验证", source: "前程无忧", explanation: "匹配后样本分布高度重合，为后续的因果推断奠定了坚实的数据基础。" },
                { src: "./data/picture/boss安慰剂测试稳健性检验.png", title: "安慰剂测试稳健性检验", source: "BOSS直聘", explanation: "红色虚线（真实系数）远在灰色随机分布之外 (p<0.001)，证明技能与薪资的关系绝非统计巧合。" },
                { src: "./data/picture/qcwy安慰剂测试稳健性检验.png", title: "安慰剂测试稳健性检验", source: "前程无忧", explanation: "安慰剂检验再次确证了结论的极高置信度。" }
            ],
            interactiveCharts: [
                { src: "./data/radar_profile_of_boss.html", title: "高薪vs低薪人才画像对比 (交互)", source: "BOSS直聘", explanation: "高薪人才画像（雷达图外圈）在学历、经验、技能三个维度上全面碾压低薪人才，不存在明显的短板。" }
            ],
            insight: "技能不仅仅是加法，更是乘法。在“高学历”和“一线城市”的加持下，核心技能的价值会被指数级放大。这解释了为何技术大牛多集中在北上广深的大厂。"
        }
    ],
    conclusion: {
        title: "结论与启示",
        subtitle: "给求职者和企业的建议",
        forJobSeekers: ["简历优化：用具体的硬技能名词（如 NLP、Spark）替代模糊的软描述", "策略选择：优先去一线城市和高学历赛道，那里技能更值钱", "终身学习：学历决定起点，但持续更新技能库才能决定终点"],
        forEmployers: ["招聘升级：JD 撰写应精准化，避免无效的“万金油”描述", "薪酬策略：为高技能匹配度的候选人提供溢价，这是降低人才错配成本的最优解", "人才识别：关注候选人的技能组合（Skill Set），而非仅看头衔和年限"],
        limitations: ["数据来源限制：仅覆盖在线招聘平台，可能遗漏高端猎头市场", "薪资测度偏差：使用发布薪资而非实际成交薪资，可能存在一定高估", "文本分析局限：TF-IDF 模型难以捕捉深层语义语境"]
    }
};

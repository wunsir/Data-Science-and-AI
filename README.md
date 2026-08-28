# Finding Jobs：招聘数据分析与 Data Agent

面向招聘者和面试官的招聘数据作品，展示一条可复核的完整链路：三平台原始文件 → 统一事实表 → 数据质量报告 → 描述性分析与关联模型 → 受限 Text-to-SQL Agent。

主题口径是**“2025 年末中国主要城市复合白领岗位样本”**，覆盖金融、产品、运营、商业分析和数据岗位。历史数据是按关键词与城市采集的便利样本。Lever 公开职位刷新代码作为实验模块保留，与主站历史样本分开。

## 当前结果

- 66 个原始文件、44,329 行，经确定性去重得到 36,452 个唯一职位；其中 34,130 条薪资状态为 `success`，可按明确规则分析。
- 统一生成 SQLite seed、质量报告、分析摘要，以及宏观 8 图、微观 21 图（21 张本地 SVG 与 8 个本地交互图）。
- 对数月薪 OLS 控制来源、岗位、城市、学历、经验、公司规模和预定义技能，使用 HC3 稳健标准误；另生成 1%/99% 截尾敏感性结果。
- 三个既有页面保持原站结构，共有 29 个图位；Data Agent 仅以桌面右侧抽屉、移动端底部面板接入，不改变页面主体。
- 公网 Data Agent 固定查询 `historical`，返回自然语言回答、结果表、可展开 SQL、数据范围和必要提示，不生成新的 Agent 图表。
- Lever 公开职位刷新及 `live`、`compare` 代码仅作为实验能力保留，不是默认用户能力；不运行 BOSS、前程无忧或智联爬虫。

静态分析结果可直接查看 [website/data/analysis_summary.json](website/data/analysis_summary.json)，数据对账见 [website/data/quality_report.json](website/data/quality_report.json)。

## 架构

```text
boss/*.xlsx ───────────────┐
qianchengwuyou/data/*.csv ├─> deterministic pipeline ─> jobs_seed.sqlite
zlzp/*/*.xlsx ────────────┘                │              ├─ jobs_analytics
                                          │              ├─ provenance
                                          │              └─ dataset_versions
                                          ├─ quality_report.json
                                          └─ analysis_summary.json + 21 SVG + 8 interactive

browser ─> FastAPI :7860 ─> historical-only public Agent ─> JSON-schema SQL plan
                                                      │
                                                      └─ read-only jobs_scoped ─> grounded answer

experimental: Lever refresh ─> normalize/dedupe/upsert ─> live scope
```

核心模块：

- `src/finding_jobs/pipeline.py`：字段映射、薪资解析、去重、provenance 和版本表。
- `src/finding_jobs/taxonomy.py`：与薪资结果无关的固定岗位/技能词典。
- `src/finding_jobs/analysis.py`：同源指标、手工 OLS/HC3、敏感性结果和 SVG。
- `src/finding_jobs/agent.py`：结构化 SQL、只读执行与数字 grounding。
- `src/finding_jobs/live.py`：实验性的固定公开职位板刷新、缓存与快照 upsert。
- `src/finding_jobs/app.py`：API、匿名会话、限流和静态页面托管。

## 数据规则

`jobs` 事实表保留 `job_key`、`data_scope`、来源及来源 ID、职位、公司、城市、搜索类别、实际职位分类，以及 `salary_raw`、原始人民币上下界、周期、薪数、月薪上下限与中点、解析状态和详细原因；同时保留学历、经验、公司规模、技能、描述、来源 URL 和观察时间。Agent 只能访问去除来源 ID、描述、URL 和原始 JSON 的 `jobs_analytics`；描述仅暴露是否存在的布尔标记。

去重先使用平台 ID。无 ID 记录使用规范化的来源、职位、公司、城市和薪资指纹；只有当该指纹唯一对应一个平台 ID 组时才桥接，多 ID 歧义不合并。每个原始行都写入 provenance，并标记是否为事实表保留记录。

薪资不做填补：

- 月薪区间按原单位换算成人民币/月；明确年薪除以 12。
- `N薪` 按月薪区间乘以 `N/12`。
- 日薪、时薪、周薪、次薪、面议和单边区间保留原文及 `unsupported` 状态，不进入薪资分析。
- 缺少周期且金额可能同时表示年薪或非月薪的记录标为 `ambiguous`；本轮因此从旧口径中排除 78 条曾被静默按月解析的记录。
- 主描述保留可解析的全部极端值；截尾仅用于回归敏感性，不替代主结果。

历史文件没有可靠的逐条发布时间或观察时间，因此统一标注为“2025 年末采集样本”，不生成时间趋势。

## 本地运行

Windows PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 重建 seed、质量报告、分析摘要和 SVG
.\.venv\Scripts\python.exe scripts\rebuild.py --output-dir artifacts

# 可选：启用真实 Data Agent（以下为 SiliconFlow 配置）
$env:LLM_API_KEY = "在本机环境变量中设置，不要写入仓库"
$env:LLM_BASE_URL = "https://api.siliconflow.cn/v1"
$env:LLM_MODEL = "deepseek-ai/DeepSeek-V3.2"
$env:LLM_RESPONSE_FORMAT = "json_schema"
$env:LLM_ENABLE_THINKING = "false"

.\.venv\Scripts\python.exe -m uvicorn finding_jobs.app:app --host 127.0.0.1 --port 7860
```

打开 `http://127.0.0.1:7860`。未配置模型密钥时，研究页和预设静态结果仍可查看，但自由提问会明确返回模型不可用，不会降级为伪 Agent。

环境变量模板见 [.env.example](.env.example)。主要变量：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `LLM_API_KEY` | 无 | OpenAI 兼容模型服务密钥 |
| `LLM_BASE_URL` | `https://api.siliconflow.cn/v1` | 模型端点 |
| `LLM_MODEL` | `deepseek-ai/DeepSeek-V3.2` | 当前评测中 historical 表现最好的候选模型 |
| `LLM_RESPONSE_FORMAT` | `json_schema` | 规划阶段结构化输出格式 |
| `LLM_ENABLE_THINKING` | `false` | 是否启用模型思考模式 |
| `JOBS_DB_PATH` | `artifacts/jobs_seed.sqlite` | 运行数据库 |
| `AGENT_QUESTIONS_PER_HOUR` | `10` | 单匿名会话提问额度 |
| `LIVE_REFRESHES_PER_HOUR` | `3` | 单匿名会话刷新额度 |
| `MAX_DAILY_AGENT_QUESTIONS` | `100` | 单实例每日问题额度 |

## API 与安全边界

- `GET /api/health`：数据库、模型和记录状态。
- `GET /api/meta`：数据口径、配额和历史问题示例。
- `POST /api/ask`：`{"question":"...", "scope_override":"historical"}`。省略范围也会固定使用历史样本；传入 `live` 或 `compare` 返回 422。
- `POST /api/live/refresh`：实验接口，接受固定职位板与城市白名单，不在主站 Agent 中开放。

SQL 必须是单条 `SELECT`，最多返回 200 行；静态检查、SQLite authorizer、函数白名单、只读连接和执行超时共同限制访问。模型回答中的阿拉伯数字若不能在结果行中定位，整个回答会被拒绝。

实验刷新使用 Lever 公开 Postings API。相同公司/城市组合缓存 10 分钟，每次最多规范化 50 条；上游失败时只返回明确错误或最后缓存。运行数据库位于容器临时目录，重启后实时记录清空。

## 测试与评估

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

测试覆盖字段映射、薪资单位、固定词典、ID/指纹去重、provenance、逐层对账、OLS/HC3、SVG、SQL 攻击、范围路由、数字 grounding、模型缺失、空结果、缓存、upsert、白名单和限流。

18 题真实模型评估入口：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_agent.py
```

题集由 8 个历史、5 个最新、3 个分组比较和 2 个不支持问题组成。脚本需要真实 `LLM_API_KEY`，无密钥时退出且不生成虚假得分；目标为支持问题 SQL 执行成功率至少 90%，不支持问题全部拒绝。

2026-08-28 使用 SiliconFlow 做了真实多模型评测。完整 18 题初轮中，Qwen3.5-35B 为 1/16、DeepSeek-V3.2 为 5/16、Qwen2.5-72B 为 6/16、GLM-4.5-Air 为 0/16；其中 Qwen2.5-72B 的通过题主要来自 experimental 范围。另以 6 个 historical 代表题筛选 DeepSeek-V3.1-Terminus、DeepSeek-V3、Qwen3.5-27B、Qwen3-30B、Qwen2.5-32B 和 Ling-flash-2.0，最高为 2/6；Seed-OSS-36B 因响应时间过长中止。

针对多模型共同暴露的问题，补充受限 `median()` 聚合，并让回答阶段只接收查询结果，不再接收覆盖范围中的数字。DeepSeek-V3.2 完整复测结果为：16 个受支持问题通过 11 个，SQL 执行及重放一致均为 14/16（87.5%），数字 grounding 为 11/16（68.75%），两个不支持问题均被拦截；8 个 historical 问题实际完成 5 个。详细本地报告默认不纳入 Git，位于 `artifacts/agent_evaluation_*.json`。

因此当前数据分析页面与确定性安全边界可继续审计，但自由提问 Agent 仍未达到发布门槛。剩余 historical 失败均是 SQL 成功后对小数格式化或百分比换算触发严格 grounding；本轮不再放宽校验或扩展功能。

## Docker 与公网模式

```powershell
docker build -t finding-jobs-agent .
docker run --rm -p 7860:7860 -e LLM_API_KEY finding-jobs-agent
```

镜像构建阶段重建历史 seed 与静态分析产物；启动时将 seed 复制到 `/tmp/finding_jobs/jobs.sqlite`，服务监听 `0.0.0.0:7860`。`ms_deploy.json` 固定 ModelScope Docker Studio 端口 7860。当前真实模型评测未达标，未进入 ModelScope 发布；仓库也不会自动创建、更新或发布公开 Studio。

`website/` 可作为 GitHub Pages 静态镜像。若 `/api/health` 不可用，页面自动进入静态模式并禁用 Data Agent，不展示无响应交互。

## 凭证与历史说明

当前工作树已移除旧 Cookie、内嵌 API key 和硬编码 MongoDB 认证，并将本地凭证文件加入忽略规则。此次没有重写 Git 历史；任何曾提交且仍可能有效的 Cookie、API key 或数据库凭证都必须在公网部署前失效或轮换。

公开实时接口选择 Lever 官方职位发布接口；旧 BOSS/前程无忧/智联脚本仅保留为历史采集与清洗参考，不由访客触发。相关边界可参阅 [Lever Postings API](https://github.com/lever/postings-api)、[智联用户服务协议](https://rd6.zhaopin.com/aboutus/legal/service) 和 [ModelScope Docker Studio](https://www.modelscope.cn/docs/studios/docker)。

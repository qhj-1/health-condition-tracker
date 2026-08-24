---
name: health-condition-tracker
description: 长期全面记录身体症状、生活习惯、用药和治疗方案，分析潜在疾病风险，生成个性化健康建议和医生沟通报告。当用户描述身体不适、希望追踪健康状况、管理用药或就诊前整理病情时使用。
---

# Health Condition Tracker 健康管理技能

> 本技能用于长期全面记录病情、分析病症、提供治疗养护方案与健康建议，并支持生成医生沟通报告与病情视图报告。

> 🌐 **网页版**：另有纯前端网页应用（免安装、免 Python、数据仅存浏览器本地），入口 docs/index.html，线上 https://qhj-1.github.io/health-condition-tracker/ ；桌面版指令选择器在 docs/selector.html。

## 1. 使用场景

本技能适用于以下典型场景（包括但不限于）：

- **症状描述**：用户描述身体不适（如头痛、发热、咳嗽），希望记录并了解可能原因。
- **家庭健康档案**：一家多人分别建档，录入时选择「添加到哪个档案」。
- **低频回访**：隔几周或有病情才回来，一次对话/一条命令接上之前的记录。
- **长期追踪**：用户希望持续记录症状与健康指标，观察变化趋势。
- **用药管理**：用户需要记录正在服用的药物，或担心多种药物相互作用。
- **报告上传**：用户上传化验单、体检报告或症状照片，希望提取并解读信息。
- **就诊辅助**：用户在就诊前希望整理病情摘要，生成医生沟通报告或病情视图报告。
- **健康咨询**：用户希望获得饮食、运动、睡眠等非医疗级个性化建议。

## 2. 重要声明

> **免责声明**：本技能提供的所有内容仅供参考，不能替代专业医疗诊断、治疗或处方。涉及诊断和治疗决策，请务必咨询合格医生或医疗机构。

**紧急情况提示**：如果用户出现以下任何紧急症状，应立即停止常规问询，第一时间建议立即就医（拨打 120 或前往急诊）：

- 剧烈疼痛（如剧烈胸痛、剧烈腹痛、剧烈头痛）
- 呼吸困难或气促
- 胸痛、胸闷（尤其伴冷汗、恶心、放射痛）
- 意识模糊、昏厥、抽搐
- 严重出血，或呕血、便血
- 言语不清、肢体无力（疑似卒中）
- 高热伴意识改变或皮疹

## 3. 功能概述

本技能提供以下 24 大功能：

1. **病情录入向导**：一问一答录入病情：开启多家人档案 → 录入症状 → 补充既往病情 → 追问情况 → 选择档案 → 可视化分析 → 生成病情视图报告。
2. **症状收集**：结构化收集症状及特征（位置、起始时间、严重程度、影响）。
3. **报告分析**：解读用户上传的化验单、体检报告、症状照片。
4. **知识库查询 + 联网搜索**：通过外部医学知识库 API 与免密钥联网搜索（DuckDuckGo / 维基百科）查询疾病与最新资料，失败时回退到内置映射。
5. **记录追踪**：长期保存健康记录，支持按时间查看与修改。
6. **用药管理**：记录药物名称、剂量、频次、起止时间，并做相互作用提醒。
7. **治疗方案**：保存医生诊断、建议、复诊时间，跟踪执行状态。
8. **个性化建议**：基于症状与生活方式生成饮食、运动、睡眠等非医疗级建议。
9. **医生报告**：生成结构化医生沟通报告，供就诊时直接使用。
10. **风险预警**：识别紧急症状并发出就医提醒，提示潜在风险趋势。
11. **多家人档案**：用 `--member` 区分家人，数据分目录保存，支持一键查看全家提醒；可用 `intake.py --enable-multi` 开启开关。
12. **图表可视化**：`scripts/charts.py` 生成症状频次、严重程度趋势、体征趋势 PNG 图。
13. **日历热力图**：`scripts/calendar_heatmap.py` 生成按月症状严重程度热力图。
14. **复诊提醒**：`scripts/reminders.py` 列出近期复诊与停药提醒（支持全部成员）。
15. **间隔期总览**：`scripts/snapshot.py` 一条命令查看距上次记录天数、逾期复诊、进行中用药、症状统计与待办，专为低频使用设计。
16. **病情视图报告**：`scripts/condition_report.py` 生成自带图表的 HTML 报告（时间线 + 症状统计 + 图表 + 用药 + 治疗方案 + 建议科室 + 体征参考范围），离线可打开。
17. **建议科室**：`scripts/departments.py` 按症状或成员近期症状推荐就诊科室。
18. **一键备份导出**：`scripts/export_data.py` 把全家数据打包成 zip（JSON + CSV + 图表），CSV 可用 Excel 直接打开。
19. **紧急红牌提示**：录入时若严重程度 ≥9 或命中 `references/red_flag_symptoms.json` 紧急症状，自动打印立即就医提醒。
20. **就诊意见与十大医院**：`scripts/hospital_advice.py` 按症状/成员推荐全国十大医院，结合患者所在城市给出最优与性价比就诊方案（含挂号渠道、费用预估、异地备案提醒）。
21. **联网资料客观摘要（多引擎交叉验证）**：`scripts/web_search.py` 默认用 DuckDuckGo / Bing / Mojeek / 维基百科 多引擎交叉验证，按网址去重统计来源数，官方/权威来源（`references/official_domains.json`）标记 [官方] 并优先，可用 `--official` 只看官方；`scripts/analyze.py --web` 在客观分析之外单独引用该摘要，明确标注来源与不确定性，分析结论不被网络信息带偏。
22. **难受程度客观评估（简单可选填）**：`scripts/severity_quiz.py` 默认快速版只问 3 个问题、全部可留空跳过；需要更细时用 `--full` 完整版（7 维，每项也可跳过）。`analyze.py --quiz`（快速）/ `--quiz-full`（完整）直接使用结果，减少主观偏差且不增加负担。
23. **报告单/体检单解读**：`scripts/lab_analyzer.py` 对化验单/体检单/CT/MRI 文字报告 OCR 或粘贴文本 → 结构化解析 → 异常 ↑/↓ 标记 → 危急值提醒 → 与上次对比 → 生成解读报告，并把血压/血糖/心率等写入体征档案（可画趋势）。CT/MRI 影像原图无法替代放射科医生判读。
24. **国际权威就诊路径**：`references/care_pathways.json` 依据 NHS / Mayo Clinic / CDC / WHO 公开指南整理 24 个症状的 5 档就诊路径（家庭观察/门诊/近期/尽快/急诊，含时间窗与升级条件）；`analyze.py` 输出【就诊路径】并引用来源，不再一刀切。

## 4. 操作步骤

### 步骤一：病情录入向导（推荐入口）

**在对话中直接按下面的顺序向用户提问**（也可引导用户自己运行 `python scripts/intake.py` 走一遍向导）：

1. **是否开启多家人档案**：首次使用时询问「是否开启多家人档案（多个家人分别建档）？」；用户同意则运行 `python scripts/intake.py --enable-multi`（配置保存在 `scripts/members_config.json`）。
2. **输入病情后添加到哪个档案**：开启多家人档案后，每次录入都询问「本次病情添加到哪个档案？」，给出已有档案列表（可运行 `python scripts/intake.py --list-members` 查看），允许选择已有档案、新建档案或使用默认档案。
3. **录入本次症状**：询问症状名称（可多个）、严重程度（1-10，按 `references/severity_scale.json` 的客观锚点询问；重度时追问对睡眠/工作/饮食的影响与趋势）、发病日期（可回填）、持续时长、备注。
4. **是否补充之前病情**：询问「是否需要补充之前（更早）的病情？」；需要时让用户补录既往症状并填真实发病日期（用 `--date` 回填）。
5. **追问情况**：根据 `references/followup_questions.json` 对每个症状追问 2-3 个相关问题（部位、诱因、伴随症状、缓解方式、检查用药等），答案写入记录的 `followup` 字段。
6. **保存记录**：运行 `python scripts/intake.py --symptom <症状> --severity <1-10> --member <档案>` 保存，或让用户运行 `python scripts/intake.py` 自助录入。
7. **给出可视化分析**：运行 `python scripts/charts.py --member <档案>`（或 `intake.py` 内置分析），输出症状频次 / 严重程度趋势图表 + 文本摘要。
8. **生成病情视图报告**：询问「是否生成病情视图报告（HTML）？」；需要则运行 `python scripts/condition_report.py --member <档案>`。

### 步骤二：初始评估与信息收集

1. 先询问核心症状，引导用户提供：**位置、起始时间、严重程度（1-10）、影响**。
2. 使用 `references/questionnaire.json` 做系统回顾；问卷包含 10 个症状类别（一般情况、头颈部、胸部、消化系统、泌尿系统、皮肤、肌肉骨骼、神经系统、生殖健康、其他补充），**每次最多询问 3 个类别**，根据回答动态调整后续问题。
3. 收集既往病史、家族史、用药情况、生活方式、近期环境变化等信息。
4. 如果用户隔了较久（如一周以上）才回来，先运行 `scripts/snapshot.py --all-members` 回顾间隔期要点（距上次记录天数、逾期复诊、进行中用药、症状统计），再开始本次评估。

### 步骤三：结构化记录

- 向用户说明会将本次评估保存为 `health_log.json`，并给出数据结构示例：

```json
{
  "date": "2026-08-21 10:30:00",
  "questionnaire_responses": {
    "头痛": true,
    "发热": false,
    "睡眠障碍": "入睡困难"
  },
  "vitals": {"血压": "120/80", "体温": "36.8"},
  "medical_history": {"既往病史": "高血压", "家族史": "无特殊"},
  "medications": ["苯磺酸氨氯地平 5mg 每日1次"],
  "lifestyle": {"睡眠": "6小时", "运动": "每周2次"},
  "uploaded_files": [],
  "notes": "工作压力大，近期加班较多"
}
```

- 提醒可用 `scripts/symptom_log.py` 或 `scripts/intake.py` 快速保存症状记录。

### 步骤四：图像/报告上传分析

- 如果用户上传的是**本地文件路径**，运行 `scripts/image_processor.py <图片路径>` 进行 OCR 文字提取。
- 如果用户在对话中直接上传图片，直接读取图片内容，不必运行脚本。
- **化验单/体检单/CT、MRI 文字报告**：优先运行 `scripts/lab_analyzer.py <图片路径> --member <档案>`（或 `--text "<粘贴文字>"`）做结构化解读：异常 ↑/↓、危急值提醒、历史对比、体征入档。
- **CT/MRI 影像原图**：可以读取/描述图片、提取报告单文字，但**影像诊断必须由放射科医生完成**，提醒用户带原片就诊，本技能不替代影像判读。
- 解读化验单/体检报告时注意：参考范围、异常指标及单位；解读症状照片时描述可见特征，并提醒照片不能替代医生面诊。

### 步骤五：调用外部医学知识库 API 与联网搜索

- 运行 `scripts/medical_api.py <症状或疾病名>` 查询医学知识库；配置文件为 `references/api_config.json`（不存在时使用默认配置，也可复制 `references/api_config.example.json` 修改）。
- 数据源按顺序回退：**维基百科中文词条**（zh.wikipedia.org，默认，无需密钥）→ **disease.sh**（https://disease.sh/v3/covid/diseases，无需密钥）→ 内置 `references/symptom_disease_map.json` + 模型自身知识；可在配置中把 `disease_api.provider` 改为 `disease_sh` 切换首选源，或用 `--provider` 临时指定。
- 需要更广的联网信息时（最新指南、医院科室、疾病百科补充），运行 `scripts/web_search.py <查询词>`：默认多引擎（DuckDuckGo / Bing / Mojeek / 维基百科）交叉验证，官方来源优先；加 `--official` 只看官方；可在 `references/api_config.json` 的 `search` 段调整引擎顺序，或用 `--engine bing` 临时指定单引擎。

### 步骤六：长期趋势分析与可视化

- 如果已有 ≥2 条记录，运行 `scripts/trend_analysis.py`，分析症状出现频率、严重程度变化、关键指标趋势。
- 输出示例：「过去一个月，头痛出现 6 次，平均严重程度从 5 升到 7，呈加重趋势。」
- 需要直观图表时运行 `scripts/charts.py`（症状频次 / 严重程度趋势 / 体征趋势）和 `scripts/calendar_heatmap.py`（按月热力图），均支持 `--member`；图表依赖 matplotlib（`pip install matplotlib`）。

### 步骤七：用药管理

- 调用 `scripts/medication_tracker.py add --name <药物> --dosage <剂量> --frequency <频次> --start <日期> --end <日期>` 记录药物。
- 检查药物相互作用，如多种 NSAIDs 同时使用风险；发现风险时提醒用户咨询医生或药师。

### 步骤八：治疗方案跟踪

- 如果用户有医生诊断，调用 `scripts/treatment_plan.py add --diagnosis <诊断> --advice <建议> --follow-up <复诊时间> --status <状态>` 保存诊断、建议、复诊时间。
- 跟踪执行状态：已执行 / 进行中 / 未开始；复诊前提醒用户更新状态。
- 运行 `scripts/reminders.py` 检查近期复诊与停药提醒（`--days` 提前天数，`--member` 指定成员，`--all-members` 扫全家）。

### 步骤九：综合分析与报告

- 汇总所有信息前，先用 `scripts/analyze.py` 做结构化分析（支持 `--quiz` 快速客观评估（3 题可选填）、`--quiz-full` 完整评估、`--severity` 严重程度、`--member` 结合历史、`--duration 3天/2周/1个月` 与 `--trend 好转/平稳/加重/快速恶化` 做**病程判断**、`--web` 联网资料；评估全部可选填，未填强度时不影响分析继续）：
- 生成包含以下部分的分析报告：

1. 症状总结
2. 可能原因
3. 异常指标
4. 紧急程度（含就医建议）
5. 建议下一步
6. 疾病百科（可选，来自 API 或内置知识库）
7. 免责声明
8. 联网资料摘要（可选，单独成段，标注来源与不确定性，不参与结论）

> 风险分级为**保守筛查**：只提醒就医时机，不构成诊断。只有真紧急症状（呼吸困难/意识模糊/严重出血等）、严重程度 ≥9 或明确恶化趋势才判「紧急」；普通胸痛/腹痛/头痛等列入「警惕」档，仅建议尽快就诊或观察，并附安抚性说明，避免过度恐慌。
> **长期客观校准**：分析会结合病程（`--duration`）、趋势（`--trend`）与历史记录判断「新发 / 慢性稳定 / 反复发作 / 加重中 / 好转中」——慢性稳定自动降一级（不吓人），明确加重才升级，真紧急永不降级。
> **符合一般人**：轻度（1-3 分）且无危险信号 → 家庭观察自愈；轻中度但已超过国际指南建议就诊时长（如腹泻>2天、咳嗽>3周、便秘>3周、乏力>2周，见 `care_pathways.json` 的 appointment_after_days）→ 升级为门诊；4-6 分 → 近期门诊；7-8 分或加重 → 尽快；只有真急症/≥9 分才急诊。

### 步骤十：个性化健康建议

- 调用 `scripts/health_advice.py`，覆盖**饮食、运动、睡眠、压力管理、戒烟限酒**。
- 强调建议具体、可执行，且为**非医疗级**指导。

### 步骤十一：生成医生沟通报告

- 调用 `scripts/report_generator.py`，生成 Markdown 格式报告并保存为 `health_report.md`。
- 报告包含：**脱敏信息（不含身份证、手机号等完整个人信息）、主诉、症状时间线、检查摘要、用药清单、待咨询问题**。

### 步骤十二：生成病情视图报告

- 调用 `scripts/condition_report.py --member <档案>`，生成自带图表的 HTML 报告并保存为 `condition_report.html`（成员目录下）。
- 报告包含：**统计卡片（记录数/症状种类/进行中用药/待复诊）、症状统计表、症状时间线、可视化图表（PNG 以 base64 内嵌）、体征记录 + 常见参考范围、用药清单、治疗方案、建议科室、待咨询问题、免责声明**。
- 支持 `--days 90` 只统计最近 90 天，`--no-charts` 不嵌入图表，`--note "建议检查血常规"` 追加备注；文件离线可打开。
- 就诊前可先运行 `scripts/departments.py --member <档案>` 看建议科室；需要医院推荐与就诊方案时运行 `scripts/hospital_advice.py --member <档案> --city <城市>`。

### 步骤十三：一键备份 / 导出数据

- 定期运行 `scripts/export_data.py --all-members` 备份全家数据，输出到 `scripts/backups/health-backup-<时间戳>.zip`。
- zip 内含：`members_config.json`、每个成员的 JSON 原始数据、`health_log.csv / medications.csv / treatment_plans.csv / vitals.csv`（Excel 可直接打开）、健康报告与全部图表 PNG。
- 备份含个人健康信息，请妥善保管；也可用 `--output D:\backup\xxx.zip` 指定位置。

### 步骤十四：就诊意见与全国十大医院推荐

- 当用户询问「去哪家医院 / 挂什么科 / 就诊方案」时，先询问**患者所在城市**（和省份），然后运行 `scripts/hospital_advice.py --member <档案> --city <城市> --province <省份>`（或 `--symptoms 头痛` / `--department 神经内科`）。
- 脚本会：按症状/科室匹配 `references/hospitals.json`（25 个科室 × 全国十大医院）→ 按同城 / 同省 / 全国三档排序 → 给出**性价比方案**（就近三甲普通门诊 + 基础检查）与**最优方案**（全国十大医院专家门诊，跨省提示异地就医备案）。
- 命中紧急症状时先提示就近急诊，不推荐跨城转诊。
- 医院信息整理自公开资料，仅供挂号参考；提醒用户以医院官方渠道为准。

## 5. 脚本与数据文件说明

| 脚本 | 功能 |
|------|------|
| intake.py | 病情录入向导：多档案开关 → 选档案 → 录入 → 补充既往 → 追问 → 可视化 → 视图报告 |
| symptom_log.py | 保存症状记录到本地 JSON |
| questionnaire.py | 读取问卷定义，引导提问 |
| image_processor.py | 图片 OCR 文字提取 |
| analyze.py | 病情分析：风险分级 / 组合打分 / 同义词匹配 / 历史结合 / --web 联网客观摘要 |
| medical_api.py | 调用外部医学 API |
| trend_analysis.py | 症状趋势与指标变化分析 |
| medication_tracker.py | 用药记录与管理 |
| treatment_plan.py | 治疗方案保存与跟踪 |
| health_advice.py | 个性化健康建议生成 |
| report_generator.py | 医生沟通报告生成（Markdown） |
| condition_report.py | 病情视图报告生成（HTML，自带图表） |
| web_search.py | 联网搜索（DuckDuckGo / 维基百科） |
| charts.py | 健康图表可视化（PNG，需 matplotlib） |
| calendar_heatmap.py | 日历热力图（PNG，需 matplotlib） |
| reminders.py | 复诊 / 停药提醒 |
| snapshot.py | 间隔期总览（低频使用快照） |
| common.py | 多家人档案路径 + 配置（members_config.json + profile.json） |
| departments.py | 建议就诊科室查询（按症状 / 按成员） |
| export_data.py | 全家数据备份导出（zip + CSV） |
| hospital_advice.py | 就诊意见与全国十大医院推荐（结合患者位置） |
| severity_quiz.py | 难受程度客观评估（多维加权，供 analyze --quiz 使用） |
| lab_analyzer.py | 报告单/体检单/化验单解读（OCR/文本 + 异常标记 + 对比） |
| self_test.py | 回归测试（100 组正常人 + 16 组边界，改算法后必跑） |

| 数据文件 | 说明 |
|----------|------|
| health_log.json | 症状记录（含 followup 追问字段） |
| medications.json | 用药记录 |
| treatment_plans.json | 治疗方案 |
| vitals.json | 体征记录 |
| members_config.json | 多家人档案开关与成员名单 |
| profile.json | 成员基础信息（可选：性别/出生年/过敏史/基础病） |
| department_map.json | 症状 → 建议科室映射 |
| red_flag_symptoms.json | 紧急症状清单（红牌提示用） |
| vitals_ranges.json | 常见体征参考范围 |
| hospitals.json | 全国十大医院知识库（25 个科室） |
| disease_risk.json | 疾病风险分级（紧急/中危 → 建议行动） |
| official_domains.json | 官方/权威来源域名库（搜索优先标记用） |
| lab_reference.json | 常用检验/体检项目参考范围与危急值 |
| lab_reports/ | 报告单解读存档（JSON + lab_report.md） |
| care_pathways.json | 国际权威就诊路径（NHS/Mayo/CDC/WHO，24 症状 × 5 档 + default 兜底） |
| tests/ | 回归测试数据（normal_cases_100.json + edge_cases.json） |
| severity_scale.json | 难受程度 1-10 客观锚点与评估维度/权重 |
| severity_history.json | 成员历次客观评估记录（members/<名字>/ 下） |
| backups/ | 一键备份导出的 zip 目录 |
| health_report.md | 医生沟通报告 |
| condition_report.html | 病情视图报告 |
| members/<成员名>/ | 多家人档案目录（每人的全部数据与图表） |

## 6. 隐私与安全

- 所有数据保存在**用户本地**（`health_log.json`、`medications.json`、`treatment_plans.json`、`members_config.json`）。
- 避免上传完整个人身份信息（姓名、身份证号、手机号等）。
- 生成医生沟通报告前进行**脱敏处理**。

## 7. 示例对话

**用户**：我最近头痛得厉害，帮我看看，妈妈也是，总说头晕。我还拍了照片传给你。（上传头部照片）

**Claude**：

1. 先问：「需要给妈妈也建档吗？是否开启多家人档案？」用户同意后运行 `python scripts/intake.py --enable-multi`。
2. 按病情录入向导提问：本次是给谁记录？症状名称？严重程度（1-10）？发病日期？持续多久？是否需要补充之前更早的病情？
3. 用 `references/followup_questions.json` 追问：头痛在哪个部位？搏动性还是胀痛？有没有恶心怕光？（妈妈的头晕）是昏沉感还是天旋地转？站起来明显吗？
4. 运行 `python scripts/intake.py --symptom 头痛 --severity 6 --member 我` 保存本人记录；再运行 `python scripts/intake.py --symptom 头晕 --severity 4 --member 妈妈` 保存妈妈记录。
5. 运行 `python scripts/charts.py --member 妈妈` 给出可视化分析（频次 / 趋势 / 热力图）。
6. 运行 `python scripts/condition_report.py --member 妈妈` 生成病情视图报告（HTML）。
7. 运行 `python scripts/analyze.py 头痛`、`python scripts/medical_api.py 头晕`、`python scripts/web_search.py 头晕 原因` 查询知识。
8. 运行 `python scripts/health_advice.py 头痛` 生成个性化建议。
9. 就诊前运行 `python scripts/report_generator.py --member 妈妈` 生成医生沟通报告，附免责声明，并确认无紧急症状。

**输出摘要**：本人头痛已出现 6 次，平均严重程度从 5 升到 7，呈加重趋势；妈妈头晕 3 次，均为体位性，建议先量血压。两份病情视图报告与医生沟通报告已生成，供就诊时使用。以上内容仅供参考，不能替代专业医疗诊断。

## 8. 多家人档案与提醒

- 开关：`python scripts/intake.py --enable-multi` 开启，`--disable-multi` 关闭，`--list-members` 查看档案；配置保存在 `scripts/members_config.json`。
- 未指定成员时，数据保存在 `scripts/` 目录（兼容单用户）；指定 `--member 妈妈` 时保存在 `scripts/members/妈妈/` 目录（health_log.json、medications.json、treatment_plans.json、vitals.json、profile.json、图表 PNG、condition_report.html 均按成员隔离）。
- 成员基础信息（可选）：可手动在 `members/<名字>/profile.json` 里记性别、出生年、过敏史、基础病，病情视图报告会读取展示。
- 支持成员档案的脚本：intake.py、symptom_log.py、trend_analysis.py、medication_tracker.py、treatment_plan.py、report_generator.py、condition_report.py、charts.py、calendar_heatmap.py、reminders.py。
- 示例：
  - `python scripts/intake.py --symptom 头痛 --severity 6 --member 妈妈`
  - `python scripts/charts.py --member 爸爸`
  - `python scripts/condition_report.py --member 妈妈`
  - `python scripts/reminders.py --all-members`

## 9. 低频使用模式（不用每天用）

- 本技能**不要求每天记录**。隔几周或有病情时回来即可，回来时：
  1. 先运行 `python scripts/snapshot.py --all-members` 快速回顾：距上次记录天数、逾期复诊、进行中用药、症状统计、待办。
  2. 再走一遍**病情录入向导**（`python scripts/intake.py`）：录入新症状 → 补充既往病情 → 追问 → 选档案 → 可视化分析 → 病情视图报告。
  3. 就诊前运行 `python scripts/report_generator.py --member <名字>` 生成医生沟通报告，并可用 `python scripts/departments.py --member <名字>` 查看建议科室。
  4. 隔一段时间运行 `python scripts/export_data.py --all-members` 备份全家数据到 `scripts/backups/`。
  5. 需要看病时运行 `python scripts/hospital_advice.py --member <名字> --city <城市>`，获得就诊意见与医院推荐。
- 复诊 / 停药提醒**无需每天运行**：只要回来时跑 `reminders.py --all-members`，逾期项目会以「已逾期 X 天」显示，不会因为隔几周没看而丢失。
- 建议：给每个成员建档案（`--member`），回来后先看快照再决定补录什么。

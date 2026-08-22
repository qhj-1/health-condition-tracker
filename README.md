# Health Condition Tracker

长期全面记录身体症状、生活习惯、用药和治疗方案，分析潜在疾病风险，生成个性化健康建议、医生沟通报告和病情视图报告。

## 功能

1. 病情录入向导（开启多家人档案 → 录入症状 → 补充既往病情 → 追问情况 → 选择档案 → 可视化分析 → 病情视图报告）
2. 症状收集
3. 报告分析（化验单 / 体检报告 / 症状照片 OCR）
4. 知识库查询 + 联网搜索（多引擎交叉验证：DuckDuckGo / Bing / Mojeek / 维基百科，官方来源优先，免密钥）
5. 记录追踪
6. 用药管理
7. 治疗方案
8. 个性化建议
9. 医生报告（Markdown）
10. 风险预警
11. 多家人档案（`--member` 分目录管理；`intake.py --enable-multi` 开启开关）
12. 图表可视化（症状频次 / 严重程度 / 体征趋势 PNG）
13. 日历热力图（按月症状热图）
14. 复诊 / 停药提醒（支持全家）
15. 间隔期总览（低频使用：隔几周回来一条命令接上）
16. 病情视图报告（HTML，时间线 + 统计 + 内嵌图表 + 建议科室 + 体征参考范围，离线可打开）
17. 建议科室查询（按症状 / 按成员近期症状）
18. 一键备份导出（全家数据打包 zip：JSON + CSV + 图表）
19. 紧急红牌提示（严重程度 ≥9 或命中紧急症状时自动提醒立即就医）
20. 就诊意见与全国十大医院推荐（结合患者位置给最优/性价比就诊方案）
21. 联网资料客观摘要（分析结论不受网络信息影响，来源单独标注）
22. 难受程度客观评估（快速版 3 题可选填；完整版 --full 每项可选填；analyze --quiz / --quiz-full 直接使用）
23. 报告单/体检单解读（OCR/文本 → 异常标记 → 危急值提醒 → 历史对比 → 体征入档）
24. 国际权威就诊路径（NHS/Mayo/CDC/WHO，症状分档 + 时间窗 + 升级条件，不搞一刀切）

## 使用说明

1. **长期放在 D 盘（推荐）**：默认安装到 `D:\codex-skills\health-condition-tracker`，脚本均按自身目录定位数据文件，放在任意位置都可运行。两种方式：
   - 一键安装（最简单）：在技能包根目录**双击 `install-to-D.bat`**，或用 PowerShell 运行 `.\install.ps1 -LinkToCodexSkills`，会自动复制到 D 盘，并在 `C:\Users\Q\.codex\skills\health-condition-tracker` 创建目录联接（junction），让 Codex 自动加载该技能（文件仍保存在 D 盘）。
   - 手动复制：`Copy-Item -Recurse -Force "<本包路径>" "D:\codex-skills\health-condition-tracker"`；如需 Codex 自动加载，再执行 `New-Item -ItemType Junction -Path "$HOME\.codex\skills\health-condition-tracker" -Target "D:\codex-skills\health-condition-tracker"`。
2. 若用于 Claude Code：将包复制到 `~/.claude/skills/health-condition-tracker` 即可自动加载。
3. 在对话中描述身体不适、上传化验单/体检报告/症状照片，或要求管理用药、就诊前整理病情时，技能会自动触发。
4. **病情录入向导（推荐）**：在对话里让 Codex 按顺序问：是否开启多家人档案 → 症状 → 是否补充之前病情 → 追问情况 → 添加到哪个档案 → 可视化分析 → 是否生成病情视图报告；也可以自己在终端运行 `python scripts/intake.py` 走一遍。
5. **低频使用**：不用每天记录。隔几周或有病情时回来，先运行 `python scripts/snapshot.py --all-members` 快速回顾，再走病情录入向导补录（可 `--date` 回填发病日期）或上传报告。
6. **指令选择器（可选）**：双击 `docs/指令选择器.html` 可在浏览器里分类选择并一键复制指令（含定时任务模板与常用命令）；`docs/` 下另有「每月快照 / 每周快照 / 就诊前报告 / 病情录入向导」等纯文本模板，复制到 Codex「自动化 / Automations」即可创建定时任务。
7. 常用脚本：

   - `python scripts/intake.py`：病情录入向导（交互）
   - `python scripts/intake.py --enable-multi`：开启多家人档案
   - `python scripts/intake.py --list-members`：查看已有档案
   - `python scripts/intake.py --symptom 头痛 --severity 6 --member 妈妈`：快速录入
   - `python scripts/condition_report.py --member 妈妈`：生成病情视图报告（HTML）
   - `python scripts/symptom_log.py`：交互式保存症状记录
   - `python scripts/questionnaire.py`：查看系统回顾问卷结构
   - `python scripts/analyze.py 头痛 发热`：基于症状-疾病映射辅助分析
   - `python scripts/medical_api.py 头痛`：查询维基百科中文词条（失败自动回退 disease.sh）
   - `python scripts/web_search.py 偏头痛 治疗`：多引擎交叉验证搜索（官方优先）
   - `python scripts/web_search.py 偏头痛 治疗 --official`：只看官方/权威来源
   - `python scripts/trend_analysis.py`：查看长期趋势
   - `python scripts/medication_tracker.py list`：查看用药记录
   - `python scripts/treatment_plan.py list`：查看治疗方案
   - `python scripts/health_advice.py 头痛`：生成个性化健康建议
   - `python scripts/report_generator.py`：生成医生沟通报告
   - `python scripts/charts.py --member 妈妈`：健康图表（需 `pip install matplotlib`）
   - `python scripts/calendar_heatmap.py --member 妈妈`：日历热力图
   - `python scripts/reminders.py --all-members`：复诊 / 停药提醒
   - `python scripts/departments.py --member 妈妈`：建议就诊科室
   - `python scripts/export_data.py --all-members`：全家数据备份导出（zip + CSV）
   - `python scripts/hospital_advice.py --member 妈妈 --city 杭州`：就诊意见 + 全国十大医院推荐（结合位置）
   - `python scripts/lab_analyzer.py "报告单.jpg" --member 妈妈 --compare`：报告单/体检单解读（OCR + 异常标记 + 对比）
   - `python scripts/analyze.py 头痛 --severity 5 --duration 2周 --trend 平稳`：病情分析（含病程判断，慢性稳定自动降级）
   - `python scripts/self_test.py`：回归测试（100 组正常人 + 16 组边界；`--only edge` 只看边界，`--show` 看失败详情）
   - `python scripts/analyze.py 头痛 发热 --severity 7 --web`：病情分析（风险分级 + 联网客观摘要）
   - `python scripts/severity_quiz.py --member 妈妈`：难受程度客观评估（快速版，3 题可选填）
   - `python scripts/severity_quiz.py --member 妈妈 --full`：完整版（7 维，每项可选填）
   - `python scripts/analyze.py 头痛 --quiz --web`：快速客观评估 + 分析 + 联网摘要
   - `python scripts/analyze.py 头痛 --quiz-full`：完整客观评估 + 分析
   - `python scripts/snapshot.py --all-members`：间隔期总览（低频使用）

## 病情录入向导流程

```text
1. 是否开启多家人档案？（首次询问，配置保存在 scripts/members_config.json）
2. 录入本次症状：症状名称（可多个）、严重程度（1-10）、发病日期、持续时长、备注
3. 是否补充之前（更早）的病情？（可回填真实发病日期）
4. 追问情况：按 references/followup_questions.json 追问 2-3 个问题
5. 本次病情添加到哪个档案？（已有档案 / 新建 / 默认）
6. 保存记录到 health_log.json
7. 可视化分析：图表 PNG + 文本摘要
8. 是否生成病情视图报告（HTML）？
```

## 数据文件

- `health_log.json`：症状记录（含 followup 追问字段）
- `medications.json`：用药记录
- `treatment_plans.json`：治疗方案
- `members_config.json`：多家人档案开关与成员名单
- `health_report.md`：生成的医生沟通报告
- `condition_report.html`：生成的病情视图报告
- `members/<成员名>/`：多家人档案目录（每人的 health_log / medications / treatment_plans / vitals / profile / 图表 / 视图报告）
- `references/department_map.json`：症状 → 建议科室
- `references/red_flag_symptoms.json`：紧急症状清单
- `references/vitals_ranges.json`：常见体征参考范围
- `scripts/backups/`：一键备份导出的 zip
- `references/hospitals.json`：全国十大医院知识库（25 个科室）
- `references/disease_risk.json`：疾病风险分级（紧急/中危）
- `references/severity_scale.json`：难受程度 1-10 客观锚点与评估维度
- `references/official_domains.json`：官方/权威来源域名库
- `references/lab_reference.json`：常用检验/体检项目参考范围与危急值
- `references/care_pathways.json`：国际权威就诊路径（NHS/Mayo/CDC/WHO）

## 依赖（可选）

- `image_processor.py` 需要：`pip install pillow pytesseract`，并安装 Tesseract OCR（含 chi_sim 简体中文语言包）。
- `medical_api.py` / `web_search.py` 仅用标准库 urllib 调用维基百科中文 / disease.sh / DuckDuckGo 公共接口，**免密钥、免额外依赖**，需联网；可复制 `references/api_config.example.json` 为 `api_config.json` 调整数据源与搜索配置。
- `charts.py` / `calendar_heatmap.py` / `condition_report.py`（嵌入图表）需要：`pip install matplotlib`（可选）。
- 其余脚本仅使用 Python 标准库，无需额外依赖。

## 免责声明

本工具提供的所有内容仅供参考，不能替代专业医疗诊断、治疗或处方。如出现剧烈疼痛、呼吸困难、胸痛、意识模糊、严重出血等紧急症状，请立即就医。

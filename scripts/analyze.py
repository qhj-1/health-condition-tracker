# -*- coding: utf-8 -*-
"""病情分析工具（优化版）：风险分级 + 症状组合分析 + 同义词匹配 + 历史结合 +
联网资料摘要（与客观分析分离）。

用法：
    python analyze.py 头痛 发热                  # 基础分析
    python analyze.py 头痛 --severity 7          # 带严重程度（影响风险分级）
    python analyze.py --member 妈妈              # 结合成员历史记录
    python analyze.py 头痛 发热 --web            # 追加联网资料摘要
    python analyze.py 头痛 --top 8               # 每个分级最多列出 N 个疾病
    python analyze.py 头痛 --json                # 输出 JSON 结构

设计原则：
- 分析结论只基于本地知识库（symptom_disease_map.json / disease_risk.json）与
  用户描述，绝不因联网搜索内容而改变判断（防止被网络信息带偏）。
- 联网搜索仅作为「资料补充」单独呈现，并标注来源与不确定性。
"""
import argparse
import functools
import json
import os
import sys

import common
from trend_analysis import extract_symptoms

REFERENCES_DIR = os.path.normpath(os.path.join(common.SCRIPT_DIR, "..", "references"))
MAP_FILE = os.path.join(REFERENCES_DIR, "symptom_disease_map.json")
RED_FLAG_FILE = os.path.join(REFERENCES_DIR, "red_flag_symptoms.json")
RISK_FILE = os.path.join(REFERENCES_DIR, "disease_risk.json")
CARE_FILE = os.path.join(REFERENCES_DIR, "care_pathways.json")
DEPARTMENT_FILE = os.path.join(REFERENCES_DIR, "department_map.json")

# 常用口语 → 知识库标准症状（第 2 轮优化：同义词匹配）
ALIAS = {
    "拉肚子": "腹泻", "拉稀": "腹泻", "拉不出": "便秘", "便不出来": "便秘",
    "睡不着": "失眠", "睡不着觉": "失眠", "头昏": "头晕", "没力气": "乏力",
    "浑身无力": "乏力", "嗓子疼": "咽喉痛", "喉咙痛": "咽喉痛",
    "心口痛": "胸痛", "胸口痛": "胸痛", "胃痛": "腹痛", "肚子疼": "腹痛",
    "肚子痛": "腹痛", "胃胀气": "腹胀", "嗳气": "打嗝", "抽筋": "腿抽筋",
    "发冷": "怕冷", "出虚汗": "出汗过多", "口干舌燥": "口渴", "眼睛干": "眼干",
    "尿不出来": "排尿困难", "尿血": "血尿", "大便带血": "便血",
    "月经不来": "闭经", "月经量太大": "月经量多", "心闷": "胸闷",
    "喘不上气": "呼吸困难", "上不来气": "呼吸困难", "晕倒": "晕厥",
    "嘴歪": "口角歪斜", "说话不清": "言语不清", "手麻": "麻木", "脚麻": "麻木",
    "腿麻": "麻木", "心发慌": "心慌", "睡不好": "失眠",
    "发烧": "发热", "低烧": "发热", "高烧": "发热", "头疼": "头痛", "胃疼": "腹痛",
    "反胃": "恶心", "想吐": "恶心", "没胃口": "食欲不振", "吃不下饭": "食欲不振",
    "腰疼": "腰痛", "脖子疼": "颈痛", "脖子痛": "颈痛", "肩膀疼": "肩痛", "肩膀痛": "肩痛",
    "膝盖疼": "膝盖痛", "关节疼": "关节痛", "脚后跟疼": "足跟痛", "背疼": "背痛",
    "喘不过气": "呼吸困难", "憋气": "胸闷", "心口闷": "胸闷", "心跳快": "心悸",
    "身上没劲": "乏力", "没精神": "乏力", "出冷汗": "出汗过多", "夜间出汗": "盗汗",
    "月经不准": "月经不调", "月经推迟": "月经不调", "头晕眼花": "头晕", "头昏眼花": "头晕",
    "鼻子堵": "鼻塞", "鼻涕多": "流鼻涕", "眼干涩": "眼干", "喷嚏": "打喷嚏",
    "口气重": "口臭", "牙肉肿": "牙龈肿痛", "掉头发": "脱发", "皮肤痒": "皮肤瘙痒", "浑身痒": "皮肤瘙痒",
    "起疹子": "皮疹", "发麻": "麻木", "肚子胀": "腹胀", "胀气": "腹胀", "大便干": "便秘",
}


@functools.lru_cache(maxsize=16)
def _load_cached(filename):
    """读取 references 下 JSON 并缓存（同一进程内多次分析只读一次文件）。"""
    path = os.path.join(REFERENCES_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _load_json(filename, default):
    data = _load_cached(filename)
    return data if data is not None else default


def load_map():
    """读取症状→疾病映射。"""
    return _load_json("symptom_disease_map.json", {})


def load_red_flags():
    """读取紧急症状清单。"""
    data = _load_json("red_flag_symptoms.json", {})
    return data.get("紧急症状", []) if isinstance(data, dict) else []


def load_care():
    """读取国际权威就诊路径库（NHS / Mayo / CDC / WHO）。"""
    data = _load_json("care_pathways.json", {})
    return data if isinstance(data, dict) else {}


def load_risk():
    """读取疾病风险分级 {紧急: {...}, 中危: {...}}。"""
    data = _load_json("disease_risk.json", {})
    return data if isinstance(data, dict) else {}


def normalize_symptoms(raw_list):
    """标准化症状：去空白、去重、口语映射为知识库名称。"""
    out = []
    for s in raw_list or []:
        s = str(s).strip()
        if not s:
            continue
        s = ALIAS.get(s, s)
        if s not in out:
            out.append(s)
    return out


def load_history(member, days=0):
    """读取成员历史症状统计，返回 {"counts": 总次数, "recent7": 近7天次数}。"""
    empty = {"counts": {}, "recent7": {}}
    if not member:
        return empty
    records = []
    path = common.path_for("health_log.json", member)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            records = data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            records = []
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=days) if days else None
    seven_ago = date.today() - timedelta(days=7)
    counts = {}
    recent7 = {}
    for rec in records:
        d = common.parse_date(rec.get("date"))
        if cutoff and (not d or d < cutoff):
            continue
        for name, _ in extract_symptoms(rec):
            counts[name] = counts.get(name, 0) + 1
            if d is not None and d >= seven_ago:
                recent7[name] = recent7.get(name, 0) + 1
    return {"counts": counts, "recent7": recent7}


def disease_specificity(disease, map_data):
    """疾病特异度：出现在越少症状里的疾病越特异。返回 0-1。"""
    total = sum(1 for diseases in map_data.values() if disease in diseases)
    return 1.0 / (1 + total)


def parse_duration(value):
    """把病程文本解析为天数：'3天/3日/2周/1个月/半年/90' 等；失败返回 None。"""
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    units = [
        ("年", 365), ("岁", 365), ("月", 30), ("周", 7), ("星期", 7), ("天", 1), ("日", 1), ("d", 1),
    ]
    for u, days in units:
        if u in s:
            m = re.search(r"(\d+(?:\.\d+)?)", s)
            if m:
                return int(float(m.group(1)) * days)
    try:
        return int(float(s))
    except ValueError:
        return None


def detect_course(symptoms, counts, recent7, duration_days=None, trend=""):
    """客观判断病程：新发 / 亚急性 / 慢性 / 反复发作 / 加重中 / 好转中。"""
    total = sum(counts.get(s, 0) for s in symptoms) if symptoms else sum(counts.values())
    r7 = sum(recent7.get(s, 0) for s in symptoms) if symptoms else sum(recent7.values())
    if trend in ("快速恶化", "明显加重", "加重"):
        kind = "加重中"
    elif trend == "好转":
        kind = "好转中"
    elif duration_days is not None:
        if duration_days <= 14:
            kind = "新发（≤2周）"
        elif duration_days <= 30:
            kind = "亚急性（2周-1个月）"
        else:
            kind = "慢性（>1个月）"
    elif total >= 3 and r7 > 0:
        kind = "反复发作"
    elif total == 0:
        kind = "新发（首次记录）"
    else:
        kind = "情况待补充（可提供病程时长）"
    # 客观加重判断：近期发作占比高 或 明确恶化
    worsening = trend in ("快速恶化", "明显加重", "加重") or (total >= 2 and r7 >= 1 and r7 / total >= 0.5)
    stable = kind.startswith("慢性") and not worsening
    return {"kind": kind, "days": duration_days, "worsening": worsening, "stable": stable}


def analyze(symptoms, member=None, days=0, severity=None, quiz=None, duration_days=None, trend=""):
    """核心分析（组合打分 + 历史加权 + 客观病程校准）。

    返回 dict：{symptoms, history, recent7, course, tiers, departments, risk, quiz}
    """
    map_data = load_map()
    history_data = load_history(member, days)
    history = history_data.get("counts", {})
    recent7 = history_data.get("recent7", {})
    all_syms = normalize_symptoms(symptoms)
    hist_syms = normalize_symptoms(list(history.keys()))

    disease_matches = {}
    for sym in all_syms:
        for d in map_data.get(sym, []):
            disease_matches.setdefault(d, set()).add(sym)
    for sym in hist_syms:
        if sym in all_syms:
            continue
        for d in map_data.get(sym, []):
            disease_matches.setdefault(d, set()).add(sym)

    red_flags = load_red_flags()
    scored = []
    for d, matched in disease_matches.items():
        matched_input = matched & set(all_syms)
        matched_hist = matched - matched_input
        spec = disease_specificity(d, map_data)
        score = len(matched_input) * 100 + len(matched_hist) * 20 + spec * 10
        # 红牌症状风险加权：命中紧急症状的疾病排名上升，避免漏掉急症
        if any(s in red_flags for s in matched_input):
            score += 30
        confidence = "高"
        if len(matched_input) == 1:
            confidence = "中" if spec >= 0.2 else "低"
        elif len(matched_input) == 0:
            confidence = "低"
        scored.append({"disease": d, "score": score, "input": sorted(matched_input),
                       "history": sorted(matched_hist), "specificity": round(spec, 3),
                       "confidence": confidence})
    scored.sort(key=lambda x: (-x["score"], -x["specificity"]))

    tiers = {"高度相关": [], "可能相关": [], "需注意（仅历史）": []}
    for item in scored:
        if len(item["input"]) >= 2:
            tiers["高度相关"].append(item)
        elif len(item["input"]) == 1:
            tiers["可能相关"].append(item)
        else:
            tiers["需注意（仅历史）"].append(item)

    departments = {}
    dept_map = _load_json("department_map.json", {})
    for sym in all_syms:
        for d in dept_map.get(sym, []):
            departments[d] = departments.get(d, 0) + 1

    course = detect_course(all_syms, history, recent7, duration_days=duration_days, trend=trend)
    # 国际指南时长阈值：症状持续时间超过建议就诊时长 → 提示安排门诊
    overdue = []
    if duration_days:
        care_map = load_care().get("symptoms", {})
        for sym in all_syms:
            thr = care_map.get(sym, {}).get("appointment_after_days")
            if thr and duration_days >= thr and trend != "好转":
                overdue.append(sym)
    risk = assess_risk(all_syms, scored, severity=severity, quiz=quiz, course=course, overdue=overdue)
    return {
        "symptoms": all_syms,
        "history": history,
        "recent7": recent7,
        "course": course,
        "tiers": tiers,
        "departments": departments,
        "risk": risk,
        "quiz": quiz,
        "overdue": overdue,
    }


def assess_risk(symptoms, scored, severity=None, quiz=None, course=None, overdue=None):
    """风险分级（保守筛查，不吓人）。

    规则：
    - 「紧急症状」或严重程度≥9 → 紧急（立即就医）
    - 「警惕症状」/急症相关疾病：结合严重程度(≥7)、症状数量(≥2)、恶化趋势 → 中危/尽快；否则仅提示排查
    - 其余 → 低，建议观察
    """
    data = _load_json("red_flag_symptoms.json", {})
    urgent_flags = data.get("紧急症状", []) if isinstance(data, dict) else []
    watch_flags = data.get("警惕症状", []) if isinstance(data, dict) else []
    risk = load_risk()
    emergency_map = risk.get("紧急", {}) if isinstance(risk, dict) else {}
    mid_map = risk.get("中危", {}) if isinstance(risk, dict) else {}

    sev = None
    if severity is not None:
        try:
            sev = int(severity)
        except (TypeError, ValueError):
            sev = None

    def _hit(disease, risk_map):
        for k in risk_map:
            if k == disease or k in disease or disease in k:
                return k
        return None

    reasons = []
    urgent_hits = []
    watch_hits = []

    # 1) 症状档位
    for s in symptoms:
        if s in urgent_flags:
            urgent_hits.append(s)
            reasons.append("症状「{}」属于需要立即评估的情况".format(s))
        elif s in watch_flags:
            watch_hits.append(s)
            reasons.append("症状「{}」需结合程度判断".format(s))

    # 2) 疾病风险（急症相关疾病需要上下文才升级，避免普通腹痛/胸痛被吓到）
    for item in scored:
        d = item["disease"]
        k = _hit(d, emergency_map)
        if k:
            if (len(item["input"]) >= 2 and sev is not None and sev >= 6) or (sev is not None and sev >= 8) or any(s in urgent_flags for s in item["input"]):
                urgent_hits.append(k)
                reasons.append("「{}」与急症疾病相关，且符合就医指征".format(k))
            else:
                watch_hits.append(k)
                reasons.append("「{}」需排查（急症相关，但暂不构成紧急）".format(k))
        else:
            k2 = _hit(d, mid_map)
            if k2:
                watch_hits.append(k2)
                reasons.append("「{}」需排查".format(k2))

    # 3) 严重程度
    if sev is not None:
        if sev >= 9:
            urgent_hits.append("严重程度达到 9-10")
            reasons.append("严重程度 9-10（无法忍受）")
        elif sev >= 7:
            watch_hits.append("严重程度达到 7-8")
            reasons.append("严重程度 7-8（较明显）")

    # 4) 客观评估
    if isinstance(quiz, dict):
        if quiz.get("red_flag"):
            urgent_hits.append("客观评估命中紧急警示")
            reasons.append("客观评估命中紧急警示：「{}」".format(quiz.get("red_flag_hit") or "是"))
        trend = (quiz.get("dimensions") or {}).get("时间趋势", {})
        if trend.get("label") == "快速恶化":
            watch_hits.append("快速恶化")
            reasons.append("客观评估提示快速恶化")
        try:
            qscore = float(quiz["score"]) if quiz.get("score") is not None else None
        except (TypeError, ValueError):
            qscore = None
        if qscore is not None and qscore >= 9:
            urgent_hits.append("客观评估综合分≥9")
            reasons.append("客观评估综合分 {}/10".format(qscore))
        elif qscore is not None and qscore >= 7:
            watch_hits.append("客观评估综合分≥7")
            reasons.append("客观评估综合分 {}/10".format(qscore))

    if urgent_hits or (sev is not None and sev >= 9):
        level = "紧急"
        action = "建议立即就医（必要时拨打 120），不要拖延。"
    elif watch_hits and ((sev is not None and sev >= 7) or "快速恶化" in watch_hits):
        level = "中危"
        action = "建议尽快（1-2 天内）就诊，避免拖延。"
    elif sev is not None and sev >= 7:
        # 程度重（7-8 分）不论是否在清单内，都应尽快就诊
        level = "中危"
        action = "程度较明显（7-8 分），建议尽快（1-2 天内）就诊，避免拖延。"
    elif watch_hits and sev is not None and sev >= 4:
        level = "中"
        action = "建议近期（1-7 天）安排门诊检查；症状持续或加重时提前就诊。"
    elif watch_hits and sev is None:
        level = "中"
        action = "未提供严重程度；建议近期安排门诊评估，若出现升级条件请提前。"
    else:
        # 普通人轻中度症状（1-6 分且不在警惕清单）：符合多数常见情况，先观察自愈
        level = "低"
        action = "程度较轻，符合多数常见情况（如吃坏肚子、受凉、疲劳），建议先休息观察 1-3 天；持续不缓解或加重再就诊。"

    # 国际指南时长阈值：轻度但已超建议就诊时长 → 升级为「中/近期门诊」（慢性稳定除外）
    if level == "低" and overdue and trend != "好转" and not (course or {}).get("stable"):
        level = "中"
        action = "症状持续时间已超过建议就诊时长（Mayo/NHS），建议安排门诊检查。"
        reasons.append("「{}」持续时间超过国际指南建议就诊时长".format("、".join(overdue[:3])))

    # 具体排查提示（弱化语气，仅作参考）
    extra = []
    for item in scored:
        d = item["disease"]
        k = _hit(d, emergency_map)
        if k:
            extra.append("{}：{}".format(k, emergency_map[k]))
        else:
            k2 = _hit(d, mid_map)
            if k2:
                extra.append("{}：{}".format(k2, mid_map[k2]))
    # 病程校准：长期稳定降级，明确加重升级（紧急永不降级，避免过度惊吓）
    course = course or {}
    if level != "紧急":
        if course.get("stable"):
            if level == "中危":
                level = "中"
                action = "病程慢性稳定，建议近期复查即可；症状有变化时再提前就诊。"
            elif level == "中":
                level = "低"
                action = "病程偏慢性且稳定，按原计划复诊即可；症状有变化时再提前就诊。"
            reasons.append("病程慢性稳定，已按长期客观情况降低紧急度")
        elif course.get("worsening"):
            if level == "低":
                level = "中"
                action = "近期有加重趋势，建议近期安排门诊检查。"
            elif level == "中":
                level = "中危"
                action = "近期呈加重趋势，建议尽快（1-2 天内）就诊。"
            reasons.append("近期呈加重趋势，已适当升级关注")
        elif course.get("kind", "").startswith("新发") and sev is not None and sev >= 8 and level == "中":
            level = "中危"
            action = "新发且程度较重，建议尽快（1-2 天内）就诊。"
            reasons.append("新发且程度较重")

    return {
        "level": level,
        "action": action,
        "reasons": reasons[:8],
        "advice": extra[:4],
        "calm": "风险分级是保守筛查，用于提醒就医时机，不构成诊断；大多数症状为常见病，不必过度紧张。",
        "course": course,
    }


_LEVEL_TO_PATHWAY = {"紧急": "急诊", "中危": "尽快", "中": "近期", "低": "家庭观察"}


def _append_care_pathway(lines, result, risk):
    """根据风险等级输出国际权威就诊路径（分档 + 时间窗 + 来源 + 症状专属建议）。"""
    care = load_care()
    levels = {x.get("level"): x for x in care.get("levels", [])}
    level = risk.get("level", "低")
    pkey = _LEVEL_TO_PATHWAY.get(level, "家庭观察")
    # 慢性稳定且低风险 → 提示按原计划门诊复诊
    course = result.get("course") or {}
    if level == "低" and course.get("stable"):
        pkey = "门诊"
    plv = levels.get(pkey) or levels.get("家庭观察")
    lines.append("【就诊路径】（依据国际权威指南，非一刀切）")
    lines.append("  {}：{}（{}）".format(plv.get("label", pkey), plv.get("timeframe", ""), plv.get("advice", "")))
    # 每个输入症状的专属档位建议（最多列 2 个）
    shown = 0
    for sym in result.get("symptoms", [])[:2]:
        care_syms = care.get("symptoms", {})
        guidance = care_syms.get(sym) or care_syms.get("default", {})
        if not guidance:
            continue
        # 列出当前档位 + 上一档（提示升级条件）
        tier_order = ["家庭观察", "门诊", "近期", "尽快", "急诊"]
        cur = pkey
        lines.append("  【{}】".format(sym))
        cur_display = cur
        if cur not in guidance:
            for t in reversed(tier_order[:tier_order.index(cur)] if cur in tier_order else []):
                if t in guidance:
                    cur_display = t
                    break
        if cur_display in guidance:
            lines.append("    · 当前档（{}级）：{}".format(cur_display, guidance[cur_display]))
        idx = tier_order.index(cur_display) if cur_display in tier_order else 0
        for higher in tier_order[idx + 1:]:
            if higher in guidance:
                lines.append("    · 若出现以下情况应升级到「{}」：{}".format(higher, guidance[higher]))
                break
        shown += 1
        if shown >= 2:
            break
    src = care.get("sources", [])
    if src:
        lines.append("  依据：{}".format("；".join("{}（{}）".format(s.get("org", ""), s.get("url", "")) for s in src[:3])))
    lines.append("")


def format_report(result, severity=None, top=10, days=0):
    """生成中文分析报告文本。"""
    lines = []
    lines.append("=" * 50)
    lines.append("病情分析报告")
    lines.append("=" * 50)
    syms_txt = "、".join(result["symptoms"]) if result["symptoms"] else "（无，仅结合历史）"
    lines.append("【一句话总结】{}：风险【{}】，{}".format(syms_txt, result["risk"]["level"], result["risk"]["action"]))
    lines.append("输入症状：{}".format(syms_txt))
    if severity is not None:
        lines.append("严重程度：{}/10".format(severity))
    if result["history"]:
        hist = "、".join("{}×{}".format(k, v) for k, v in sorted(result["history"].items(), key=lambda kv: -kv[1])[:8])
        lines.append("近期历史症状（近 {} 天）：{}".format("全部" if not days else days, hist))
    lines.append("")
    risk = result["risk"]
    course = result.get("course") or {}
    if course:
        lines.append("【病程判断】{}".format(course.get("kind", "未知")))
        if course.get("days") is not None:
            lines.append("  病程时长：约 {} 天".format(course["days"]))
    lines.append("【风险分级】{}".format(risk["level"]))
    lines.append("  建议：{}".format(risk["action"]))
    if risk["reasons"]:
        lines.append("  依据：{}".format("；".join(risk["reasons"])))
    if risk["advice"]:
        lines.append("  需排查项：{}".format("；".join(risk["advice"])))
    lines.append("  提示：{}".format(risk.get("calm", "")))
    lines.append("")

    _append_care_pathway(lines, result, risk)

    quiz = result.get("quiz")
    if isinstance(quiz, dict) and quiz:
        lines.append("【客观难受程度评估（{}）】".format(quiz.get("mode", "快速版")))
        if quiz.get("score") is not None:
            lines.append("  综合分：{}/10（{}）".format(quiz["score"], quiz.get("level", "")))
        else:
            lines.append("  未填写强度，未计算综合分（可随时用 severity_quiz.py 补评）。")
        parts = []
        for k, v in (quiz.get("dimensions") or {}).items():
            parts.append("{}：{}".format(k, v.get("label", v.get("value", ""))))
        if parts:
            lines.append("  已填分项：{}".format("；".join(parts)))
        if quiz.get("red_flag"):
            lines.append("  [紧急警示]：{}".format(quiz.get("red_flag_hit") or "是"))
        lines.append("")

    shown_any = False
    for tier in ("高度相关", "可能相关", "需注意（仅历史）"):
        items = result["tiers"].get(tier, [])
        if not items:
            continue
        shown_any = True
        lines.append("【{}】".format(tier))
        for item in items[:top]:
            matched = "、".join(item["input"] + ["历史:" + h for h in item["history"]])
            lines.append("  - {}（置信度{}，关联：{}）".format(item["disease"], item.get("confidence", "中"), matched))
        lines.append("")
    if not shown_any:
        lines.append("【可能疾病】本地知识库未匹配到明确条目；建议结合医生问诊或联网资料补充了解。")
        lines.append("")

    if result["departments"]:
        depts = sorted(result["departments"].items(), key=lambda kv: -kv[1])[:5]
        lines.append("【建议科室】{}".format("、".join("{}".format(d) for d, _ in depts)))
        lines.append("")
    lines.append("【建议检查（仅供参考，以医生为准）】")
    lines.append("  常见初筛：血常规、尿常规、基础生化；根据症状可加影像（B超/CT）或专科检查。")
    lines.append("")
    lines.append("-" * 50)
    lines.append("分析依据：本地知识库（symptom_disease_map.json / disease_risk.json / red_flag_symptoms.json）。")
    lines.append("免责声明：本分析仅供参考，不构成诊断；如有紧急症状请立即就医。")
    return "\n".join(lines)


def format_web_summary(queries, max_results=3):
    """联网资料摘要（第 4 轮优化；第 23 项：多引擎交叉验证 + 官方优先）。
    只做资料补充，不参与分析判断。"""
    try:
        from web_search import cross_validate
    except ImportError:
        return "（联网搜索模块不可用）"
    blocks = []
    for q in queries[:2]:
        items, meta = cross_validate(q, max_results=max_results)
        if not items:
            blocks.append("【{}】未搜索到可靠结果。".format(q))
            continue
        blocks.append("【{}】共 {} 条独立来源，官方/权威 {} 条（引擎 {}）。".format(
            q, meta["total"], meta["official_count"], "、".join(meta["engines_ok"]) or "无"))
        for i, item in enumerate(items[:4], 1):
            tag = "[官方]" if item["official"] else ""
            src = "[{}个来源]".format(item["source_count"]) if item["source_count"] > 1 else ""
            blocks.append("  {}. {}{}{}".format(i, item.get("title", "无标题"), tag, src))
            if item.get("url"):
                blocks.append("    {}".format(item["url"]))
            if item.get("snippet"):
                blocks.append("    摘要：{}".format(item["snippet"][:160]))
        if meta["official_count"] == 0:
            blocks.append("  [提示] 未找到官方/权威来源，请谨慎并自行核实。")
    return "\n".join(blocks)


def main():
    parser = argparse.ArgumentParser(description="病情分析（风险分级 + 组合分析 + 可选联网资料）")
    parser.add_argument("symptoms", nargs="*", help="症状名称，如：头痛 发热")
    parser.add_argument("--severity", type=int, default=0, help="严重程度 1-10（影响风险分级）")
    parser.add_argument("--member", default="", help="结合成员历史记录，如：妈妈")
    parser.add_argument("--days", type=int, default=0, help="结合历史最近 N 天（0=全部）")
    parser.add_argument("--duration", default="", help="本次病程时长，如：3天 / 2周 / 1个月（用于客观病程判断）")
    parser.add_argument("--trend", default="", choices=["好转", "平稳", "加重", "明显加重", "快速恶化"], help="和之前比的变化趋势（可选）")
    parser.add_argument("--top", type=int, default=10, help="每个分级最多列出的疾病数，默认 10")
    parser.add_argument("--web", action="store_true", help="追加联网资料摘要（与分析结论分离）")
    parser.add_argument("--quiz", action="store_true", help="先做快速客观评估（3 题可选填），再分析（推荐）")
    parser.add_argument("--quiz-full", action="store_true", help="完整版客观评估（7 维，每项可选填）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 结构")
    args = parser.parse_args()

    member = None
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效。")
            return 1
    symptoms = list(args.symptoms)
    if not symptoms and not member:
        parser.print_help()
        return 1
    if args.days < 0:
        print("[错误] --days 不能为负数。")
        return 1
    severity = args.severity or None
    if severity is not None and not 1 <= severity <= 10:
        print("[错误] 严重程度必须是 1-10。")
        return 1

    quiz = None
    if args.quiz or args.quiz_full:
        try:
            from severity_quiz import run_quiz
            mode = "full" if args.quiz_full else "quick"
            quiz = run_quiz(member, mode=mode)
            if quiz.get("score") is not None:
                severity = quiz["score"]
        except Exception as e:
            print("[提示] 客观评估未完成（{}），将使用 --severity / 默认继续。".format(e))

    duration_days = parse_duration(args.duration) if args.duration else None
    result = analyze(symptoms, member=member, days=args.days, severity=severity, quiz=quiz,
                     duration_days=duration_days, trend=args.trend)

    # 第 4 轮优化：先出客观分析，联网摘要放在后面且明确标注
    if args.json:
        payload = {
            "symptoms": result["symptoms"],
            "risk": result["risk"],
            "quiz": result.get("quiz"),
            "diseases": {tier: [x["disease"] for x in items] for tier, items in result["tiers"].items()},
            "departments": sorted(result["departments"].items(), key=lambda kv: -kv[1])[:5],
            "course": result.get("course"),
            "overdue": result.get("overdue"),
            "pathway": _LEVEL_TO_PATHWAY.get(result["risk"]["level"], "家庭观察"),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(format_report(result, severity=severity, top=max(1, args.top), days=args.days))

    if args.web:
        print("")
        print("=" * 50)
        print("[联网资料摘要]（仅供参考，不代表诊断结论）")
        print("=" * 50)
        queries = [x["disease"] for tier in ("高度相关", "可能相关") for x in result["tiers"].get(tier, [])][:2]
        if not queries:
            queries = [" ".join(result["symptoms"])] if result["symptoms"] else []
        if queries:
            print(format_web_summary(queries, max_results=3))
        print("")
        print("[客观性说明]：上面的分析结论在联网搜索前已完成，仅基于本地知识库与您的描述；")
        print("   网络内容可能过时、含广告或不可靠，不能替代医生意见，请勿因搜索结果改变就医决定。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

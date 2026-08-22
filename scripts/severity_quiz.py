# -*- coding: utf-8 -*-
"""难受程度客观评估（简单化 + 可选填）。

- 快速版（默认，--quick）：只问 3 个问题，全部可留空跳过：
    1) 最近最明显时不适有多强（0-10，留空=跳过）
    2) 是否影响睡眠/工作/饮食（留空=跳过）
    3) 和之前比（好转/平稳/加重，留空=跳过）
    4) 紧急警示筛查（留空=无）
- 完整版（--full）：7 个维度，每项都可留空跳过，按已填维度重新归一化权重。

用法：
    python severity_quiz.py                     # 快速版（推荐，简单）
    python severity_quiz.py --full              # 完整版（进阶，每项可选填）
    python severity_quiz.py --member 妈妈       # 结果存入成员档案 severity_history.json
    python severity_quiz.py --member 妈妈 --json
"""
import argparse
import json
import os
import sys
from datetime import datetime

import common

REFERENCES_DIR = os.path.normpath(os.path.join(common.SCRIPT_DIR, "..", "references"))
SCALE_FILE = os.path.join(REFERENCES_DIR, "severity_scale.json")


def ask(prompt):
    """带提示符输入，非交互环境返回空字符串。"""
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def load_scale():
    """读取评估标准。"""
    try:
        with open(SCALE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def ask_pain_optional(scale):
    """询问 0-10 强度（可留空跳过），返回 (值或None, 文字锚点)。"""
    anchors = scale.get("verbal_scale", [])
    print("--- 强度参考（0-10，可留空跳过）---")
    for a in anchors:
        print("  {} = {}".format(a.get("score"), a.get("label")))
    while True:
        raw = ask("最近最明显时，不适有多强？（0-10，直接回车=跳过）：")
        if not raw:
            return None, ""
        try:
            val = int(raw)
        except ValueError:
            print("  请输入整数。")
            continue
        if 0 <= val <= 10:
            label = ""
            for a in anchors:
                if a.get("score") == val:
                    label = a.get("label", "")
                    break
            return val, label
        print("  请输入 0-10 的整数。")


def ask_choice_optional(question, options):
    """询问单选维度（可留空跳过），返回 (选项标签或None, 分值或None)。"""
    labels = list(options.keys())
    print("  " + question)
    for i, lab in enumerate(labels, 1):
        print("    {}. {}（直接回车=跳过）".format(i, lab))
    while True:
        raw = ask("  请选择编号，或直接回车跳过：")
        if not raw:
            return None, None
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(labels):
                return labels[idx - 1], options[labels[idx - 1]]
        for lab in labels:
            if raw == lab:
                return lab, options[lab]
        print("  请选择有效编号或选项文字。")


def run_quiz(member=None, mode="quick"):
    """执行评估。mode: quick（默认简单）/ full（完整可选填）。返回结果字典。"""
    scale = load_scale()
    dims = scale.get("dimensions", {})
    flags = scale.get("red_flags", [])
    mode_label = "快速版（简单）" if mode != "full" else "完整版（可选填）"

    print("=" * 50)
    print("难受程度客观评估（{}）".format(mode_label))
    print("=" * 50)

    answers = {}
    if mode == "full":
        pain, pain_label = ask_pain_optional(scale)
        if pain is not None:
            answers["疼痛不适强度"] = {"value": pain, "label": pain_label}
        for key, cfg in dims.items():
            if key == "疼痛不适强度":
                continue
            label, val = ask_choice_optional(cfg.get("question", key), cfg.get("options", {}))
            if label is not None:
                answers[key] = {"value": val, "label": label}
    else:
        # 快速版：3 个问题，全部可选填
        pain, pain_label = ask_pain_optional(scale)
        if pain is not None:
            answers["疼痛不适强度"] = {"value": pain, "label": pain_label}
        impact = ask("是否影响睡眠/工作/饮食？（可留空=跳过，如：影响睡眠）：")
        if impact:
            answers["生活影响"] = {"value": 1, "label": impact}
        trend_raw = ask("和之前比？（可留空=跳过，如：加重 / 快速恶化）：")
        trend_map = {"好转": -1, "平稳": 0, "略加重": 1, "加重": 2, "明显加重": 2, "快速恶化": 3}
        if trend_raw:
            trend_key = trend_raw.strip()
            answers["时间趋势"] = {"value": trend_map.get(trend_key, 1), "label": trend_key}

    # 紧急警示筛查（可留空=无）
    red_flag = False
    red_hit = ""
    print("--- 紧急警示筛查（直接回车=无）---")
    print("  如出现：{}，应优先就医。".format("、".join(flags)))
    while True:
        raw = ask("  是否出现其中任何一项？（有/无，直接回车=无）：")
        if not raw or raw in ("无", "没有", "否", "n", "N", "no"):
            break
        if raw in ("有", "是", "要", "y", "Y", "yes"):
            red_flag = True
            red_hit = ask("  请说明是哪一项（可多写）：")
            break
        print("  请回答 有/无。")

    # 计分：只按已填维度计算，并重新归一化权重
    score = None
    if answers:
        if mode == "full":
            total_w = 0.0
            acc = 0.0
            for key, cfg in dims.items():
                if key not in answers:
                    continue
                w = cfg.get("weight", 0.10)
                v = answers[key]["value"]
                acc += (v / 3.0 * 10) * w if key != "疼痛不适强度" else v * w
                total_w += w
            if total_w > 0:
                score = acc / total_w
        else:
            # 快速版：强度为基准，趋势作为修正量（加重加分、好转减分），不再除以总权重
            if "疼痛不适强度" in answers:
                base = answers["疼痛不适强度"]["value"]
                adj = 0.0
                if "时间趋势" in answers:
                    adj = answers["时间趋势"]["value"] * 0.5
                if "生活影响" in answers:
                    adj += 0.5  # 已影响生活 → 综合分略升
                score = max(0.0, min(10.0, base + adj))
        if score is not None:
            score = round(score, 1)

    level = "未评估"
    action = "未填写强度，无法评级；建议先简单自评（0-10）或直接就诊。"
    if score is not None:
        level = "极重度"
        action = "建议立即就医评估，必要时急诊。"
        for lv in scale.get("levels", []):
            if lv.get("min", 0) <= score <= lv.get("max", 10):
                level = lv.get("name", "中")
                action = lv.get("action", "")
                break
    if red_flag:
        level = "极重度（含紧急警示）"
        action = "立即就医（拨打 120 或就近急诊），不要等待。"
    elif answers.get("时间趋势", {}).get("label") == "快速恶化":
        level = "重度"
        action = "建议尽快（1-2 天内）就诊，避免拖延。"
    elif score is not None and score >= 9:
        level = "极重度"
        action = "立即就医评估，必要时急诊。"

    result = {
        "mode": mode_label,
        "score": score,
        "level": level,
        "action": action,
        "dimensions": answers,
        "red_flag": red_flag,
        "red_flag_hit": red_hit,
        "answered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    if member and score is not None:
        path = common.path_for("severity_history.json", member)
        history = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                history = data if isinstance(data, list) else []
            except (OSError, json.JSONDecodeError):
                history = []
        history.append(result)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        result["history_path"] = path
    return result


def print_result(result):
    """打印评估结果。"""
    print("=" * 50)
    print("评估结果")
    print("=" * 50)
    if result["score"] is not None:
        print("综合难受程度：{}/10（{}）".format(result["score"], result["level"]))
    else:
        print("本次未填写强度，未计算综合分。")
    print("建议：{}".format(result["action"]))
    print("-" * 50)
    for k, v in result["dimensions"].items():
        print("  {}：{}".format(k, v.get("label", v.get("value", ""))))
    if result["red_flag"]:
        print("  [紧急警示]：{}".format(result["red_flag_hit"] or "是"))
    if result.get("history_path"):
        print("已存入：{}".format(result["history_path"]))
    print("-" * 50)
    print("免责声明：评估结果仅供参考，不能替代专业医疗诊断。")


def main():
    parser = argparse.ArgumentParser(description="难受程度客观评估（快速简单版 / 完整可选填版）")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    parser.add_argument("--quick", action="store_true", help="快速版（默认，3 题可选填）")
    parser.add_argument("--full", action="store_true", help="完整版（7 维，每项可选填）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()
    member = None
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效。")
            return 1
    mode = "full" if args.full else "quick"
    result = run_quiz(member, mode=mode)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())

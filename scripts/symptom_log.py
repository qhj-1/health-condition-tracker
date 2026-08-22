# -*- coding: utf-8 -*-
"""症状记录工具：将一条症状记录保存到 health_log.json（支持多家人档案）。

数据文件：health_log.json（数组格式）；未指定成员时保存在脚本目录，
指定 --member 时保存在 members/<成员名>/health_log.json。
"""
import argparse
import json
import os
import sys
from datetime import datetime

import common


def load_log(member=None):
    """读取健康日志，返回记录列表；文件不存在或损坏时返回空列表。"""
    path = common.path_for("health_log.json", member)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        print("[警告] 读取 health_log.json 失败（{}），将创建新记录。".format(e))
        return []


def save_record(record, member=None):
    """将一条症状记录追加保存到指定成员的 health_log.json。"""
    records = load_log(member)
    records.append(record)
    path = common.path_for("health_log.json", member)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    who = member or "默认档案"
    print("=" * 50)
    print("[确认] 症状记录已保存（成员：{}）。".format(who))
    print("  日期    : {}".format(record["date"]))
    print("  症状    : {}".format(record["symptom"]))
    print("  严重程度: {}/10".format(record.get("severity", "未填写")))
    print("  持续时长: {}".format(record.get("duration", "") or "未填写"))
    print("  备注    : {}".format(record.get("notes", "") or "无"))
    print("  当前共有 {} 条记录。".format(len(records)))
    print("  保存位置: {}".format(path))
    print("=" * 50)


def ask(prompt):
    """带提示符的输入函数，遇到非交互环境返回空字符串。"""
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def choose_member_simple():
    """多家人档案开启时选择录入到哪个档案（默认 / 已有 / 新建）。"""
    members = common.list_members()
    print("--- 本次症状记录到哪个档案？ ---")
    print("  0. 默认档案（不区分成员）")
    for i, m in enumerate(members, start=1):
        print("  {}. {}".format(i, m))
    print("  {}. 新建档案".format(len(members) + 1))
    while True:
        raw = ask("请输入编号或档案名（直接回车=默认档案）：")
        if not raw:
            print("  本次记录将保存到默认档案。")
            return None
        if raw.isdigit():
            idx = int(raw)
            if idx == 0:
                return None
            if 1 <= idx <= len(members):
                common.register_member(members[idx - 1])
                return members[idx - 1]
            if idx == len(members) + 1:
                name = common.sanitize_member(ask("新档案名字（如：爸爸）："))
                if name:
                    common.register_member(name)
                    return name
                print("  档案名不能为空或含非法字符。")
                continue
            print("  编号超出范围。")
            continue
        name = common.sanitize_member(raw)
        if not name:
            print("  档案名无效（不能为空或含 / \\ : * ? \" < > | 等字符）。")
            continue
        common.register_member(name)
        return name


def interactive_mode(member=None):
    """命令行交互输入模式（多家人档案开启时可选择档案）。"""
    print("=" * 50)
    print("症状记录 - 交互模式（成员：{}）".format(member or "默认档案"))
    print("=" * 50)
    if member is None and common.load_config().get("multi_member"):
        member = choose_member_simple()
    symptom = ask("症状名称（必填，如：头痛）：")
    if not symptom:
        print("[错误] 症状名称不能为空。")
        return 1
    while True:
        severity_raw = ask("严重程度（1-10，必填）：")
        try:
            severity = int(severity_raw)
        except ValueError:
            print("  请输入整数。")
            continue
        if 1 <= severity <= 10:
            break
        print("  严重程度必须是 1-10 的整数，请重新输入。")
    date_value = ask("发病日期（可留空=现在，如 2026-08-10）：")
    duration = ask("持续时长（如：2天 / 1周）：")
    notes = ask("备注（可选）：")
    save_record(_build_record(symptom, severity, duration, notes, date_value), member)
    return 0


def _build_record(symptom, severity, duration="", notes="", date_value=None):
    """构造一条症状记录（同时写入 symptoms 列表，便于趋势分析使用）。"""
    date_str = date_value.strip() if date_value and date_value.strip() else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "date": date_str,
        "symptom": symptom,
        "severity": severity,
        "duration": duration or "",
        "notes": notes or "",
        "symptoms": [{"name": symptom, "severity": severity}],
    }


def main():
    parser = argparse.ArgumentParser(description="保存一条症状记录到 health_log.json")
    parser.add_argument("--symptom", help="症状名称")
    parser.add_argument("--severity", type=int, help="严重程度 1-10")
    parser.add_argument("--duration", help="持续时长")
    parser.add_argument("--notes", help="备注")
    parser.add_argument("--date", default="", help="发病日期，如 2026-08-10（默认现在）")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    args = parser.parse_args()
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效（不能为空或含 / \\ : * ? \" < > | 等字符）。")
            return 1
    else:
        member = None

    if args.symptom and args.severity is not None:
        if not 1 <= args.severity <= 10:
            print("[错误] 严重程度必须是 1-10 的整数。")
            return 1
        for name in common.split_symptoms(args.symptom):
            save_record(
                _build_record(name, args.severity, args.duration or "", args.notes or "", args.date or None),
                member,
            )
        return 0
    return interactive_mode(member)


if __name__ == "__main__":
    sys.exit(main())

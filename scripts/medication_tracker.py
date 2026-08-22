# -*- coding: utf-8 -*-
"""用药管理工具：记录、查看、删除用药信息，并做简单的药物相互作用提醒（支持多家人档案）。

数据文件：medications.json；指定 --member 时保存在 members/<成员名>/medications.json。

用法示例：
    python medication_tracker.py add --name 布洛芬 --dosage 400mg --frequency 每日2次 --member 妈妈
    python medication_tracker.py list --member 妈妈
    python medication_tracker.py remove 1 --member 妈妈
"""
import argparse
import json
import os
import sys
from datetime import datetime

import common

# 常见非甾体抗炎药（NSAIDs），用于提醒多种 NSAIDs 同时使用的风险
NSAIDS = ["布洛芬", "阿司匹林", "双氯芬酸", "萘普生", "塞来昔布", "吲哚美辛", "美洛昔康", "酮洛芬"]


def load_medications(member=None):
    """读取指定成员的用药记录，返回列表；文件不存在或损坏时返回空列表。"""
    path = common.path_for("medications.json", member)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_medications(items, member=None):
    """保存用药列表到指定成员的 medications.json。"""
    path = common.path_for("medications.json", member)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def add_medication(name, dosage="", frequency="", start_date="", end_date="", notes="", member=None):
    """添加一条用药记录，返回新记录。"""
    items = load_medications(member)
    record = {
        "name": name,
        "dosage": dosage,
        "frequency": frequency,
        "start_date": start_date or datetime.now().strftime("%Y-%m-%d"),
        "end_date": end_date,
        "notes": notes,
    }
    items.append(record)
    save_medications(items, member)
    return record


def list_medications(member=None):
    """返回指定成员的所有用药记录。"""
    return load_medications(member)


def remove_medication(index, member=None):
    """按序号（从 1 开始）删除用药记录，成功返回被删除的记录，失败返回 None。"""
    items = load_medications(member)
    if 1 <= index <= len(items):
        removed = items.pop(index - 1)
        save_medications(items, member)
        return removed
    return None


def check_interactions(items=None):
    """检查进行中的用药是否存在相互作用风险，返回中文警告列表。"""
    items = items if items is not None else load_medications()
    active = [m for m in items if not m.get("end_date")]
    nsaids = [m for m in active if any(n in m.get("name", "") for n in NSAIDS)]
    warnings = []
    if len(nsaids) >= 2:
        names = "、".join(m["name"] for m in nsaids)
        warnings.append(
            ("提示：检测到多种非甾体抗炎药（NSAIDs）同时使用：{}。"
             "同时使用可能增加胃肠道出血和肾损伤风险，请咨询医生或药师。").format(names)
        )
    return warnings


def print_medications(items=None):
    """打印用药记录列表。"""
    items = items if items is not None else load_medications()
    if not items:
        print("暂无用药记录。")
        return
    print("当前共 {} 条用药记录：".format(len(items)))
    for i, m in enumerate(items, 1):
        status = "结束于 {}".format(m.get("end_date")) if m.get("end_date") else "进行中"
        print(
            "  {}. {}（{}，{}）开始于 {}，{}".format(
                i,
                m.get("name", ""),
                m.get("dosage", ""),
                m.get("frequency", ""),
                m.get("start_date", ""),
                status,
            )
        )


def main():
    parser = argparse.ArgumentParser(description="用药记录与管理")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    sub = parser.add_subparsers(dest="command")

    add_p = sub.add_parser("add", help="添加用药记录")
    add_p.add_argument("--name", required=True, help="药物名称")
    add_p.add_argument("--dosage", default="", help="剂量，如 400mg")
    add_p.add_argument("--frequency", default="", help="频次，如 每日2次")
    add_p.add_argument("--start", default="", help="开始日期，默认今天")
    add_p.add_argument("--end", default="", help="结束日期")
    add_p.add_argument("--notes", default="", help="备注")

    sub.add_parser("list", help="查看用药记录")

    rem_p = sub.add_parser("remove", help="删除用药记录")
    rem_p.add_argument("index", type=int, help="记录序号（从 1 开始）")

    args = parser.parse_args()
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效（不能为空或含 / \\ : * ? \" < > | 等字符）。")
            return 1
    else:
        member = None

    if args.command == "add":
        record = add_medication(args.name, args.dosage, args.frequency, args.start, args.end, args.notes, member)
        print("=" * 50)
        print("[确认] 已添加用药记录：{}（成员：{}）".format(record["name"], member or "默认档案"))
        print("  剂量：{}，频次：{}".format(record["dosage"] or "未填写", record["frequency"] or "未填写"))
        print("  开始日期：{}，结束日期：{}".format(record["start_date"], record["end_date"] or "进行中"))
    elif args.command == "list":
        print("=" * 50)
        print("用药记录（成员：{}）".format(member or "默认档案"))
        print("=" * 50)
        print_medications(list_medications(member))
        for warning in check_interactions(list_medications(member)):
            print(warning)
    elif args.command == "remove":
        removed = remove_medication(args.index, member)
        if removed:
            print("[确认] 已删除用药记录：{}".format(removed["name"]))
        else:
            print("[错误] 序号无效。")
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

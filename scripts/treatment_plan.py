# -*- coding: utf-8 -*-
"""治疗方案跟踪工具：保存医生诊断、建议、复诊时间，并跟踪执行状态（支持多家人档案）。

执行状态：已执行 / 进行中 / 未开始
数据文件：treatment_plans.json；指定 --member 时保存在 members/<成员名>/treatment_plans.json。

用法示例：
    python treatment_plan.py add --diagnosis 偏头痛 --advice 规律作息 --follow-up 2026-09-01 --member 妈妈
    python treatment_plan.py list --member 妈妈
    python treatment_plan.py update 1 已执行 --member 妈妈
"""
import argparse
import json
import os
import sys
from datetime import datetime

import common

STATUS_OPTIONS = ("已执行", "进行中", "未开始")


def load_plans(member=None):
    """读取指定成员的治疗方案，返回列表；文件不存在或损坏时返回空列表。"""
    path = common.path_for("treatment_plans.json", member)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_plans(items, member=None):
    """保存治疗方案列表到指定成员的 treatment_plans.json。"""
    path = common.path_for("treatment_plans.json", member)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def add_plan(diagnosis, advice="", follow_up_date="", status="未开始", member=None):
    """保存一条治疗方案，返回新记录。"""
    if status not in STATUS_OPTIONS:
        status = "未开始"
    items = load_plans(member)
    plan = {
        "diagnosis": diagnosis,
        "advice": advice,
        "follow_up_date": follow_up_date,
        "status": status,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    items.append(plan)
    save_plans(items, member)
    return plan


def update_status(index, status, member=None):
    """按序号（从 1 开始）更新治疗方案状态，成功返回更新后的记录，失败返回 None。"""
    if status not in STATUS_OPTIONS:
        return None
    items = load_plans(member)
    if 1 <= index <= len(items):
        items[index - 1]["status"] = status
        save_plans(items, member)
        return items[index - 1]
    return None


def list_plans(member=None):
    """返回指定成员的所有治疗方案。"""
    return load_plans(member)


def print_plans(items=None):
    """打印治疗方案列表。"""
    items = items if items is not None else load_plans()
    if not items:
        print("暂无治疗方案记录。")
        return
    print("当前共 {} 个治疗方案：".format(len(items)))
    for i, p in enumerate(items, 1):
        box = "[X]" if p.get("status") == "已执行" else ("[-]" if p.get("status") == "进行中" else "[ ]")
        print("  {}. {}（状态：{}）".format(i, p.get("diagnosis", ""), p.get("status", "未开始")))
        print("     建议：{}".format(p.get("advice", "") or "无"))
        print("     执行状态：{} {}".format(box, p.get("status", "未开始")))
        if p.get("follow_up_date"):
            print("     复诊时间：{}".format(p["follow_up_date"]))


def main():
    parser = argparse.ArgumentParser(description="治疗方案保存与跟踪")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    sub = parser.add_subparsers(dest="command")

    add_p = sub.add_parser("add", help="添加治疗方案")
    add_p.add_argument("--diagnosis", required=True, help="诊断")
    add_p.add_argument("--advice", default="", help="医生建议")
    add_p.add_argument("--follow-up", dest="follow_up", default="", help="复诊时间，如 2026-09-01")
    add_p.add_argument("--status", default="未开始", choices=STATUS_OPTIONS, help="执行状态")

    sub.add_parser("list", help="查看治疗方案")

    upd_p = sub.add_parser("update", help="更新治疗方案状态")
    upd_p.add_argument("index", type=int, help="方案序号（从 1 开始）")
    upd_p.add_argument("status", choices=STATUS_OPTIONS, help="新状态")

    args = parser.parse_args()
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效（不能为空或含 / \\ : * ? \" < > | 等字符）。")
            return 1
    else:
        member = None

    if args.command == "add":
        plan = add_plan(args.diagnosis, args.advice, args.follow_up, args.status, member)
        print("=" * 50)
        print("[确认] 已保存治疗方案：{}（成员：{}）".format(plan["diagnosis"], member or "默认档案"))
        print("  状态：{}，复诊时间：{}".format(plan["status"], plan["follow_up_date"] or "未设置"))
    elif args.command == "list":
        print("=" * 50)
        print("治疗方案（成员：{}）".format(member or "默认档案"))
        print("=" * 50)
        print_plans(list_plans(member))
    elif args.command == "update":
        plan = update_status(args.index, args.status, member)
        if plan:
            print("[确认] 已将方案「{}」状态更新为：{}".format(plan["diagnosis"], plan["status"]))
        else:
            print("[错误] 序号或状态无效。")
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

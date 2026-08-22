# -*- coding: utf-8 -*-
"""复诊 / 用药到期提醒：扫描治疗方案与用药记录，列出近期需要复诊或停药的项目。

用法：
    python reminders.py                  # 默认档案，未来 7 天
    python reminders.py --days 14        # 未来 14 天（含已逾期）
    python reminders.py --member 妈妈    # 指定成员
    python reminders.py --all-members    # 扫描所有家人档案
"""
import argparse
import json
import os
import sys
from datetime import date

import common


def _parse_date(value):
    """尝试多种格式解析日期，失败返回 None（委托 common.parse_date）。"""
    return common.parse_date(value)


def _load_list(filename, member=None):
    path = common.path_for(filename, member)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def collect_members(args_member, all_members):
    """返回要扫描的成员列表；all_members 时扫描已建档案 + 配置登记的成员。"""
    if all_members:
        return common.list_members() or [None]
    if args_member:
        clean = common.sanitize_member(args_member)
        if not clean:
            print("[错误] 成员名无效（不能为空或含非法字符）。")
            return [None]
        return [clean]
    return [None]


def collect_reminders(members, days):
    """返回提醒列表，元素为 (类别, 成员, 标题, 日期, 剩余天数)。"""
    today = date.today()
    reminders = []
    for member in members:
        who = member if member else "默认档案"
        for plan in _load_list("treatment_plans.json", member):
            if plan.get("status") == "已执行":
                continue
            fdate = _parse_date(plan.get("follow_up_date"))
            if not fdate:
                continue
            left = (fdate - today).days
            if left <= days:
                reminders.append(("复诊", who, plan.get("diagnosis", ""), fdate, left))
        for med in _load_list("medications.json", member):
            edate = _parse_date(med.get("end_date"))
            if not edate:
                continue
            left = (edate - today).days
            if 0 <= left <= days:
                reminders.append(("停药", who, med.get("name", ""), edate, left))
    reminders.sort(key=lambda x: x[3])
    return reminders


def main():
    parser = argparse.ArgumentParser(description="复诊 / 用药到期提醒")
    parser.add_argument("--days", type=int, default=7, help="提前提醒天数，默认 7（含已逾期）")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    parser.add_argument("--all-members", action="store_true", help="扫描所有家人档案")
    parser.add_argument("--ignore", default="", help="忽略某条提醒，格式：复诊:诊断:日期 或 停药:药名:日期")
    parser.add_argument("--show-ignored", action="store_true", help="查看已忽略列表")
    args = parser.parse_args()

    if args.show_ignored:
        _print_ignored()
        return 0
    if args.ignore:
        _add_ignored(args.ignore)
        return 0

    members = collect_members(args.member, args.all_members)
    reminders = collect_reminders(members, args.days)

    print("=" * 50)
    print("健康提醒（未来 {} 天内 / 含逾期）".format(args.days))
    print("=" * 50)
    if not reminders:
        print("暂无复诊或停药提醒。")
        return 0
    today = date.today()
    for kind, who, title, when, left in reminders:
        if left < 0:
            tag = "已逾期 {} 天".format(-left)
        elif left == 0:
            tag = "就是今天"
        else:
            tag = "还有 {} 天".format(left)
        print("  [{}] {}｜{}｜{}（{}）".format(kind, who, title, when.isoformat(), tag))
    print("-" * 50)
    print("共 {} 条提醒。提醒仅供参考，请以医生安排为准。".format(len(reminders)))
    return 0


IGNORE_FILE = os.path.join(common.SCRIPT_DIR, "reminders_ignore.json")


def _load_ignored():
    if not os.path.exists(IGNORE_FILE):
        return []
    try:
        with open(IGNORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_ignored(items):
    with open(IGNORE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _add_ignored(text):
    items = _load_ignored()
    if text not in items:
        items.append(text)
        _save_ignored(items)
        print("[确认] 已加入忽略列表：" + text)
    else:
        print("[提示] 已在忽略列表中。")


def _print_ignored():
    items = _load_ignored()
    print("已忽略的提醒（{} 条）：".format(len(items)))
    for it in items:
        print("  - " + it)
    if not items:
        print("  无。")


def _is_ignored(reminder):
    kind, who, title, when, _ = reminder
    candidates = [
        "{}:{}:{}".format(kind, title, when.isoformat()),
        "{}:{}".format(kind, title),
    ]
    for it in _load_ignored():
        if any(it == c for c in candidates):
            return True
    return False


if __name__ == "__main__":
    sys.exit(main())

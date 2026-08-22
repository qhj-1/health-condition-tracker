# -*- coding: utf-8 -*-
"""健康总览（间隔期快照）：隔几周 / 有病情才回来使用时，一条命令快速回顾全部要点。

用法：
    python snapshot.py                  # 默认档案
    python snapshot.py --member 妈妈    # 指定成员
    python snapshot.py --all-members    # 全家

输出：距上次记录天数、近期症状、进行中用药、治疗方案与复诊（含逾期）、
症状统计（近 30/90 天）、提醒、待办与建议。
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta

import common
from reminders import _parse_date, collect_members, collect_reminders
from trend_analysis import extract_symptoms


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


def _fmt(value):
    try:
        f = float(value)
        return str(int(f)) if f.is_integer() else "{:.1f}".format(f)
    except (TypeError, ValueError):
        return str(value)


def _symptom_stats(logs, days):
    """返回近 days 天内症状统计 {名称: {"count": n, "severities": [...]}}。"""
    cutoff = date.today() - timedelta(days=days)
    stats = {}
    for rec in logs:
        d = _parse_date(rec.get("date"))
        if not d or d < cutoff:
            continue
        for name, sev in extract_symptoms(rec):
            item = stats.setdefault(name, {"count": 0, "severities": []})
            item["count"] += 1
            if sev is not None:
                item["severities"].append(sev)
    return stats


def _stats_line(stats):
    if not stats:
        return "无"
    parts = []
    for name, item in sorted(stats.items(), key=lambda kv: -kv[1]["count"])[:6]:
        avg = ""
        if item["severities"]:
            avg = "（均分{}）".format(_fmt(sum(item["severities"]) / len(item["severities"])))
        parts.append("{}{}×{}".format(name, avg, item["count"]))
    return "、".join(parts)


def snapshot_member(member):
    """生成单个成员的健康总览文本。"""
    who = member if member else "默认档案"
    lines = []
    lines.append("=" * 50)
    lines.append("健康总览（{}）".format(who))
    lines.append("生成时间：{}".format(datetime.now().strftime("%Y-%m-%d %H:%M")))
    lines.append("=" * 50)

    logs = _load_list("health_log.json", member)
    meds = _load_list("medications.json", member)
    plans = _load_list("treatment_plans.json", member)

    # 1) 距上次记录
    last_date = None
    for rec in logs:
        d = _parse_date(rec.get("date"))
        if d and (last_date is None or d > last_date):
            last_date = d
    if last_date:
        gap = (date.today() - last_date).days
        lines.append("距上次记录：{} 天（上次：{}）".format(gap, last_date.isoformat()))
        if gap >= 7:
            lines.append("  提示：间隔较久，如有新症状 / 就医 / 用药变化，请补录或上传报告。")
    else:
        lines.append("暂无健康记录。")
    lines.append("")

    # 2) 近期症状
    lines.append("【近期症状（最近 5 条）】")
    if not logs:
        lines.append("  无")
    else:
        for rec in logs[-5:]:
            sev = rec.get("severity")
            sev_txt = "，严重程度 {}/10".format(_fmt(sev)) if sev not in (None, "") else ""
            lines.append("  {}：{}{}".format(rec.get("date", "?"), rec.get("symptom", "?"), sev_txt))
    lines.append("")

    # 3) 进行中用药
    lines.append("【进行中用药】")
    active = [m for m in meds if not m.get("end_date")]
    if not active:
        lines.append("  无")
    else:
        for m in active:
            lines.append("  {}（{}，{}）开始于 {}".format(
                m.get("name", ""), m.get("dosage", ""), m.get("frequency", ""), m.get("start_date", "")))
    lines.append("")

    # 4) 治疗方案与复诊
    lines.append("【治疗方案与复诊】")
    if not plans:
        lines.append("  无")
    else:
        for p in plans:
            box = "[x]" if p.get("status") == "已执行" else ("[-]" if p.get("status") == "进行中" else "[ ]")
            fd_txt = ""
            d = _parse_date(p.get("follow_up_date"))
            if d:
                left = (d - date.today()).days
                if left < 0:
                    fd_txt = "，复诊：{}（已逾期 {} 天！）".format(p["follow_up_date"], -left)
                elif left == 0:
                    fd_txt = "，复诊：{}（就是今天！）".format(p["follow_up_date"])
                else:
                    fd_txt = "，复诊：{}（还有 {} 天）".format(p["follow_up_date"], left)
            lines.append("  {} {}（状态：{}）{}".format(
                box, p.get("diagnosis", ""), p.get("status", "未开始"), fd_txt))
    lines.append("")

    # 5) 症状统计
    lines.append("【症状统计（近 30 / 90 天）】")
    lines.append("  近 30 天：{}".format(_stats_line(_symptom_stats(logs, 30))))
    lines.append("  近 90 天：{}".format(_stats_line(_symptom_stats(logs, 90))))
    lines.append("")

    # 6) 提醒（30 天内，含逾期）
    lines.append("【复诊 / 停药提醒（30 天内）】")
    reminders = collect_reminders([member], 30)
    if not reminders:
        lines.append("  无")
    else:
        for kind, _, title, when, left in reminders:
            tag = "已逾期 {} 天".format(-left) if left < 0 else ("今天" if left == 0 else "还有 {} 天".format(left))
            lines.append("  [{}] {}（{}）{}".format(kind, title, when.isoformat(), tag))
    lines.append("")

    # 7) 待办与建议
    todos = []
    for p in plans:
        if p.get("status") != "已执行":
            d = _parse_date(p.get("follow_up_date"))
            if d and d < date.today():
                todos.append("尽快复诊：{}（原定 {}）".format(p.get("diagnosis", ""), p.get("follow_up_date")))
    if not active and meds:
        todos.append("用药记录中无进行中项目，如需停药请补录 end_date")
    lines.append("【待办与建议】")
    if not todos:
        lines.append("  暂无待办。")
    else:
        for t in todos:
            lines.append("  ☐ " + t)
    lines.append("  就诊前可用 report_generator.py --member {} 生成医生沟通报告。".format(member or "默认"))
    lines.append("  有新症状可补录：symptom_log.py --symptom <症状> --severity <1-10> --date <发病日期> --member {}".format(member or "默认"))
    lines.append("")
    lines.append("免责声明：以上内容仅供参考，不能替代专业医疗诊断。")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="健康总览（间隔期快照）")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    parser.add_argument("--all-members", action="store_true", help="生成全家总览")
    args = parser.parse_args()

    members = collect_members(args.member, args.all_members)
    if args.all_members and members == [None]:
        print("[提示] 还没有家人档案，将显示默认档案；给成员记录症状即可自动建档。")

    for i, member in enumerate(members):
        if i:
            print()
        print(snapshot_member(member))
    return 0


if __name__ == "__main__":
    sys.exit(main())

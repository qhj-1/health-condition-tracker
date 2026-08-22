# -*- coding: utf-8 -*-
"""医生沟通报告生成工具：汇总健康记录、用药与治疗方案，生成 Markdown 报告（支持多家人档案）。

数据来源：health_log.json、medications.json、treatment_plans.json
输出：打印到屏幕，并保存为 health_report.md（未指定成员时在 scripts/ 目录，
指定 --member 时在 members/<成员名>/ 目录）。
"""
import argparse
import json
import os
import sys
from datetime import datetime

import common


def _load_json(filename, default, member=None):
    """安全读取指定成员目录下的 JSON 文件，文件不存在或损坏时返回默认值。"""
    path = common.path_for(filename, member)
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _fmt_number(value):
    """格式化数值：整数不带小数点。"""
    try:
        num = float(value)
        return str(int(num)) if num.is_integer() else "{:g}".format(num)
    except (TypeError, ValueError):
        return str(value)


def _extract(rec):
    """从一条记录中提取 (症状名, 严重程度) 列表（兼容两种数据结构）。"""
    items = rec.get("symptoms")
    if isinstance(items, list) and items:
        return [(it.get("name"), it.get("severity")) for it in items if it.get("name")]
    name = rec.get("symptom")
    if name:
        return [(name, rec.get("severity"))]
    return []


def build_report(member=None):
    """生成 Markdown 格式的医生沟通报告文本。"""
    logs = _load_json("health_log.json", [], member)
    meds = _load_json("medications.json", [], member)
    plans = _load_json("treatment_plans.json", [], member)

    lines = []
    who = "成员：{}".format(member) if member else "默认档案"
    lines.append("# 健康记录报告")
    lines.append("")
    lines.append("**生成日期**：{}".format(datetime.now().strftime("%Y-%m-%d %H:%M")))
    lines.append("")
    lines.append("**{}**".format(who))
    lines.append("")
    lines.append("---")
    lines.append("")

    # 一、症状时间线（按时间先后，完整列出）
    lines.append("## 一、症状时间线")
    lines.append("")
    if not logs:
        lines.append("暂无症状记录。")
    else:
        for rec in logs:
            date = rec.get("date", "未知日期")
            names = _extract(rec)
            if not names:
                continue
            parts = []
            for name, severity in names:
                sev = "，严重程度 {}/10".format(_fmt_number(severity)) if severity not in (None, "") else ""
                parts.append("{}{}".format(name, sev))
            line = "- **{}**：{}".format(date, "；".join(parts))
            extra = []
            if rec.get("duration"):
                extra.append("持续 {}".format(rec["duration"]))
            if rec.get("notes"):
                extra.append("备注：{}".format(rec["notes"]))
            fup = rec.get("followup")
            if isinstance(fup, dict) and fup:
                extra.append("追问：{}".format("；".join("{}：{}".format(q, a) for q, a in fup.items())))
            if extra:
                line += "（{}）".format("｜".join(extra))
            lines.append(line)
    lines.append("")

    # 二、用药清单
    lines.append("## 二、用药清单")
    lines.append("")
    if not meds:
        lines.append("暂无用药记录。")
    else:
        lines.append("| 药物 | 剂量 | 频次 | 开始日期 |")
        lines.append("|------|------|------|----------|")
        for m in meds:
            lines.append(
                "| {} | {} | {} | {} |".format(
                    m.get("name", ""), m.get("dosage", ""), m.get("frequency", ""), m.get("start_date", "")
                )
            )
    lines.append("")

    # 三、治疗方案
    lines.append("## 三、治疗方案")
    lines.append("")
    if not plans:
        lines.append("暂无治疗方案记录。")
    else:
        for p in plans:
            status = p.get("status", "未开始")
            box = "[x]" if status == "已执行" else ("[-]" if status == "进行中" else "[ ]")
            lines.append("- **诊断**：{}".format(p.get("diagnosis", "")))
            lines.append("  - 建议：{}".format(p.get("advice", "") or "无"))
            lines.append("  - 执行状态：{} {}".format(box, status))
            if p.get("follow_up_date"):
                lines.append("  - 复诊时间：{}".format(p["follow_up_date"]))
    lines.append("")

    # 四、待咨询医生的问题
    lines.append("## 四、待咨询医生的问题（占位）")
    lines.append("")
    lines.append("（请就诊前补充，例如：我的症状是否需要进一步检查？当前用药是否需要调整？）")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("> 免责声明：本报告由健康记录工具自动生成，内容仅供参考，不能替代专业医疗诊断。")
    lines.append("> 如出现剧烈疼痛、呼吸困难、胸痛、意识模糊、严重出血等紧急症状，请立即就医。")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="医生沟通报告生成")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    args = parser.parse_args()
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效（不能为空或含 / \\ : * ? \" < > | 等字符）。")
            return 1
    else:
        member = None

    print("=" * 50)
    print("医生沟通报告生成（成员：{}）".format(member or "默认档案"))
    print("=" * 50)
    report = build_report(member)
    print(report)
    output_path = common.path_for("health_report.md", member)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print("=" * 50)
    print("[确认] 报告已保存到：{}".format(output_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""病情录入向导：一问一答录入病情，自动追问、补充既往病情、选择档案、可视化分析与病情视图报告。

典型流程（交互模式）：
1. 询问是否开启多家人档案（首次使用；配置保存在 scripts/members_config.json）
2. 录入本次症状（可一次多个，逗号分隔）
3. 询问是否补充之前（更早的）病情，可回填真实发病日期
4. 追问情况（基于 references/followup_questions.json）
5. 选择本次病情添加到哪个档案
6. 保存记录
7. 给出可视化分析（图表 + 文本摘要）
8. 询问是否生成病情视图报告（HTML，自带图表）

用法：
    python intake.py                           # 交互向导（推荐）
    python intake.py --symptom 头痛 --severity 6 --member 妈妈   # 快速录入
    python intake.py --enable-multi            # 开启多家人档案
    python intake.py --disable-multi           # 关闭多家人档案
    python intake.py --list-members            # 查看已有档案
"""
import argparse
import json
import os
import sys

import common
from symptom_log import _build_record, load_log

REF_DIR = os.path.normpath(os.path.join(common.SCRIPT_DIR, "..", "references"))
FOLLOWUP_FILE = os.path.join(REF_DIR, "followup_questions.json")


def ask(prompt):
    """带提示符的输入函数，非交互环境返回空字符串。"""
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def ask_yes_no(prompt, default="n"):
    """询问是/否，返回 True/False；直接回车使用默认值。"""
    hint = "y/N" if default != "y" else "Y/n"
    while True:
        ans = ask("{} [{}]：".format(prompt, hint)).lower()
        if not ans:
            return default == "y"
        if ans in ("y", "yes", "是", "要", "对"):
            return True
        if ans in ("n", "no", "否", "不", "不要"):
            return False
        print("  请回答 是/否（或 y/n）。")


def ask_int(prompt, required=True):
    """询问整数；非必填时直接回车返回 None。"""
    while True:
        raw = ask(prompt)
        if not raw:
            if not required:
                return None
            print("  此项必填。")
            continue
        try:
            return int(raw)
        except ValueError:
            print("  请输入整数。")


_ANCHORS_SHOWN = [False]


def ask_severity(prompt):
    """询问严重程度 1-10（带客观锚点），非法输入会重新提问。"""
    if not _ANCHORS_SHOWN[0]:
        _ANCHORS_SHOWN[0] = True
        try:
            with open(os.path.join(REF_DIR, "severity_scale.json"), "r", encoding="utf-8") as f:
                scale = json.load(f)
            anchors = scale.get("verbal_scale", [])
        except (OSError, json.JSONDecodeError):
            anchors = []
        if anchors:
            print("--- 难受程度客观参考 ---")
            for a in anchors:
                print("  {} = {}".format(a.get("score"), a.get("label")))
    while True:
        raw = ask(prompt)
        if not raw:
            print("  此项必填。")
            continue
        try:
            value = int(raw)
        except ValueError:
            print("  请输入整数。")
            continue
        if 1 <= value <= 10:
            return value
        print("  严重程度必须是 1-10 的整数，请重新输入。")


def load_followups():
    """读取追问问题模板，返回 {"generic": [...], "symptoms": {...}}。"""
    try:
        with open(FOLLOWUP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"generic": [], "symptoms": {}}
        data.setdefault("generic", [])
        data.setdefault("symptoms", {})
        return data
    except (OSError, json.JSONDecodeError):
        return {"generic": [], "symptoms": {}}


def collect_entries():
    """录入本次症状，返回记录字典列表（未保存）。"""
    entries = []
    print("--- 录入本次症状（可一次输入多个，用逗号分隔；直接回车结束） ---")
    while True:
        symptom_text = ask("症状名称（如：头痛 或 头痛,恶心）：")
        if not symptom_text:
            if entries:
                break
            print("  至少需要录入一个症状。")
            continue
        severity = ask_severity("严重程度（1-10，必填）：")
        date_value = ask("发病日期（可留空=今天，如 2026-08-10）：")
        duration = ask("持续时长（如：2天 / 1周，可留空）：")
        notes = ask("备注（如：诱因、缓解方式，可留空）：")
        if severity >= 5:
            impact = ask("是否影响睡眠/工作/饮食？（可留空，如：影响睡眠）：")
            trend = ask("和之前比：好转/平稳/加重？（可留空）：")
            extra = []
            if impact:
                extra.append("影响：{}".format(impact))
            if trend:
                extra.append("趋势：{}".format(trend))
            if extra:
                notes = (notes + "；" if notes else "") + "；".join(extra)
        names = common.split_symptoms(symptom_text)
        for name in names:
            entries.append(_build_record(name, severity, duration, notes, date_value))
        print("  已记录：{}。可继续录入下一个症状，或直接回车结束。".format("、".join(names)))
    return entries


def collect_previous(entries):
    """询问是否补充之前（更早）的病情，是则继续录入并追加到 entries。"""
    if not ask_yes_no("是否需要补充之前（更早）的病情？", default="n"):
        return
    print("--- 补充既往病情（发病日期建议填真实日期） ---")
    while True:
        symptom_text = ask("既往症状名称（如：头晕；直接回车结束）：")
        if not symptom_text:
            break
        severity = ask_severity("当时严重程度（1-10，必填）：")
        date_value = ask("发病日期（必填，如 2026-07-15）：")
        if not date_value:
            print("  补充既往病情需要填写发病日期，便于时间线排序。")
            continue
        duration = ask("持续时长（可留空）：")
        notes = ask("备注（可留空）：")
        for name in common.split_symptoms(symptom_text):
            entries.append(_build_record(name, severity, duration, notes, date_value))
        print("  已补充：{}。可继续录入，或直接回车结束。".format(symptom_text))


def run_followups(entries):
    """基于 followup_questions.json 对每个症状追问情况，答案写入记录 followup 字段。"""
    templates = load_followups()
    generic = templates.get("generic", [])
    specific = templates.get("symptoms", {})
    print("--- 追问情况（每项直接回车可跳过，最多追问 9 题） ---")
    asked = 0
    for rec in entries:
        if asked >= 9:
            print("  （追问已达上限，其余记录不再追问）")
            break
        name = rec.get("symptom", "")
        if not name:
            continue
        qs = specific.get(name, [])[:3]
        if not qs:
            qs = generic[:2]
        answers = {}
        for q in qs:
            if asked >= 9:
                break
            ans = ask("【{}】{}：".format(name, q))
            if ans:
                answers[q] = ans
            asked += 1
        if answers:
            rec["followup"] = answers
    print("  追问完成。")


def save_records(entries, member=None):
    """把多条记录追加保存到指定成员档案。"""
    if not entries:
        print("[提示] 没有可保存的记录。")
        return
    records = load_log(member)
    before = len(records)
    records.extend(entries)
    path = common.path_for("health_log.json", member)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    who = member or "默认档案"
    print("=" * 50)
    print("[确认] 本次共保存 {} 条记录（成员：{}，累计 {} 条）。".format(len(entries), who, before + len(entries)))
    print("  保存位置：{}".format(path))
    print("=" * 50)


def check_red_flags(entries):
    """检查记录：命中「紧急症状」或严重程度 ≥9 → 立即就医；命中「警惕症状」→ 建议尽快就医/观察。"""
    red_flag_file = os.path.join(REF_DIR, "red_flag_symptoms.json")
    urgent, watch = [], []
    try:
        with open(red_flag_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            urgent = data.get("紧急症状", []) or []
            watch = data.get("警惕症状", []) or []
    except (OSError, json.JSONDecodeError):
        pass
    urgent_hit, watch_hit = set(), set()
    for rec in entries:
        sev = rec.get("severity")
        try:
            if sev is not None and int(sev) >= 9:
                urgent_hit.add("严重程度达到 9-10（无法忍受）")
        except (TypeError, ValueError):
            pass
        name = rec.get("symptom", "")
        for f in urgent:
            if f and (f in name or name in f):
                urgent_hit.add(f)
        for f in watch:
            if f and (f in name or name in f):
                watch_hit.add(f)
    if urgent_hit:
        print("=" * 50)
        print("[紧急提醒] 请立即就医（拨打 120 或前往急诊）：")
        for h in sorted(urgent_hit):
            print("  - {}".format(h))
        print("=" * 50)
    elif watch_hit:
        print("-" * 50)
        print("[注意] 以下症状建议尽快（1-2 天内）就医或密切观察，不必恐慌：")
        for h in sorted(watch_hit):
            print("  - {}".format(h))
        print("  若持续加重或出现紧急情况，请立即就医。")
        print("-" * 50)

def choose_member():
    """开启多家人档案时选择档案：已有档案 / 新建 / 默认档案。"""
    members = common.list_members()
    print("--- 本次病情添加到哪个档案？ ---")
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


def _extract(rec):
    """从一条记录中提取 (症状名, 严重程度) 列表（兼容两种数据结构）。"""
    items = rec.get("symptoms")
    if isinstance(items, list) and items:
        return [(it.get("name"), it.get("severity")) for it in items if it.get("name")]
    name = rec.get("symptom")
    if name:
        return [(name, rec.get("severity"))]
    return []


def run_visualization(member=None):
    """生成图表并打印文本分析摘要；matplotlib 不可用时只打印文本摘要。"""
    records = load_log(member)
    who = member or "默认档案"
    print("=" * 50)
    print("可视化分析（{}）".format(who))
    print("=" * 50)
    if not records:
        print("  暂无记录，先录入数据后再分析。")
        return

    stats = {}
    for rec in records:
        day = str(rec.get("date", ""))[:10]
        for name, sev in _extract(rec):
            item = stats.setdefault(name, {"count": 0, "sevs": [], "last": day})
            item["count"] += 1
            if sev is not None:
                item["sevs"].append(sev)
            if day and day > item["last"]:
                item["last"] = day

    print("【症状统计】")
    if not stats:
        print("  无")
    else:
        for name, item in sorted(stats.items(), key=lambda kv: -kv[1]["count"])[:8]:
            avg = ""
            if item["sevs"]:
                avg = "，平均严重程度 {:.1f}/10".format(sum(item["sevs"]) / len(item["sevs"]))
            print("  {}：{} 次{}，最近 {}".format(name, item["count"], avg, item["last"] or "未知"))
    print("")

    try:
        import charts
        charts._setup_chinese_font()
        generated = []
        p1 = charts.plot_symptom_frequency(records, member)
        p2 = charts.plot_severity_trend(records, member)
        generated.extend(x for x in (p1, p2) if x)
        if generated:
            print("【图表已生成】")
            for p in generated:
                print("  " + p)
        else:
            print("【图表】数据不足，未生成 PNG（文本摘要见上）。")
    except ImportError:
        print("【图表】未安装 matplotlib，跳过 PNG 图表（可运行：pip install matplotlib）。")
    except Exception as e:
        print("【图表】生成失败：{}".format(e))
    print("免责声明：以上分析仅供参考，不能替代专业医疗诊断。")


def run_report(member=None):
    """生成病情视图报告（HTML）。"""
    try:
        import condition_report
    except Exception as e:
        print("病情视图报告生成失败：{}".format(e))
        return
    path = condition_report.build_report(member, include_charts=True)
    print("病情视图报告已生成：{}".format(path))
    print("在资源管理器中找到该 HTML 文件，双击即可在浏览器查看。")


def interactive():
    print("=" * 50)
    print("病情录入向导（Health Condition Tracker）")
    print("=" * 50)
    cfg = common.load_config()
    multi = cfg.get("multi_member", False)
    if not multi:
        if ask_yes_no("是否开启多家人档案（多个家人分别建档）？", default="n"):
            common.set_multi_member(True)
            multi = True
            print("  已开启多家人档案。之后录入时会询问添加到哪个档案。")
        else:
            print("  保持默认档案（所有记录保存在默认档案）。")
    print("")

    entries = collect_entries()
    if not entries:
        print("[提示] 未录入任何症状，已退出。")
        return 0
    collect_previous(entries)
    run_followups(entries)

    member = None
    if multi:
        member = choose_member()
        if member:
            common.register_member(member)

    save_records(entries, member)
    check_red_flags(entries)
    run_visualization(member)
    if ask_yes_no("是否生成病情视图报告（HTML）？", default="n"):
        run_report(member)
    print("完成。隔几周或有新病情时，随时回来再走一遍向导即可。")
    return 0


def quick(args):
    """非交互快速录入：一条命令保存症状，并给出可视化分析与可选视图报告。"""
    member = None
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效（不能为空或含 / \\ : * ? \" < > | 等字符）。")
            return 1
    if not 1 <= args.severity <= 10:
        print("[错误] 严重程度必须是 1-10 的整数。")
        return 1
    names = common.split_symptoms(args.symptom)
    if not names:
        print("[错误] 症状名称不能为空。")
        return 1
    records = [
        _build_record(name, args.severity, args.duration or "", args.notes or "", args.date or None)
        for name in names
    ]
    save_records(records, member)
    check_red_flags(records)
    run_visualization(member)
    if args.report:
        run_report(member)
    return 0


def main():
    parser = argparse.ArgumentParser(description="病情录入向导：录入 + 追问 + 选档案 + 可视化 + 视图报告")
    parser.add_argument("--symptom", help="症状名称（快速录入）")
    parser.add_argument("--severity", type=int, help="严重程度 1-10（快速录入）")
    parser.add_argument("--date", default="", help="发病日期（默认现在）")
    parser.add_argument("--duration", default="", help="持续时长")
    parser.add_argument("--notes", default="", help="备注")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    parser.add_argument("--report", action="store_true", help="快速录入后生成病情视图报告")
    parser.add_argument("--enable-multi", action="store_true", help="开启多家人档案")
    parser.add_argument("--disable-multi", action="store_true", help="关闭多家人档案")
    parser.add_argument("--list-members", action="store_true", help="查看已有档案")
    args = parser.parse_args()

    if args.enable_multi:
        common.set_multi_member(True)
        print("[确认] 已开启多家人档案。录入病情时会询问添加到哪个档案。")
        return 0
    if args.disable_multi:
        common.set_multi_member(False)
        print("[确认] 已关闭多家人档案。之后记录都保存到默认档案。")
        return 0
    if args.list_members:
        members = common.list_members()
        cfg = common.load_config()
        print("多家人档案：{}".format("开启" if cfg.get("multi_member") else "关闭"))
        if members:
            print("已有档案：{}".format("、".join(members)))
        else:
            print("暂未建立档案。")
        return 0
    if args.symptom and args.severity is not None:
        return quick(args)
    return interactive()


if __name__ == "__main__":
    sys.exit(main())

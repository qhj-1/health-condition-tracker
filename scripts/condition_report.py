# -*- coding: utf-8 -*-
"""病情视图报告生成工具：把健康记录、用药、治疗方案与图表汇总成一份自带图表的 HTML 报告。

用法：
    python condition_report.py                     # 默认档案
    python condition_report.py --member 妈妈       # 指定成员
    python condition_report.py --days 90           # 只统计最近 90 天
    python condition_report.py --no-charts         # 不生成/不嵌入图表

输出：members/<成员名>/condition_report.html（或 scripts/condition_report.html），
图表以 base64 内嵌，离线可打开。
"""
import argparse
import base64
import html
import json
import os
import sys
from datetime import datetime, timedelta

import common

REFERENCES_DIR = os.path.normpath(os.path.join(common.SCRIPT_DIR, "..", "references"))
DEPARTMENT_FILE = os.path.join(REFERENCES_DIR, "department_map.json")
VITALS_RANGES_FILE = os.path.join(REFERENCES_DIR, "vitals_ranges.json")


def _load_ref_json(filename):
    """读取 references 下的 JSON 辅助数据，失败返回空字典。"""
    path = os.path.join(REFERENCES_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


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


def _fmt_number(value):
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


def _trend(sevs):
    """根据严重程度序列返回趋势箭头：升 ↑ / 降 ↓ / 平稳 →（不足 3 点返回空）。"""
    vals = [s for s in sevs if s is not None]
    if len(vals) < 3:
        return ""
    first, last = vals[0], vals[-1]
    if last - first > 0.5:
        return " ↑"
    if first - last > 0.5:
        return " ↓"
    return " →"


def _severity_badge(sev):
    if sev is None or sev == "":
        return "<span class='badge muted'>未评分</span>"
    s = html.escape(_fmt_number(sev))
    try:
        n = float(sev)
        level = "low" if n <= 3 else ("mid" if n <= 6 else "high")
    except (TypeError, ValueError):
        level = "muted"
    return "<span class='badge {}'>严重度 {}/10</span>".format(level, s)


def _embed_images(member, include_charts):
    """生成并读取图表 PNG，返回 (images_html, note)。"""
    if not include_charts:
        return "", "（未启用图表）"
    try:
        import charts
        charts._setup_chinese_font()
        records = _load_list("health_log.json", member)
        paths = []
        p = charts.plot_symptom_frequency(records, member)
        if p:
            paths.append(p)
        p = charts.plot_severity_trend(records, member)
        if p:
            paths.append(p)
        paths.extend(charts.plot_vitals(_load_list("vitals.json", member), member))
    except ImportError:
        return "", "（未安装 matplotlib，未嵌入图表；可运行 pip install matplotlib 后重试）"
    except Exception as e:
        return "", "（图表生成失败：{}）".format(e)
    if not paths:
        return "", "（数据不足，未生成图表）"
    blocks = []
    for p in paths:
        try:
            with open(p, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            blocks.append(
                "<figure><img src='data:image/png;base64,{}' alt='{}'><figcaption>{}</figcaption></figure>".format(
                    b64, html.escape(os.path.basename(p)), html.escape(os.path.basename(p))
                )
            )
        except OSError:
            continue
    return "<div class='charts'>" + "".join(blocks) + "</div>", ""


def build_report(member=None, days=None, include_charts=True, output_name="condition_report.html", extra_notes=""):
    """生成病情视图报告 HTML 并保存，返回文件路径。"""
    who = member if member else "默认档案"
    logs = _load_list("health_log.json", member)
    meds = _load_list("medications.json", member)
    plans = _load_list("treatment_plans.json", member)
    vitals = _load_list("vitals.json", member)

    def key(rec):
        d = common.parse_date(rec.get("date"))
        return d if d is not None else datetime.min

    logs_sorted = sorted(logs, key=key)
    if days:
        cutoff = datetime.now().date() - timedelta(days=days)
        logs_sorted = [r for r in logs_sorted if key(r).date() >= cutoff]

    stats = {}
    for rec in logs_sorted:
        day = str(rec.get("date", ""))[:10]
        for name, sev in _extract(rec):
            item = stats.setdefault(name, {"count": 0, "sevs": [], "last": day})
            item["count"] += 1
            if sev is not None:
                item["sevs"].append(sev)
            if day and day > item["last"]:
                item["last"] = day

    active_meds = [m for m in meds if not m.get("end_date")]
    pending_plans = [p for p in plans if p.get("status") != "已执行" and p.get("follow_up_date")]

    first_day = str(logs_sorted[0].get("date", ""))[:10] if logs_sorted else "—"
    last_day = str(logs_sorted[-1].get("date", ""))[:10] if logs_sorted else "—"
    span = ""
    if logs_sorted and first_day != last_day:
        span = "{} 至 {}".format(first_day, last_day)
    elif last_day != "—":
        span = last_day

    # 时间线（最新在前）
    timeline_items = []
    for rec in reversed(logs_sorted):
        date = html.escape(str(rec.get("date", "")))
        names = _extract(rec)
        if not names:
            continue
        parts = []
        for name, sev in names:
            parts.append("{} {}".format(html.escape(name), _severity_badge(sev)))
        badge_html = "".join(parts)
        extra = []
        if rec.get("duration"):
            extra.append("持续：{}".format(html.escape(str(rec["duration"]))))
        if rec.get("notes"):
            extra.append("备注：{}".format(html.escape(str(rec["notes"]))))
        fup = rec.get("followup")
        if isinstance(fup, dict) and fup:
            fup_txt = "；".join("{}：{}".format(html.escape(q), html.escape(str(a))) for q, a in fup.items())
            extra.append("追问：{}".format(fup_txt))
        extra_html = ""
        if extra:
            extra_html = "<div class='tl-extra'>" + "<br>".join(extra) + "</div>"
        timeline_items.append("<li><div class='tl-date'>{}</div>{}{}</li>".format(date, badge_html, extra_html))

    # 症状统计表
    stats_rows = []
    for name, item in sorted(stats.items(), key=lambda kv: -kv[1]["count"]):
        avg = "—"
        if item["sevs"]:
            avg = "{:.1f}".format(sum(item["sevs"]) / len(item["sevs"]))
        stats_rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(name), item["count"], avg, item["last"] or "—", _trend(item["sevs"])
            )
        )

    # 体征表
    vital_rows = []
    for rec in vitals:
        date = html.escape(str(rec.get("date", ""))[:10])
        cells = [date]
        for k in ("体重", "体温", "心率", "血压", "血糖", "血氧"):
            v = rec.get(k, "")
            cells.append(html.escape(str(v)) if v not in (None, "") else "—")
        vital_rows.append("<tr>" + "".join("<td>{}</td>".format(c) for c in cells) + "</tr>")

    # 用药表
    med_rows = []
    for m in meds:
        med_rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(m.get("name", ""))),
                html.escape(str(m.get("dosage", ""))),
                html.escape(str(m.get("frequency", ""))),
                html.escape(str(m.get("start_date", ""))),
                html.escape(str(m.get("end_date", ""))) if m.get("end_date") else "进行中",
            )
        )

    # 治疗方案
    plan_items = []
    for p in plans:
        status = p.get("status", "未开始")
        plan_items.append(
            "<li><b>{}（{}）</b><br>建议：{}<br>复诊：{}<br>状态：{}</li>".format(
                html.escape(str(p.get("diagnosis", ""))),
                html.escape(status),
                html.escape(str(p.get("advice", "") or "无")),
                html.escape(str(p.get("follow_up_date", "") or "未安排")),
                html.escape(status),
            )
        )

    images_html, chart_note = _embed_images(member, include_charts)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    h = []
    h.append("<!DOCTYPE html>")
    h.append('<html lang="zh-CN">')
    h.append("<head>")
    h.append('<meta charset="UTF-8">')
    h.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    h.append("<title>病情视图报告 - {} - {}</title>".format(html.escape(who), generated_at))
    h.append("<style>")
    h.append("body{font-family:'Microsoft YaHei','PingFang SC',sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#222;background:#f6f8fa;}")
    h.append("h1{font-size:24px;} .sub{color:#666;font-size:13px;margin-bottom:18px;}")
    h.append(".cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:22px;}")
    h.append(".card{background:#fff;border:1px solid #dfe3e8;border-radius:10px;padding:12px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,.05);}")
    h.append(".card b{display:block;font-size:22px;color:#1f4e79;} .card span{font-size:12px;color:#666;}")
    h.append("h2{font-size:17px;color:#1f4e79;border-left:4px solid #1f4e79;padding-left:8px;margin:26px 0 10px;}")
    h.append("table{width:100%;border-collapse:collapse;background:#fff;font-size:13px;}")
    h.append("th,td{border:1px solid #e3e6ea;padding:7px 9px;text-align:left;} th{background:#eef3fa;}")
    h.append(".timeline{list-style:none;margin:0;padding:0;}")
    h.append(".timeline li{position:relative;border-left:2px solid #4C78A8;margin:0 0 14px 8px;padding:2px 0 2px 16px;}")
    h.append(".tl-date{color:#888;font-size:12px;margin-bottom:2px;}")
    h.append(".tl-extra{color:#555;font-size:12.5px;margin-top:4px;}")
    h.append(".badge{display:inline-block;border-radius:10px;padding:1px 8px;font-size:12px;color:#fff;margin-left:6px;}")
    h.append(".badge.low{background:#5aa469;} .badge.mid{background:#e0a53a;} .badge.high{background:#d9534f;} .badge.muted{background:#9aa4af;}")
    h.append(".charts img{max-width:100%;border:1px solid #e3e6ea;border-radius:8px;margin:6px 0;background:#fff;}")
    h.append(".charts figure{margin:8px 0;} .charts figcaption{font-size:12px;color:#888;}")
    h.append(".note{background:#fff8e6;border:1px solid #f0d98c;border-radius:8px;padding:10px 14px;font-size:13px;color:#7a5c00;}")
    h.append("footer{margin-top:26px;font-size:12px;color:#888;}")
    h.append("</style>")
    h.append("</head>")
    h.append("<body>")
    h.append("<h1>病情视图报告</h1>")
    h.append('<div class="sub">成员：{} ｜ 生成时间：{} ｜ 统计范围：{}</div>'.format(html.escape(who), generated_at, html.escape(span)))
    h.append('<div class="cards">')
    h.append("<div class='card'><b>{}</b><span>记录条数</span></div>".format(len(logs_sorted)))
    h.append("<div class='card'><b>{}</b><span>症状种类</span></div>".format(len(stats)))
    h.append("<div class='card'><b>{}</b><span>进行中用药</span></div>".format(len(active_meds)))
    h.append("<div class='card'><b>{}</b><span>待复诊</span></div>".format(len(pending_plans)))
    h.append("<div class='card'><b>{}</b><span>最近记录</span></div>".format(last_day))
    h.append("</div>")

    # 趋势预警：严重程度呈上升趋势的症状
    warn_names = [n for n, it in stats.items() if _trend(it.get("sevs", [])) == " ↑"][:5]
    if warn_names:
        h.append("<p class='note'><b>趋势预警：</b>{} 呈加重趋势，建议优先关注或近期就诊。</p>".format(
            "、".join(html.escape(n) for n in warn_names)))

    h.append("<h2>一、症状统计</h2>")
    if stats_rows:
        h.append("<table><tr><th>症状</th><th>次数</th><th>平均严重度</th><th>最近出现</th><th>趋势</th></tr>" + "".join(stats_rows) + "</table>")
    else:
        h.append('<p class="note">暂无症状记录。</p>')

    h.append("<h2>二、症状时间线</h2>")
    if timeline_items:
        h.append('<ul class="timeline">' + "".join(timeline_items) + "</ul>")
    else:
        h.append('<p class="note">暂无症状记录。</p>')

    h.append("<h2>三、可视化图表</h2>")
    if images_html:
        h.append(images_html)
    else:
        h.append('<p class="note">{}。录入后生成图表再重新打开本报告即可看到。</p>'.format(html.escape(str(chart_note))))

    if vital_rows:
        h.append("<h2>四、体征记录</h2>")
        h.append("<table><tr><th>日期</th><th>体重</th><th>体温</th><th>心率</th><th>血压</th><th>血糖</th><th>血氧</th></tr>" + "".join(vital_rows) + "</table>")
        ranges = _load_ref_json("vitals_ranges.json")
        range_rows = []
        for k, v in ranges.items():
            if k in ("版本", "说明", "language", "_comment"):
                continue
            range_rows.append("<tr><td>{}</td><td>{}</td></tr>".format(html.escape(str(k)), html.escape(str(v))))
        if range_rows:
            h.append("<p class='note'><b>常见参考范围（非诊断标准）：</b></p>")
            h.append("<table><tr><th>指标</th><th>参考范围</th></tr>" + "".join(range_rows) + "</table>")

    h.append("<h2>五、用药清单</h2>")
    if med_rows:
        h.append("<table><tr><th>药物</th><th>剂量</th><th>频次</th><th>开始</th><th>结束</th></tr>" + "".join(med_rows) + "</table>")
    else:
        h.append('<p class="note">暂无用药记录。</p>')

    h.append("<h2>六、治疗方案</h2>")
    if plan_items:
        h.append('<ul class="timeline">' + "".join(plan_items) + "</ul>")
    else:
        h.append('<p class="note">暂无治疗方案记录。</p>')

    # 建议科室：按出现最多的症状查 department_map.json
    dept_map = _load_ref_json("department_map.json")
    dept_counts = {}
    for name in stats:
        for dep in dept_map.get(name, []):
            dept_counts[dep] = dept_counts.get(dep, 0) + 1
    h.append("<h2>七、建议科室（参考）</h2>")
    if dept_counts:
        ordered = sorted(dept_counts.items(), key=lambda kv: -kv[1])
        h.append("<ul class='timeline'>" + "".join(
            "<li>{}（关联症状 {} 种）</li>".format(html.escape(d), c) for d, c in ordered[:5]
        ) + "</ul>")
        h.append('<p class="note">科室仅为参考，请以当地医院分诊为准。</p>')
    else:
        h.append('<p class="note">暂无匹配的建议科室，可结合症状询问医生或全科门诊。</p>')

    h.append("<h2>八、建议下一步</h2>")
    notes_lines = ["就诊前请补充：是否建议进一步检查？当前用药是否需要调整？是否建议转诊专科？"]
    if extra_notes:
        notes_lines.append(extra_notes)
    h.append('<p class="note">' + " ".join(html.escape(str(x)) for x in notes_lines) + "</p>")

    h.append("<h2>九、待咨询医生的问题（占位）</h2>")
    h.append("<ul><li>我的症状是否需要进一步检查？</li><li>当前用药是否需要调整？</li><li>复诊前需要注意什么？</li></ul>")

    h.append('<p class="note">免责声明：本报告由健康记录工具自动生成，内容仅供参考，不能替代专业医疗诊断。如出现剧烈疼痛、呼吸困难、胸痛、意识模糊、严重出血等紧急症状，请立即就医。</p>')
    h.append("<footer>由 health-condition-tracker 技能生成 · 图表已内嵌，离线可查看</footer>")
    h.append("</body></html>")

    path = common.path_for(output_name, member)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(h))
    return path


def main():
    parser = argparse.ArgumentParser(description="病情视图报告（HTML）")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    parser.add_argument("--days", type=int, default=0, help="只统计最近 N 天（0=全部）")
    parser.add_argument("--no-charts", action="store_true", help="不生成/不嵌入图表")
    parser.add_argument("--output", default="", help="输出文件名（默认 condition_report.html）")
    parser.add_argument("--note", default="", help="追加到「建议下一步」的备注（如：建议检查血常规）")
    args = parser.parse_args()
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效（不能为空或含 / \\ : * ? \" < > | 等字符）。")
            return 1
    else:
        member = None
    if args.days < 0:
        print("[错误] --days 不能为负数。")
        return 1
    days = args.days or None
    path = build_report(member, days=days, include_charts=not args.no_charts, output_name=args.output or "condition_report.html", extra_notes=args.note)
    print("=" * 50)
    print("病情视图报告已生成：{}".format(path))
    print("双击该 HTML 文件即可在浏览器中查看（图表已内嵌，离线可用）。")
    print("免责声明：报告仅供参考，不能替代专业医疗诊断。")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())

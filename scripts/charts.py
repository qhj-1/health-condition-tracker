# -*- coding: utf-8 -*-
"""图表可视化工具：把健康记录画成 PNG 图表（症状频次条形图、严重程度趋势折线图、体征趋势图）。

依赖：matplotlib（pip install matplotlib），中文字体自动使用微软雅黑/黑体。

用法：
    python charts.py                        # 默认档案，全部图表
    python charts.py --member 妈妈          # 指定成员
    python charts.py --type symptoms        # 只画症状图表
    python charts.py --type vitals          # 只画体征图表（需要 vitals.json）
"""
import argparse
import json
import os
import sys

import common
from trend_analysis import extract_symptoms

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
except ImportError:
    plt = None
    font_manager = None


def _setup_chinese_font():
    if font_manager is None or plt is None:
        return
    for name in ("Microsoft YaHei", "SimHei", "SimSun", "PingFang SC", "Noto Sans CJK SC"):
        try:
            font_manager.findfont(name, fallback_to_default=False)
            plt.rcParams["font.sans-serif"] = [name]
            break
        except Exception:
            continue
    plt.rcParams["axes.unicode_minus"] = False


def _load_json(filename, member=None):
    path = common.path_for(filename, member)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _agg_symptoms(records):
    """按症状聚合，返回 {名称: {"count": int, "points": [(日期, 严重程度或None)]}}。"""
    stats = {}
    for rec in records:
        day = str(rec.get("date", ""))[:10]
        for name, sev in extract_symptoms(rec):
            item = stats.setdefault(name, {"count": 0, "points": []})
            item["count"] += 1
            item["points"].append((day, sev))
    return stats


def plot_symptom_frequency(records, member, top=10):
    stats = _agg_symptoms(records)
    if not stats:
        print("[提示] 无足够症状数据，跳过频次图。")
        return None
    items = sorted(stats.items(), key=lambda kv: -kv[1]["count"])[:top]
    names = [k for k, _ in items][::-1]
    counts = [v["count"] for _, v in items][::-1]
    fig, ax = plt.subplots(figsize=(8, max(3, len(names) * 0.5)))
    ax.barh(names, counts, color="#4C78A8")
    for i, c in enumerate(counts):
        ax.text(c + 0.1, i, str(c), va="center", fontsize=9)
    ax.set_xlabel("出现次数")
    ax.set_title("症状出现频次 TOP {}".format(len(names)))
    fig.tight_layout()
    path = common.path_for("chart_symptom_frequency.png", member)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_severity_trend(records, member, top=3):
    stats = _agg_symptoms(records)
    if not stats:
        print("[提示] 无足够症状数据，跳过趋势图。")
        return None
    items = sorted(stats.items(), key=lambda kv: -kv[1]["count"])[:top]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    plotted = False
    for name, item in items:
        pts = [(d, s) for d, s in item["points"] if s is not None]
        if len(pts) < 2:
            continue
        xs = list(range(len(pts)))
        ys = [p[1] for p in pts]
        labels = [p[0][5:] if p[0] else "" for p in pts]
        ax.plot(xs, ys, marker="o", label=name)
        if len(labels) == len(xs):
            ax.set_xticks(xs, labels, rotation=45, fontsize=8)
        plotted = True
    if not plotted:
        print("[提示] 严重程度数据不足，跳过趋势图。")
        plt.close(fig)
        return None
    ax.set_ylabel("严重程度（1-10）")
    ax.set_ylim(0, 10.5)
    ax.set_title("症状严重程度趋势")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = common.path_for("chart_severity_trend.png", member)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


import re as _re

_BP_RE = _re.compile(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)")


def _parse_bp(value):
    """把 '120/80' 或 '120/80 mmHg' 解析为 (收缩压, 舒张压)。"""
    if isinstance(value, str):
        m = _BP_RE.search(value)
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except (TypeError, ValueError):
                return None
    return None


def plot_vitals(vitals, member):
    if not vitals:
        print("[提示] 未找到 vitals.json（体征记录），跳过体征图。")
        return []
    series = {k: [] for k in ("体重", "体温", "心率", "血糖", "血氧")}
    bp_sys, bp_dia = [], []
    for rec in vitals:
        day = str(rec.get("date", ""))[:10]
        for key in series:
            val = rec.get(key)
            if val in (None, ""):
                continue
            try:
                series[key].append((day, float(val)))
            except (TypeError, ValueError):
                continue
        bp = _parse_bp(rec.get("血压", ""))
        if bp:
            bp_sys.append((day, bp[0]))
            bp_dia.append((day, bp[1]))
    plot_items = [(k, v) for k, v in series.items() if len(v) >= 2]
    if bp_sys:
        plot_items.append(("血压-收缩压", bp_sys))
        plot_items.append(("血压-舒张压", bp_dia))
    if not plot_items:
        print("[提示] 体征数据不足（每项至少 2 条），跳过体征图。")
        return []
    paths = []
    for key, pts in plot_items:
        fig, ax = plt.subplots(figsize=(8, 3.5))
        xs = list(range(len(pts)))
        ax.plot(xs, [p[1] for p in pts], marker="o")
        ax.set_xticks(xs, [p[0][5:] if p[0] else "" for p in pts], rotation=45, fontsize=8)
        ax.set_title("{}趋势".format(key))
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fname = "chart_vital_{}.png".format(key)
        path = common.path_for(fname, member)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description="健康图表可视化（PNG）")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    parser.add_argument("--type", choices=["symptoms", "vitals", "all"], default="all", help="图表类型")
    parser.add_argument("--top", type=int, default=10, help="频次图最多显示的症状数")
    args = parser.parse_args()
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效（不能为空或含 / \\ : * ? \" < > | 等字符）。")
            return 1
    else:
        member = None
    args.top = max(1, args.top)

    if plt is None:
        print("[错误] 缺少 matplotlib。请先安装：")
        print("    pip install matplotlib")
        return 1
    _setup_chinese_font()

    who = "成员：{}".format(member) if member else "默认档案"
    print("=" * 50)
    print("健康图表生成（{}）".format(who))
    print("=" * 50)

    generated = []
    if args.type in ("symptoms", "all"):
        records = _load_json("health_log.json", member)
        p1 = plot_symptom_frequency(records, member, args.top)
        p2 = plot_severity_trend(records, member)
        generated.extend(x for x in (p1, p2) if x)
    if args.type in ("vitals", "all"):
        generated.extend(plot_vitals(_load_json("vitals.json", member), member))

    if not generated:
        print("未生成任何图表（数据不足）。")
        return 1
    print("-" * 50)
    print("已生成 {} 张图表：".format(len(generated)))
    for p in generated:
        print("  " + p)
    print("免责声明：图表仅供参考，不能替代专业医疗诊断。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

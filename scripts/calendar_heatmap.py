# -*- coding: utf-8 -*-
"""日历热力图：把指定月份的每日症状严重程度画成日历热力图（PNG）。

依赖：matplotlib（pip install matplotlib）。

用法：
    python calendar_heatmap.py                     # 默认档案，本月
    python calendar_heatmap.py --member 妈妈       # 指定成员
    python calendar_heatmap.py --year 2026 --month 9
"""
import argparse
import calendar as cal
import json
import os
import sys
from datetime import date

import common
from trend_analysis import extract_symptoms

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib import colormaps
    from matplotlib.colors import Normalize
except ImportError:
    plt = None
    font_manager = None
    Normalize = None


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


def _load_records(member=None):
    path = common.path_for("health_log.json", member)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _daily_severity(records):
    """返回 {YYYY-MM-DD: 当日最大严重程度}。无严重程度但有症状记为 1。"""
    daily = {}
    for rec in records:
        day = str(rec.get("date", ""))[:10]
        if not day:
            continue
        for _, sev in extract_symptoms(rec):
            value = sev if sev is not None else 1
            daily[day] = max(daily.get(day, 0), float(value))
    return daily


def _month_grid(year, month):
    """返回 (weeks, day_positions)。weeks 为周一开头的周列表。"""
    _, days_in_month = cal.monthrange(year, month)
    weeks = []
    week = [0] * 7
    for day in range(1, days_in_month + 1):
        wd = date(year, month, day).weekday()
        week[wd] = day
        if wd == 6 or day == days_in_month:
            weeks.append(week)
            week = [0] * 7
    return weeks, days_in_month


def render_heatmap(year, month, member=None):
    weeks, days_in_month = _month_grid(year, month)
    daily = _daily_severity(_load_records(member))
    rows = len(weeks)
    data = [[0.0] * 7 for _ in range(rows)]
    labels = [[""] * 7 for _ in range(rows)]
    has_data = False
    for r, week in enumerate(weeks):
        for c, day in enumerate(week):
            if day == 0:
                continue
            key = "{:04d}-{:02d}-{:02d}".format(year, month, day)
            sev = daily.get(key, 0)
            if sev:
                has_data = True
            data[r][c] = sev
            labels[r][c] = str(day)

    fig, ax = plt.subplots(figsize=(10, 1.4 * rows + 1.6))
    cmap = colormaps["YlOrRd"].copy()
    cmap.set_under("#FFFFFF")
    im = ax.imshow(data, cmap=cmap, norm=Normalize(vmin=0.5, vmax=10), aspect="auto")
    ax.set_xticks(range(7))
    ax.set_xticklabels(["一", "二", "三", "四", "五", "六", "日"], fontsize=10)
    ax.set_yticks(range(rows))
    ax.set_yticklabels([""] * rows)
    for r in range(rows):
        for c in range(7):
            ax.text(c, r, labels[r][c], ha="center", va="center", fontsize=9,
                    color="black" if data[r][c] == 0 else "white")
    who = "成员：{}".format(member) if member else "默认档案"
    ax.set_title("{}年{}月 健康热力图（{}）".format(year, month, who), fontsize=13)
    if not has_data:
        ax.text(3, rows / 2 - 0.3, "该月无症状记录", ha="center", va="center",
                fontsize=12, color="#888888")
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("当日最大严重程度（1-10）")
    fig.tight_layout()
    path = common.path_for("calendar_heatmap_{:04d}-{:02d}.png".format(year, month), member)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path, has_data


def main():
    parser = argparse.ArgumentParser(description="日历热力图（PNG）")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    parser.add_argument("--year", type=int, default=0, help="年份，默认当前年")
    parser.add_argument("--month", type=int, default=0, help="月份 1-12，默认当前月")
    args = parser.parse_args()
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效（不能为空或含 / \\ : * ? \" < > | 等字符）。")
            return 1
    else:
        member = None

    if plt is None:
        print("[错误] 缺少 matplotlib。请先安装：")
        print("    pip install matplotlib")
        return 1
    _setup_chinese_font()

    today = date.today()
    year = args.year or today.year
    month = args.month or today.month
    if not 1 <= month <= 12:
        print("[错误] 月份必须是 1-12。")
        return 1

    path, has_data = render_heatmap(year, month, member)
    print("=" * 50)
    print("日历热力图已生成：{}".format(path))
    if not has_data:
        print("（该月没有症状记录，图中为空白月份）")
    print("免责声明：图表仅供参考，不能替代专业医疗诊断。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

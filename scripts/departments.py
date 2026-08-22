# -*- coding: utf-8 -*-
"""建议科室查询工具：按症状给出建议就诊科室；也可按成员历史症状统计推荐科室。

用法：
    python departments.py 头痛 发热
    python departments.py --member 妈妈
    python departments.py --member 妈妈 --days 90
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta

import common
from trend_analysis import extract_symptoms

REFERENCES_DIR = os.path.normpath(os.path.join(common.SCRIPT_DIR, "..", "references"))
DEPARTMENT_FILE = os.path.join(REFERENCES_DIR, "department_map.json")


def load_departments():
    """读取症状→科室映射，返回字典；失败返回空字典。"""
    try:
        with open(DEPARTMENT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _parse_date(value):
    return common.parse_date(value)


def query_departments(symptoms, dept_map):
    """给定症状列表，返回按出现症状数排序的科室列表 [(科室, 关联症状数)]。"""
    counts = {}
    for s in symptoms:
        s = str(s).strip()
        for dep in dept_map.get(s, []):
            counts[dep] = counts.get(dep, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])


def recommend_for_member(member, days=0):
    """按成员近期症状统计推荐科室，返回 (症状列表, 科室列表)。"""
    records = []
    path = common.path_for("health_log.json", member)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            records = data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            records = []
    cutoff = date.today() - timedelta(days=days) if days else None
    symptom_counts = {}
    for rec in records:
        d = _parse_date(rec.get("date"))
        if cutoff and (not d or d < cutoff):
            continue
        for name, _ in extract_symptoms(rec):
            symptom_counts[name] = symptom_counts.get(name, 0) + 1
    symptoms = sorted(symptom_counts, key=lambda k: -symptom_counts[k])
    return symptoms, query_departments(symptoms, load_departments())


def main():
    parser = argparse.ArgumentParser(description="建议就诊科室查询")
    parser.add_argument("symptoms", nargs="*", help="症状名称，如：头痛 发热")
    parser.add_argument("--member", default="", help="按成员近期症状统计推荐（如：妈妈）")
    parser.add_argument("--days", type=int, default=0, help="统计最近 N 天（0=全部）")
    args = parser.parse_args()

    if args.days < 0:
        print("[错误] --days 不能为负数。")
        return 1
    print("=" * 50)
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效。")
            return 1
        print("建议科室推荐（成员：{}，最近 {} 天）".format(member, args.days or "全部"))
        print("=" * 50)
        symptoms, depts = recommend_for_member(member, args.days)
        if not symptoms:
            print("该成员暂无症状记录。")
            return 0
        print("近期症状：{}".format("、".join(symptoms[:10])))
    else:
        print("建议科室查询")
        print("=" * 50)
        symptoms = args.symptoms
        if not symptoms:
            parser.print_help()
            return 1
        print("输入症状：{}".format("、".join(symptoms)))
        depts = query_departments(symptoms, load_departments())
    print("-" * 50)
    if not depts:
        print("未找到匹配科室，建议先看全科门诊，由医生分诊。")
    else:
        print("建议科室（按关联症状数排序）：")
        for i, (dep, n) in enumerate(depts[:6], 1):
            print("  {}. {}（关联 {} 种症状）".format(i, dep, n))
    print("免责声明：科室仅为参考，请以当地医院分诊为准。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""回归测试：100 组正常人数据 + 16 组边界情况（缺省/组合），验证风险分级符合一般人体感。

用法：
    python scripts/self_test.py              # 运行全部
    python scripts/self_test.py --show       # 同时打印失败详情
    python scripts/self_test.py --only 100   # 只跑 100 组正常人
    python scripts/self_test.py --only edge  # 只跑边界情况

说明：
- 数据：tests/normal_cases_100.json（症状/严重度/病程/趋势 + 期望档位）
        tests/edge_cases.json（缺严重度/缺病程/多症状组合 + 期望档位）
- 期望档位由「符合一般人」规则生成：轻度短期→低；超国际指南时长→中（好转中除外）；
  7-8 分或加重→中危；真急症/≥9 分→紧急；组合升级需 ≥6 分；慢性稳定自动降级。
- 全部通过返回 0，有失败返回 1。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import analyze

TESTS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests"))
FILES = {
    "100": "normal_cases_100.json",
    "edge": "edge_cases.json",
}


def _symptoms_of(case):
    if isinstance(case.get("symptoms"), list) and case["symptoms"]:
        return case["symptoms"]
    return [case.get("symptom", "")]


def main():
    parser = argparse.ArgumentParser(description="风险分级回归测试")
    parser.add_argument("--show", action="store_true", help="打印失败详情")
    parser.add_argument("--only", default="", choices=list(FILES.keys()) + [""], help="只跑指定数据集：100 / edge")
    args = parser.parse_args()

    files = {k: v for k, v in FILES.items() if not args.only or k == args.only}
    total_pass = 0
    total_all = 0
    all_failed = []
    for key, fname in files.items():
        path = os.path.join(TESTS_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            cases = json.load(f)
        passed = 0
        failed = []
        for case in cases:
            try:
                result = analyze(
                    _symptoms_of(case),
                    severity=case.get("severity"),
                    duration_days=case.get("duration_days"),
                    trend=case.get("trend", ""),
                )
                got = result["risk"]["level"]
            except Exception as e:
                got = "异常：" + str(e)
            if got == case["expected"]:
                passed += 1
            else:
                failed.append({
                    "id": case["id"], "symptoms": _symptoms_of(case),
                    "severity": case.get("severity"), "days": case.get("duration_days"),
                    "trend": case.get("trend", ""), "expected": case["expected"], "got": got,
                    "note": case.get("note", ""),
                })
        total_pass += passed
        total_all += len(cases)
        all_failed.extend(failed)
        print("[{}] 通过 {}/{}".format(key, passed, len(cases)))
        if failed and args.show:
            for x in failed[:15]:
                print("    [{}] {} sev={} days={} trend={}：期望 {}，实际 {}".format(
                    x["id"], "+".join(x["symptoms"]), x["severity"], x["days"], x["trend"], x["expected"], x["got"]))

    print("=" * 60)
    print("回归测试总计：通过 {}/{}（{:.1f}%）".format(total_pass, total_all, total_pass * 100.0 / total_all))
    if all_failed:
        print("失败 {} 组；如期望与实际不一致，请检查 analyze.py 或重新生成测试期望。".format(len(all_failed)))
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

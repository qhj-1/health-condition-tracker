# -*- coding: utf-8 -*-
"""长期趋势分析工具：读取 health_log.json，分析症状出现频率与严重程度变化趋势（支持多家人档案）。

兼容三种记录格式：
1. 记录含 "symptoms" 列表，元素为 {"name": ..., "severity": ...}
2. 记录含 "questionnaire_responses"，键为症状，值为 True 或非否定字符串视为出现
3. 记录直接含 "symptom" 与 "severity" 字段（symptom_log.py 保存的格式）
"""
import argparse
import json
import os
import sys

import common

# 表示"未出现该症状"的回答
_NEGATIVE_WORDS = {"否", "无", "没有", "未出现", "未见", "不", "false", "no", "不是"}


def load_log(member=None):
    """读取指定成员的健康日志，返回记录列表；文件不存在或损坏时返回空列表。"""
    path = common.path_for("health_log.json", member)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _to_number(value):
    """尽力把严重程度转换为数值，失败返回 None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_positive(value):
    """判断问卷回答是否表示"出现该症状"。True 或非否定、非空白的字符串视为出现。"""
    if value is True:
        return True
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return False
        if s in _NEGATIVE_WORDS or s.startswith("无"):
            return False
        return True
    return False


def extract_symptoms(record):
    """从单条记录中提取 (症状名, 严重程度或None) 列表。"""
    if not isinstance(record, dict):
        return []
    result = []
    symptoms = record.get("symptoms")
    if isinstance(symptoms, list):
        for item in symptoms:
            if isinstance(item, dict) and item.get("name"):
                result.append((str(item["name"]), _to_number(item.get("severity"))))
        return result
    responses = record.get("questionnaire_responses")
    if isinstance(responses, dict):
        for key, value in responses.items():
            if _is_positive(value):
                result.append((str(key), None))
        return result
    if record.get("symptom"):
        result.append((str(record["symptom"]), _to_number(record.get("severity"))))
    return result


def analyze_trend(records):
    """按症状聚合统计（时间加权：最近 7 天权重更高），返回统计字典。"""
    from datetime import date, datetime
    stats = {}
    today = date.today()
    for record in records:
        weight = 1.0
        d = None
        try:
            d = datetime.strptime(str(record.get("date", ""))[:10], "%Y-%m-%d").date()
        except ValueError:
            d = None
        if d is not None:
            age = (today - d).days
            if age < 7:
                weight = 2.0
            elif age < 30:
                weight = 1.5
        for name, severity in extract_symptoms(record):
            item = stats.setdefault(name, {"count": 0, "severities": [], "recent7": 0, "prior": 0})
            item["count"] += 1
            if d is not None and age < 7:
                item["recent7"] += 1
            else:
                item["prior"] += 1
            if severity is not None:
                item["severities"].append(severity)
    return stats


def _fmt(value):
    """格式化数值：整数不带小数点。"""
    return str(int(value)) if value.is_integer() else "{:.1f}".format(value)


def _trend_label(severities):
    """根据严重程度序列计算趋势。数据不足 3 次时返回 None。"""
    if len(severities) < 3:
        return None
    half = len(severities) // 2
    first_avg = sum(severities[:half]) / half
    second_avg = sum(severities[half:]) / (len(severities) - half)
    diff = second_avg - first_avg
    if diff >= 0.5:
        trend = "上升（加重）"
    elif diff <= -0.5:
        trend = "下降（减轻）"
    else:
        trend = "稳定"
    return trend, first_avg, second_avg


def build_report(records):
    """生成中文趋势报告文本。"""
    if not records:
        return "暂无足够数据：health_log.json 中没有记录。"
    stats = analyze_trend(records)
    if not stats:
        return "暂无足够数据：未能从记录中提取到症状信息。"
    lines = ["=" * 50, "健康趋势分析报告", "=" * 50]
    if len(records) > 1:
        lines.append("共分析 {} 条记录。".format(len(records)))
    for name, item in sorted(stats.items(), key=lambda kv: (-kv[1]["count"], kv[0])):
        severities = item["severities"]
        recent = "，近 7 天 {} 次（此前 {} 次）".format(item["recent7"], item["prior"]) if item["recent7"] else ""
        if len(severities) < 3:
            lines.append("· {}：出现 {} 次（无严重程度数据）{}".format(name, item["count"], recent))
            continue
        trend, first_avg, second_avg = _trend_label(severities)
        lines.append(
            "· {}：出现 {} 次，平均严重程度从 {} 变为 {}，趋势：{}{}".format(
                name, item["count"], _fmt(first_avg), _fmt(second_avg), trend, recent
            )
        )
    lines.append("-" * 50)
    lines.append("免责声明：以上内容仅供参考，不能替代专业医疗诊断。")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="症状趋势与指标变化分析")
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
    print("健康趋势分析（成员：{}）".format(member or "默认档案"))
    print("=" * 50)
    records = load_log(member)
    print(build_report(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())

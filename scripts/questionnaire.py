# -*- coding: utf-8 -*-
"""问卷工具：读取 references/questionnaire.json 并打印问卷结构，供分析使用。"""
import json
import os
import sys

REFERENCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references")
QUESTIONNAIRE_FILE = os.path.join(REFERENCES_DIR, "questionnaire.json")


def load_questionnaire():
    """读取问卷 JSON，返回字典；失败时返回空字典并打印中文提示。"""
    try:
        with open(QUESTIONNAIRE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print("[错误] 无法读取问卷文件 {}：{}".format(QUESTIONNAIRE_FILE, e))
        return {}


def print_questionnaire_structure(data=None):
    """按类别打印所有问题。data 为 load_questionnaire() 的返回值。"""
    data = data if data else load_questionnaire()
    if not data:
        print("暂无问卷数据。")
        return
    categories = data.get("categories", {})
    if not categories:
        print("问卷结构中没有 categories 字段。")
        return
    total = 0
    for cat_id, cat in categories.items():
        name = cat.get("name", cat_id)
        questions = cat.get("questions", [])
        total += len(questions)
        print("-" * 50)
        print("[{}] {}（{} 条）".format(cat_id, name, len(questions)))
        for q in questions:
            print("  - {} [{}] {}".format(q.get("id", "?"), q.get("type", "?"), q.get("question", "")))
    print("-" * 50)
    print("共 {} 个类别，{} 个问题。".format(len(categories), total))


def main():
    print("=" * 50)
    print("健康问卷结构")
    print("=" * 50)
    print_questionnaire_structure()
    return 0


if __name__ == "__main__":
    sys.exit(main())

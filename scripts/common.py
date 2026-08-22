# -*- coding: utf-8 -*-
"""公共工具模块：提供多家人档案的数据目录、文件路径解析与配置管理。

目录约定：
- 未指定成员时，数据保存在 scripts/ 目录（兼容旧版单用户）。
- 指定成员时，数据保存在 scripts/members/<成员名>/ 目录。

多家人档案配置保存在 scripts/members_config.json：
- multi_member: 是否开启多家人档案（True/False）
- members: 已登记成员名单
成员基础信息（可选）保存在 members/<成员名>/profile.json。
"""
import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = "members_config.json"

_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')


def sanitize_member(name):
    """清洗成员名，防止路径穿越与非法字符（如 ../ 或含 \\ / : * ? " < > |）。

    返回清洗后的名称；非法（为空）返回 None。
    """
    if not name:
        return None
    name = _INVALID_CHARS.sub("_", str(name).strip())
    name = name.replace("..", "_")
    name = name.strip(" ._")
    return name or None


def data_dir(member=None):
    """返回成员数据目录；member 为空或清洗后无效时返回脚本目录，
    否则创建并返回 members/<成员名>（成员名会自动清洗，防止路径穿越）。"""
    if member:
        clean = sanitize_member(member)
        if clean:
            d = os.path.join(SCRIPT_DIR, "members", clean)
            os.makedirs(d, exist_ok=True)
            return d
    return SCRIPT_DIR


def path_for(filename, member=None):
    """返回数据文件在指定成员目录下的完整路径。"""
    return os.path.join(data_dir(member), filename)


def config_path():
    """多家人档案配置文件路径。"""
    return os.path.join(SCRIPT_DIR, CONFIG_FILE)


def load_config():
    """读取多家人档案配置；文件不存在或损坏时返回默认配置。"""
    default = {"multi_member": False, "members": []}
    if not os.path.exists(config_path()):
        return default
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default
        data.setdefault("multi_member", False)
        data.setdefault("members", [])
        return data
    except (OSError, json.JSONDecodeError):
        return default


def save_config(config):
    """保存多家人档案配置。"""
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def set_multi_member(enabled):
    """开启/关闭多家人档案，返回更新后的配置。"""
    cfg = load_config()
    cfg["multi_member"] = bool(enabled)
    save_config(cfg)
    return cfg


def register_member(name):
    """把成员名登记到配置的 members 列表（清洗并去重），返回更新后的配置。"""
    name = sanitize_member(name)
    if not name:
        return load_config()
    cfg = load_config()
    if name not in cfg["members"]:
        cfg["members"].append(name)
        save_config(cfg)
    return cfg


def list_members():
    """返回全部成员档案名：members/ 目录下已存在的目录 + 配置中登记的成员（去重、排序）。"""
    members_dir = os.path.join(SCRIPT_DIR, "members")
    existing = []
    if os.path.isdir(members_dir):
        existing = sorted(
            d for d in os.listdir(members_dir)
            if os.path.isdir(os.path.join(members_dir, d))
        )
    cfg = load_config()
    known = [m for m in cfg.get("members", []) if m not in existing]
    return sorted(set(existing + known))


def parse_date(value):
    """宽容解析日期：支持 2026-08-10 / 2026/8/10 / 2026-8-1 / 带时间 等。
    解析失败返回 None。"""
    if not value:
        return None
    s = str(value).strip()
    # 去掉时间部分（空格或 T 分隔）
    head = s[:10]
    for sep in (" ", "T"):
        if sep in s:
            head = s.split(sep)[0]
    try:
        from datetime import date
        return date.fromisoformat(head)
    except ValueError:
        pass
    parts = re.split(r"[-/]", head)
    if len(parts) == 3:
        try:
            from datetime import date
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, TypeError):
            return None
    return None


def split_symptoms(text):
    """把用户输入的症状按逗号/顿号/分号/空格拆开去重。"""
    if not text:
        return []
    for sep in (",", "，", "、", ";", "；"):
        text = text.replace(sep, " ")
    parts = []
    for item in text.split():
        item = item.strip()
        if item and item not in parts:
            parts.append(item)
    return parts


def load_profile(member=None):
    """读取成员档案基础信息；无档案或损坏时返回空字典。member 为 None 时返回空字典。"""
    if not member:
        return {}
    path = path_for("profile.json", member)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_profile(member, profile):
    """保存成员档案基础信息到 members/<成员名>/profile.json。"""
    if not member or not isinstance(profile, dict):
        return
    path = path_for("profile.json", member)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

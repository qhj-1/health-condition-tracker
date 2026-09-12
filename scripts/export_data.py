# -*- coding: utf-8 -*-
"""数据备份 / 导出工具：把全部健康数据打包成 zip（含 JSON + CSV，CSV 可直接用 Excel 打开）。

用法：
    python export_data.py                    # 默认档案
    python export_data.py --all-members      # 全家备份（推荐）
    python export_data.py --member 妈妈      # 指定成员
    python export_data.py --output D:\\backup\\my-health.zip   # 自定义输出位置

输出：scripts/backups/health-backup-YYYYMMDD-HHMMSS.zip（默认）。
"""
import argparse
import csv
import io
import json
import os
import sys
import zipfile
from datetime import datetime

import common

BACKUP_DIR = os.path.join(common.SCRIPT_DIR, "backups")

JSON_FILES = ["health_log.json", "medications.json", "treatment_plans.json", "vitals.json", "profile.json", "severity_history.json", "health_report.md", "condition_report.html"]
CSV_SPECS = {
    "health_log.csv": ["date", "symptom", "severity", "duration", "notes", "followup"],
    "medications.csv": ["name", "dosage", "frequency", "start_date", "end_date", "notes"],
    "treatment_plans.csv": ["diagnosis", "advice", "follow_up_date", "status", "created_at"],
    "vitals.csv": ["date", "体重", "体温", "心率", "血压", "血糖", "血氧"],
    "severity_history.csv": ["answered_at", "score", "level", "red_flag", "red_flag_hit"],
}


def _sanitize_cell(value):
    """防止 CSV 公式注入：以 = + - @ 开头的单元格加单引号前缀。"""
    s = "" if value is None else str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


def _row_from(record, keys):
    row = []
    for k in keys:
        v = record.get(k, "")
        if k == "followup" and isinstance(v, dict):
            v = "；".join("{}：{}".format(q, a) for q, a in v.items())
        row.append(_sanitize_cell(v))
    return row


def _add_csv(zf, folder, member):
    """把某个成员的 JSON 数据转成 CSV 写入 zip；无数据则跳过。"""
    for csv_name, keys in CSV_SPECS.items():
        json_name = csv_name.replace(".csv", ".json")
        data = []
        path = common.path_for(json_name, member)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    parsed = json.load(f)
                if isinstance(parsed, list):
                    data = parsed
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                continue
        if not data:
            continue
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(keys)
        for rec in data:
            writer.writerow(_row_from(rec, keys))
        zf.writestr("{}/{}".format(folder, csv_name), "\ufeff" + buf.getvalue())


def _add_json_files(zf, folder, member):
    """把某个成员的数据 JSON/报告/图表复制进 zip。"""
    for name in JSON_FILES:
        path = common.path_for(name, member)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                zf.writestr("{}/{}".format(folder, name), f.read())
        except (OSError, UnicodeDecodeError):
            continue
    # 图表 PNG
    dir_path = common.data_dir(member)
    for fname in sorted(os.listdir(dir_path)):
        if fname.endswith(".png"):
            try:
                with open(os.path.join(dir_path, fname), "rb") as f:
                    zf.writestr("{}/charts/{}".format(folder, fname), f.read())
            except OSError:
                continue


def export(members, output_path=None, keep=10):
    """导出成员列表到 zip，返回输出路径与统计；keep 为备份目录保留份数（默认 10）。"""
    if output_path:
        out = output_path
    else:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        out = os.path.join(BACKUP_DIR, "health-backup-{}.zip".format(datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]))
    parent = os.path.dirname(out)
    if parent:
        os.makedirs(parent, exist_ok=True)
    stats = []
    summary_lines = ["health-condition-tracker 数据备份", "时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ""]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        cfg_path = common.config_path()
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                zf.writestr("members_config.json", f.read())
        for member in members:
            folder = "default" if member is None else "members/{}".format(member)
            _add_json_files(zf, folder, member)
            _add_csv(zf, folder, member)
            count = len([n for n in zf.namelist() if n.startswith(folder + "/")])
            stats.append((member or "默认档案", count))
        for who, count in stats:
            summary_lines.append("{}：{} 个文件".format(who, count))
        # summary.txt 必须在 with 块内写入（zip 关闭后写入会抛 ValueError）
        zf.writestr("summary.txt", "\n".join(summary_lines))

    # 轮转：只保留最近 keep 份备份
    if not output_path:
        try:
            old = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("health-backup-") and f.endswith(".zip"))
            for f in old[:-keep] if keep > 0 else []:
                os.remove(os.path.join(BACKUP_DIR, f))
        except OSError:
            pass
    return out, stats


def main():
    parser = argparse.ArgumentParser(description="健康数据备份 / 导出（zip + CSV）")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    parser.add_argument("--all-members", action="store_true", help="备份全家档案（推荐）")
    parser.add_argument("--output", default="", help="zip 输出路径（默认 scripts/backups/）")
    parser.add_argument("--keep", type=int, default=10, help="备份目录最多保留份数，默认 10（0=不清理）")
    args = parser.parse_args()

    if args.all_members:
        members = common.list_members() or [None]
    elif args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效。")
            return 1
        members = [member]
    else:
        members = [None]

    out, stats = export(members, args.output or None, keep=args.keep)
    print("=" * 50)
    print("[确认] 健康数据备份完成：{}".format(out))
    for who, count in stats:
        print("  {}：{} 个文件".format(who, count))
    print("CSV 可用 Excel / WPS 直接打开；zip 请妥善保管（含个人健康信息）。")
    print("免责声明：以上内容仅供参考，不能替代专业医疗诊断。")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())

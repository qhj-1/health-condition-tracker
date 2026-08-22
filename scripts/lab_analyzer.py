# -*- coding: utf-8 -*-
"""报告单 / 体检单 / 化验单解读工具：OCR 或粘贴文本 → 结构化解析 →
异常标记（↑/↓）→ 危急值提醒 → 历史对比 → 生成解读报告，并把体征写入档案。

用法：
    python lab_analyzer.py <图片路径>                      # OCR 化验单/体检单/报告单
    python lab_analyzer.py --text "<粘贴的报告文字>"
    python lab_analyzer.py <图片路径> --member 妈妈
    python lab_analyzer.py <图片路径> --member 妈妈 --compare   # 与上次报告对比
    python lab_analyzer.py --text "..." --no-vitals        # 不写入体征档案
    python lab_analyzer.py --text "..." --json

说明：
- CT / MRI 等影像原图无法用 OCR 判读，请以放射科「文字报告」为准；本工具只解读文字报告。
- 参考范围为通用成人范围，各医院可能不同，以报告单标注为准。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

import common

REFERENCES_DIR = os.path.normpath(os.path.join(common.SCRIPT_DIR, "..", "references"))
LAB_REF_FILE = os.path.join(REFERENCES_DIR, "lab_reference.json")

VITALS_KEYS = {
    "体温": "体温",
    "心率": "心率",
    "血氧饱和度": "血氧",
    "空腹血糖": "血糖",
    "血压": "血压",
    "体重": "体重",
}


def load_lab_ref():
    """读取检验项目参考库，返回 items 列表与别名映射。"""
    items = []
    try:
        with open(LAB_REF_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", []) if isinstance(data, dict) else []
    except (OSError, json.JSONDecodeError):
        items = []
    alias = {}
    for it in items:
        for a in it.get("aliases", []):
            alias[str(a).strip().lower()] = it
    return items, alias


def extract_text_from_image(path):
    """用 image_processor 提取图片文字。"""
    try:
        from image_processor import extract_text
    except ImportError:
        return "", "[错误] 缺少 image_processor 模块。"
    return extract_text(path)


def parse_line(line):
    """解析一行：名称 数值 单位 参考范围。返回字典或 None。"""
    # 血压特殊格式：120/80
    if re.search(r"血压", line) or re.search(r"\bbp\b", line.lower()):
        m_bp = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", line)
        if m_bp:
            return {
                "name": "血压",
                "value": float(m_bp.group(1)),
                "value_text": "{}/{}".format(m_bp.group(1), m_bp.group(2)),
                "sys": int(m_bp.group(1)),
                "dia": int(m_bp.group(2)),
                "unit": "mmHg",
                "range_text": "90-139/60-89",
                "raw": line,
            }
    # 找参考范围（区间或单侧）
    range_text = ""
    rest = line
    m_r = re.search(r"([<>≤≥]?\d+(?:\.\d+)?)\s*[-~—]\s*([<>≤≥]?\d+(?:\.\d+)?)", rest)
    if m_r:
        range_text = m_r.group(0)
        rest = rest.replace(range_text, " ")
    else:
        m_s = re.search(r"([<>≤≥])\s*(\d+(?:\.\d+)?)", rest)
        if m_s:
            range_text = m_s.group(0)
            rest = rest.replace(range_text, " ")
    # 数值与单位：先临时移除 10^9/L 这类含数字单位，避免其中数字被误取
    rest_no_unit = re.sub(r"×?\s*10\s*\^\s*\d+\s*/\s*L", " ", rest)
    nums = list(re.finditer(r"\d+(?:\.\d+)?", rest_no_unit))
    if not nums:
        return None
    unit = ""
    val = None
    pos = -1
    unit_re = re.compile(r"(?:×?\s*10\s*\^\s*\d+\s*/\s*L|[A-Za-z%μu℃]+(?:\s*/\s*[A-Za-z]+)?|次/分)")
    for m in reversed(nums):
        candidate = float(m.group())
        p = rest.rfind(m.group())
        if p < 0:
            continue
        after = rest[p + len(m.group()):].strip()
        m_u = unit_re.match(after)
        if m_u:
            val, pos, unit = candidate, p, m_u.group(0)
            break
        if val is None:
            val, pos, unit = candidate, p, ""
    if val is None:
        return None
    before = rest[:pos]
    # 名称：去掉前导序号与尾部杂字符
    name = re.sub(r"^[\d\s.、:：\-]+", "", before).strip()
    name = re.sub(r"[\s:：|_\-—]+$", "", name).strip()
    if not name:
        return None
    return {"name": name, "value": val, "value_text": str(val), "unit": unit,
            "range_text": range_text, "raw": line}


def find_ref(name, alias):
    """用别名映射查找参考项；返回项目字典或 None。"""
    n = str(name).strip().lower()
    candidates = [n, n.replace(" ", "")]
    parts = re.split(r"[\s\-_]+", n)
    candidates.extend(parts)
    for ln in (6, 4, 3, 2):
        if len(n) >= ln:
            candidates.append(n[-ln:])
    for c in candidates:
        if c in alias:
            return alias[c]
    return None


def classify(item, ref):
    """判断异常状态：正常 / ↑ / ↓ / 异常 / 危急 / 未比对。"""
    status = "未比对"
    note = ""
    if ref is None:
        return status, note
    note = ref.get("hint", "")
    crit = ref.get("critical") or {}
    val = item.get("value")

    if "sys" in item:  # 血压
        sys_v, dia_v = item["sys"], item["dia"]
        sys_ok = 90 <= sys_v <= 139
        dia_ok = 60 <= dia_v <= 89
        if not sys_ok or not dia_ok:
            status = "异常"
        else:
            status = "正常"
        return status, note

    if not isinstance(val, (int, float)):
        return status, note
    lo, hi = ref.get("range_min"), ref.get("range_max")
    if lo is None and hi is None:
        return status, note
    if lo is not None and val < lo:
        status = "↓"
    elif hi is not None and val > hi:
        status = "↑"
    else:
        status = "正常"
    cl, ch = crit.get("low"), crit.get("high")
    if cl is not None and val <= cl:
        status = "危急"
    elif ch is not None and val >= ch:
        status = "危急"
    return status, note


def parse_line_tokens(line):
    """兜底：空格分隔的简单表格行，如 "白细胞 6.5 3.5-9.5"。"""
    tokens = line.split()
    if len(tokens) < 2:
        return None
    for i in range(len(tokens) - 1, 0, -1):
        if re.fullmatch(r"\d+(?:\.\d+)?", tokens[i]):
            val = float(tokens[i])
            range_text = ""
            for t in tokens[i + 1:]:
                if re.search(r"[-~—]|<|>", t):
                    range_text = t
                    break
            name = " ".join(tokens[:i]).strip()
            if not name:
                return None
            return {"name": name, "value": val, "value_text": str(val), "unit": "",
                    "range_text": range_text, "raw": line}
    return None


def parse_report(text):
    """解析整段文字，返回项目列表（正则优先，token 兜底）。"""
    items = []
    seen = set()
    for line in text.splitlines():
        parsed = parse_line(line) or parse_line_tokens(line)
        if not parsed:
            continue
        key = (parsed["name"], parsed["value_text"])
        if key in seen:
            continue
        seen.add(key)
        items.append(parsed)
    return items


def append_vitals(items, member, ts):
    """把可识别体征写入 vitals.json。"""
    rec = {"date": ts}
    added = False
    for it in items:
        key = VITALS_KEYS.get(it.get("ref_name", ""))
        if not key:
            continue
        if key == "血压":
            rec["血压"] = it.get("value_text", "")
        else:
            rec[key] = it.get("value")
        added = True
    if not added:
        return False
    path = common.path_for("vitals.json", member)
    vitals = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            vitals = data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            vitals = []
    vitals.append(rec)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(vitals, f, ensure_ascii=False, indent=2)
    return True


def load_latest_previous(member):
    """读取该成员最近一份已存报告（用于对比）。"""
    dirp = os.path.join(common.data_dir(member), "lab_reports")
    if not os.path.isdir(dirp):
        return None
    jsons = sorted(f for f in os.listdir(dirp) if f.endswith(".json"))
    if not jsons:
        return None
    try:
        with open(os.path.join(dirp, jsons[-1]), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def save_report(result, member):
    """保存报告 JSON 与 Markdown，返回 (json_path, md_path)。"""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dirp = os.path.join(common.data_dir(member), "lab_reports")
    os.makedirs(dirp, exist_ok=True)
    json_path = os.path.join(dirp, "lab_{}.json".format(ts))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    md_path = common.path_for("lab_report.md", member)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result["markdown"])
    return json_path, md_path


def build_result(text, member, source):
    """解析 + 分类 + 对比，返回结果字典（含 markdown）。"""
    items = parse_report(text)
    _, alias = load_lab_ref()
    enriched = []
    for it in items:
        ref = find_ref(it["name"], alias)
        it["ref_name"] = ref["name"] if ref else it["name"]
        status, note = classify(it, ref)
        it["status"] = status
        it["hint"] = note
        if ref and ref.get("range_text"):
            range_display = ref["range_text"]
        elif ref and ref.get("range_min") is not None and ref.get("range_max") is not None:
            range_display = "{}-{}".format(ref["range_min"], ref["range_max"])
        elif ref and ref.get("range_min") is not None:
            range_display = ">{}".format(ref["range_min"])
        elif ref and ref.get("range_max") is not None:
            range_display = "<{}".format(ref["range_max"])
        else:
            range_display = it["range_text"] or "以报告为准"
        it["range_display"] = range_display
        enriched.append(it)

    abnormal = [x for x in enriched if x["status"] in ("↑", "↓", "异常", "危急")]
    critical = [x for x in enriched if x["status"] == "危急"]
    normal = [x for x in enriched if x["status"] == "正常"]
    unknown = [x for x in enriched if x["status"] == "未比对"]

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    who = member or "默认档案"
    lines = []
    lines.append("=" * 50)
    lines.append("报告单解读（{}）".format(who))
    lines.append("时间：{}　来源：{}".format(ts, source))
    lines.append("=" * 50)
    lines.append("共识别 {} 项，异常 {} 项，正常 {} 项，未比对 {} 项。".format(
        len(enriched), len(abnormal), len(normal), len(unknown)))
    if critical:
        lines.append("")
        lines.append("[危急值提醒] 以下项目请尽快就医：")
        for x in critical:
            lines.append("  - {} {}（{}）".format(x["name"], x["value_text"], x.get("unit", "")))
    if abnormal:
        lines.append("")
        lines.append("【异常指标】")
        for x in abnormal:
            lines.append("  - {} {} {}（参考 {}）{}".format(
                x["name"], x["value_text"], x["status"], x["range_display"],
                "——" + x["hint"] if x["hint"] else ""))
    if normal:
        lines.append("")
        lines.append("【正常指标】{}".format("、".join(
            "{} {}".format(x["name"], x["value_text"]) for x in normal[:20])))
        if len(normal) > 20:
            lines.append("  （其余 {} 项从略）".format(len(normal) - 20))
    if unknown:
        lines.append("")
        lines.append("【未比对（库中无参考范围）】{}".format("、".join(
            "{} {}".format(x["name"], x["value_text"]) for x in unknown[:10])))
    if critical or abnormal:
        lines.append("")
        lines.append("【建议】异常指标请结合症状就诊相应科室；危急值请立即就医。")

    # 历史对比
    if member:
        prev = load_latest_previous(member)
        if prev:
            prev_abnormal = {x["name"] for x in prev.get("items", []) if x.get("status") in ("↑", "↓", "异常", "危急")}
            cur_abnormal = {x["name"] for x in enriched if x["status"] in ("↑", "↓", "异常", "危急")}
            new_ones = sorted(cur_abnormal - prev_abnormal)
            resolved = sorted(prev_abnormal - cur_abnormal)
            lines.append("")
            lines.append("【与上次报告对比】")
            if new_ones:
                lines.append("  新出现异常：{}".format("、".join(new_ones)))
            else:
                lines.append("  无新出现异常。")
            if resolved:
                lines.append("  已恢复正常：{}".format("、".join(resolved)))
    lines.append("")
    lines.append("免责声明：本解读基于通用参考范围与规则，仅供参考，不能替代医生诊断；请以报告单和医生意见为准。")
    return {
        "items": enriched,
        "abnormal_count": len(abnormal),
        "critical": [{"name": x["name"], "value": x["value_text"]} for x in critical],
        "markdown": "\n".join(lines),
    }


def main():
    parser = argparse.ArgumentParser(description="报告单/体检单/化验单解读（OCR 或文本）")
    parser.add_argument("images", nargs="*", help="一张或多张图片路径（化验单/体检单/报告单）")
    parser.add_argument("--folder", default="", help="批量识别文件夹内所有图片（jpg/png/jpeg/bmp/webp）")
    parser.add_argument("--text", default="", help="直接粘贴报告文字（无需 OCR）")
    parser.add_argument("--member", default="", help="成员名（多家人档案），如：妈妈")
    parser.add_argument("--compare", action="store_true", help="与上次报告对比（默认仅成员模式）")
    parser.add_argument("--no-vitals", action="store_true", help="不把体征写入 vitals.json")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    member = None
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效。")
            return 1

    text = ""
    source = ""
    paths = []
    if args.folder:
        for fname in sorted(os.listdir(args.folder)):
            if fname.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
                paths.append(os.path.join(args.folder, fname))
    paths.extend(args.images)
    if args.text:
        text = args.text.strip()
        source = "粘贴文本"
    elif paths:
        parts = []
        for p in paths:
            print("正在 OCR 识别：{} ...".format(p))
            t, error = extract_text_from_image(p)
            if error:
                print(error)
                return 1
            if t:
                parts.append(t)
        text = "\n".join(parts)
        source = "OCR：{} 张图片".format(len(paths))
        if not text:
            print("[提示] 未从图片中识别到文字（可能不是文字报告单）。")
            return 1
    else:
        parser.print_help()
        return 1

    result = build_result(text, member, source)
    if args.compare and not member:
        print("[提示] --compare 需要 --member 才能对比该成员上次报告；本次仅单独解读。")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    print(result["markdown"])
    json_path, md_path = save_report(result, member)
    print("-" * 50)
    print("[确认] 报告已存档：{}".format(json_path))
    print("[确认] 解读报告：{}".format(md_path))
    if not args.no_vitals:
        if append_vitals(result["items"], member, datetime.now().strftime("%Y-%m-%d %H:%M:%S")):
            print("[确认] 已把可识别体征写入 vitals.json（可用于趋势图）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

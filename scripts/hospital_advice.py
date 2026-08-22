# -*- coding: utf-8 -*-
"""就诊意见与医院推荐工具：按症状 / 成员 / 科室给出全国十大医院，并结合患者位置
给出最优与性价比就诊方案。

用法：
    python hospital_advice.py --symptoms 头痛                 # 按症状
    python hospital_advice.py --member 妈妈                   # 按成员近期症状
    python hospital_advice.py --department 神经内科           # 直接按科室
    python hospital_advice.py --symptoms 头痛 --city 杭州 --province 浙江
    python hospital_advice.py --member 妈妈 --city 广州 --province 广东

数据来源：references/hospitals.json（整理自公开资料，供挂号参考，请以官方渠道为准）。
"""
import argparse
import json
import os
import sys

import common
from departments import load_departments, query_departments, recommend_for_member

REFERENCES_DIR = os.path.normpath(os.path.join(common.SCRIPT_DIR, "..", "references"))
HOSPITALS_FILE = os.path.join(REFERENCES_DIR, "hospitals.json")
RED_FLAG_FILE = os.path.join(REFERENCES_DIR, "red_flag_symptoms.json")

# 常用城市 → 省份（用于在没有 --province 时推断；仅覆盖常见城市）
CITY_PROVINCE = {
    "北京": "北京", "上海": "上海", "天津": "天津", "重庆": "重庆",
    "广州": "广东", "深圳": "广东", "东莞": "广东", "佛山": "广东", "珠海": "广东", "中山": "广东", "惠州": "广东", "汕头": "广东",
    "杭州": "浙江", "宁波": "浙江", "温州": "浙江", "绍兴": "浙江", "嘉兴": "浙江", "台州": "浙江", "金华": "浙江", "湖州": "浙江",
    "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏", "南通": "江苏", "徐州": "江苏", "扬州": "江苏", "盐城": "江苏", "淮安": "江苏", "连云港": "江苏",
    "济南": "山东", "青岛": "山东", "烟台": "山东", "潍坊": "山东", "淄博": "山东", "临沂": "山东", "济宁": "山东", "泰安": "山东",
    "郑州": "河南", "洛阳": "河南", "南阳": "河南", "新乡": "河南", "开封": "河南", "许昌": "河南",
    "武汉": "湖北", "襄阳": "湖北", "宜昌": "湖北", "荆州": "湖北", "黄冈": "湖北",
    "长沙": "湖南", "株洲": "湖南", "湘潭": "湖南", "岳阳": "湖南", "常德": "湖南", "衡阳": "湖南", "郴州": "湖南", "永州": "湖南",
    "成都": "四川", "绵阳": "四川", "南充": "四川", "泸州": "四川", "宜宾": "四川", "乐山": "四川", "德阳": "四川", "达州": "四川",
    "西安": "陕西", "咸阳": "陕西", "宝鸡": "陕西", "渭南": "陕西", "榆林": "陕西", "汉中": "陕西",
    "沈阳": "辽宁", "大连": "辽宁", "鞍山": "辽宁", "抚顺": "辽宁",
    "长春": "吉林", "吉林": "吉林", "四平": "吉林", "延吉": "吉林",
    "哈尔滨": "黑龙江", "齐齐哈尔": "黑龙江", "大庆": "黑龙江", "牡丹江": "黑龙江",
    "石家庄": "河北", "唐山": "河北", "保定": "河北", "邯郸": "河北", "廊坊": "河北", "秦皇岛": "河北",
    "太原": "山西", "大同": "山西", "临汾": "山西", "运城": "山西",
    "合肥": "安徽", "芜湖": "安徽", "蚌埠": "安徽", "安庆": "安徽", "阜阳": "安徽", "滁州": "安徽",
    "福州": "福建", "厦门": "福建", "泉州": "福建", "漳州": "福建", "莆田": "福建", "宁德": "福建",
    "南昌": "江西", "赣州": "江西", "九江": "江西", "上饶": "江西", "宜春": "江西",
    "昆明": "云南", "曲靖": "云南", "大理": "云南", "丽江": "云南", "玉溪": "云南",
    "贵阳": "贵州", "遵义": "贵州", "六盘水": "贵州", "毕节": "贵州",
    "南宁": "广西", "柳州": "广西", "桂林": "广西", "梧州": "广西", "北海": "广西",
    "海口": "海南", "三亚": "海南", "儋州": "海南",
    "兰州": "甘肃", "天水": "甘肃", "酒泉": "甘肃",
    "西宁": "青海", "格尔木": "青海",
    "银川": "宁夏", "石嘴山": "宁夏",
    "乌鲁木齐": "新疆", "喀什": "新疆", "伊犁": "新疆",
    "呼和浩特": "内蒙古", "包头": "内蒙古", "鄂尔多斯": "内蒙古", "赤峰": "内蒙古",
    "拉萨": "西藏", "日喀则": "西藏",
    "香港": "香港", "澳门": "澳门", "台北": "台湾",
}


def ask(prompt):
    """带提示符的输入函数，非交互环境返回空字符串。"""
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def load_hospitals():
    """读取医院知识库，返回 {"specialties": {...}}；失败返回空结构。"""
    try:
        with open(HOSPITALS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("specialties"), dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"specialties": {}}


def load_red_flags():
    """读取紧急症状清单，返回列表。"""
    try:
        with open(RED_FLAG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get("紧急症状", []) or []
    except (OSError, json.JSONDecodeError):
        pass
    return []


def norm_city(name):
    """规范化城市名：去掉「市」后缀。"""
    s = str(name or "").strip()
    if s.endswith("市"):
        s = s[:-1]
    return s


def resolve_province(city, province):
    """确定省份：显式省份 > 常用城市映射。"""
    city = norm_city(city)
    if province:
        return str(province).strip()
    if city in CITY_PROVINCE:
        return CITY_PROVINCE[city]
    return ""


def split_by_location(hospitals, city, province):
    """把某科室医院列表分为 (同城, 同省, 其他)。"""
    city = norm_city(city)
    same_city, same_prov, others = [], [], []
    for h in hospitals:
        h_city = norm_city(h.get("city", ""))
        h_prov = str(h.get("province", "")).strip()
        if city and h_city == city:
            same_city.append(h)
        elif province and h_prov == province:
            same_prov.append(h)
        else:
            others.append(h)
    return same_city, same_prov, others


def format_hospitals(items, top=None):
    """格式化医院列表（带序号与备注）。"""
    if top:
        items = items[:top]
    lines = []
    for i, h in enumerate(items, 1):
        note = h.get("note", "")
        lines.append("  {}. {}（{}）{}".format(i, h.get("name", ""), h.get("city", ""), "——" + note if note else ""))
    return lines


def check_emergency(symptoms):
    """命中紧急/警惕症状时打印对应提示（两档，避免过度恐慌）。"""
    data = load_red_flags()
    urgent = data.get("紧急症状", []) if isinstance(data, dict) else []
    watch = data.get("警惕症状", []) if isinstance(data, dict) else []
    hit_u = [f for f in urgent if any(f and (f in s or s in f) for s in symptoms)]
    hit_w = [f for f in watch if any(f and (f in s or s in f) for s in symptoms)]
    if hit_u:
        print("=" * 50)
        print("[紧急提醒] 症状「{}」建议立即就近急诊，不要跨城转诊！".format("、".join(hit_u[:5])))
        print("  急诊原则：先就近稳定病情，再考虑转诊到专科医院。")
        print("=" * 50)
        return True
    if hit_w:
        print("-" * 50)
        print("[注意] 症状「{}」建议尽快就近就诊评估，不必恐慌；若持续加重请立即就医。".format("、".join(hit_w[:5])))
        print("-" * 50)
    return False

def build_advice(departments, city, province, symptoms=None, budget=""):
    """生成就诊意见文本并打印，返回是否命中紧急提示。"""
    data = load_hospitals()
    all_specialties = data.get("specialties", {})
    fee_note = data.get("费用提示", "")
    emergency = False
    if symptoms:
        emergency = check_emergency(symptoms)

    print("=" * 50)
    print("就诊意见与医院推荐")
    print("=" * 50)
    if city:
        print("患者位置：{}（{}）".format(city, province or "省份未提供"))
    else:
        print("患者位置：未提供（将按全国十大医院 + 就近三甲给出建议）")
    print("建议科室：{}".format("、".join(departments[:3])))
    print("-" * 50)

    any_city = False
    any_prov = False
    for dep in departments[:3]:
        hospitals = all_specialties.get(dep, [])
        if not hospitals:
            print("【{}】暂无收录医院，建议先看当地三甲医院。".format(dep))
            continue
        same_city, same_prov, others = split_by_location(hospitals, city, province)
        if same_city:
            any_city = True
        if same_prov:
            any_prov = True
        print("【{}】全国十大医院".format(dep))
        if same_city:
            print("  ◆ 同城（最近、最方便）：")
            for line in format_hospitals(same_city):
                print(line)
        if same_prov:
            print("  ◆ 同省：")
            for line in format_hospitals(same_prov, top=3):
                print(line)
        print("  ◆ 全国其他（疑难/顶尖专家）：")
        for line in format_hospitals(others, top=5):
            print(line)
        print("")

    print("=" * 50)
    print("就诊方案")
    print("=" * 50)
    print("【性价比方案（推荐先走这条）】")
    if any_city:
        print("  1. 先挂同城三甲普通门诊（约 20-100 元），完成基础检查（血常规、影像等）；")
        print("  2. 若同城医院就在全国十大之列，直接挂其专家门诊，省去跨城费用；")
        print("  3. 检查结果出来后如需第二意见，再考虑省级或全国顶级医院。")
    else:
        print("  1. 先挂本市/最近三甲普通门诊完成基础检查（约 20-100 元）；")
        print("  2. 确需专科治疗时，优先选同省省会三甲（普通门诊即可）；")
        print("  3. 避免一上来就跨省挂特需，先留好本地检查结果。")
    print("【最优方案（病情复杂 / 本地难以确诊时）】")
    if any_city:
        print("  1. 挂同城全国十大医院专家门诊（约 50-300 元）；")
        print("  2. 疑难病可再申请多学科会诊（MDT）。")
    else:
        print("  1. 选择离您最近的全国十大医院（见上「同省 / 全国其他」列表）；")
        print("  2. 提前在官方渠道挂专家号，先线上咨询或问诊确认再动身；")
        print("  3. 跨省就诊前先在「国家医保服务平台」APP 办理异地就医备案，报销比例更高。")
    if budget == "普通":
        print("【费用预估（您选择普通档）】普通门诊约 20-100 元；建议先普通门诊做基础检查，再按需升级。检查治疗另计。")
    elif budget == "专家":
        print("【费用预估（您选择专家档）】专家门诊约 50-300 元；同城/同省专家优先，减少差旅。检查治疗另计。")
    elif budget == "特需":
        print("【费用预估（您选择特需档）】特需/国际部约 300-1500 元以上；可更快约到顶尖专家，费用较高。检查治疗另计。")
    else:
        print("【费用预估】" + (fee_note or "普通门诊约20-100元、专家约50-300元、特需/国际部约300-1500元以上；检查治疗另计。"))
    print("")
    print("【挂号渠道】")
    print("  1. 医院官方公众号 / APP（最可靠，放号时间一般早上 8:00 前后）；")
    print("  2. 省级统一挂号平台（如北京 114、上海健康云、广东粤健通等）；")
    print("  3. 电话 12320 / 114 辅助挂号；特需/国际部可直接电话预约。")
    print("")
    print("【就诊前准备】")
    print("  1. 带上既往病历、检查报告、影像片与用药清单；")
    print("  2. 可先用 report_generator.py --member <名字> 生成病情摘要，方便医生快速了解；")
    print("  3. 异地就医先做医保备案，并确认目标医院是否在定点名单内。")
    print("=" * 50)
    print("免责声明：医院信息整理自公开资料，仅供挂号参考；排名、科室与费用可能变化，请以医院官方渠道为准。本内容不构成医疗建议。")
    return emergency


def resolve_departments(args):
    """根据参数解析建议科室列表。"""
    if args.department:
        return [args.department]
    if args.member:
        member = common.sanitize_member(args.member)
        if not member:
            print("[错误] 成员名无效。")
            return None
        symptoms, depts = recommend_for_member(member, args.days)
        if not symptoms:
            print("该成员暂无症状记录，请先录入病情或改用 --symptoms / --department。")
            return None
        print("成员近期症状：{}".format("、".join(symptoms[:8])))
        return [d for d, _ in depts]
    if args.symptoms:
        depts = query_departments(args.symptoms, load_departments())
        return [d for d, _ in depts] or ["全科"]
    return None


def main():
    parser = argparse.ArgumentParser(description="就诊意见与医院推荐（全国十大 + 结合患者位置）")
    parser.add_argument("--symptoms", nargs="*", help="症状名称，如：--symptoms 头痛 发热")
    parser.add_argument("--member", default="", help="按成员近期症状推荐（如：妈妈）")
    parser.add_argument("--department", default="", help="直接指定科室，如：神经内科")
    parser.add_argument("--city", default="", help="患者所在城市，如：杭州")
    parser.add_argument("--province", default="", help="患者所在省份（直辖市可省略）")
    parser.add_argument("--days", type=int, default=0, help="按成员统计最近 N 天（0=全部）")
    parser.add_argument("--budget", default="", choices=["普通", "专家", "特需"], help="预算档：普通 / 专家 / 特需（影响方案建议）")
    args = parser.parse_args()

    if args.days < 0:
        print("[错误] --days 不能为负数。")
        return 1
    departments = resolve_departments(args)
    if not departments:
        parser.print_help()
        return 1

    city = norm_city(args.city)
    if not city:
        city = norm_city(ask("请提供患者所在城市（如：杭州；直接回车=不提供）："))
    province = resolve_province(city, args.province)
    if city and not province:
        province = ask("所在省份（如：浙江；直接回车=跳过）：").strip()

    symptoms = list(args.symptoms or [])
    if args.member:
        # 取成员近期症状用于紧急提示
        member = common.sanitize_member(args.member)
        symptoms, _ = recommend_for_member(member, args.days)
        symptoms = symptoms[:8]

    build_advice(departments, city, province, symptoms=symptoms, budget=args.budget)
    return 0


if __name__ == "__main__":
    sys.exit(main())

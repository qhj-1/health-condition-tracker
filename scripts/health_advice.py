# -*- coding: utf-8 -*-
"""个性化健康建议工具：基于症状与生活方式，生成饮食、运动、睡眠、压力管理、
戒烟限酒等非医疗级健康建议。

用法示例：
    python health_advice.py 头痛 失眠
    python health_advice.py --symptoms 头痛 --sleep-hours 5 --exercise 每周1次
"""
import argparse
import sys


def generate_advice(symptoms, lifestyle=None):
    """根据症状与生活方式生成个性化健康建议列表。

    参数：
        symptoms: 症状名称列表
        lifestyle: 可选字典，支持 sleep_hours、exercise、smoking、alcohol 等键
    返回：
        建议字符串列表（按类别分组）
    """
    lifestyle = lifestyle or {}
    text = "、".join(symptoms)
    advice = []

    # ---------- 饮食 ----------
    diet = ["【饮食建议】"]
    if any(k in text for k in ("头痛", "偏头痛")):
        diet.append("规律进餐，避免饥饿诱发头痛；减少咖啡因和酒精摄入。")
    if any(k in text for k in ("咳嗽", "咽喉", "咽痛", "喉咙")):
        diet.append("多喝温水，保持咽喉湿润；避免辛辣、过烫食物。")
    if any(k in text for k in ("恶心", "腹痛", "胃", "腹泻", "呕吐", "消化不良")):
        diet.append("清淡饮食、少食多餐；腹泻时注意补充水分和电解质。")
    if "便秘" in text:
        diet.append("增加膳食纤维（蔬菜、水果、全谷物）和饮水量，养成定时排便习惯。")
    if any(k in text for k in ("乏力", "疲劳", "贫血")):
        diet.append("保证优质蛋白和铁、维生素 B12 摄入，如瘦肉、蛋、深色蔬菜。")
    if any(k in text for k in ("心悸", "失眠", "焦虑")):
        diet.append("下午之后避免浓茶、咖啡等含咖啡因饮品。")
    if any(k in text for k in ("皮疹", "过敏", "荨麻疹")):
        diet.append("留意并避开可疑致敏食物，记录饮食与皮疹的关系。")
    diet.append("总体保持均衡饮食，少油少盐少糖，戒烟限酒。")
    advice.append("\n".join(diet))

    # ---------- 运动 ----------
    exercise = ["【运动建议】"]
    if any(k in text for k in ("关节痛", "肌肉痛", "肿胀", "活动受限")):
        exercise.append("避免剧烈或负重运动，选择低冲击活动（如散步、游泳），以不加重疼痛为度。")
    if any(k in text for k in ("胸痛", "呼吸困难", "心悸")):
        exercise.append("胸痛、呼吸困难或心悸期间暂停运动，先就医明确原因。")
    if "乏力" in text or "疲劳" in text:
        exercise.append("从轻度活动开始（如每天散步 10-15 分钟），循序渐进。")
    if "失眠" in text or "睡眠" in text:
        exercise.append("白天适度运动有助于夜间入睡，但睡前 2 小时避免剧烈运动。")
    if not any(k in text for k in ("胸痛", "呼吸困难", "心悸", "关节痛")):
        exercise.append("保持每周 3-5 次、每次 30 分钟左右的规律中等强度运动。")
    advice.append("\n".join(exercise))

    # ---------- 睡眠 ----------
    sleep = ["【睡眠建议】"]
    sleep_hours = lifestyle.get("sleep_hours")
    if sleep_hours:
        try:
            if float(sleep_hours) < 7:
                sleep.append("您目前的睡眠时长偏少，建议逐步调整到每晚 7-8 小时。")
        except (TypeError, ValueError):
            pass
    if "失眠" in text or "睡眠障碍" in text:
        sleep.append("固定作息时间，睡前一小时远离手机屏幕，保持卧室安静、黑暗、凉爽。")
    else:
        sleep.append("保持规律作息，尽量固定入睡和起床时间。")
    advice.append("\n".join(sleep))

    # ---------- 压力管理 ----------
    stress = ["【压力与心理建议】"]
    if any(k in text for k in ("焦虑", "失眠", "头痛", "情绪", "压力")):
        stress.append("尝试正念呼吸、冥想或写日记，每天留出 10 分钟放松时间。")
    else:
        stress.append("注意劳逸结合，避免长期过劳。")
    advice.append("\n".join(stress))

    # ---------- 戒烟限酒 ----------
    habits = ["【生活习惯（戒烟限酒）】"]
    if lifestyle.get("smoking") and str(lifestyle["smoking"]).strip().lower() not in ("无", "否", "没有", "no"):
        habits.append("吸烟会加重多种症状，建议尽快戒烟；必要时可咨询戒烟门诊。")
    if lifestyle.get("alcohol") and str(lifestyle["alcohol"]).strip().lower() not in ("无", "否", "没有", "no"):
        habits.append("建议严格限制饮酒，服药期间应避免饮酒。")
    if len(habits) == 1:
        habits.append("建议戒烟限酒，减少对身体的额外负担。")
    advice.append("\n".join(habits))

    return advice


def main():
    parser = argparse.ArgumentParser(description="生成个性化健康建议（非医疗级）")
    parser.add_argument("symptoms", nargs="*", help="症状名称，如：头痛 失眠")
    parser.add_argument("--symptoms", nargs="*", dest="symptoms_opt", help="症状名称（等价于位置参数，如：--symptoms 头痛 失眠）")
    parser.add_argument("--sleep-hours", help="每晚睡眠小时数")
    parser.add_argument("--exercise", help="运动情况，如：每周2次")
    parser.add_argument("--smoking", help="吸烟情况，如：每天10支 / 无")
    parser.add_argument("--alcohol", help="饮酒情况，如：偶尔 / 无")
    args = parser.parse_args()

    symptoms = list(args.symptoms) + list(args.symptoms_opt or [])
    lifestyle = {
        "sleep_hours": args.sleep_hours,
        "exercise": args.exercise,
        "smoking": args.smoking,
        "alcohol": args.alcohol,
    }

    print("=" * 50)
    print("个性化健康建议")
    print("=" * 50)
    if not symptoms:
        print("[提示] 未提供症状，将给出通用健康建议。")
    else:
        print("症状：{}".format("、".join(symptoms)))
    print("-" * 50)
    for section in generate_advice(symptoms, lifestyle):
        print(section)
        print("-" * 50)
    print("免责声明：以上为通用健康生活方式建议，仅供参考，不能替代专业医疗诊断。")
    print("如出现剧烈疼痛、呼吸困难、胸痛、意识模糊、严重出血等紧急症状，请立即就医。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

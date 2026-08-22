# -*- coding: utf-8 -*-
"""外部医学知识库 API 查询工具（多数据源，无需密钥）。

数据源（按顺序回退）：
1. wikipedia   —— 维基百科中文医学词条（默认，zh.wikipedia.org）
2. disease_sh  —— disease.sh 公开接口（https://disease.sh/v3/covid/diseases）
3. 内置知识库   —— references/symptom_disease_map.json + 模型自身知识

配置文件：references/api_config.json（不存在时使用默认配置；可复制
references/api_config.example.json 修改后另存为 api_config.json）。

用法：
    python medical_api.py <症状或疾病名>
    python medical_api.py <名称> --provider disease_sh
    python medical_api.py <名称> --max-chars 800
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

REFERENCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references")
CONFIG_FILE = os.path.join(REFERENCES_DIR, "api_config.json")

DEFAULT_CONFIG = {
    "disease_api": {
        "provider": "wikipedia",
        "enabled": True,
        "fallback_provider": "disease_sh",
    },
    "wikipedia": {
        "base_url": "https://zh.wikipedia.org/w/api.php",
        "api_key": "",
        "language": "zh",
    },
    "disease_sh": {
        "base_url": "https://disease.sh/v3/covid/diseases",
        "api_key": "",
        "enabled": True,
    },
    "ocr": {"engine": "tesseract", "language": "chi_sim+eng"},
}


def load_config():
    """读取 references/api_config.json；文件不存在或解析失败时返回默认配置。"""
    default = json.loads(json.dumps(DEFAULT_CONFIG))
    if not os.path.exists(CONFIG_FILE):
        print("[提示] 未找到配置文件 {}，将使用默认数据源。".format(CONFIG_FILE))
        return default
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        merged = json.loads(json.dumps(DEFAULT_CONFIG))
        for section, values in config.items():
            if isinstance(values, dict) and section in merged:
                merged[section].update(values)
            else:
                merged[section] = values
        return merged
    except (OSError, json.JSONDecodeError) as e:
        print("[警告] 读取配置失败（{}），使用默认配置。".format(e))
        return default


def _http_get_json(url, api_key="", extra_headers=None):
    """发起 GET 请求并解析 JSON，返回 (data, error)。"""
    headers = {"User-Agent": "health-condition-tracker/1.0 (personal health skill)"}
    if api_key:
        headers["Authorization"] = "Bearer {}".format(api_key)
    if extra_headers:
        headers.update(extra_headers)
    last = ""
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8")), ""
        except Exception as e:
            last = str(e)
    return None, last


def _wikipedia_query(term, config):
    """通过维基百科 API 查询词条解释。返回 (results, error)。"""
    base = config.get("base_url", DEFAULT_CONFIG["wikipedia"]["base_url"])
    params = {
        "action": "query",
        "prop": "extracts",
        "exintro": "1",
        "explaintext": "1",
        "format": "json",
        "redirects": "1",
        "titles": term,
    }
    url = "{}?{}".format(base, urllib.parse.urlencode(params))
    data, error = _http_get_json(url, extra_headers={"Accept": "application/json"})
    if data is None:
        return None, error
    pages = (data.get("query") or {}).get("pages") or {}
    results = []
    for page_id, page in pages.items():
        if int(page_id) < 0:  # 负 ID 表示词条不存在
            continue
        title = page.get("title", term)
        extract = (page.get("extract") or "").strip()
        if not extract:
            continue
        results.append({
            "name": title,
            "description": extract,
            "source": "wikipedia",
            "url": "https://zh.wikipedia.org/wiki/{}".format(urllib.parse.quote(title.replace(" ", "_"))),
        })
    if not results:
        return [], "维基百科中未找到「{}」相关词条。".format(term)
    return results, ""


def _disease_sh_query(term, config):
    """通过 disease.sh 查询疾病信息（直接查询，失败则列举查找）。返回 (results, error)。"""
    base = config.get("base_url", DEFAULT_CONFIG["disease_sh"]["base_url"]).rstrip("/")
    api_key = config.get("api_key", "")
    url = "{}/{}".format(base, urllib.parse.quote(term))
    data, error = _http_get_json(url, api_key)
    if data is not None:
        if isinstance(data, list):
            return data, ""
        return [data], ""
    list_data, list_error = _http_get_json(base, api_key)
    if isinstance(list_data, list):
        matches = []
        for item in list_data:
            name = str(item.get("name", ""))
            if term.lower() in name.lower() or name.lower() in term.lower():
                matches.append(item)
        if matches:
            return matches[:5], ""
        return [], "disease.sh 列表中未找到与「{}」匹配的疾病。".format(term)
    return None, "直接查询失败（{}），且列表查询也失败（{}）。".format(error, list_error)


def format_disease_sh(data):
    """将 disease.sh 返回的疾病信息格式化为中文输出行。"""
    name = data.get("name") or data.get("disease") or data.get("title") or "未知疾病"
    lines = ["疾病名称：{}".format(name)]
    desc = data.get("description") or data.get("info") or data.get("summary")
    lines.append("描述：{}".format(desc or "（无描述）"))
    symptoms = data.get("symptoms") or data.get("common_symptoms")
    if symptoms:
        if isinstance(symptoms, list):
            lines.append("常见症状：{}".format("、".join(str(s) for s in symptoms)))
        else:
            lines.append("常见症状：{}".format(symptoms))
    treatment = data.get("treatment") or data.get("treatment_info")
    if treatment:
        if isinstance(treatment, list):
            lines.append("治疗信息：{}".format("；".join(str(t) for t in treatment)))
        else:
            lines.append("治疗信息：{}".format(treatment))
    prevention = data.get("prevention") or data.get("prevention_measures")
    if prevention:
        if isinstance(prevention, list):
            lines.append("预防措施：{}".format("；".join(str(p) for p in prevention)))
        else:
            lines.append("预防措施：{}".format(prevention))
    return "\n".join(lines)


PROVIDERS = {
    "wikipedia": _wikipedia_query,
    "disease_sh": _disease_sh_query,
}


def query(term, provider, config, max_chars=1200):
    """调用指定数据源查询。返回 (results, error)。"""
    if provider not in PROVIDERS:
        return None, "未知数据源：{}（可选：{}）".format(provider, "、".join(sorted(PROVIDERS)))
    section = config.get(provider, {})
    return PROVIDERS[provider](term, section)


def format_results(results, provider, max_chars):
    """按数据源格式化查询结果。"""
    blocks = []
    for i, item in enumerate(results, 1):
        if len(results) > 1:
            blocks.append("----- 匹配结果 {} -----".format(i))
        if provider == "wikipedia":
            name = item.get("name", "未知")
            desc = item.get("description", "")
            if max_chars and len(desc) > max_chars:
                desc = desc[:max_chars] + "……"
            blocks.append("疾病名称：{}".format(name))
            blocks.append("描述：{}".format(desc))
            blocks.append("参考链接：{}".format(item.get("url", "")))
        else:
            blocks.append(format_disease_sh(item))
    return "\n".join(blocks)


def main():
    parser = argparse.ArgumentParser(description="查询外部医学知识库中的疾病/症状信息")
    parser.add_argument("term", help="症状或疾病名称，如：头痛 或 covid-19")
    parser.add_argument("--provider", default="", help="数据源：wikipedia / disease_sh，默认取配置")
    parser.add_argument("--max-chars", type=int, default=1200, help="百科描述最大字符数，默认 1200")
    args = parser.parse_args()

    config = load_config()
    api = config.get("disease_api", {})
    if not api.get("enabled", True):
        print("[提示] 外部 API 已在配置中禁用，将直接使用内置知识库。")
        return 1
    primary = args.provider or api.get("provider", "wikipedia")
    fallback = api.get("fallback_provider", "disease_sh")

    print("=" * 50)
    print("医学知识库查询：{}（数据源：{}）".format(args.term, primary))
    print("=" * 50)

    results, error = query(args.term, primary, config, args.max_chars)
    active = primary
    if not results:
        print("[提示] 数据源「{}」未返回结果：{}".format(primary, error))
        results, error2 = query(args.term, fallback, config, args.max_chars)
        active = fallback
        if results:
            print("[提示] 已回退到数据源「{}」。".format(fallback))
        else:
            print("[提示] 回退数据源「{}」也未返回结果：{}".format(fallback, error2))
    if not results:
        print("将回退到内置知识库（references/symptom_disease_map.json）和模型自身知识。")
        return 1

    print(format_results(results, active, args.max_chars))
    print("-" * 50)
    print("免责声明：以上内容仅供参考，不能替代专业医疗诊断。")
    print("如出现剧烈疼痛、呼吸困难、胸痛、意识模糊、严重出血等紧急症状，请立即就医。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

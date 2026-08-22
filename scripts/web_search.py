# -*- coding: utf-8 -*-
"""联网搜索工具（多引擎 + 交叉验证 + 官方优先，全部免密钥）。

引擎（按配置顺序回退）：
1. duckduckgo —— DuckDuckGo HTML 搜索
2. bing       —— Bing 网页搜索
3. mojeek     —— Mojeek 搜索（对爬虫友好）
4. brave      —— Brave 搜索（部分网络可能被拦截，失败自动跳过）
5. wikipedia  —— 维基百科搜索（语言由配置决定，默认中文 zh）

交叉验证（--cross，默认）：
- 多个引擎独立返回后按网址去重，统计「同一信息被几个独立来源命中」；
- 官方/权威来源（references/official_domains.json）标记 [官方] 并优先展示；
- 可用 --official 只看官方来源。

用法：
    python web_search.py <查询词>
    python web_search.py <查询词> --official
    python web_search.py <查询词> --engine bing
    python web_search.py <查询词> --max-results 8
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

REFERENCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references")
CONFIG_FILE = os.path.join(REFERENCES_DIR, "api_config.json")
OFFICIAL_FILE = os.path.join(REFERENCES_DIR, "official_domains.json")

DEFAULT_CONFIG = {
    "search": {
        "engines": ["duckduckgo", "bing", "mojeek", "wikipedia"],
        "max_results": 5,
        "language": "zh",
    },
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 health-condition-tracker/1.0"


def load_config():
    """读取 references/api_config.json 中的 search 配置；文件缺失或解析失败时用默认值。"""
    default = json.loads(json.dumps(DEFAULT_CONFIG))
    if not os.path.exists(CONFIG_FILE):
        print("[提示] 未找到配置文件 {}，将使用默认搜索配置。".format(CONFIG_FILE))
        return default
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        merged = json.loads(json.dumps(DEFAULT_CONFIG))
        if isinstance(config.get("search"), dict):
            merged["search"].update(config["search"])
        return merged
    except (OSError, json.JSONDecodeError) as e:
        print("[警告] 读取配置失败（{}），使用默认搜索配置。".format(e))
        return default


def load_official():
    """读取官方/权威域名库。"""
    default = {"suffixes": [], "domains": [], "keywords": []}
    if not os.path.exists(OFFICIAL_FILE):
        return default
    try:
        with open(OFFICIAL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in default:
            if isinstance(data.get(k), list):
                default[k] = data[k]
    except (OSError, json.JSONDecodeError):
        pass
    return default


def _http_get(url, retries=1):
    """GET 请求并返回 UTF-8 文本；失败自动重试 retries 次后抛出异常。"""
    last = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8", "Accept": "text/html"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            last = e
    raise last


def _resolve_url(href):
    """把跳转链接还原成真实 URL。"""
    if not href:
        return ""
    href = html.unescape(href.strip())
    if "uddg=" in href:
        parsed = urllib.parse.urlparse(href)
        params = urllib.parse.parse_qs(parsed.query)
        if params.get("uddg"):
            return params["uddg"][0]
    if href.startswith("//"):
        href = "https:" + href
    return href


def _clean_text(text):
    """去掉 HTML 标签并反转义实体。"""
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def _url_key(url):
    """网址去重键：去掉协议、www、尾斜杠与查询参数。"""
    u = urllib.parse.urlparse(url)
    host = (u.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = (u.path or "").rstrip("/")
    return "{}|{}".format(host, path)


def is_official(url):
    """判断网址是否来自官方/权威来源。"""
    cfg = load_official()
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except ValueError:
        return False
    if host.startswith("www."):
        host = host[4:]
    for suf in cfg.get("suffixes", []):
        if host.endswith(suf):
            return True
    for d in cfg.get("domains", []):
        d = d.lower()
        if host == d or host.endswith("." + d):
            return True
    for kw in cfg.get("keywords", []):
        if kw in host:
            return True
    return False


def search_duckduckgo(query, max_results=5, language=None):
    """DuckDuckGo HTML 搜索。language 仅用于兼容统一调用。"""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    page = _http_get(url)
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        re.S,
    )
    results = []
    for m in pattern.finditer(page):
        results.append({
            "title": _clean_text(m.group(2)),
            "url": _resolve_url(m.group(1)),
            "snippet": _clean_text(m.group(3)),
        })
        if len(results) >= max_results:
            break
    return results


def search_bing(query, max_results=5, language=None):
    """Bing 网页搜索（HTML 解析）。"""
    url = "https://www.bing.com/search?q={}&setlang=zh-hans&cc=cn&count={}".format(
        urllib.parse.quote(query), max_results
    )
    page = _http_get(url)
    blocks = re.findall(r'<li class="b_algo".*?</li>', page, re.S)
    results = []
    for b in blocks:
        href = re.search(r'<a[^>]+href="([^"]+)"', b)
        title = re.search(r'<h2[^>]*>(.*?)</h2>', b, re.S)
        snippet = re.search(r'<p[^>]*>(.*?)</p>', b, re.S)
        if not href:
            continue
        results.append({
            "title": _clean_text(title.group(1)) if title else "",
            "url": _resolve_url(href.group(1)),
            "snippet": _clean_text(snippet.group(1)) if snippet else "",
        })
        if len(results) >= max_results:
            break
    return results


def search_mojeek(query, max_results=5, language=None):
    """Mojeek 搜索（对爬虫友好）。"""
    url = "https://www.mojeek.com/search?q=" + urllib.parse.quote(query)
    page = _http_get(url)
    links = re.findall(r'<a class="ob"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S)
    snippets = re.findall(r'<p class="s">(.*?)</p>', page, re.S)
    results = []
    for i, (href, title) in enumerate(links):
        results.append({
            "title": _clean_text(title),
            "url": _resolve_url(href),
            "snippet": _clean_text(snippets[i]) if i < len(snippets) else "",
        })
        if len(results) >= max_results:
            break
    return results


def search_brave(query, max_results=5, language=None):
    """Brave 搜索（部分网络可能被拦截，失败自动跳过）。"""
    url = "https://search.brave.com/search?q=" + urllib.parse.quote(query) + "&source=web"
    page = _http_get(url)
    blocks = re.findall(r'<div class="snippet"[^>]*>(.*?)</div>', page, re.S)
    results = []
    for b in blocks:
        href = re.search(r'<a[^>]+href="([^"]+)"', b)
        title = re.search(r'<a[^>]+href="[^"]+"[^>]*>(.*?)</a>', b, re.S)
        if not href:
            continue
        results.append({
            "title": _clean_text(title.group(1)) if title else "",
            "url": _resolve_url(href.group(1)),
            "snippet": _clean_text(b)[:300],
        })
        if len(results) >= max_results:
            break
    return results


def search_wikipedia(query, max_results=5, language="zh"):
    """维基百科搜索。"""
    base = "https://{}.wikipedia.org/w/api.php".format(language)
    params = {
        "action": "query", "list": "search", "srsearch": query,
        "format": "json", "srlimit": str(max_results), "utf8": "1",
    }
    url = base + "?" + urllib.parse.urlencode(params)
    data = json.loads(_http_get(url))
    results = []
    for item in (data.get("query") or {}).get("search", []):
        title = item.get("title", "")
        results.append({
            "title": title,
            "url": "https://{}.wikipedia.org/wiki/{}".format(language, urllib.parse.quote(title.replace(" ", "_"))),
            "snippet": _clean_text(item.get("snippet", "")),
        })
        if len(results) >= max_results:
            break
    return results


ENGINES = {
    "duckduckgo": search_duckduckgo,
    "bing": search_bing,
    "mojeek": search_mojeek,
    "brave": search_brave,
    "wikipedia": search_wikipedia,
}


def search(query, engines=None, max_results=5, language="zh"):
    """按顺序调用引擎，返回 (results, errors)。results 为合并后的条目列表。"""
    engines = engines or list(DEFAULT_CONFIG["search"]["engines"])
    results = []
    errors = []
    for name in engines:
        func = ENGINES.get(name)
        if func is None:
            errors.append("未知引擎：{}".format(name))
            continue
        try:
            found = func(query, max_results=max_results, language=language)
        except Exception as e:
            errors.append("{}：{}".format(name, e))
            continue
        if found:
            print("[提示] 数据源「{}」返回 {} 条结果。".format(name, len(found)))
            results.extend(found)
            break
        errors.append("{}：未返回结果".format(name))
    return results, errors


def cross_validate(query, engines=None, max_results=5, official_only=False, language="zh"):
    """多引擎交叉验证：按网址去重，统计来源数与官方标记。

    返回 (items, meta)：
    items 为 [{title, url, snippet, sources:[引擎名], source_count, official}]
    meta 为 {engines_ok, engines_failed, total, official_count, official_only}
    """
    engines = engines or list(DEFAULT_CONFIG["search"]["engines"])
    per_engine = {}
    failed = []
    for name in engines:
        func = ENGINES.get(name)
        if func is None:
            failed.append(name)
            continue
        try:
            per_engine[name] = func(query, max_results=max_results, language=language) or []
        except Exception as e:
            failed.append(name)
            per_engine[name] = []

    merged = {}
    for engine, items in per_engine.items():
        for item in items:
            url = item.get("url", "")
            if not url:
                continue
            key = _url_key(url)
            if key not in merged:
                merged[key] = {
                    "title": item.get("title", ""),
                    "url": url,
                    "snippet": item.get("snippet", ""),
                    "sources": [],
                    "source_count": 0,
                    "official": is_official(url),
                }
            entry = merged[key]
            if engine not in entry["sources"]:
                entry["sources"].append(engine)
                entry["source_count"] += 1
            if not entry["title"] and item.get("title"):
                entry["title"] = item["title"]
            if not entry["snippet"] and item.get("snippet"):
                entry["snippet"] = item["snippet"]

    items = list(merged.values())
    items.sort(key=lambda x: (-int(x["official"]), -x["source_count"]))
    if official_only:
        items = [x for x in items if x["official"]]

    meta = {
        "engines_ok": [e for e in engines if e not in failed],
        "engines_failed": failed,
        "total": len(items),
        "official_count": sum(1 for x in items if x["official"]),
        "official_only": official_only,
    }
    return items, meta


def format_cross(query, items, meta):
    """格式化交叉验证结果。"""
    lines = []
    lines.append("=" * 50)
    lines.append("联网搜索（多引擎交叉验证）：{}".format(query))
    lines.append("  可用引擎：{}；失败：{}".format(
        "、".join(meta["engines_ok"]) or "无",
        "、".join(meta["engines_failed"]) or "无",
    ))
    lines.append("  独立结果 {} 条，其中官方/权威 {} 条。".format(meta["total"], meta["official_count"]))
    lines.append("=" * 50)
    if not items:
        lines.append("未搜索到结果，建议更换关键词或稍后重试。")
        return "\n".join(lines)

    official_items = [x for x in items if x["official"]]
    other_items = [x for x in items if not x["official"]]
    if official_items:
        lines.append("【官方 / 权威来源（优先参考）】")
        for i, item in enumerate(official_items, 1):
            tag = "[{}个来源]".format(item["source_count"]) if item["source_count"] > 1 else "[1个来源]"
            lines.append("  {}. {} {}".format(i, item["title"] or "无标题", tag))
            lines.append("     {}".format(item["url"]))
            if item["snippet"]:
                lines.append("     {}".format(item["snippet"][:180]))
        lines.append("")
    if other_items:
        lines.append("【其他来源（仅供参考，需自行核实）】")
        for i, item in enumerate(other_items, 1):
            lines.append("  {}. {} [{}个来源]".format(i, item["title"] or "无标题", item["source_count"]))
            lines.append("     {}".format(item["url"]))
            if item["snippet"]:
                lines.append("     {}".format(item["snippet"][:180]))
        lines.append("")

    # 一致性提示
    if meta["official_only"]:
        lines.append("已按 --official 只显示官方来源。")
    if meta["total"] == 0:
        lines.append("[提示] 无任何来源命中，请谨慎对待。")
    elif meta["official_count"] == 0:
        lines.append("[提示] 未找到官方/权威来源，以下信息一致性较低，请以政府、医院官网或专业指南核实。")
    elif meta["total"] < 2:
        lines.append("[提示] 独立来源较少，建议换关键词交叉核实。")
    else:
        lines.append("[提示] 已按官方优先排序；同一条信息被多个独立引擎命中越多，可信度相对越高。")
    lines.append("免责声明：搜索结果仅供参考，不构成医疗建议；请以官方渠道信息为准。")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="联网搜索（多引擎 + 交叉验证 + 官方优先，免密钥）")
    parser.add_argument("query", help="查询词，如：偏头痛 治疗")
    parser.add_argument("--engine", default="", help="只用单个引擎：duckduckgo / bing / mojeek / brave / wikipedia")
    parser.add_argument("--max-results", type=int, default=0, help="每引擎最大结果数，默认取配置")
    parser.add_argument("--cross", action="store_true", default=True, help="多引擎交叉验证（默认开启）")
    parser.add_argument("--official", action="store_true", help="只显示官方/权威来源")
    args = parser.parse_args()

    config = load_config()
    search_cfg = config.get("search", {})
    max_results = max(1, args.max_results or int(search_cfg.get("max_results", 5)))
    language = search_cfg.get("language", "zh")

    if args.engine:
        engines = [args.engine]
    else:
        engines = list(search_cfg.get("engines", DEFAULT_CONFIG["search"]["engines"]))

    if not args.engine and args.cross:
        items, meta = cross_validate(args.query, engines=engines, max_results=max_results,
                                     official_only=args.official, language=language)
        print(format_cross(args.query, items, meta))
        return 0

    # 单引擎旧模式
    results, errors = search(args.query, engines=engines, max_results=max_results, language=language)
    print("=" * 50)
    print("联网搜索：{}（引擎：{}）".format(args.query, "、".join(engines)))
    print("=" * 50)
    if not results:
        for e in errors:
            print("  - " + e)
        print("未返回结果，请稍后重试。")
        return 1
    for i, item in enumerate(results, 1):
        tag = " [官方]" if is_official(item.get("url", "")) else ""
        print("{}. {}{}".format(i, item.get("title", "无标题"), tag))
        print("   URL：{}".format(item.get("url", "")))
        if item.get("snippet"):
            print("   摘要：{}".format(item["snippet"][:200]))
        print("-" * 50)
    print("免责声明：以上搜索结果仅供参考，不构成医疗建议。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

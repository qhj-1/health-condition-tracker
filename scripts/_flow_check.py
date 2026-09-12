# -*- coding: utf-8 -*-
"""流敏感静态检查（维护用）：找出「只在部分分支中赋值、却在分支外使用」的局部变量。

这类 bug 在运行时表现为 UnboundLocalError / NameError，平时跑正常用例不会暴露
（例如 analyze.py 的 trend、export_data.py 的 zf），因此单独用本工具兜底。

用法：
    python scripts/_flow_check.py            # 检查 scripts/ 下所有脚本
    python scripts/_flow_check.py path.py    # 检查指定文件
返回码：0=未发现可疑点，1=发现可疑点。
"""
import ast
import builtins
import os
import sys

BUILTINS = set(dir(builtins))
BRANCH = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler, ast.With, ast.AsyncWith)


def _stored_names(node):
    """收集 node 子树中所有被赋值/导入/绑定的名字。

    不进入嵌套的 def / class 内部（那些是各自独立的作用域，不属于本函数）。
    """
    out = set()

    def walk(n):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)          # 只记录这个名字本身
            return                   # 不下钻其函数体
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            out.add(n.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        for ch in ast.iter_child_nodes(n):
            walk(ch)

    walk(node)
    return out


def _always_terminates(stmts):
    """判断语句序列是否一定以 continue/break/return/raise 结束（即不会往下走）。"""
    if not stmts:
        return False
    last = stmts[-1]
    if isinstance(last, (ast.Continue, ast.Break, ast.Return, ast.Raise)):
        return True
    if isinstance(last, ast.If):
        return _always_terminates(last.body) and _always_terminates(last.orelse)
    return False


def _guaranteed_names(node):
    """返回 node 中「所有执行路径上都会被赋值」的名字。

    处理 if/else 全覆盖、try/except 全覆盖、顺序语句等情况。
    """
    if isinstance(node, ast.If):
        body = _guaranteed_names_body(node.body)
        other = _guaranteed_names_body(node.orelse) if node.orelse else set()
        if node.orelse and _always_terminates(node.orelse):
            return body          # else 分支必终止，走 if 分支时 body 必然执行
        if _always_terminates(node.body):
            return other
        return body & other
    if isinstance(node, ast.Try):
        body = _guaranteed_names_body(node.body)
        handlers = []
        for h in node.handlers:
            if _always_terminates(h.body):
                continue          # 该异常路径不会继续往下执行
            handlers.append(_guaranteed_names_body(h.body))
        if node.orelse:
            handlers.append(_guaranteed_names_body(node.orelse))
        if not handlers:
            return body
        common = set.intersection(*handlers) if len(handlers) > 1 else handlers[0]
        return body & common
    if isinstance(node, ast.While):
        # while True: ... break 的循环体至少执行一次
        is_true = isinstance(node.test, ast.Constant) and node.test.value is True
        has_break = any(isinstance(n, ast.Break) for n in ast.walk(node))
        if is_true and has_break:
            return _guaranteed_names_body(node.body) | _guaranteed_names_body(node.orelse)
        # 普通循环体可能一次都不执行；只有 else 子句必然执行
        return _guaranteed_names_body(node.orelse) if node.orelse else set()
    if isinstance(node, (ast.For, ast.AsyncFor)):
        # 循环体可能一次都不执行；只有 else 子句必然执行
        return _guaranteed_names_body(node.orelse) if node.orelse else set()
    return _stored_names(node)


def _guaranteed_names_body(body):
    out = set()
    for stmt in body:
        out |= _guaranteed_names(stmt)
    return out


def module_names(tree):
    return _guaranteed_names_body(tree.body)


def analyze_func(fn, globals_):
    params = set()
    for a in list(fn.args.args) + list(fn.args.kwonlyargs) + list(fn.args.posonlyargs):
        params.add(a.arg)
    if fn.args.vararg:
        params.add(fn.args.vararg.arg)
    if fn.args.kwarg:
        params.add(fn.args.kwarg.arg)

    uncond = _guaranteed_names_body(fn.body)
    cond_only = set()
    loads = []

    def walk(node, cond):
        # 各类「绑定」：except as e / lambda 参数 / import / with as / for 目标
        if isinstance(node, ast.arg):
            (cond_only if cond else uncond).add(node.arg)
            return
        if isinstance(node, ast.ExceptHandler) and node.name:
            (cond_only if cond else uncond).add(node.name)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                nm = (a.asname or a.name).split(".")[0]
                (cond_only if cond else uncond).add(nm)
        if isinstance(node, ast.Global):
            for n in node.names:
                uncond.add(n)          # global 声明视为已定义
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # 嵌套函数/类是独立作用域，只看其名字，不下钻其内部
            if cond:
                cond_only.add(node.name)
            else:
                uncond.add(node.name)
            return
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                if cond:
                    cond_only.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                loads.append((node.id, node.lineno, cond))
        if isinstance(node, BRANCH):
            cond = True
        for ch in ast.iter_child_nodes(node):
            walk(ch, cond)

    for stmt in fn.body:
        walk(stmt, False)

    dunders = {"__name__", "__file__", "__doc__", "__package__", "__spec__", "__builtins__"}
    problems = []
    seen = set()
    for name, line, cond in loads:
        defined = (name in params or name in uncond or name in cond_only
                   or name in globals_ or name in BUILTINS or name in dunders)
        if not defined:
            key = ("UNDEF", name, line)
            if key not in seen:
                seen.add(key)
                problems.append(("UNDEF", fn.name, name, line))
            continue
        if cond or name in params or name in uncond or name in globals_ or name in BUILTINS:
            continue
        if name in cond_only and name not in uncond and (name, line) not in seen:
            seen.add((name, line))
            problems.append(("BRANCH", fn.name, name, line))
    return problems


def check_file(path):
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    globals_ = module_names(tree) | BUILTINS
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.extend(analyze_func(node, globals_))
    return out


def main():
    targets = sys.argv[1:]
    if not targets:
        targets = []
        for base, _, files in os.walk(os.path.dirname(os.path.abspath(__file__))):
            for f in sorted(files):
                if f.endswith(".py") and not f.startswith("_flow_check"):
                    targets.append(os.path.join(base, f))
    total = 0
    for p in targets:
        for kind, fn, name, line in check_file(p):
            total += 1
            if kind == "UNDEF":
                print("UNDEFINED {} :: 函数 {} 使用未定义的名字 {}（第 {} 行，可能缺少 import）".format(p, fn, name, line))
            else:
                print("SUSPECT   {} :: 函数 {} 中变量 {} 在第 {} 行分支外使用（仅部分分支赋值）".format(p, fn, name, line))
    print("可疑点合计：{}".format(total))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())

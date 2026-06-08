#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
json_tool.py — JSON 数据处理工具：格式化美化、单行压缩以及清理还原转义过的 JSON 字符串。

用法示例：
  python json_tool.py format '{"name":"bob","age":20}'
  python json_tool.py format ./config.json
  python json_tool.py minify '{\n  "name": "bob"\n}'
  python json_tool.py clean '\"{\\\"name\\\":\\\"bob\\\"}\"'
  cat data.json | python json_tool.py format
"""

from __future__ import annotations
import sys
import os
import json
import argparse
from typing import Any


# ── 颜色输出 ─────────────────────────────────────────────────────────────────
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    def c_err(s): return f"{Fore.RED}{s}{Style.RESET_ALL}"
    def c_info(s): return f"{Fore.GREEN}{s}{Style.RESET_ALL}"
except ImportError:
    def c_err(s): return s
    def c_info(s): return s


def get_input_content(val_or_path: str | None) -> str:
    """获取输入的 JSON 字符串内容（来自参数、文件或 stdin）"""
    if val_or_path is None or val_or_path == "":
        # 从 stdin 读取
        if sys.stdin.isatty():
            print("请输入 JSON 内容（Ctrl+D 或 Ctrl+Z+Enter 结束）：", file=sys.stderr)
        return sys.stdin.read().strip()

    # 如果是本地文件，读取文件
    if os.path.exists(val_or_path) and os.path.isfile(val_or_path):
        try:
            with open(val_or_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            print(c_err(f"读取文件失败: {e}"), file=sys.stderr)
            sys.exit(1)

    # 否则直接作为字符串
    return val_or_path.strip()


def parse_json(raw: str) -> Any:
    """尝试用各种方法解析 JSON"""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # 如果解析失败，尝试去掉头尾多余的包裹引号
        if raw.startswith('"') and raw.endswith('"') and len(raw) > 2:
            try:
                # 尝试用 python loads 剥离一层转义外壳
                unescaped = json.loads(raw)
                return json.loads(unescaped)
            except Exception:
                pass
        raise e


def handle_format(args):
    """格式化并美化 JSON"""
    raw = get_input_content(args.input)
    if not raw:
        print(c_err("错误: 输入内容为空"), file=sys.stderr)
        sys.exit(1)

    try:
        data = parse_json(raw)
        formatted = json.dumps(data, ensure_ascii=False, indent=2)
        print(formatted)
    except Exception as e:
        print(c_err(f"JSON 格式化失败: {e}"), file=sys.stderr)
        sys.exit(1)


def handle_minify(args):
    """压缩 JSON (单行无空格)"""
    raw = get_input_content(args.input)
    if not raw:
        print(c_err("错误: 输入内容为空"), file=sys.stderr)
        sys.exit(1)

    try:
        data = parse_json(raw)
        minified = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        print(minified)
    except Exception as e:
        print(c_err(f"JSON 压缩失败: {e}"), file=sys.stderr)
        sys.exit(1)


def handle_clean(args):
    """还原被双重转义（带有反斜杠）的 JSON 字符串"""
    raw = get_input_content(args.input)
    if not raw:
        print(c_err("错误: 输入内容为空"), file=sys.stderr)
        sys.exit(1)

    # 1. 尝试直接去掉反斜杠
    # 例如将 \" 替换为 ", \\\" 替换为 \" 等
    # 如果字符串最前面是引号，剥离最外层引号
    if raw.startswith('"') and raw.endswith('"') and len(raw) > 2:
        try:
            raw = json.loads(raw)
        except Exception:
            # 强行剥除最外层双引号
            raw = raw[1:-1]

    # 清理常见的转义反斜杠
    cleaned = raw.replace('\\"', '"').replace('\\\\', '\\')
    
    # 再次尝试解析
    try:
        data = json.loads(cleaned)
        formatted = json.dumps(data, ensure_ascii=False, indent=2)
        print(formatted)
    except Exception as e:
        # 如果普通替换不行，退一步直接用 eval 剥离或显示清洗后文本
        print(c_warn(f"警告: 无法完全解析为 JSON ({e})。以下为去除反斜杠后的清洗文本：\n"))
        print(cleaned)


# 警告信息高亮
def c_warn(s):
    try:
        from colorama import Fore
        return f"{Fore.YELLOW}{s}"
    except ImportError:
        return s


def main():
    p = argparse.ArgumentParser(
        description="JSON 数据工具：支持格式化/美化、单行压缩和转义 JSON 清理还原。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # format
    p_fmt = sub.add_parser("format", help="美化并格式化 JSON")
    p_fmt.add_argument("input", nargs="?", help="JSON 字符串或文件路径。若不传，从标准输入读取")
    p_fmt.set_defaults(func=handle_format)

    # minify
    p_min = sub.add_parser("minify", help="压缩 JSON 为单行")
    p_min.add_argument("input", nargs="?", help="JSON 字符串或文件路径。若不传，从标准输入读取")
    p_min.set_defaults(func=handle_minify)

    # clean
    p_cln = sub.add_parser("clean", help="清洗并还原转义过的 JSON 字符串")
    p_cln.add_argument("input", nargs="?", help="包含转义符的 JSON 字符串或文件。若不传，从标准输入读取")
    p_cln.set_defaults(func=handle_clean)

    args = p.parse_args()

    # Reconfigure stdout for utf-8
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    args.func(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dev_tool.py — 开发者日常百宝箱：提供时间戳转换、Base64/URL 编解码、哈希计算等高频功能。

用法示例：
  python dev_tool.py time 1717764000
  python dev_tool.py time "2024-06-07 22:00:00"
  python dev_tool.py base64 encode "hello world"
  python dev_tool.py url decode "%E4%BD%A0%E5%A5%BD"
  python dev_tool.py hash md5 "admin123"
  python dev_tool.py hash sha256 ./file.txt
"""

import sys
import os
import time
import base64
import urllib.parse
import hashlib
import argparse
from datetime import datetime

# ── 颜色输出 ─────────────────────────────────────────────────────────────────
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    def c_label(s): return f"{Fore.CYAN}{s}{Style.RESET_ALL}"
    def c_val(s): return f"{Fore.GREEN}{s}{Style.RESET_ALL}"
    def c_err(s): return f"{Fore.RED}{s}{Style.RESET_ALL}"
except ImportError:
    def c_label(s): return s
    def c_val(s): return s
    def c_err(s): return s

def handle_time(args):
    """处理时间戳与日期字符串互转"""
    val = args.value
    if val is None or val.lower() == "now":
        # 获取当前时间
        ts = time.time()
        dt = datetime.fromtimestamp(ts)
        print(f"{c_label('当前时间戳 (秒)  :')} {c_val(int(ts))}")
        print(f"{c_label('当前时间戳 (毫秒):')} {c_val(int(ts * 1000))}")
        print(f"{c_label('本地格式化时间   :')} {c_val(dt.strftime('%Y-%m-%d %H:%M:%S'))}")
        return

    # 1. 尝试判定是否为时间戳数字
    if val.isdigit():
        num = int(val)
        # 13位为毫秒时间戳，10位为秒级时间戳
        if len(val) == 13:
            ts_sec = num / 1000.0
        else:
            ts_sec = float(num)
        try:
            dt = datetime.fromtimestamp(ts_sec)
            print(f"{c_label('时间戳 (秒)    :')} {val if len(val) == 10 else int(ts_sec)}")
            print(f"{c_label('本地格式化时间 :')} {c_val(dt.strftime('%Y-%m-%d %H:%M:%S'))}")
        except Exception as e:
            print(c_err(f"时间戳数值超出范围: {e}"), file=sys.stderr)
            sys.exit(1)
        return

    # 2. 尝试解析时间字符串
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
    ]
    dt = None
    for fmt in formats:
        try:
            dt = datetime.strptime(val, fmt)
            break
        except ValueError:
            continue

    if dt is None:
        print(c_err(f"错误: 无法解析的时间格式 '{val}'。支持格式如 YYYY-MM-DD HH:MM:SS"), file=sys.stderr)
        sys.exit(1)

    ts_sec = int(dt.timestamp())
    print(f"{c_label('格式化时间   :')} {val}")
    print(f"{c_label('时间戳 (秒)  :')} {c_val(ts_sec)}")
    print(f"{c_label('时间戳 (毫秒):')} {c_val(ts_sec * 1000)}")


def handle_base64(args):
    """处理 Base64 编码与解码"""
    op = args.op
    val = args.value

    if op == "encode":
        encoded = base64.b64encode(val.encode("utf-8")).decode("utf-8")
        print(f"{c_label('Base64 编码结果:')} {c_val(encoded)}")
    elif op == "decode":
        try:
            # 补齐 Padding
            missing_padding = len(val) % 4
            if missing_padding:
                val += "=" * (4 - missing_padding)
            decoded_bytes = base64.b64decode(val.encode("utf-8"))
            # 尝试 utf-8，失败再试 gbk
            for enc in ("utf-8", "gbk"):
                try:
                    decoded = decoded_bytes.decode(enc)
                    print(f"{c_label(f'Base64 解码结果 [{enc}]:')} {c_val(decoded)}")
                    return
                except UnicodeDecodeError:
                    continue
            print(f"{c_label('Base64 解码结果 [bytes]:')} {c_val(repr(decoded_bytes))}")
        except Exception as e:
            print(c_err(f"Base64 解码失败: {e}"), file=sys.stderr)
            sys.exit(1)


def handle_url(args):
    """处理 URL 编码与解码"""
    op = args.op
    val = args.value

    if op == "encode":
        encoded = urllib.parse.quote(val, safe="")
        print(f"{c_label('URL 编码结果:')} {c_val(encoded)}")
    elif op == "decode":
        try:
            decoded = urllib.parse.unquote(val)
            print(f"{c_label('URL 解码结果:')} {c_val(decoded)}")
        except Exception as e:
            print(c_err(f"URL 解码失败: {e}"), file=sys.stderr)
            sys.exit(1)


def handle_hash(args):
    """计算哈希值（支持字符串和文件）"""
    alg = args.alg.lower()
    val = args.value

    h = hashlib.md5() if alg == "md5" else hashlib.sha256()

    # 如果是存在的文件路径，计算文件哈希
    if os.path.exists(val) and os.path.isfile(val):
        try:
            with open(val, "rb") as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            print(f"{c_label(f'文件 {alg.upper()} :')} {c_path(val)}")
            print(f"{c_label('Hash 结果    :')} {c_val(h.hexdigest())}")
            return
        except OSError as e:
            print(c_err(f"读取文件失败: {e}"), file=sys.stderr)
            sys.exit(1)

    # 否则计算字符串哈希
    h.update(val.encode("utf-8"))
    print(f"{c_label(f'字符串 {alg.upper()}:')} {val!r}")
    print(f"{c_label('Hash 结果      :')} {c_val(h.hexdigest())}")


# 用于美化终端输出文件路径
def c_path(s):
    try:
        from colorama import Fore
        return f"{Fore.CYAN}{s}"
    except ImportError:
        return s


def main():
    p = argparse.ArgumentParser(
        description="开发者百宝箱：提供时间转换、Base64/URL编解码、哈希计算等高频工具。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="tool", required=True)

    # ── time ──────────────────────────────────────────
    p_time = sub.add_parser("time", help="时间戳与日期时间互转")
    p_time.add_argument("value", nargs="?", default="now", help="10/13位时间戳，或 YYYY-MM-DD HH:MM:SS，不传代表当前时间")
    p_time.set_defaults(func=handle_time)

    # ── base64 ────────────────────────────────────────
    p_b64 = sub.add_parser("base64", help="Base64 编码 / 解码")
    p_b64.add_argument("op", choices=["encode", "decode"], help="encode: 编码, decode: 解码")
    p_b64.add_argument("value", help="要编码/解码的文本")
    p_b64.set_defaults(func=handle_base64)

    # ── url ───────────────────────────────────────────
    p_url = sub.add_parser("url", help="URL 编码 / 解码")
    p_url.add_argument("op", choices=["encode", "decode"], help="encode: 编码, decode: 解码")
    p_url.add_argument("value", help="要编码/解码的网址/参数")
    p_url.set_defaults(func=handle_url)

    # ── hash ──────────────────────────────────────────
    p_hash = sub.add_parser("hash", help="计算 MD5 或 SHA-256 哈希值")
    p_hash.add_argument("alg", choices=["md5", "sha256"], help="哈希算法")
    p_hash.add_argument("value", help="字符串内容，或者是要计算的本地文件路径")
    p_hash.set_defaults(func=handle_hash)

    args = p.parse_args()
    
    # 强制命令行输出编码为 utf-8，解决 Windows console 乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
        
    args.func(args)


if __name__ == "__main__":
    main()

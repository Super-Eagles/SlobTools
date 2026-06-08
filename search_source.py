#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_source.py — 在指定目录的源码中查找关键词或正则，支持自动检测 UTF-8/GBK 编码，并高亮匹配行。

用法示例：
  python search_source.py "class User"
  python search_source.py "void.*init" --regex --dir ./src
  python search_source.py "TODO" --case-sensitive --ext .cpp .h
"""

from __future__ import annotations
import os
import sys
import re
import argparse

# ── Colorama 颜色高亮 ─────────────────────────────────────────────────────────
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    def c_path(s): return f"{Fore.CYAN}{s}{Style.RESET_ALL}"
    def c_line(s): return f"{Fore.YELLOW}{s}{Style.RESET_ALL}"
    def c_match(s): return f"{Fore.RED}{Style.BRIGHT}{s}{Style.RESET_ALL}"
    def c_info(s): return f"{Fore.GREEN}{s}{Style.RESET_ALL}"
    def c_err(s): return f"{Fore.RED}{s}{Style.RESET_ALL}"
    def c_warn(s): return f"{Fore.YELLOW}{s}{Style.RESET_ALL}"
except ImportError:
    def c_path(s): return s
    def c_line(s): return s
    def c_match(s): return s
    def c_info(s): return s
    def c_err(s): return s
    def c_warn(s): return s

# ── 引入公共编码模块 ──────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
try:
    from encoding_utils import guess_encoding, is_text_file
except ImportError:
    # 简单的 fallback 降级
    def is_text_file(path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        return ext in (".txt", ".py", ".cpp", ".h", ".cs", ".java", ".js", ".ts", ".html", ".css", ".json", ".md", ".xml", ".sql")
        
    def guess_encoding(raw: bytes):
        if raw.startswith(b"\xef\xbb\xbf"):
            return "utf-8", 1.0, True
        try:
            raw.decode("utf-8", errors="strict")
            return "utf-8", 0.9, True
        except Exception:
            pass
        try:
            raw.decode("gbk", errors="strict")
            return "gbk", 0.7, True
        except Exception:
            pass
        return "unknown", 0.0, False


SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build", "out", "target", ".idea", ".vs",
}

def load_file_content(path: str) -> tuple[str, str] | None:
    """加载文件，返回 (文本内容, 编码格式)；若失败返回 None。"""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None

    if not raw:
        return "", "utf-8"

    # 先试猜
    enc, conf, certain = guess_encoding(raw)
    
    # 双重保护：如果猜错，按正常逻辑解码
    for encoding in (enc, "utf-8", "gbk"):
        if encoding == "unknown" or not encoding:
            continue
        try:
            # 去除 UTF-8 BOM
            if encoding == "utf-8" and raw.startswith(b"\xef\xbb\xbf"):
                decoded = raw[3:].decode("utf-8")
            else:
                decoded = raw.decode(encoding)
            return decoded, encoding
        except Exception:
            continue
            
    # 强行解码（带替换符）
    try:
        return raw.decode("gbk", errors="replace"), "gbk (lossy)"
    except Exception:
        return None


def search_in_file(
    path: str,
    pattern: str,
    *,
    use_regex: bool = False,
    case_sensitive: bool = False,
) -> list[tuple[int, str, list[tuple[int, int]]]]:
    """
    在单个文件中搜索关键词，返回: list of (行号, 匹配行内容, 匹配区间 [(start_idx, end_idx), ...])
    """
    loaded = load_file_content(path)
    if loaded is None:
        return []
        
    content, enc = loaded
    lines = content.splitlines()
    matches = []
    
    flags = 0 if case_sensitive else re.IGNORECASE
    
    if use_regex:
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            print(c_err(f"正则表达式错误: {e}"), file=sys.stderr)
            sys.exit(1)
            
        for i, line in enumerate(lines):
            line_matches = []
            for m in regex.finditer(line):
                line_matches.append((m.start(), m.end()))
            if line_matches:
                matches.append((i + 1, line, line_matches))
    else:
        needle = pattern if case_sensitive else pattern.lower()
        for i, line in enumerate(lines):
            search_line = line if case_sensitive else line.lower()
            line_matches = []
            start = 0
            while True:
                idx = search_line.find(needle, start)
                if idx == -1:
                    break
                line_matches.append((idx, idx + len(pattern)))
                start = idx + len(pattern)
            if line_matches:
                matches.append((i + 1, line, line_matches))
                
    return matches


def highlight_line(line: str, spans: list[tuple[int, int]]) -> str:
    """高亮匹配行中的关键词"""
    # 合并区间
    spans = sorted(spans)
    parts = []
    last_idx = 0
    for start, end in spans:
        if start < last_idx:
            # 重叠，扩展上次的区间
            continue
        parts.append(line[last_idx:start])
        parts.append(c_match(line[start:end]))
        last_idx = end
    parts.append(line[last_idx:])
    return "".join(parts)


def main():
    p = argparse.ArgumentParser(
        description="全局源码查找工具，自动检测 UTF-8/GBK，高亮匹配行。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("pattern", help="要搜索的关键词或正则表达式")
    p.add_argument("-d", "--dir", default=".", help="搜索的根目录（默认当前目录）")
    p.add_argument("-r", "--regex", action="store_true", help="将 pattern 视为正则表达式")
    p.add_argument("-c", "--case-sensitive", action="store_true", help="搜索时区分大小写（默认不区分）")
    p.add_argument("-e", "--ext", nargs="+", help="限制匹配的文件后缀，例如: .py .cpp .h")
    p.add_argument("--exclude-dirs", nargs="+", help="额外排除的子目录")
    args = p.parse_args()

    # Reconfigure stdout for utf-8
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    root_dir = os.path.abspath(args.dir)
    if not os.path.isdir(root_dir):
        print(c_err(f"错误: '{root_dir}' 不是有效目录"), file=sys.stderr)
        sys.exit(1)

    exclude_dirs = SKIP_DIRS.copy()
    if args.exclude_dirs:
        exclude_dirs.update(args.exclude_dirs)

    allowed_exts = None
    if args.ext:
        allowed_exts = {e if e.startswith(".") else f".{e}" for e in args.ext}

    print(c_info(f"🔍 正在搜索: {args.pattern!r}  目录: {root_dir}"))
    print(c_info("─" * 60))

    match_files_count = 0
    total_matches_count = 0

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # 就地修改 dirnames 以剪枝排除目录
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            
            # 后缀过滤
            if allowed_exts:
                _, ext = os.path.splitext(name)
                if ext.lower() not in allowed_exts:
                    continue
            elif not is_text_file(path):
                # 默认只查找文本文件
                continue

            matches = search_in_file(
                path,
                args.pattern,
                use_regex=args.regex,
                case_sensitive=args.case_sensitive
            )
            
            if matches:
                match_files_count += 1
                total_matches_count += len(matches)
                rel_path = os.path.relpath(path, root_dir)
                print(c_path(f"📄 {rel_path}"))
                for line_num, line_content, spans in matches:
                    hl_line = highlight_line(line_content.strip(), spans)
                    print(f"  {c_line(f'{line_num:4d}')}: {hl_line}")
                print()

    print(c_info("─" * 60))
    print(c_info(f"🎉 搜索完成。共在 {match_files_count} 个文件中找到 {total_matches_count} 处匹配。"))


if __name__ == "__main__":
    main()

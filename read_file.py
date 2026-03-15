#!/usr/bin/env python3
"""
read_gbk.py — 读取 / 搜索文本文件，自动识别 GBK / UTF-8 编码，输出为 UTF-8。

用法示例：
  python read_gbk.py file.txt                          # 读取全文（自动检测编码）
  python read_gbk.py file.txt --start 10 --end 20      # 读取第 10~20 行
  python read_gbk.py file.txt --search "关键词"         # 搜索（含上下文）
  python read_gbk.py file.txt --search "pattern" --regex --context 3
  python read_gbk.py file.txt --encoding gbk            # 手动指定编码
  python read_gbk.py file.txt --encoding utf-8          # 手动指定编码
  python read_gbk.py file.txt --out result.txt          # 结果写入文件
"""

from __future__ import annotations
import sys
import os
import re
import argparse

# ── 依赖公共模块（同目录）────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
try:
    from encoding_utils import UTF8_BOM, guess_encoding, strip_utf8_bom
    _HAS_UTILS = True
except ImportError:
    _HAS_UTILS = False
    UTF8_BOM = b"\xef\xbb\xbf"
    def strip_utf8_bom(raw: bytes) -> bytes:
        return raw[len(UTF8_BOM):] if raw.startswith(UTF8_BOM) else raw
    def guess_encoding(raw: bytes):
        if raw.startswith(UTF8_BOM):
            return "utf-8", 1.0, True
        try:
            raw.decode("utf-8", errors="strict")
            return "utf-8", 0.9, True
        except (UnicodeDecodeError, ValueError):
            pass
        try:
            raw.decode("gbk", errors="strict")
            return "gbk", 0.7, False
        except (UnicodeDecodeError, ValueError):
            pass
        return "unknown", 0.0, False


# ── 核心：读取文件为行列表 ───────────────────────────────────────────────────

def load_lines(file_path: str, encoding: str = "auto") -> tuple[list[str], str]:
    """
    读取文件，返回 (行列表, 实际使用的编码名称)。
    encoding="auto" 时自动检测 GBK / UTF-8；
    也可手动传入 "gbk" / "utf-8" / "utf8" 等强制解码。
    """
    with open(file_path, "rb") as f:
        raw = f.read()

    if not raw:
        return [], "utf-8"

    # ── 手动指定编码 ──────────────────────────────────────────────────────────
    if encoding.lower() != "auto":
        enc = encoding.lower().replace("-", "")
        if enc in ("utf8", "utf8sig"):
            content = strip_utf8_bom(raw).decode("utf-8", errors="replace")
            return content.splitlines(), "utf-8"
        else:
            content = raw.decode(encoding, errors="replace")
            return content.splitlines(), encoding

    # ── 自动检测 ──────────────────────────────────────────────────────────────
    # 优先判断 UTF-8 BOM
    if raw.startswith(UTF8_BOM):
        content = strip_utf8_bom(raw).decode("utf-8", errors="replace")
        return content.splitlines(), "utf-8 (BOM)"

    detected_enc, conf, certain = guess_encoding(raw)

    # 检测为 UTF-8，且置信度足够高
    if detected_enc == "utf-8" and (certain or conf >= 0.80):
        content = raw.decode("utf-8", errors="replace")
        return content.splitlines(), f"utf-8 (置信度 {conf:.0%})"

    # 检测为 GBK
    if detected_enc == "gbk":
        content = raw.decode("gbk", errors="replace")
        return content.splitlines(), f"gbk (置信度 {conf:.0%})"

    # 纯 ASCII 子集（两种编码均可解，优先 UTF-8）
    if all(b < 0x80 for b in raw):
        content = raw.decode("utf-8")
        return content.splitlines(), "ascii"

    # 兜底：强制 GBK 解码（GBK 是 ASCII 超集，不会抛异常）
    content = raw.decode("gbk", errors="replace")
    return content.splitlines(), f"gbk (兜底, 检测={detected_enc})"


def sanitize(line: str) -> str:
    """将不可打印字符（换行除外）替换为空格，防止终端乱码。"""
    return "".join(c if (c.isprintable() or c == "\t") else " " for c in line)


# ── 读取指定行范围 ───────────────────────────────────────────────────────────

def read_lines(lines: list[str], start: int, end: int | None) -> str:
    """
    返回带行号的文本块。
    start / end 均为 1-indexed，end=None 表示读到末尾。
    """
    total = len(lines)
    end = total if end is None else end

    if start < 1:
        start = 1
    if end > total:
        end = total
    if start > end:
        return f"(无内容：start={start} > end={end}，文件共 {total} 行)"

    width = len(str(total))   # 行号宽度自适应文件大小
    out: list[str] = [f"# 文件共 {total} 行，显示第 {start}～{end} 行"]
    for i in range(start - 1, end):
        out.append(f"{i + 1:{width}}: {sanitize(lines[i])}")
    return "\n".join(out)


# ── 搜索 ─────────────────────────────────────────────────────────────────────

def search_lines(
    lines: list[str],
    pattern: str,
    *,
    use_regex: bool = False,
    ignore_case: bool = True,
    context: int = 0,
) -> str:
    """
    在行列表中搜索 pattern，返回格式化的匹配块。
    支持普通字符串匹配（默认）和正则表达式（--regex）。
    """
    flags = re.IGNORECASE if ignore_case else 0

    if use_regex:
        try:
            compiled = re.compile(pattern, flags)
        except re.error as e:
            return f"正则表达式错误：{e}"
        match_fn = lambda line: compiled.search(line) is not None  # noqa: E731
    else:
        needle = pattern.lower() if ignore_case else pattern
        match_fn = (
            lambda line: needle in line.lower()
            if ignore_case
            else lambda line: needle in line  # noqa: E731
        )

    total = len(lines)
    width = len(str(total))
    out: list[str] = []
    match_count = 0

    for i, line in enumerate(lines):
        if not match_fn(line):
            continue
        match_count += 1
        ctx_start = max(0, i - context)
        ctx_end = min(total, i + context + 1)
        out.append(f"─── 第 {i + 1} 行匹配 ───")
        for j in range(ctx_start, ctx_end):
            marker = ">>" if j == i else "  "
            out.append(f"{marker}{j + 1:{width}}: {sanitize(lines[j])}")

    if not out:
        return f'未找到匹配项："{pattern}"'
    out.insert(0, f"# 共找到 {match_count} 处匹配（模式：{pattern!r}）\n")
    return "\n".join(out)


# ── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="读取或搜索文本文件（自动识别 GBK / UTF-8），输出为 UTF-8。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("filename", help="文件路径（GBK 或 UTF-8）")
    p.add_argument("--encoding", default="auto", metavar="ENC",
                   help="手动指定编码：gbk / utf-8 / auto（默认 auto）")
    p.add_argument("--start", type=int, default=1, metavar="N",
                   help="起始行（1-indexed，默认 1）")
    p.add_argument("--end", type=int, default=None, metavar="N",
                   help="结束行（1-indexed，默认末尾）")
    p.add_argument("--search", type=str, default=None, metavar="PATTERN",
                   help="搜索字符串或正则表达式")
    p.add_argument("--regex", action="store_true",
                   help="将 --search 的值视为正则表达式")
    p.add_argument("--case-sensitive", action="store_true",
                   help="搜索时区分大小写（默认不区分）")
    p.add_argument("--context", type=int, default=2, metavar="N",
                   help="搜索结果上下文行数（默认 2）")
    p.add_argument("--out", type=str, default=None, metavar="FILE",
                   help="将结果写入文件（UTF-8），默认输出到 stdout")
    p.add_argument("--stats", action="store_true",
                   help="仅输出文件统计信息（行数、字节数、编码）")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    path = os.path.abspath(args.filename)
    if not os.path.exists(path):
        print(f"错误：文件 '{path}' 不存在。", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(path):
        print(f"错误：'{path}' 不是普通文件。", file=sys.stderr)
        sys.exit(1)

    try:
        lines, detected_enc = load_lines(path, args.encoding)
    except Exception as e:
        print(f"读取文件失败：{e}", file=sys.stderr)
        sys.exit(1)

    # ── 仅统计模式 ───────────────────────────────────────────────────────────
    if args.stats:
        size = os.path.getsize(path)
        result = (
            f"文件  ：{path}\n"
            f"编码  ：{detected_enc}\n"
            f"大小  ：{size:,} 字节\n"
            f"行数  ：{len(lines):,} 行\n"
            f"字符数：{sum(len(l) for l in lines):,}"
        )
    # ── 搜索模式 ─────────────────────────────────────────────────────────────
    elif args.search is not None:
        result = search_lines(
            lines,
            args.search,
            use_regex=args.regex,
            ignore_case=not args.case_sensitive,
            context=args.context,
        )
    # ── 读取模式 ─────────────────────────────────────────────────────────────
    else:
        result = read_lines(lines, args.start, args.end)

    # ── 输出 ─────────────────────────────────────────────────────────────────
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"结果已写入：{args.out}", file=sys.stderr)
    else:
        # stdout 在 Windows 上可能是 gbk；强制 utf-8 输出
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(result)


if __name__ == "__main__":
    main()

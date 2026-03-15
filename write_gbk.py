#!/usr/bin/env python3
"""
write_gbk.py — 对 GBK 编码文件进行安全写入，绝不破坏原有编码。

专为 AI 工具调用设计：所有内容以 UTF-8 传入，内部自动转换为 GBK 写回。
操作前自动备份，写入后校验编码完整性。

━━━ 支持的操作模式（--mode）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  append    在文件末尾追加内容
  insert    在指定行之前插入内容
  replace   替换指定行范围（含 start，含 end）的内容
  delete    删除指定行范围
  patch     全局文本替换（--old 旧文本，--new 新文本，支持正则）
  overwrite 用新内容完全覆盖文件

━━━ 内容来源（三选一）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  --content "文本"        直接传入 UTF-8 字符串
  --content-file path     从 UTF-8 文件读取内容
  （不传则从 stdin 读取）

━━━ 安全特性 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • 写入前自动生成 .bak 备份（可用 --no-backup 关闭）
  • 新内容若含 GBK 不支持的字符，默认拒绝写入（--allow-loss 可覆盖）
  • 原子写入：先写临时文件，再 rename，避免写到一半崩溃导致文件损坏
  • 写入后重新读取校验，确认文件仍可被 GBK 解码

━━━ 典型用法 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # 追加一行
  python write_gbk.py file.txt --mode append --content "新的一行"

  # 在第 5 行前插入
  python write_gbk.py file.txt --mode insert --start 5 --content "插入内容"

  # 替换第 10~15 行
  python write_gbk.py file.txt --mode replace --start 10 --end 15 \\
      --content-file new_block.txt

  # 删除第 3~7 行
  python write_gbk.py file.txt --mode delete --start 3 --end 7

  # 全局字符串替换
  python write_gbk.py file.txt --mode patch --old "旧字符串" --new "新字符串"

  # 正则替换（所有数字前加 #）
  python write_gbk.py file.txt --mode patch --old "\\d+" --new "#\\g<0>" --regex

  # 完全覆盖
  python write_gbk.py file.txt --mode overwrite --content-file new_content.txt

  # 预览（不写入）
  python write_gbk.py file.txt --mode replace --start 1 --end 3 \\
      --content "preview" --dry-run
"""

from __future__ import annotations
import sys
import os
import re
import shutil
import tempfile
import argparse
import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
try:
    from encoding_utils import UTF8_BOM, is_gbk_strict
except ImportError:
    UTF8_BOM = b"\xef\xbb\xbf"

    def is_gbk_strict(raw: bytes) -> bool:
        try:
            raw.decode("gbk", errors="strict")
            return True
        except (UnicodeDecodeError, ValueError):
            return False


# ══════════════════════════════════════════════════════════════════════════════
# 核心辅助
# ══════════════════════════════════════════════════════════════════════════════

def load_gbk(path: str) -> tuple[list[str], bool]:
    """
    加载 GBK 文件，返回 (行列表, 文件末尾是否原本有换行)。
    对新建文件（不存在）返回空列表。
    """
    if not os.path.exists(path):
        return [], False

    with open(path, "rb") as f:
        raw = f.read()

    # 剥离 UTF-8 BOM（不应存在于 GBK 文件中，但防御性处理）
    if raw.startswith(UTF8_BOM):
        raw = raw[len(UTF8_BOM):]

    content = raw.decode("gbk", errors="replace")
    trailing_newline = content.endswith("\n")
    lines = content.splitlines()
    return lines, trailing_newline


def encode_to_gbk(text: str, *, allow_loss: bool = False) -> bytes:
    """
    将 UTF-8 字符串编码为 GBK 字节。
    allow_loss=False 时若有不可编码字符则抛出 UnicodeEncodeError。
    """
    errors = "replace" if allow_loss else "strict"
    return text.encode("gbk", errors=errors)


def save_gbk_atomic(path: str, lines: list[str], *, allow_loss: bool = False) -> None:
    """
    原子写入：先写临时文件，再 rename，保证中途失败不损坏原文件。
    保留原文件末尾换行习惯（GBK 文件通常有末尾换行）。
    """
    content = "\n".join(lines)
    if lines:  # 保持末尾换行
        content += "\n"

    gbk_bytes = encode_to_gbk(content, allow_loss=allow_loss)

    # 写入前验证：确认编码结果可被 GBK 无损还原
    if not is_gbk_strict(gbk_bytes):
        raise RuntimeError("编码后的字节无法被 GBK 解码，操作已中止。")

    dir_name = os.path.dirname(os.path.abspath(path)) or "."
    tmp_fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(gbk_bytes)
        os.replace(tmp_path, path)   # 原子性 rename
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def backup(path: str) -> str | None:
    """生成带时间戳的 .bak 备份，返回备份路径；文件不存在则返回 None。"""
    if not os.path.exists(path):
        return None
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = f"{path}.{ts}.bak"
    shutil.copy2(path, bak_path)
    return bak_path


def read_content_input(args: argparse.Namespace) -> str:
    """从 --content / --content-file / stdin 读取 UTF-8 内容。"""
    if args.content is not None:
        return args.content
    if args.content_file is not None:
        with open(args.content_file, "r", encoding="utf-8") as f:
            return f.read()
    # stdin
    if sys.stdin.isatty():
        print("请输入内容（Ctrl+D / Ctrl+Z+Enter 结束）：", file=sys.stderr)
    return sys.stdin.read()


def validate_line_range(start: int, end: int | None, total: int) -> tuple[int, int]:
    """校验并规范化行范围，返回 (start_idx, end_idx)，均为 0-indexed，左闭右闭。"""
    if start < 1:
        raise ValueError(f"--start 必须 ≥ 1，当前值：{start}")
    s = start - 1
    e = (end - 1) if end is not None else total - 1
    if e >= total:
        e = total - 1
    if s > e and total > 0:
        raise ValueError(f"--start ({start}) > --end ({end or total})，行范围无效。")
    return s, e


# ══════════════════════════════════════════════════════════════════════════════
# 各操作实现
# ══════════════════════════════════════════════════════════════════════════════

def op_append(lines: list[str], content: str) -> list[str]:
    """在文件末尾追加内容。"""
    new_lines = content.splitlines()
    return lines + new_lines


def op_insert(lines: list[str], content: str, start: int) -> list[str]:
    """
    在第 start 行之前插入内容（1-indexed）。
    start=1 → 插入到文件最前面；start > len(lines) → 等同追加。
    """
    new_lines = content.splitlines()
    idx = max(0, min(start - 1, len(lines)))
    return lines[:idx] + new_lines + lines[idx:]


def op_replace(lines: list[str], content: str, start: int, end: int | None) -> list[str]:
    """替换 [start, end] 行范围（1-indexed，双闭区间）。"""
    total = len(lines)
    if total == 0:
        return content.splitlines()
    s, e = validate_line_range(start, end, total)
    new_lines = content.splitlines()
    return lines[:s] + new_lines + lines[e + 1:]


def op_delete(lines: list[str], start: int, end: int | None) -> list[str]:
    """删除 [start, end] 行范围（1-indexed，双闭区间）。"""
    total = len(lines)
    if total == 0:
        return lines
    s, e = validate_line_range(start, end, total)
    return lines[:s] + lines[e + 1:]


def op_patch(
    lines: list[str],
    old: str,
    new: str,
    *,
    use_regex: bool = False,
    count: int = 0,
) -> tuple[list[str], int]:
    """
    全局文本替换，支持跨行匹配（先 join，再替换，再 split）。
    返回 (新行列表, 替换次数)。
    count=0 表示替换所有。
    """
    full_text = "\n".join(lines)
    if use_regex:
        result, n = re.subn(old, new, full_text, count=count)
    else:
        if count:
            result = full_text.replace(old, new, count)
            n = full_text.count(old) if count == 0 else min(full_text.count(old), count)
        else:
            n = full_text.count(old)
            result = full_text.replace(old, new)
    return result.splitlines(), n


def op_overwrite(content: str) -> list[str]:
    """完全覆盖文件。"""
    return content.splitlines()


# ══════════════════════════════════════════════════════════════════════════════
# 差异预览
# ══════════════════════════════════════════════════════════════════════════════

def show_diff(old_lines: list[str], new_lines: list[str], context: int = 3) -> str:
    """生成简洁的统一差异预览（不依赖 difflib 以外的库）。"""
    import difflib
    old_str = [l + "\n" for l in old_lines]
    new_str = [l + "\n" for l in new_lines]
    diff = difflib.unified_diff(
        old_str, new_str,
        fromfile="原始文件", tofile="修改后",
        n=context,
    )
    return "".join(diff) or "（无变化）"


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

MODES = ("append", "insert", "replace", "delete", "patch", "overwrite")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="对 GBK 编码文件进行安全写入（专为 AI 工具调用设计）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── 必填 ────────────────────────────────────────────────────────────────
    p.add_argument("filename", help="目标 GBK 文件路径")
    p.add_argument("--mode", choices=MODES, required=True,
                   help=f"操作模式：{' | '.join(MODES)}")

    # ── 内容来源（append / insert / replace / overwrite 用）────────────────
    content_group = p.add_mutually_exclusive_group()
    content_group.add_argument("--content", type=str, default=None,
                               metavar="TEXT",
                               help="直接传入 UTF-8 内容字符串")
    content_group.add_argument("--content-file", type=str, default=None,
                               metavar="FILE",
                               help="从 UTF-8 文件读取内容")

    # ── 行范围（insert / replace / delete 用）───────────────────────────────
    p.add_argument("--start", type=int, default=1, metavar="N",
                   help="起始行（1-indexed，默认 1）")
    p.add_argument("--end", type=int, default=None, metavar="N",
                   help="结束行（1-indexed，默认与 --start 相同或末尾）")

    # ── patch 专用 ───────────────────────────────────────────────────────────
    p.add_argument("--old", type=str, default=None, metavar="PATTERN",
                   help="[patch] 要被替换的旧文本或正则模式")
    p.add_argument("--new", type=str, default=None, metavar="TEXT",
                   help="[patch] 替换为的新文本（支持正则反向引用）")
    p.add_argument("--regex", action="store_true",
                   help="[patch] 将 --old 视为正则表达式")
    p.add_argument("--count", type=int, default=0, metavar="N",
                   help="[patch] 最多替换 N 次（0 = 全部，默认 0）")

    # ── 安全 / 预览 ─────────────────────────────────────────────────────────
    p.add_argument("--no-backup", action="store_true",
                   help="不生成 .bak 备份（谨慎使用）")
    p.add_argument("--allow-loss", action="store_true",
                   help="允许 GBK 不支持的字符被替换为 ?（默认拒绝）")
    p.add_argument("--dry-run", action="store_true",
                   help="预览变更，不实际写入文件")
    p.add_argument("--diff", action="store_true",
                   help="显示差异预览（自动启用 --dry-run 效果显示）")
    p.add_argument("--create", action="store_true",
                   help="文件不存在时自动创建")

    return p


def main() -> None:  # noqa: C901
    parser = build_parser()
    args = parser.parse_args()

    path = os.path.abspath(args.filename)
    mode = args.mode

    # ── 文件存在性检查 ───────────────────────────────────────────────────────
    if not os.path.exists(path):
        if args.create or mode in ("append", "overwrite"):
            # 自动创建空文件
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            open(path, "wb").close()
            print(f"[write_gbk] 已创建新文件：{path}", file=sys.stderr)
        else:
            _err(f"文件不存在：'{path}'\n提示：使用 --create 可自动创建。")

    if not os.path.isfile(path):
        _err(f"'{path}' 不是普通文件。")

    # ── 加载原文件 ───────────────────────────────────────────────────────────
    try:
        old_lines, _ = load_gbk(path)
    except Exception as e:
        _err(f"读取文件失败：{e}")

    # ── 执行操作 ─────────────────────────────────────────────────────────────
    new_lines: list[str]
    extra_info = ""

    try:
        if mode == "append":
            content = read_content_input(args)
            new_lines = op_append(old_lines, content)

        elif mode == "insert":
            content = read_content_input(args)
            new_lines = op_insert(old_lines, content, args.start)

        elif mode == "replace":
            content = read_content_input(args)
            end = args.end if args.end is not None else args.start
            new_lines = op_replace(old_lines, content, args.start, end)

        elif mode == "delete":
            end = args.end if args.end is not None else args.start
            new_lines = op_delete(old_lines, args.start, end)

        elif mode == "patch":
            if args.old is None:
                _err("--mode patch 需要 --old 参数。")
            new_text = args.new if args.new is not None else ""
            new_lines, n = op_patch(
                old_lines, args.old, new_text,
                use_regex=args.regex,
                count=args.count,
            )
            extra_info = f"共替换 {n} 处"

        elif mode == "overwrite":
            content = read_content_input(args)
            new_lines = op_overwrite(content)

        else:
            _err(f"未知模式：{mode}")

    except (ValueError, re.error) as e:
        _err(str(e))

    # ── 预检：GBK 可编码性 ───────────────────────────────────────────────────
    test_content = "\n".join(new_lines) + "\n"
    try:
        encode_to_gbk(test_content, allow_loss=False)
    except UnicodeEncodeError as e:
        if not args.allow_loss:
            # 找出具体的不可编码字符
            bad = sorted({c for c in test_content if _cannot_gbk(c)})
            sample = ", ".join(f"U+{ord(c):04X}({c})" for c in bad[:8])
            _err(
                f"内容含 GBK 不支持的字符，操作已中止。\n"
                f"不可编码字符（共 {len(bad)} 种）：{sample}\n"
                f"提示：使用 --allow-loss 可强制写入（不支持的字符将被替换为 ?）。"
            )

    # ── 差异预览 ─────────────────────────────────────────────────────────────
    if args.diff or args.dry_run:
        diff_text = show_diff(old_lines, new_lines)
        print("─── 差异预览 " + "─" * 48)
        print(diff_text)
        if extra_info:
            print(f"[{extra_info}]")
        if args.dry_run:
            print("─── DRY-RUN：未写入任何内容 " + "─" * 32)
            return

    # ── 备份 ────────────────────────────────────────────────────────────────
    if not args.no_backup and os.path.getsize(path) > 0:
        bak = backup(path)
        if bak:
            print(f"[write_gbk] 备份：{bak}", file=sys.stderr)

    # ── 原子写入 ─────────────────────────────────────────────────────────────
    try:
        save_gbk_atomic(path, new_lines, allow_loss=args.allow_loss)
    except Exception as e:
        _err(f"写入失败：{e}")

    # ── 写入后校验 ───────────────────────────────────────────────────────────
    with open(path, "rb") as f:
        verify_raw = f.read()
    if not is_gbk_strict(verify_raw):
        _err("⚠️  写入后校验失败：文件无法被 GBK 解码，请检查备份！")

    # ── 成功报告 ─────────────────────────────────────────────────────────────
    size = os.path.getsize(path)
    print(
        f"[write_gbk] ✅ {mode} 成功 → {path}\n"
        f"            行数：{len(old_lines)} → {len(new_lines)}，"
        f"大小：{size:,} 字节"
        + (f"，{extra_info}" if extra_info else ""),
        file=sys.stderr,
    )


def _err(msg: str) -> None:
    print(f"[write_gbk] 错误：{msg}", file=sys.stderr)
    sys.exit(1)


def _cannot_gbk(c: str) -> bool:
    try:
        c.encode("gbk")
        return False
    except (UnicodeEncodeError, ValueError):
        return True


if __name__ == "__main__":
    main()

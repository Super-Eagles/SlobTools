#!/usr/bin/env python3
r"""
write_file.py — 对文本文件进行安全写入，自动识别并保持原有编码（GBK / UTF-8）。

专为 AI 工具调用设计：所有内容以 UTF-8 字符串传入，脚本自动检测目标文件编码，
并以相同编码写回，绝不破坏原有编码。
操作前自动备份，写入后校验编码完整性。

━━━ 支持的操作模式（--mode）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  append    在文件末尾追加内容
  insert    在指定行之前插入内容
  replace   替换指定行范围（含 start，含 end）的内容
  delete    删除指定行范围
  patch     全局文本替换（--old 旧文本，--new 新文本，支持正则）
  overwrite 用新内容完全覆盖文件

━━━ 内容来源（三选一）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  --content "文本"        直接传入字符串
  --content-file path     从 UTF-8 文件读取内容
  （不传则从 stdin 读取）

━━━ 安全特性 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • 自动检测文件编码（GBK / UTF-8），写回时保持一致
  • 可用 --encoding gbk / utf-8 手动指定，跳过自动检测
  • GBK 文件写入前检查新内容是否包含 GBK 不支持的字符（默认拒绝，--allow-loss 可覆盖）
  • 写入前自动生成 .bak 备份（--no-backup 可关闭）
  • 原子写入：先写临时文件，再 rename，避免写到一半崩溃导致文件损坏
  • 写入后重新读取校验，确认文件编码完整

━━━ 典型用法 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # 追加一行（自动识别编码）
  python write_file.py file.txt --mode append --content "新的一行"

  # 在第 5 行前插入
  python write_file.py file.txt --mode insert --start 5 --content "插入内容"

  # 替换第 10~15 行
  python write_file.py file.txt --mode replace --start 10 --end 15 \
      --content-file new_block.txt

  # 删除第 3~7 行
  python write_file.py file.txt --mode delete --start 3 --end 7

  # 全局字符串替换
  python write_file.py file.txt --mode patch --old "旧字符串" --new "新字符串"

  # 正则替换
  python write_file.py file.txt --mode patch --old "\d+" --new "#\g<0>" --regex

  # 完全覆盖
  python write_file.py file.txt --mode overwrite --content-file new_content.txt

  # 手动指定编码（跳过自动检测）
  python write_file.py file.txt --mode append --content "内容" --encoding gbk
  python write_file.py file.txt --mode append --content "内容" --encoding utf-8

  # 预览（不写入）
  python write_file.py file.txt --mode replace --start 1 --end 3 \
      --content "preview" --dry-run --diff
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
    from encoding_utils import (
        UTF8_BOM, is_gbk_strict, is_utf8_strict,
        guess_encoding, strip_utf8_bom,
    )
except ImportError:
    UTF8_BOM = b"\xef\xbb\xbf"

    def strip_utf8_bom(raw: bytes) -> bytes:
        return raw[len(UTF8_BOM):] if raw.startswith(UTF8_BOM) else raw

    def is_gbk_strict(raw: bytes) -> bool:
        try:
            raw.decode("gbk", errors="strict")
            return True
        except (UnicodeDecodeError, ValueError):
            return False

    def is_utf8_strict(raw: bytes) -> bool:
        try:
            strip_utf8_bom(raw).decode("utf-8", errors="strict")
            return True
        except (UnicodeDecodeError, ValueError):
            return False

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


# ══════════════════════════════════════════════════════════════════════════════
# 编码检测与文件加载
# ══════════════════════════════════════════════════════════════════════════════

class FileEncoding:
    """描述文件的编码信息，驱动后续的读取和写回逻辑。"""
    def __init__(self, name: str, has_bom: bool = False, confidence: float = 1.0):
        self.name = name          # "gbk" 或 "utf-8"
        self.has_bom = has_bom    # 是否为 UTF-8 with BOM
        self.confidence = confidence

    def __str__(self) -> str:
        label = "utf-8 (BOM)" if self.name == "utf-8" and self.has_bom else self.name
        if self.confidence < 1.0:
            return f"{label} (置信度 {self.confidence:.0%})"
        return label


def detect_file_encoding(raw: bytes, override: str | None = None) -> FileEncoding:
    """检测原始字节的编码，override 可手动指定 'gbk' 或 'utf-8'。"""
    if override and override.lower() not in ("auto", ""):
        enc = override.lower().replace("-", "")
        if enc in ("utf8", "utf8sig"):
            return FileEncoding("utf-8", has_bom=raw.startswith(UTF8_BOM))
        return FileEncoding("gbk")

    if not raw:
        return FileEncoding("utf-8")
    if raw.startswith(UTF8_BOM):
        return FileEncoding("utf-8", has_bom=True, confidence=1.0)

    enc, conf, certain = guess_encoding(raw)

    if enc == "utf-8" and (certain or conf >= 0.80):
        return FileEncoding("utf-8", confidence=conf)
    if enc == "gbk":
        return FileEncoding("gbk", confidence=conf)
    if all(b < 0x80 for b in raw):
        return FileEncoding("utf-8", confidence=1.0)

    return FileEncoding("gbk", confidence=0.5)  # 兜底


def load_file(path: str, encoding_override: str | None = None) -> tuple[list[str], FileEncoding]:
    """加载文件，返回 (行列表, 编码信息)。文件不存在时返回空列表。"""
    if not os.path.exists(path):
        default = "utf-8" if (encoding_override or "").lower().replace("-","") in ("utf8","utf8sig") else "gbk"
        return [], FileEncoding(default)

    with open(path, "rb") as f:
        raw = f.read()

    file_enc = detect_file_encoding(raw, encoding_override)
    if file_enc.name == "utf-8":
        content = strip_utf8_bom(raw).decode("utf-8", errors="replace")
    else:
        content = raw.decode("gbk", errors="replace")

    return content.splitlines(), file_enc


# ══════════════════════════════════════════════════════════════════════════════
# 编码感知的保存与校验
# ══════════════════════════════════════════════════════════════════════════════

def encode_content(text: str, file_enc: FileEncoding, *, allow_loss: bool = False) -> bytes:
    if file_enc.name == "utf-8":
        data = text.encode("utf-8")
        return (UTF8_BOM + data) if file_enc.has_bom else data
    else:
        return text.encode("gbk", errors="replace" if allow_loss else "strict")


def verify_encoded(raw: bytes, file_enc: FileEncoding) -> bool:
    if file_enc.name == "utf-8":
        return is_utf8_strict(strip_utf8_bom(raw))
    return is_gbk_strict(raw)


def save_atomic(path: str, lines: list[str], file_enc: FileEncoding, *, allow_loss: bool = False) -> None:
    """原子写入：临时文件 + rename。"""
    content = ("\n".join(lines) + "\n") if lines else ""
    raw = encode_content(content, file_enc, allow_loss=allow_loss)

    if not verify_encoded(raw, file_enc):
        raise RuntimeError(f"编码后字节无法被 {file_enc.name} 解码，操作已中止。")

    dir_name = os.path.dirname(os.path.abspath(path)) or "."
    tmp_fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(raw)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ══════════════════════════════════════════════════════════════════════════════
# 通用辅助
# ══════════════════════════════════════════════════════════════════════════════

def backup(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{path}.{ts}.bak"
    shutil.copy2(path, bak)
    return bak


def read_content_input(args: argparse.Namespace) -> str:
    if args.content is not None:
        return args.content
    if args.content_file is not None:
        with open(args.content_file, "r", encoding="utf-8") as f:
            return f.read()
    if sys.stdin.isatty():
        print("请输入内容（Ctrl+D / Ctrl+Z+Enter 结束）：", file=sys.stderr)
    return sys.stdin.read()


def validate_line_range(start: int, end: int | None, total: int) -> tuple[int, int]:
    if start < 1:
        raise ValueError(f"--start 必须 ≥ 1，当前值：{start}")
    s = start - 1
    e = (end - 1) if end is not None else total - 1
    if e >= total:
        e = total - 1
    if s > e and total > 0:
        raise ValueError(f"--start ({start}) > --end ({end or total})，行范围无效。")
    return s, e


def _cannot_gbk(c: str) -> bool:
    try:
        c.encode("gbk")
        return False
    except (UnicodeEncodeError, ValueError):
        return True


# ══════════════════════════════════════════════════════════════════════════════
# 各操作实现（纯行列表操作，与编码无关）
# ══════════════════════════════════════════════════════════════════════════════

def op_append(lines: list[str], content: str) -> list[str]:
    return lines + content.splitlines()

def op_insert(lines: list[str], content: str, start: int) -> list[str]:
    idx = max(0, min(start - 1, len(lines)))
    return lines[:idx] + content.splitlines() + lines[idx:]

def op_replace(lines: list[str], content: str, start: int, end: int | None) -> list[str]:
    if not lines:
        return content.splitlines()
    s, e = validate_line_range(start, end, len(lines))
    return lines[:s] + content.splitlines() + lines[e + 1:]

def op_delete(lines: list[str], start: int, end: int | None) -> list[str]:
    if not lines:
        return lines
    s, e = validate_line_range(start, end, len(lines))
    return lines[:s] + lines[e + 1:]

def op_patch(lines: list[str], old: str, new: str, *, use_regex: bool = False, count: int = 0) -> tuple[list[str], int]:
    full = "\n".join(lines)
    if use_regex:
        result, n = re.subn(old, new, full, count=count)
    else:
        n = min(full.count(old), count) if count else full.count(old)
        result = full.replace(old, new, count or -1)
    return result.splitlines(), n

def op_overwrite(content: str) -> list[str]:
    return content.splitlines()


# ══════════════════════════════════════════════════════════════════════════════
# 差异预览
# ══════════════════════════════════════════════════════════════════════════════

def show_diff(old_lines: list[str], new_lines: list[str], context: int = 3) -> str:
    import difflib
    diff = difflib.unified_diff(
        [l + "\n" for l in old_lines],
        [l + "\n" for l in new_lines],
        fromfile="原始文件", tofile="修改后", n=context,
    )
    return "".join(diff) or "（无变化）"


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

MODES = ("append", "insert", "replace", "delete", "patch", "overwrite")

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="对文本文件进行安全写入，自动识别并保持原有编码（GBK / UTF-8）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("filename", help="目标文件路径（GBK 或 UTF-8）")
    p.add_argument("--mode", choices=MODES, required=True,
                   help=f"操作模式：{' | '.join(MODES)}")
    p.add_argument("--encoding", default="auto", metavar="ENC",
                   help="手动指定编码：gbk / utf-8 / auto（默认 auto）")

    cg = p.add_mutually_exclusive_group()
    cg.add_argument("--content", type=str, default=None, metavar="TEXT",
                    help="直接传入内容字符串")
    cg.add_argument("--content-file", type=str, default=None, metavar="FILE",
                    help="从 UTF-8 文件读取内容")

    p.add_argument("--start", type=int, default=1, metavar="N",
                   help="起始行（1-indexed，默认 1）")
    p.add_argument("--end", type=int, default=None, metavar="N",
                   help="结束行（1-indexed，默认与 --start 相同或末尾）")

    p.add_argument("--old", type=str, default=None, metavar="PATTERN",
                   help="[patch] 要被替换的旧文本或正则模式")
    p.add_argument("--new", type=str, default=None, metavar="TEXT",
                   help="[patch] 替换为的新文本（支持正则反向引用）")
    p.add_argument("--regex", action="store_true",
                   help="[patch] 将 --old 视为正则表达式")
    p.add_argument("--count", type=int, default=0, metavar="N",
                   help="[patch] 最多替换 N 次（0 = 全部，默认 0）")

    p.add_argument("--no-backup", action="store_true", help="不生成 .bak 备份")
    p.add_argument("--allow-loss", action="store_true",
                   help="GBK 文件：允许不支持的字符替换为 ?（默认拒绝）")
    p.add_argument("--dry-run", action="store_true", help="预览变更，不实际写入文件")
    p.add_argument("--diff", action="store_true", help="显示差异预览")
    p.add_argument("--create", action="store_true", help="文件不存在时自动创建")
    return p


def main() -> None:  # noqa: C901
    args = build_parser().parse_args()
    path = os.path.abspath(args.filename)
    mode = args.mode

    # ── 文件存在性检查 ────────────────────────────────────────────────────────
    if not os.path.exists(path):
        if args.create or mode in ("append", "overwrite"):
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            open(path, "wb").close()
            print(f"[write_file] 已创建新文件：{path}", file=sys.stderr)
        else:
            _err(f"文件不存在：'{path}'\n提示：使用 --create 可自动创建。")
    if not os.path.isfile(path):
        _err(f"'{path}' 不是普通文件。")

    # ── 加载文件（同时检测编码）──────────────────────────────────────────────
    try:
        old_lines, file_enc = load_file(path, args.encoding)
    except Exception as e:
        _err(f"读取文件失败：{e}")

    print(f"[write_file] 检测编码：{file_enc}", file=sys.stderr)

    # ── 执行操作 ──────────────────────────────────────────────────────────────
    extra_info = ""
    try:
        if mode == "append":
            new_lines = op_append(old_lines, read_content_input(args))
        elif mode == "insert":
            new_lines = op_insert(old_lines, read_content_input(args), args.start)
        elif mode == "replace":
            end = args.end if args.end is not None else args.start
            new_lines = op_replace(old_lines, read_content_input(args), args.start, end)
        elif mode == "delete":
            end = args.end if args.end is not None else args.start
            new_lines = op_delete(old_lines, args.start, end)
        elif mode == "patch":
            if args.old is None:
                _err("--mode patch 需要 --old 参数。")
            new_lines, n = op_patch(
                old_lines, args.old, args.new or "",
                use_regex=args.regex, count=args.count,
            )
            extra_info = f"共替换 {n} 处"
        elif mode == "overwrite":
            new_lines = op_overwrite(read_content_input(args))
        else:
            _err(f"未知模式：{mode}")
    except (ValueError, re.error) as e:
        _err(str(e))

    # ── GBK 文件：预检新内容可编码性 ─────────────────────────────────────────
    if file_enc.name == "gbk":
        test = "\n".join(new_lines) + "\n"
        try:
            test.encode("gbk", errors="strict")
        except UnicodeEncodeError:
            if not args.allow_loss:
                bad = sorted({c for c in test if _cannot_gbk(c)})
                sample = ", ".join(f"U+{ord(c):04X}({c})" for c in bad[:8])
                _err(
                    f"新内容含 GBK 不支持的字符，操作已中止。\n"
                    f"不可编码字符（共 {len(bad)} 种）：{sample}\n"
                    f"提示：使用 --allow-loss 可强制写入（字符将被替换为 ?）。"
                )

    # ── 差异预览 ──────────────────────────────────────────────────────────────
    if args.diff or args.dry_run:
        print("─── 差异预览 " + "─" * 48)
        print(show_diff(old_lines, new_lines))
        if extra_info:
            print(f"[{extra_info}]")
        if args.dry_run:
            print("─── DRY-RUN：未写入任何内容 " + "─" * 32)
            return

    # ── 备份 ──────────────────────────────────────────────────────────────────
    if not args.no_backup and os.path.getsize(path) > 0:
        bak = backup(path)
        if bak:
            print(f"[write_file] 备份：{bak}", file=sys.stderr)

    # ── 原子写入 ──────────────────────────────────────────────────────────────
    try:
        save_atomic(path, new_lines, file_enc, allow_loss=args.allow_loss)
    except Exception as e:
        _err(f"写入失败：{e}")

    # ── 写入后校验 ────────────────────────────────────────────────────────────
    with open(path, "rb") as f:
        verify_raw = f.read()
    if not verify_encoded(verify_raw, file_enc):
        _err(f"⚠️  写入后校验失败：文件无法被 {file_enc.name} 解码，请检查备份！")

    size = os.path.getsize(path)
    print(
        f"[write_file] ✅ {mode} 成功 → {path}\n"
        f"            编码：{file_enc}，行数：{len(old_lines)} → {len(new_lines)}，"
        f"大小：{size:,} 字节"
        + (f"，{extra_info}" if extra_info else ""),
        file=sys.stderr,
    )


def _err(msg: str) -> None:
    print(f"[write_file] 错误：{msg}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()

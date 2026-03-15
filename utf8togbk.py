#!/usr/bin/env python3
"""
utf8togbk.py — 批量将目录下文本文件从 UTF-8 转换为 GBK。

用法：
  python utf8togbk.py <源目录> <目标目录> [选项]

选项：
  --dry-run        预览操作，不实际写入任何文件
  --strict         遇到不可编码字符时报错（默认：用 ? 替换并警告）
  --confidence N   编码置信度阈值（默认 0.80）
  --log FILE       将日志同时写入指定文件
  --follow-links   跟随符号链接（默认不跟随）
"""

from __future__ import annotations
import os
import sys
import shutil
import argparse
from typing import IO

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
from encoding_utils import (
    TEXT_EXTENSIONS, is_text_file, is_pure_ascii,
    is_utf8_strict, is_gbk_strict, guess_encoding, UTF8_BOM, strip_utf8_bom,
)

# ── 状态码 ───────────────────────────────────────────────────────────────────
STATUS_CONVERTED    = "converted"      # UTF-8 → GBK 成功
STATUS_ALREADY_GBK  = "already_gbk"   # 已是 GBK，直接复制
STATUS_ASCII        = "ascii"          # 纯 ASCII，直接复制
STATUS_SKIPPED      = "skipped"        # 非文本文件
STATUS_EMPTY        = "empty"          # 空文件
STATUS_LOSSY        = "lossy"          # 含不可编码字符，已替换
STATUS_UNCERTAIN    = "uncertain"      # 编码不确定
STATUS_UNKNOWN      = "unknown"        # 编码无法识别
STATUS_ERROR        = "error"          # 异常


def convert_file(
    src_path: str,
    dst_path: str,
    *,
    dry_run: bool = False,
    strict: bool = False,
    confidence_threshold: float = 0.80,
) -> tuple[str, str]:
    if not is_text_file(src_path):
        return STATUS_SKIPPED, ""

    try:
        with open(src_path, "rb") as f:
            raw = f.read()
    except OSError as e:
        return STATUS_ERROR, str(e)

    if not dry_run:
        os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)

    # 空文件
    if not raw:
        if not dry_run:
            shutil.copy2(src_path, dst_path)
        return STATUS_EMPTY, ""

    # 纯 ASCII（GBK 兼容，直接复制）
    if is_pure_ascii(raw):
        if not dry_run:
            shutil.copy2(src_path, dst_path)
        return STATUS_ASCII, ""

    # 判断当前编码
    enc, conf, certain = guess_encoding(raw)

    # ── 已是 GBK ──────────────────────────────────────────────────────────
    if enc == "gbk" and (certain or conf >= confidence_threshold):
        if not dry_run:
            shutil.copy2(src_path, dst_path)
        return STATUS_ALREADY_GBK, ""

    # ── UTF-8（含或不含 BOM）→ GBK ────────────────────────────────────────
    if enc in ("utf-8", "ascii") or is_utf8_strict(raw):
        text_bytes = strip_utf8_bom(raw)
        try:
            text = text_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as e:
            return STATUS_ERROR, f"UTF-8 解码失败：{e}"

        # 检测是否有无法编码的字符
        try:
            gbk_data = text.encode("gbk", errors="strict")
            if not dry_run:
                with open(dst_path, "wb") as f:
                    f.write(gbk_data)
            return STATUS_CONVERTED, ""
        except UnicodeEncodeError as e:
            if strict:
                return STATUS_ERROR, f"含不可编码字符（GBK 不支持）：{e}"

            # 非严格模式：统计不可编码字符，用 ? 替换
            bad_chars = {c for c in text if _cannot_gbk(c)}
            gbk_data = text.encode("gbk", errors="replace")
            if not dry_run:
                with open(dst_path, "wb") as f:
                    f.write(gbk_data)
            sample = ", ".join(
                f"U+{ord(c):04X}({c})" for c in sorted(bad_chars)[:5]
            )
            note = f"{len(bad_chars)} 个字符无法编码，已替换为 ?：{sample}"
            if len(bad_chars) > 5:
                note += f"……（共 {len(bad_chars)} 个）"
            return STATUS_LOSSY, note

    # ── 编码不确定 ────────────────────────────────────────────────────────
    if enc == "unknown" or conf < confidence_threshold:
        if not dry_run:
            shutil.copy2(src_path, dst_path)
        return STATUS_UNCERTAIN, f"编码={enc}，置信度={conf:.0%}，原样复制"

    # ── 其他已知编码（非 UTF-8/GBK）─────────────────────────────────────
    if not dry_run:
        shutil.copy2(src_path, dst_path)
    return STATUS_UNKNOWN, f"编码为 {enc}（非 UTF-8），原样复制"


def _cannot_gbk(c: str) -> bool:
    try:
        c.encode("gbk")
        return False
    except (UnicodeEncodeError, ValueError):
        return True


# ── 目录遍历 ─────────────────────────────────────────────────────────────────

def convert_directory(
    src_dir: str,
    dst_dir: str,
    *,
    dry_run: bool = False,
    strict: bool = False,
    confidence_threshold: float = 0.80,
    log_file: IO | None = None,
    follow_links: bool = False,
) -> None:
    src_dir = os.path.abspath(src_dir)
    dst_dir = os.path.abspath(dst_dir)

    if not os.path.isdir(src_dir):
        _err(f"源目录 '{src_dir}' 不存在或不是有效目录。")
    if src_dir == dst_dir:
        _err("源目录与目标目录不能相同。")
    if dst_dir.startswith(src_dir + os.sep):
        _err("目标目录不能是源目录的子目录。")

    if not dry_run:
        os.makedirs(dst_dir, exist_ok=True)

    stats: dict[str, int] = {}

    def _log(msg: str) -> None:
        print(msg)
        if log_file:
            log_file.write(msg + "\n")

    _log(f"源目录  ：{src_dir}")
    _log(f"目标目录：{dst_dir}")
    if dry_run:
        _log("⚠️  DRY-RUN 模式：不写入任何文件")
    _log("─" * 60)

    LABELS = {
        STATUS_CONVERTED:   "UTF8→GBK",
        STATUS_ALREADY_GBK: "已是GBK ",
        STATUS_ASCII:       "ASCII   ",
        STATUS_SKIPPED:     "跳  过  ",
        STATUS_EMPTY:       "空文件  ",
        STATUS_LOSSY:       "⚠ 有损转",
        STATUS_UNCERTAIN:   "⚠ 不确定",
        STATUS_UNKNOWN:     "⚠ 未知码",
        STATUS_ERROR:       "✖ 失  败",
    }

    for dirpath, dirnames, filenames in os.walk(src_dir, followlinks=follow_links):
        dirnames.sort()
        for filename in sorted(filenames):
            src_path = os.path.join(dirpath, filename)
            if not follow_links and os.path.islink(src_path):
                _log(f"  [符号链接] {os.path.relpath(src_path, src_dir)}")
                continue
            rel_path = os.path.relpath(src_path, src_dir)
            dst_path = os.path.join(dst_dir, rel_path)
            status, note = convert_file(
                src_path, dst_path,
                dry_run=dry_run,
                strict=strict,
                confidence_threshold=confidence_threshold,
            )
            stats[status] = stats.get(status, 0) + 1
            label = LABELS.get(status, status)
            suffix = f"  ← {note}" if note else ""
            _log(f"  [{label}] {rel_path}{suffix}")

    total = sum(stats.values())
    warn = sum(stats.get(s, 0) for s in (STATUS_LOSSY, STATUS_UNCERTAIN, STATUS_UNKNOWN, STATUS_ERROR))

    _log("\n" + "=" * 60)
    _log("完成，统计结果：")
    _log(f"  ✅ UTF-8→GBK 转换  ：{stats.get(STATUS_CONVERTED, 0):4} 个文件")
    _log(f"  ℹ️  已是 GBK        ：{stats.get(STATUS_ALREADY_GBK, 0):4} 个文件")
    _log(f"  ℹ️  纯 ASCII        ：{stats.get(STATUS_ASCII, 0):4} 个文件")
    _log(f"  ⏭️  非文本跳过      ：{stats.get(STATUS_SKIPPED, 0):4} 个文件")
    _log(f"  📄 空文件          ：{stats.get(STATUS_EMPTY, 0):4} 个文件")
    _log(f"  ⚠️  有损/不确定/其他：{stats.get(STATUS_LOSSY, 0) + stats.get(STATUS_UNCERTAIN, 0) + stats.get(STATUS_UNKNOWN, 0):4} 个文件")
    _log(f"  ✖  失败            ：{stats.get(STATUS_ERROR, 0):4} 个文件")
    _log(f"  📁 合计扫描        ：{total:4} 个文件")
    _log(f"\n输出目录：{dst_dir}")
    _log("=" * 60)

    if warn > 0:
        _log("\n⚠️  有文件需要人工核查，请查看上方带 ⚠ / ✖ 的条目。")


def _err(msg: str) -> None:
    print(f"错误：{msg}", file=sys.stderr)
    sys.exit(1)


# ── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="批量将目录下文本文件从 UTF-8 转换为 GBK。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("src_dir", help="源目录")
    p.add_argument("dst_dir", help="目标目录")
    p.add_argument("--dry-run", action="store_true", help="预览，不写入文件")
    p.add_argument("--strict", action="store_true",
                   help="遇到不可编码字符时报错（默认：替换为 ?）")
    p.add_argument("--confidence", type=float, default=0.80, metavar="N",
                   help="编码置信度阈值（0~1，默认 0.80）")
    p.add_argument("--log", type=str, default=None, metavar="FILE",
                   help="日志同时写入文件")
    p.add_argument("--follow-links", action="store_true", help="跟随符号链接")
    return p


def main() -> None:
    args = build_parser().parse_args()
    log_file = None
    if args.log:
        log_file = open(args.log, "w", encoding="utf-8")
    try:
        convert_directory(
            args.src_dir, args.dst_dir,
            dry_run=args.dry_run,
            strict=args.strict,
            confidence_threshold=args.confidence,
            log_file=log_file,
            follow_links=args.follow_links,
        )
    finally:
        if log_file:
            log_file.close()


if __name__ == "__main__":
    main()

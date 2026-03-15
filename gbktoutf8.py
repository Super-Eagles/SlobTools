#!/usr/bin/env python3
"""
gbktoutf8.py — 批量将目录下文本文件从 GBK 转换为 UTF-8。

用法：
  python gbktoutf8.py <源目录> <目标目录> [选项]

选项：
  --dry-run        预览操作，不实际写入任何文件
  --with-bom       输出 UTF-8 文件时加入 BOM（适配旧版 Windows 工具链）
  --confidence N   编码置信度阈值，低于此值视为不确定（默认 0.80）
  --log FILE       将日志同时写入指定文件
  --follow-links   跟随符号链接（默认不跟随）
"""

from __future__ import annotations
import os
import sys
import shutil
import argparse
import logging
from typing import IO

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
from encoding_utils import (
    TEXT_EXTENSIONS, is_text_file, is_pure_ascii,
    is_utf8_strict, is_gbk_strict, guess_encoding, UTF8_BOM,
)

# ── 转换单个文件 ──────────────────────────────────────────────────────────────

Result = tuple[str, str]   # (状态码, 附加消息)

STATUS_CONVERTED      = "converted"       # GBK → UTF-8 成功
STATUS_ALREADY_UTF8   = "already_utf8"    # 已是 UTF-8，直接复制
STATUS_ASCII          = "ascii"           # 纯 ASCII（UTF-8 子集），直接复制
STATUS_SKIPPED        = "skipped"         # 非文本文件，跳过
STATUS_EMPTY          = "empty"           # 空文件，直接复制
STATUS_UNCERTAIN      = "uncertain"       # 编码不确定，直接复制并警告
STATUS_UNKNOWN        = "unknown"         # 无法识别编码，直接复制并警告
STATUS_ERROR          = "error"           # 异常


def convert_file(
    src_path: str,
    dst_path: str,
    *,
    dry_run: bool = False,
    with_bom: bool = False,
    confidence_threshold: float = 0.80,
) -> Result:
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

    # 纯 ASCII：UTF-8 / GBK 均能解，直接复制即可
    if is_pure_ascii(raw):
        if not dry_run:
            shutil.copy2(src_path, dst_path)
        return STATUS_ASCII, ""

    # UTF-8 with BOM：剥离 BOM 后按需重写
    if raw.startswith(UTF8_BOM):
        data = raw[len(UTF8_BOM):]
        if not dry_run:
            out = (UTF8_BOM + data) if with_bom else data
            with open(dst_path, "wb") as f:
                f.write(out)
        return STATUS_ALREADY_UTF8, "（含 BOM，已处理）"

    # 严格 UTF-8（无 BOM）
    if is_utf8_strict(raw):
        if not dry_run:
            out = UTF8_BOM + raw if with_bom else raw
            with open(dst_path, "wb") as f:
                f.write(out)
        return STATUS_ALREADY_UTF8, ""

    # 使用智能编码检测
    enc, conf, certain = guess_encoding(raw)

    if enc == "gbk":
        if conf < confidence_threshold and not certain:
            msg = f"置信度 {conf:.0%}，低于阈值，仍尝试转换（建议人工核查）"
        else:
            msg = ""
        try:
            text = raw.decode("gbk", errors="strict")
            utf8_data = text.encode("utf-8")
            if with_bom:
                utf8_data = UTF8_BOM + utf8_data
            if not dry_run:
                with open(dst_path, "wb") as f:
                    f.write(utf8_data)
            return STATUS_CONVERTED, msg
        except (UnicodeDecodeError, UnicodeEncodeError) as e:
            # 降级：允许替换字符后转换
            text = raw.decode("gbk", errors="replace")
            utf8_data = text.encode("utf-8")
            if with_bom:
                utf8_data = UTF8_BOM + utf8_data
            if not dry_run:
                with open(dst_path, "wb") as f:
                    f.write(utf8_data)
            return STATUS_CONVERTED, f"（含替换字符，原因：{e}）"

    if enc == "unknown":
        if not dry_run:
            shutil.copy2(src_path, dst_path)
        return STATUS_UNKNOWN, "无法识别编码，原样复制"

    # 编码是其他（非 GBK/UTF-8），且置信度不足
    if conf < confidence_threshold:
        if not dry_run:
            shutil.copy2(src_path, dst_path)
        return STATUS_UNCERTAIN, f"检测结果={enc}，置信度={conf:.0%}，原样复制"

    # 其他已知编码（如 latin-1 等）：原样复制并提示
    if not dry_run:
        shutil.copy2(src_path, dst_path)
    return STATUS_UNCERTAIN, f"编码为 {enc}（非 GBK），原样复制"


# ── 目录遍历 ─────────────────────────────────────────────────────────────────

def convert_directory(
    src_dir: str,
    dst_dir: str,
    *,
    dry_run: bool = False,
    with_bom: bool = False,
    confidence_threshold: float = 0.80,
    log_file: IO | None = None,
    follow_links: bool = False,
) -> None:
    src_dir = os.path.abspath(src_dir)
    dst_dir = os.path.abspath(dst_dir)

    # 安全检查
    if not os.path.isdir(src_dir):
        _err(f"源目录 '{src_dir}' 不存在或不是有效目录。")
    if src_dir == dst_dir:
        _err("源目录与目标目录不能相同。")
    if dst_dir.startswith(src_dir + os.sep):
        _err("目标目录不能是源目录的子目录。")

    if not dry_run:
        os.makedirs(dst_dir, exist_ok=True)

    stats: dict[str, int] = {
        STATUS_CONVERTED: 0, STATUS_ALREADY_UTF8: 0, STATUS_ASCII: 0,
        STATUS_SKIPPED: 0, STATUS_EMPTY: 0,
        STATUS_UNCERTAIN: 0, STATUS_UNKNOWN: 0, STATUS_ERROR: 0,
    }

    def _log(msg: str) -> None:
        print(msg)
        if log_file:
            log_file.write(msg + "\n")

    _log(f"源目录  ：{src_dir}")
    _log(f"目标目录：{dst_dir}")
    if dry_run:
        _log("⚠️  DRY-RUN 模式：不写入任何文件")
    _log("─" * 60)

    for dirpath, dirnames, filenames in os.walk(src_dir, followlinks=follow_links):
        # 排序保证输出顺序稳定
        dirnames.sort()
        for filename in sorted(filenames):
            src_path = os.path.join(dirpath, filename)

            # 跳过符号链接（除非 --follow-links）
            if not follow_links and os.path.islink(src_path):
                _log(f"  [符号链接] {os.path.relpath(src_path, src_dir)}")
                continue

            rel_path = os.path.relpath(src_path, src_dir)
            dst_path = os.path.join(dst_dir, rel_path)
            status, note = convert_file(
                src_path, dst_path,
                dry_run=dry_run,
                with_bom=with_bom,
                confidence_threshold=confidence_threshold,
            )
            stats[status] = stats.get(status, 0) + 1

            LABELS = {
                STATUS_CONVERTED:    "GBK→UTF8",
                STATUS_ALREADY_UTF8: "已UTF-8 ",
                STATUS_ASCII:        "ASCII   ",
                STATUS_SKIPPED:      "跳  过  ",
                STATUS_EMPTY:        "空文件  ",
                STATUS_UNCERTAIN:    "⚠ 不确定",
                STATUS_UNKNOWN:      "⚠ 未知码",
                STATUS_ERROR:        "✖ 失  败",
            }
            label = LABELS.get(status, status)
            suffix = f"  ← {note}" if note else ""
            _log(f"  [{label}] {rel_path}{suffix}")

    total = sum(stats.values())
    _log("\n" + "=" * 60)
    _log("完成，统计结果：")
    _log(f"  ✅ GBK→UTF-8 转换  ：{stats[STATUS_CONVERTED]:4} 个文件")
    _log(f"  ℹ️  已是 UTF-8      ：{stats[STATUS_ALREADY_UTF8]:4} 个文件")
    _log(f"  ℹ️  纯 ASCII        ：{stats[STATUS_ASCII]:4} 个文件")
    _log(f"  ⏭️  非文本跳过      ：{stats[STATUS_SKIPPED]:4} 个文件")
    _log(f"  📄 空文件          ：{stats[STATUS_EMPTY]:4} 个文件")
    _log(f"  ⚠️  编码不确定/其他 ：{stats[STATUS_UNCERTAIN] + stats[STATUS_UNKNOWN]:4} 个文件")
    _log(f"  ✖  失败            ：{stats[STATUS_ERROR]:4} 个文件")
    _log(f"  📁 合计扫描        ：{total:4} 个文件")
    _log(f"\n输出目录：{dst_dir}")
    _log("=" * 60)

    if stats[STATUS_UNCERTAIN] + stats[STATUS_UNKNOWN] + stats[STATUS_ERROR] > 0:
        _log("\n⚠️  有文件需要人工核查，请查看上方带 ⚠ / ✖ 的条目。")


def _err(msg: str) -> None:
    print(f"错误：{msg}", file=sys.stderr)
    sys.exit(1)


# ── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="批量将目录下文本文件从 GBK 转换为 UTF-8。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("src_dir", help="源目录")
    p.add_argument("dst_dir", help="目标目录")
    p.add_argument("--dry-run", action="store_true", help="预览，不写入文件")
    p.add_argument("--with-bom", action="store_true", help="输出 UTF-8 文件加入 BOM")
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
            with_bom=args.with_bom,
            confidence_threshold=args.confidence,
            log_file=log_file,
            follow_links=args.follow_links,
        )
    finally:
        if log_file:
            log_file.close()


if __name__ == "__main__":
    main()

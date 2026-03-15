#!/usr/bin/env python3
"""
read_excel.py — Excel 内容对比工具（忽略格式，只比较单元格值）
安装依赖: pip install openpyxl
用法:     python read_excel.py 表1.xlsx 表2.xlsx
"""

import sys
from collections import defaultdict
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


def get_value(ws, row, col):
    v = ws.cell(row=row, column=col).value
    return "" if v is None else str(v)


def compare_sheets(ws1, ws2):
    """返回按行分组的差异: {row: [(col_ref, v1, v2), ...]}"""
    max_rows = max(ws1.max_row or 0, ws2.max_row or 0)
    max_cols = max(ws1.max_column or 0, ws2.max_column or 0)

    row_diffs = defaultdict(list)
    for r in range(1, max_rows + 1):
        for c in range(1, max_cols + 1):
            v1 = get_value(ws1, r, c)
            v2 = get_value(ws2, r, c)
            if v1 != v2:
                ref = f"{get_column_letter(c)}{r}"
                row_diffs[r].append((ref, v1, v2))

    return row_diffs


def main():
    if len(sys.argv) != 3:
        print("用法: python cmp.py 表1.xlsx 表2.xlsx")
        sys.exit(1)

    file1, file2 = sys.argv[1], sys.argv[2]

    try:
        wb1 = load_workbook(file1, data_only=True)
    except FileNotFoundError:
        print(f"❌ 找不到文件: {file1}"); sys.exit(1)

    try:
        wb2 = load_workbook(file2, data_only=True)
    except FileNotFoundError:
        print(f"❌ 找不到文件: {file2}"); sys.exit(1)

    sheets1, sheets2 = wb1.sheetnames, wb2.sheetnames

    print(f"\n{'='*60}")
    print(f"  表1: {file1}")
    print(f"  表2: {file2}")
    print(f"{'='*60}")

    only_s1 = [s for s in sheets1 if s not in sheets2]
    only_s2 = [s for s in sheets2 if s not in sheets1]
    if only_s1:
        print(f"  ⚠️  仅表1有的 Sheet: {only_s1}")
    if only_s2:
        print(f"  ⚠️  仅表2有的 Sheet: {only_s2}")

    total_diff_sheets = 0

    for s1, s2 in zip(sheets1, sheets2):
        label = s1 if s1 == s2 else f"{s1} vs {s2}"
        row_diffs = compare_sheets(wb1[s1], wb2[s2])

        print(f"\n{'─'*60}")
        print(f"  📄 Sheet: {label}")
        print(f"{'─'*60}")

        if not row_diffs:
            print("  ✅ 内容完全一致")
        else:
            total_diff_sheets += 1
            diff_cells = sum(len(v) for v in row_diffs.values())
            print(f"  共 {len(row_diffs)} 行、{diff_cells} 处差异:\n")

            for row in sorted(row_diffs.keys()):
                cells = row_diffs[row]
                print(f"  差异 第{row}行")
                print(f"  表1 Sheet: {label}")
                refs1 = "  ".join(f"{ref}['{v1}']" for ref, v1, _ in cells)
                print(f"  第{row}行  {refs1}")
                print(f"  表2 Sheet: {label}")
                refs2 = "  ".join(f"{ref}['{v2}']" for ref, _, v2 in cells)
                print(f"  第{row}行  {refs2}")
                print()

    print(f"{'='*60}")
    print(f"  {'🎉 所有 Sheet 内容一致！' if total_diff_sheets == 0 else f'共 {total_diff_sheets} 个 Sheet 有差异'}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

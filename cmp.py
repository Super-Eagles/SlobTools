#!/usr/bin/env python3
"""
Excel 表格对比工具
用法: python cmp.py 表1.xlsx 表2.xlsx
"""

import sys
import pandas as pd
from openpyxl.utils import get_column_letter


def compare_sheets(df1, df2, sheet_name):
    """对比两个 DataFrame，返回差异信息"""
    diffs = []

    # 对齐列和行（以较大者为准）
    all_cols = sorted(set(df1.columns) | set(df2.columns), key=lambda x: (str(type(x)), x))

    only_in_1 = [c for c in df1.columns if c not in df2.columns]
    only_in_2 = [c for c in df2.columns if c not in df1.columns]

    if only_in_1:
        diffs.append(f"  ⚠️  仅在表1中存在的列: {only_in_1}")
    if only_in_2:
        diffs.append(f"  ⚠️  仅在表2中存在的列: {only_in_2}")

    if len(df1) != len(df2):
        diffs.append(f"  ⚠️  行数不同: 表1={len(df1)} 行，表2={len(df2)} 行")

    # 逐单元格对比（公共列）
    common_cols = [c for c in df1.columns if c in df2.columns]
    # 预先计算每列在 df1 中的真实位置（用于生成正确的 Excel 列字母）
    df1_col_positions = {col: i for i, col in enumerate(df1.columns)}
    cell_diffs = []

    for col in common_cols:
        for row_idx in range(max(len(df1), len(df2))):
            val1 = df1[col].iloc[row_idx] if row_idx < len(df1) else "<缺失>"
            val2 = df2[col].iloc[row_idx] if row_idx < len(df2) else "<缺失>"

            # 统一 NaN 比较
            v1_nan = pd.isna(val1) if not isinstance(val1, str) else False
            v2_nan = pd.isna(val2) if not isinstance(val2, str) else False

            if v1_nan and v2_nan:
                continue
            if v1_nan:
                val1 = "<空>"
            if v2_nan:
                val2 = "<空>"

            if str(val1) != str(val2):
                # Excel 坐标：使用该列在 df1 中的真实列位置（+1 转为 1-indexed）
                actual_col_idx = df1_col_positions.get(col, 0)
                col_letter = get_column_letter(actual_col_idx + 1)
                excel_row = row_idx + 2
                cell_ref = f"{col_letter}{excel_row}"
                cell_diffs.append(
                    f"    [{cell_ref}] 列「{col}」行{row_idx + 1}: "
                    f"表1={repr(val1)}  →  表2={repr(val2)}"
                )

    if cell_diffs:
        diffs.append(f"  📋 单元格差异（共 {len(cell_diffs)} 处）:")
        diffs.extend(cell_diffs)

    return diffs


def main():
    if len(sys.argv) != 3:
        print("用法: python cmp.py 表1.xlsx 表2.xlsx")
        sys.exit(1)

    file1, file2 = sys.argv[1], sys.argv[2]

    try:
        wb1 = pd.read_excel(file1, sheet_name=None, header=0)
    except FileNotFoundError:
        print(f"❌ 找不到文件: {file1}")
        sys.exit(1)

    try:
        wb2 = pd.read_excel(file2, sheet_name=None, header=0)
    except FileNotFoundError:
        print(f"❌ 找不到文件: {file2}")
        sys.exit(1)

    sheets1 = list(wb1.keys())
    sheets2 = list(wb2.keys())

    print(f"\n{'='*60}")
    print(f"  对比文件: {file1}  vs  {file2}")
    print(f"{'='*60}")
    print(f"  表1 Sheet 列表: {sheets1}")
    print(f"  表2 Sheet 列表: {sheets2}")

    only_s1 = [s for s in sheets1 if s not in sheets2]
    only_s2 = [s for s in sheets2 if s not in sheets1]
    if only_s1:
        print(f"  ⚠️  仅在表1中存在的 Sheet: {only_s1}")
    if only_s2:
        print(f"  ⚠️  仅在表2中存在的 Sheet: {only_s2}")

    # 按顺序对比同名 sheet（以位置对齐）
    common_sheets = []
    for i, (s1, s2) in enumerate(zip(sheets1, sheets2)):
        common_sheets.append((s1, s2))

    total_diff_sheets = 0

    for s1, s2 in common_sheets:
        label = f"Sheet: {s1}" if s1 == s2 else f"Sheet: {s1}（表1） vs {s2}（表2）"
        df1 = wb1[s1]
        df2 = wb2[s2]

        diffs = compare_sheets(df1, df2, s1)

        print(f"\n{'─'*60}")
        print(f"  📄 {label}")
        print(f"{'─'*60}")

        if not diffs:
            print("  ✅ 无差异")
        else:
            total_diff_sheets += 1
            for line in diffs:
                print(line)

    print(f"\n{'='*60}")
    if total_diff_sheets == 0:
        print("  🎉 两个文件完全一致！")
    else:
        print(f"  📊 对比完成，共 {total_diff_sheets} 个 Sheet 存在差异")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

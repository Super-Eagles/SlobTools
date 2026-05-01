#!/usr/bin/env python3
# 用法:
#   python replace.py <查找> <替换>        # 直接替换
#   python replace.py <查找> <替换> dry    # 只预览，不修改
print("vvv")
import os, sys

if len(sys.argv) < 3:
    print("用法:")
    print("  replace_source <查找> <替换>        # 直接替换")
    print("  replace_source <查找> <替换> dry    # 只预览，不修改")
    print("错误: 参数不足，请提供查找词和替换词。")
    sys.exit(1)

OLD = sys.argv[1]
NEW = sys.argv[2]
DRY = len(sys.argv) > 3

EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h",
    ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".sh",
    ".html", ".css", ".scss", ".json", ".yaml", ".yml", ".toml", ".xml",
    ".md", ".txt", ".sql", ".txt",
}
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build",
}

total_files, total_count = 0, 0

print(f"当前目录: {os.path.abspath('.')}")
print(f"查找: {OLD!r}  替换为: {NEW!r}  模式: {'预览' if DRY else '替换'}")
print("-" * 50)

for dirpath, dirnames, filenames in os.walk("."):
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    for name in filenames:
        if not any(name.endswith(ext) for ext in EXTS):
            continue
        path = os.path.join(dirpath, name)
        enc = None
        for encoding in ("utf-8", "gbk"):
            try:
                text = open(path, encoding=encoding).read()
                enc = encoding
                break
            except Exception:
                continue
        if enc is None:
            print(f"  跳过(编码失败): {name}")
            continue
        count = text.count(OLD)
        if count == 0:
            continue
        total_files += 1
        total_count += count
        print(f"  {'[预览]' if DRY else '[替换]'} {path}  ({count} 处)  [{enc}]")
        if not DRY:
            open(path, "w", encoding=enc).write(text.replace(OLD, NEW))

print("-" * 50)
print(f"共 {total_files} 个文件，{total_count} 处{'匹配' if DRY else '已替换'}。")
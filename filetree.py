#!/usr/bin/env python3
"""
filetree.py —— 生成只含源码和配置文件的文件树
用法: python filetree.py [路径] [选项]

选项:
  -o, --output FILE   将结果写入文件（默认输出到终端）
  -d, --max-depth N   最大目录深度（默认不限制）
  --no-color          关闭颜色输出
"""

import os
import sys
import argparse

# ── 需要完整跳过的目录名 ────────────────────────────────────────────────────────
SKIP_DIRS = {
    # 依赖 / 包管理
    "node_modules", ".pnp", ".yarn",
    "vendor",                          # Go / PHP Composer
    ".venv", "venv", "env", ".env",    # Python 虚拟环境
    "Pods",                            # CocoaPods
    # 构建输出
    "dist", "build", "out", "output",
    "target",                          # Rust / Maven
    "bin", "obj",                      # C# / .NET
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".tox",
    "*.egg-info",                      # 下面用前缀匹配
    ".gradle", ".idea", ".vs",
    "CMakeFiles",
    # 版本控制 / IDE
    ".git", ".svn", ".hg",
    ".DS_Store",
    # 覆盖率 / 报告
    "coverage", ".nyc_output", "htmlcov",
    # 临时
    "tmp", "temp", ".tmp",
}

# 目录名前缀匹配（包含这些前缀的目录也跳过）
SKIP_DIR_PREFIXES = (".cache", "__")

# ── 允许的文件扩展名（源码 + 配置） ──────────────────────────────────────────────
ALLOWED_EXTENSIONS = {
    # ---------- 通用配置 ----------
    ".json", ".jsonc", ".json5",
    ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf",
    ".env", ".env.example", ".env.sample",
    ".xml",
    ".properties",
    # ---------- 构建配置 ----------
    ".cmake",
    # ---------- Python ----------
    ".py", ".pyi", ".pyw",
    # ---------- JavaScript / TypeScript ----------
    ".js", ".mjs", ".cjs",
    ".ts", ".tsx", ".jsx",
    ".vue", ".svelte",
    # ---------- Web ----------
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    # ---------- Shell ----------
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
    # ---------- 系统语言 ----------
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx",
    ".rs",          # Rust
    ".go",          # Go
    ".java",        # Java
    ".kt", ".kts",  # Kotlin
    ".swift",       # Swift
    ".m", ".mm",    # Objective-C
    ".cs",          # C#
    ".fs", ".fsx",  # F#
    ".vb",          # VB.NET
    # ---------- Ruby / PHP / Perl ----------
    ".rb", ".rake", ".erb",
    ".php",
    ".pl", ".pm",
    # ---------- 其他脚本 ----------
    ".lua",
    ".r", ".R",
    ".scala",
    ".ex", ".exs",   # Elixir
    ".erl", ".hrl",  # Erlang
    ".clj", ".cljs", # Clojure
    ".hs", ".lhs",   # Haskell
    ".ml", ".mli",   # OCaml
    ".dart",
    ".sql",
    ".graphql", ".gql",
    ".proto",        # Protobuf
    # ---------- 文档型配置 ----------
    ".md", ".rst", ".txt",
    ".dockerfile",
    ".tf", ".tfvars",   # Terraform
    ".nix",
    ".lock",            # Cargo.lock / Gemfile.lock 等
}

# 无扩展名但应保留的文件名（精确匹配）
ALLOWED_EXACT_NAMES = {
    "Makefile", "GNUmakefile", "makefile",
    "Dockerfile", "Containerfile",
    "Procfile",
    "Gemfile", "Rakefile", "Brewfile",
    "Cargo.lock", "Pipfile", "Pipfile.lock",
    "go.sum",
    ".gitignore", ".gitattributes", ".gitmodules",
    ".editorconfig",
    ".eslintrc", ".prettierrc", ".stylelintrc",
    ".babelrc", ".browserslistrc",
    ".nvmrc", ".node-version", ".python-version",
    ".rubocop.yml",
    "CMakeLists.txt",
    "LICENSE", "LICENSE.md", "LICENSE.txt",
    "AUTHORS", "CHANGELOG", "CHANGELOG.md",
    "requirements.txt", "constraints.txt",
    "package.json", "package-lock.json",
    "pyproject.toml", "setup.py", "setup.cfg",
    "tsconfig.json", "jsconfig.json",
    "Makefile.am", "configure.ac",
}

# ── 即使扩展名匹配也要排除的模式 ──────────────────────────────────────────────────
SKIP_FILE_SUFFIXES = (
    ".min.js", ".min.css",      # 压缩产物
    ".bundle.js",
    ".map",                     # source map（可按需开放）
    ".pyc", ".pyo", ".pyd",
    ".class",                   # Java 字节码
    ".o", ".obj", ".a", ".lib", # 编译中间产物
    ".so", ".dylib", ".dll",    # 动态库
    ".exe", ".out", ".elf",
    ".wasm",
    ".jar", ".war", ".ear",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".ttf", ".woff", ".woff2", ".eot",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".db", ".sqlite", ".sqlite3",
)

# ── 颜色 ───────────────────────────────────────────────────────────────────────
BLUE  = "\033[34m"
RESET = "\033[0m"

def should_skip_dir(name: str) -> bool:
    if name in SKIP_DIRS:
        return True
    if any(name.startswith(p) for p in SKIP_DIR_PREFIXES):
        return True
    # egg-info 之类带通配符的
    if name.endswith(".egg-info") or name.endswith(".dist-info"):
        return True
    return False

def should_include_file(name: str) -> bool:
    # 精确名称优先
    if name in ALLOWED_EXACT_NAMES:
        return True
    # 排除优先于允许
    lower = name.lower()
    if any(lower.endswith(s) for s in SKIP_FILE_SUFFIXES):
        return False
    # 按扩展名判断
    _, ext = os.path.splitext(name)
    return ext.lower() in ALLOWED_EXTENSIONS

def build_tree(
    root: str,
    prefix: str = "",
    max_depth: int | None = None,
    current_depth: int = 0,
    use_color: bool = True,
) -> list[str]:
    if max_depth is not None and current_depth > max_depth:
        return []

    try:
        entries = sorted(os.scandir(root), key=lambda e: (e.is_file(), e.name.lower()))
    except PermissionError:
        return [f"{prefix}[权限不足]"]

    lines = []
    # 过滤
    visible = []
    for e in entries:
        if e.is_dir(follow_symlinks=False):
            if not should_skip_dir(e.name):
                visible.append(e)
        elif e.is_file(follow_symlinks=False):
            if should_include_file(e.name):
                visible.append(e)

    for i, entry in enumerate(visible):
        is_last = i == len(visible) - 1
        connector = "└── " if is_last else "├── "
        extension = "    " if is_last else "│   "

        if entry.is_dir(follow_symlinks=False):
            name = (f"{BLUE}{entry.name}{RESET}" if use_color else entry.name) + "/"
            lines.append(f"{prefix}{connector}{name}")
            lines.extend(
                build_tree(
                    entry.path,
                    prefix + extension,
                    max_depth,
                    current_depth + 1,
                    use_color,
                )
            )
        else:
            lines.append(f"{prefix}{connector}{entry.name}")

    return lines

def main():
    parser = argparse.ArgumentParser(
        description="生成只含源码和配置文件的文件树",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", nargs="?", default=".", help="目标路径（默认当前目录）")
    parser.add_argument("-o", "--output", help="输出到文件")
    parser.add_argument("-d", "--max-depth", type=int, default=None, metavar="N", help="最大深度")
    parser.add_argument("--no-color", action="store_true", help="关闭颜色")
    args = parser.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"错误：'{root}' 不是有效目录", file=sys.stderr)
        sys.exit(1)

    use_color = not args.no_color and sys.stdout.isatty()

    header = (f"{BLUE}{root}{RESET}" if use_color else root) + "/"
    lines = [header] + build_tree(root, max_depth=args.max_depth, use_color=use_color)
    output = "\n".join(lines)

    if args.output:
        # 写文件时去掉 ANSI 颜色
        clean = "\n".join(
            line.replace(BLUE, "").replace(RESET, "") for line in lines
        )
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(clean + "\n")
        print(f"已写入：{args.output}")
    else:
        print(output)

if __name__ == "__main__":
    main()

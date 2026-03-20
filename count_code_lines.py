#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
软件源码行数统计工具
适用于软件著作权申请代码统计
作者：CodeBuddy
"""

import os
import sys
import argparse
from collections import defaultdict


class CodeLineCounter:
    """代码行数统计器"""
    
    # 常见编程语言文件扩展名
    LANGUAGE_EXTENSIONS = {
        'C++': ['.cpp', '.cxx', '.cc', '.h', '.hpp', '.hxx', '.hh', '.h++', '.c++', '.cppm', '.ixx', '.inl', '.ipp', '.tpp'],
        'C': ['.c', '.h'],
        'C#': ['.cs'],
        'Java': ['.java'],
        'Python': ['.py'],
        'JavaScript': ['.js', '.jsx'],
        'TypeScript': ['.ts', '.tsx'],
        'HTML': ['.html', '.htm'],
        'CSS': ['.css', '.scss', '.sass', '.less', '.qss'],
        'Go': ['.go'],
        'Rust': ['.rs'],
        'PHP': ['.php'],
        'Ruby': ['.rb'],
        'Swift': ['.swift'],
        'Kotlin': ['.kt'],
        'Objective-C': ['.m', '.mm'],
        'SQL': ['.sql'],
        'Shell': ['.sh', '.bash'],
        'PowerShell': ['.ps1'],
        'XML': ['.xml', '.qrc', '.ui'],
        'JSON': ['.json'],
        'YAML': ['.yml', '.yaml'],
        'Markdown': ['.md', '.markdown'],
        'Vue': ['.vue'],
        'Assembly': ['.asm', '.s', '.S'],
        'CUDA': ['.cu', '.cuh'],
        'OpenCL': ['.cl'],
        'Resource Script': ['.rc', '.rc2', '.def'],
        'Makefile': ['Makefile', 'makefile', '.mk'],
        'CMake': ['CMakeLists.txt', '.cmake'],
        'QMake': ['.pri', '.pro'],
    }
    
    # 默认排除的目录
    DEFAULT_EXCLUDE_DIRS = {
        '.git', '.svn', '.hg',  # 版本控制
        'node_modules', 'vendor', 'packages',  # 依赖
        'build', 'dist', 'target', 'out', 'Release', 'Debug',  # 构建输出
        '.vs', '.idea', '.vscode', '__pycache__', '.pytest_cache',  # IDE和缓存
        'bin', 'obj', 'lib', 'libs',  # 编译输出
        'docs', 'doc', 'documentation', 'examples', 'test', 'tests',  # 文档和测试
        'third_party', 'third-party', 'external', 'deps',  # 第三方代码
    }
    
    # 默认排除的文件扩展名（非源代码文件）
    DEFAULT_EXCLUDE_EXTENSIONS = {
        # 图片文件
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp',
        # 二进制和可执行文件
        '.exe', '.dll', '.so', '.dylib', '.lib', '.a', '.obj', '.o', '.pdb', '.idb',
        '.bin', '.pch', '.dat', '.idx', '.vsdx', '.xmind', '.debug', '.release', '.depend',
        # 压缩包
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz',
        # 文档文件
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp',
        # 日志和临时文件
        '.log', '.tlog', '.tmp', '.temp', '.cache', '.swp', '.swo',
        # IDE和构建系统文件
        '.user', '.suo', '.sln', '.vcxproj', '.filters', '.props',
        '.stash', '.aps', '.res', '.ilk', '.exp', '.manifest', '.ilk',
        # 配置文件
        '.ini', '.cfg', '.conf', '.config', '.properties', '.setting', '.settings',
        '.rule', '.in',
        # 其他
        '.cbt', '.lastbuildstate', '.hint', '.recipe',
    }

    def __init__(self, extensions=None, exclude_dirs=None, exclude_files=None):
        """
        初始化统计器
        
        Args:
            extensions: 要统计的文件扩展名列表，None表示统计所有
            exclude_dirs: 要排除的目录列表
            exclude_files: 要排除的文件列表
        """
        self.extensions = set(extensions) if extensions else None
        # 始终保留默认排除目录；若用户额外指定了目录，追加到默认集合中而非替换
        self.exclude_dirs = self.DEFAULT_EXCLUDE_DIRS.copy()
        if exclude_dirs:
            self.exclude_dirs.update(exclude_dirs)
        self.exclude_files = set(exclude_files) if exclude_files else set()
        
        # 统计数据
        self.stats = {
            'total_files': 0,
            'total_lines': 0,
            'total_code': 0,
            'total_comments': 0,
            'total_blank': 0,
        }
        self.language_stats = defaultdict(lambda: {
            'files': 0,
            'lines': 0,
            'code': 0,
            'comments': 0,
            'blank': 0,
        })
    
    def get_language(self, filename):
        """根据文件名判断编程语言"""
        name_lower = filename.lower()
        ext = os.path.splitext(name_lower)[1]
        
        for lang, extensions in self.LANGUAGE_EXTENSIONS.items():
            # 检查扩展名（已统一小写，直接比较）
            if ext in extensions:
                return lang
            # 检查完整文件名（Makefile / CMakeLists.txt 等无扩展名或特殊名文件）
            # 统一转小写比较，避免大小写不一致导致漏检（如 CMakeLists.txt → cmakelists.txt）
            if any(name_lower == e.lower() for e in extensions if not e.startswith('.')):
                return lang
        return 'Other'
    
    def is_comment_line(self, line, language):
        """判断是否为注释行"""
        stripped = line.strip()
        if not stripped:
            return False
        
        # C/C++/C#/Java/JavaScript/TypeScript/CSS 风格
        if language in ['C++', 'C', 'C#', 'Java', 'JavaScript', 'TypeScript', 'Go', 'Rust', 'Swift', 'Kotlin', 'Objective-C', 'PHP', 'CUDA', 'OpenCL', 'Resource Script', 'CSS']:
            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                return True
        
        # Python/Shell/Ruby/Perl/YAML/Assembly/Makefile/CMake/QMake 风格
        if language in ['Python', 'Shell', 'Ruby', 'PowerShell', 'YAML', 'Assembly', 'Makefile', 'CMake', 'QMake']:
            if stripped.startswith('#'):
                return True
            # Assembly 特有的 ; 注释
            if language == 'Assembly' and stripped.startswith(';'):
                return True
        
        # HTML/XML 风格
        if language in ['HTML', 'XML']:
            if stripped.startswith('<!--'):
                return True
        
        # SQL 风格
        if language == 'SQL':
            if stripped.startswith('--'):
                return True
        
        return False
    
    def count_file(self, filepath):
        """统计单个文件的行数"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"  警告: 无法读取文件 {filepath}: {e}")
            return None
        
        total_lines = len(lines)
        blank_lines = 0
        comment_lines = 0
        code_lines = 0
        
        language = self.get_language(os.path.basename(filepath))
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_lines += 1
            elif self.is_comment_line(line, language):
                comment_lines += 1
            else:
                code_lines += 1
        
        return {
            'total': total_lines,
            'code': code_lines,
            'comments': comment_lines,
            'blank': blank_lines,
            'language': language,
        }
    
    def should_exclude(self, path, is_dir=True):
        """判断是否应该排除"""
        name = os.path.basename(path)
        
        if is_dir:
            return name in self.exclude_dirs
        else:
            if name in self.exclude_files:
                return True
            # 检查扩展名是否在默认排除列表中
            ext = os.path.splitext(name)[1].lower()
            if ext in self.DEFAULT_EXCLUDE_EXTENSIONS:
                return True
            if self.extensions:
                return ext not in self.extensions
            return False
    
    def scan_directory(self, directory):
        """扫描目录并统计"""
        print(f"\n正在扫描目录: {directory}")
        print("-" * 60)
        
        for root, dirs, files in os.walk(directory):
            # 过滤目录
            dirs[:] = [d for d in dirs if not self.should_exclude(os.path.join(root, d), True)]
            
            for filename in files:
                filepath = os.path.join(root, filename)
                
                if self.should_exclude(filepath, False):
                    continue
                
                result = self.count_file(filepath)
                if result:
                    lang = result['language']
                    
                    # 更新总统计
                    self.stats['total_files'] += 1
                    self.stats['total_lines'] += result['total']
                    self.stats['total_code'] += result['code']
                    self.stats['total_comments'] += result['comments']
                    self.stats['total_blank'] += result['blank']
                    
                    # 更新语言统计
                    self.language_stats[lang]['files'] += 1
                    self.language_stats[lang]['lines'] += result['total']
                    self.language_stats[lang]['code'] += result['code']
                    self.language_stats[lang]['comments'] += result['comments']
                    self.language_stats[lang]['blank'] += result['blank']
    
    def print_report(self):
        """打印统计报告"""
        print("\n" + "=" * 70)
        print(" " * 20 + "代 码 统 计 报 告")
        print("=" * 70)
        
        # 总体统计
        total = self.stats['total_lines']
        def pct(n): return f"{n / total * 100:.1f}%" if total > 0 else "—"
        print("\n【总体统计】")
        print(f"  总文件数:    {self.stats['total_files']:>8} 个")
        print(f"  总行数:      {total:>8} 行")
        if total == 0:
            print("  （未扫描到任何代码文件）")
            return
        print(f"  代码行:      {self.stats['total_code']:>8} 行 ({pct(self.stats['total_code'])})")
        print(f"  注释行:      {self.stats['total_comments']:>8} 行 ({pct(self.stats['total_comments'])})")
        print(f"  空行:        {self.stats['total_blank']:>8} 行 ({pct(self.stats['total_blank'])})")
        
        # 按语言统计
        if self.language_stats:
            print("\n【按语言统计】")
            print("-" * 70)
            print(f"{'语言':<15} {'文件数':>8} {'总行数':>10} {'代码行':>10} {'注释行':>10} {'空行':>8}")
            print("-" * 70)
            
            # 按代码行数排序
            sorted_langs = sorted(
                self.language_stats.items(),
                key=lambda x: x[1]['code'],
                reverse=True
            )
            
            for lang, stat in sorted_langs:
                print(f"{lang:<15} {stat['files']:>8} {stat['lines']:>10} {stat['code']:>10} {stat['comments']:>10} {stat['blank']:>8}")
            
            print("-" * 70)
        
        print("\n" + "=" * 70)
        print("注: 以上统计仅包含实际代码，不包含第三方库和生成文件")
        print("=" * 70)
    
    def save_report(self, output_file,in_directory):
        """保存报告到文件"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"代码统计报告{in_directory}\n")
            f.write("=" * 70 + "\n\n")
            
            f.write("【总体统计】\n")
            f.write(f"总文件数: {self.stats['total_files']} 个\n")
            f.write(f"总行数: {self.stats['total_lines']} 行\n")
            f.write(f"代码行: {self.stats['total_code']} 行\n")
            f.write(f"注释行: {self.stats['total_comments']} 行\n")
            f.write(f"空行: {self.stats['total_blank']} 行\n\n")
            
            if self.language_stats:
                f.write("【按语言统计】\n")
                for lang, stat in sorted(self.language_stats.items(), key=lambda x: x[1]['code'], reverse=True):
                    f.write(f"{lang}  {stat['files']} 个文件: {stat['code']} :行代码\n")
        
        print(f"\n报告已保存到: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='软件源码行数统计工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s                           # 统计当前目录
  %(prog)s -d /path/to/code          # 统计指定目录
  %(prog)s -e .cpp .h .hpp           # 只统计 C++ 文件
  %(prog)s -o report.txt             # 输出报告到文件
  %(prog)s -d . -e .cpp -o result.txt # 组合使用
        """
    )
    
    parser.add_argument(
        '-d', '--directory',
        default='.',
        help='要统计的目录 (默认: 当前目录)'
    )
    
    parser.add_argument(
        '-e', '--extensions',
        nargs='+',
        help='要统计的文件扩展名，如: .cpp .h .py'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='输出报告到文件'
    )
    
    parser.add_argument(
        '--exclude-dirs',
        nargs='+',
        help='额外排除的目录'
    )
    
    parser.add_argument(
        '--list-langs',
        action='store_true',
        help='列出支持的所有语言'
    )
    
    args = parser.parse_args()
    
    # 列出支持的语言
    if args.list_langs:
        print("\n支持的编程语言:")
        for lang, exts in sorted(CodeLineCounter.LANGUAGE_EXTENSIONS.items()):
            print(f"  {lang:<15} {', '.join(exts)}")
        print()
        return
    
    # 检查目录是否存在
    if not os.path.isdir(args.directory):
        print(f"错误: 目录不存在: {args.directory}")
        sys.exit(1)
    
    # 扩展名转换为小写
    extensions = None
    if args.extensions:
        extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in args.extensions]
    
    # 创建统计器
    counter = CodeLineCounter(
        extensions=extensions,
        exclude_dirs=set(args.exclude_dirs) if args.exclude_dirs else None
    )
    
    # 执行统计
    counter.scan_directory(args.directory)
    
    # 打印报告
    counter.print_report()
    
    # 保存报告
    if args.output:
        counter.save_report(args.output,args.directory)
    
    # 返回代码行数（可用于脚本调用）
    return counter.stats['total_code']


if __name__ == '__main__':
    code_lines = main()
    sys.exit(0)

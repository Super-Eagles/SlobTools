import os
import sys
import shutil
from pathlib import Path

def copy_qt_msvc_sources(src_dir, dest_dir):
    src_path = Path(src_dir).resolve()
    dest_path = Path(dest_dir).resolve()

    if not src_path.exists():
        print(f"❌ 错误：输入路径不存在: {src_dir}")
        return

    # 如果输入和输出路径相同，直接退出防止死循环
    if src_path == dest_path:
        print("❌ 错误：输入路径和输出路径不能相同！")
        return

    # 定义需要保留的后缀名 (涵盖 C++, Qt 以及 MSVC 工程文件)
    allowed_extensions = {
        # C/C++ 源码
        '.cpp', '.h', '.hpp', '.c', '.cc', '.cxx', '.hxx',
        # Qt 专属资源
        '.ui', '.qrc', '.ts', '.tr',
        # 工程结构文件
        '.sln', '.vcxproj', '.filters', '.pro', '.pri'
    }

    # 特殊文件精确匹配 (例如 CMake 构建文件)
    allowed_filenames = {'cmakelists.txt'}

    # 遇到这些目录直接跳过，不进去遍历（提升效率，防止复制临时生成的 cpp 文件如 moc 等）
    ignore_dirs = {
        '.vs', 'debug', 'release', 'x64', 'x86', 
        'generatedfiles', 'build', '.git', '.svn', 'out'
    }

    copy_count = 0

    print(f"📦 开始从源目录提取: {src_path}")
    print(f"📂 目标目录: {dest_path}\n")

    for current_dir, dirs, files in os.walk(src_path):
        # 就地修改 dirs 列表，让 os.walk 提前跳过不需要的目录
        dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs]

        for file in files:
            file_path = Path(current_dir) / file
            
            # 判断是否是我们需要的源码或工程文件
            is_valid_ext = file_path.suffix.lower() in allowed_extensions
            is_valid_name = file.lower() in allowed_filenames

            if is_valid_ext or is_valid_name:
                # 获取相对路径，用于在目标目录重建树状结构
                rel_path = file_path.relative_to(src_path)
                target_path = dest_path / rel_path

                # 确保目标文件的父目录存在
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # 复制文件 (copy2 会尽可能保留文件的元数据)
                shutil.copy2(file_path, target_path)
                print(f"✅ 已复制: {rel_path}")
                copy_count += 1

    print(f"\n🎉 提取完成！共复制了 {copy_count} 个源码文件。")

if __name__ == "__main__":
    # 检查参数数量
    if len(sys.argv) != 3:
        print("💡 用法: python copy_qt_src.py <输入路径> <输出路径>")
        print("   示例: python copy_qt_src.py D:\\MyProject D:\\MyProject_Clean")
        sys.exit(1)
    
    source_directory = sys.argv[1]
    destination_directory = sys.argv[2]
    
    copy_qt_msvc_sources(source_directory, destination_directory)
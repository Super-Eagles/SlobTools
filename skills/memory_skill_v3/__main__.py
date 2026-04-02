"""
memory_skill_v3 · 包入口
=========================
支持直接以模块方式运行：
    python -m memory_skill_v3 <command> [options]

等价于：
    python -m memory_skill_v3.session_cli <command> [options]

示例：
    python -m memory_skill_v3 ensure  --workspace /your/project
    python -m memory_skill_v3 remember --workspace /your/project --query "当前任务"
    python -m memory_skill_v3 write    --workspace /your/project \\
        --question "问题" --answer "回答" --summary "摘要" --keywords-json '["kw1"]'
    python -m memory_skill_v3 flush    --workspace /your/project
    python -m memory_skill_v3 stats    --workspace /your/project
    python -m memory_skill_v3 setup    --workspace /your/project
"""

from .session_cli import main

if __name__ == "__main__":
    main()

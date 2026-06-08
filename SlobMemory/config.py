import os


def _read_persisted_windows_env(name: str):
    try:
        import winreg
    except ImportError:
        return None

    key_specs = (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    )

    for root, subkey in key_specs:
        try:
            with winreg.OpenKey(root, subkey) as key:
                value, _ = winreg.QueryValueEx(key, name)
                if value not in (None, ""):
                    return str(value)
        except OSError:
            continue

    return None


def _get_env(name: str, default: str):
    value = os.environ.get(name)
    if value not in (None, ""):
        if "memory_skill_v3" in value.lower():
            return default
        return value

    persisted = _read_persisted_windows_env(name)
    if persisted not in (None, ""):
        if "memory_skill_v3" in persisted.lower():
            return default
        return persisted

    return default


REDIS_URL        = _get_env("MEMORY_REDIS_URL",        "redis://127.0.0.1:6379")
SQLITE_PATH      = _get_env("MEMORY_SQLITE_PATH",      r"D:\soft\SlobTools\SlobMemory\memory.db")
EMBED_MODEL      = _get_env("MEMORY_EMBED_MODEL",      "paraphrase-multilingual-MiniLM-L12-v2")
EMBED_DIM        = int(_get_env("MEMORY_EMBED_DIM",    "384"))
TOP_K            = int(_get_env("MEMORY_TOP_K",        "5"))
SIM_THRESHOLD    = float(_get_env("MEMORY_SIM_THRESHOLD",   "0.75"))
MERGE_THRESHOLD  = float(_get_env("MEMORY_MERGE_THRESHOLD", "0.88"))
SESSION_TTL      = int(_get_env("MEMORY_SESSION_TTL",  "86400"))

# 注入到 prompt 的记忆 token 预算。
# 建议值：GPT-4 / Claude → 1200，GPT-3.5 → 800，长上下文模型可放大到 2000+。
MEMORY_TOKEN_BUDGET = int(_get_env("MEMORY_TOKEN_BUDGET", "1200"))

# ── 向量嵌入服务（可选）──────────────────────────────────────────────────────
# 设置此项后，embedding.py 进入远程模式，不再本地加载 ~470 MB 模型。
# 留空（默认）保持原有本地加载行为，完全向后兼容。
#
# 示例：
#   export MEMORY_EMBED_SERVICE_URL=http://127.0.0.1:7731
#   python embed_server.py          # 在另一个终端启动服务
#   python your_app.py              # 主进程无需加载模型
#
# 注意：默认值为空字符串，表示本地模式。
#       如需远程模式，需显式设置环境变量 MEMORY_EMBED_SERVICE_URL。
EMBED_SERVICE_URL = _get_env("MEMORY_EMBED_SERVICE_URL", "")

# 自定义记忆分类词表（可选）。
# - CATEGORY_HINTS       完整替换默认词表，dict[str, list[str]]
# - EXTRA_CATEGORY_HINTS 按类别追加，不影响其他类别
# 示例：
#   from memory_skill_v3 import config
#   config.EXTRA_CATEGORY_HINTS = {"preference": ["偏好", "prefer"], "fact": ["架构"]}
CATEGORY_HINTS       = None   # type: dict | None
EXTRA_CATEGORY_HINTS = None   # type: dict | None


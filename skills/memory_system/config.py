import os

REDIS_URL        = os.environ.get("MEMORY_REDIS_URL",        "redis://localhost:6379")
SQLITE_PATH      = os.environ.get("MEMORY_SQLITE_PATH",      "./memory.db")
EMBED_MODEL      = os.environ.get("MEMORY_EMBED_MODEL",      "paraphrase-multilingual-MiniLM-L12-v2")
EMBED_DIM        = int(os.environ.get("MEMORY_EMBED_DIM",    "384"))
TOP_K            = int(os.environ.get("MEMORY_TOP_K",        "5"))
SIM_THRESHOLD    = float(os.environ.get("MEMORY_SIM_THRESHOLD",   "0.75"))
MERGE_THRESHOLD  = float(os.environ.get("MEMORY_MERGE_THRESHOLD", "0.88"))
SESSION_TTL      = int(os.environ.get("MEMORY_SESSION_TTL",  "86400"))

# 注入到 prompt 的记忆 token 预算。
# 建议值：GPT-4 / Claude ≈ 1200，GPT-3.5 ≈ 800，长上下文模型可放大至 2000+。
MEMORY_TOKEN_BUDGET = int(os.environ.get("MEMORY_TOKEN_BUDGET", "1200"))

# 自定义记忆分类词表（可选）。
# - CATEGORY_HINTS       完整替换默认词表，dict[str, list[str]]
# - EXTRA_CATEGORY_HINTS 按类别追加，不影响其他类别
# 示例：
#   from memory_skill_v2 import config
#   config.EXTRA_CATEGORY_HINTS = {"preference": ["喜好", "prefer"], "fact": ["架构图"]}
CATEGORY_HINTS       = None   # type: dict | None
EXTRA_CATEGORY_HINTS = None   # type: dict | None

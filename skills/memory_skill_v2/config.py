import os

REDIS_URL        = os.environ.get("MEMORY_REDIS_URL",        "redis://localhost:6379")
SQLITE_PATH      = os.environ.get("MEMORY_SQLITE_PATH",      "./memory.db")
EMBED_MODEL      = os.environ.get("MEMORY_EMBED_MODEL",      "paraphrase-multilingual-MiniLM-L12-v2")
EMBED_DIM        = int(os.environ.get("MEMORY_EMBED_DIM",    "384"))
TOP_K            = int(os.environ.get("MEMORY_TOP_K",        "5"))
SIM_THRESHOLD    = float(os.environ.get("MEMORY_SIM_THRESHOLD",   "0.75"))
MERGE_THRESHOLD  = float(os.environ.get("MEMORY_MERGE_THRESHOLD", "0.88"))
SESSION_TTL      = int(os.environ.get("MEMORY_SESSION_TTL",  "86400"))

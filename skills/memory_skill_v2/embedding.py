"""
utils/embedding.py
==================
两种运行模式（自动检测，无需改调用方）：

  远程模式（推荐）：
    设置环境变量  MEMORY_EMBED_SERVICE_URL=http://127.0.0.1:7731
    本模块变为 HTTP 客户端，不加载 sentence-transformers，启动几乎零开销。

  本地模式（向后兼容）：
    不设置 MEMORY_EMBED_SERVICE_URL，行为与改造前完全相同。
    模型在首次调用 embed() 时懒加载（~470 MB）。
"""

from .. import config
import logging

logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

# ── 本地模式的懒加载单例 ───────────────────────────────────────────────────────
_local_model = None


def _service_url() -> str:
    """返回远程服务 URL，未配置则返回空字符串。"""
    return (getattr(config, "EMBED_SERVICE_URL", None) or "").rstrip("/")


# ── 远程模式：HTTP 客户端 ──────────────────────────────────────────────────────
def _remote_embed(text: str) -> list:
    import requests
    url = _service_url()
    try:
        resp = requests.post(
            f"{url}/embed",
            json={"text": text},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception as exc:
        raise RuntimeError(
            f"[memory-skill] Embedding service unreachable at {url}. "
            "Run `python embed_server.py` first, or unset MEMORY_EMBED_SERVICE_URL "
            "to fall back to local mode."
        ) from exc


def _remote_embed_batch(texts: list) -> list:
    import requests
    url = _service_url()
    try:
        resp = requests.post(
            f"{url}/embed_batch",
            json={"texts": texts},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]
    except Exception as exc:
        raise RuntimeError(
            f"[memory-skill] Embedding service unreachable at {url}. "
            "Run `python embed_server.py` first, or unset MEMORY_EMBED_SERVICE_URL "
            "to fall back to local mode."
        ) from exc


# ── 本地模式：懒加载 ──────────────────────────────────────────────────────────
def _get_local_model():
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        _local_model = SentenceTransformer(config.EMBED_MODEL)
    return _local_model


# ── 公开 API（调用方无需修改）────────────────────────────────────────────────
def embed(text: str) -> list:
    if _service_url():
        return _remote_embed(text)
    vec = _get_local_model().encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: list) -> list:
    if _service_url():
        return _remote_embed_batch(texts)
    vecs = _get_local_model().encode(
        texts, normalize_embeddings=True, batch_size=32
    )
    return [v.tolist() for v in vecs]


def ping_service() -> bool:
    """
    检查远程服务是否就绪（供 api.setup() 调用）。
    本地模式下永远返回 True。
    """
    url = _service_url()
    if not url:
        return True
    import requests
    try:
        resp = requests.get(f"{url}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False

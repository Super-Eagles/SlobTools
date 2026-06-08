from .. import config
import logging

logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

_local_model = None
_http_session = None  # 复用 requests.Session，避免每次调用重建连接


def _service_url() -> str:
    return (getattr(config, "EMBED_SERVICE_URL", None) or "").rstrip("/")


def _get_session():
    """返回复用的 requests.Session 单例，减少 TCP 握手开销。"""
    global _http_session
    if _http_session is None:
        import requests
        _http_session = requests.Session()
    return _http_session


def close_session():
    """显式关闭 HTTP session，释放底层 socket，确保进程能干净退出。"""
    global _http_session
    if _http_session is not None:
        try:
            _http_session.close()
        except Exception:
            pass
        _http_session = None


def _remote_embed(text: str) -> list:
    url = _service_url()
    try:
        resp = _get_session().post(f"{url}/embed", json={"text": text}, timeout=10)
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception as exc:
        raise RuntimeError(
            f"[memory-skill] Embedding service unreachable at {url}. "
            "Run `python embed_server.py` first, or unset MEMORY_EMBED_SERVICE_URL "
            "to fall back to local mode."
        ) from exc


def _remote_embed_batch(texts: list) -> list:
    url = _service_url()
    try:
        resp = _get_session().post(f"{url}/embed_batch", json={"texts": texts}, timeout=30)
        resp.raise_for_status()
        return resp.json()["embeddings"]
    except Exception as exc:
        raise RuntimeError(
            f"[memory-skill] Embedding service unreachable at {url}. "
            "Run `python embed_server.py` first, or unset MEMORY_EMBED_SERVICE_URL "
            "to fall back to local mode."
        ) from exc


def _get_local_model():
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        _local_model = SentenceTransformer(config.EMBED_MODEL)
    return _local_model


def embed(text: str) -> list:
    if _service_url():
        return _remote_embed(text)
    vec = _get_local_model().encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: list) -> list:
    if _service_url():
        return _remote_embed_batch(texts)
    vecs = _get_local_model().encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vecs]


def ping_service() -> bool:
    url = _service_url()
    if not url:
        return True
    try:
        resp = _get_session().get(f"{url}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False

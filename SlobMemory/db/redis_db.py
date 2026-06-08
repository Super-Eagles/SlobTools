import redis as _redis
from .. import config

_client = None


def get_client():
    global _client
    if _client is None:
        _client = _redis.from_url(config.REDIS_URL, decode_responses=True)
    return _client


def close():
    """显式关闭连接池，确保进程能干净退出。"""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None


def ping():
    try:
        return get_client().ping()
    except Exception:
        return False


def check_persistence():
    """检查 Redis 是否开启了持久化，未开启时打印 warning。
    托管 Redis（如 Upstash）会禁用 CONFIG GET，此时静默跳过。
    """
    try:
        r = get_client()
        save_cfg    = r.config_get("save").get("save", "")
        rdb_enabled = bool(save_cfg.strip())
        info        = r.info("persistence")
        aof_enabled = info.get("aof_enabled", 0) == 1

        if not rdb_enabled and not aof_enabled:
            import sys
            print(
                "[memory-skill] WARNING: Redis persistence is OFF. "
                "Hot memories will be lost on Redis restart before flush(). "
                "Enable RDB (CONFIG SET save '3600 1') or AOF to avoid data loss.",
                file=sys.stderr,
            )
    except Exception:
        pass


def hot_key(user_id, session_id, turn, item_index=0):
    return f"mem:hot:{user_id}:{session_id}:{turn}:{item_index}"


def turns_key(session_id):
    return f"session:turns:{session_id}"


def index_key(user_id, session_id):
    return f"mem:idx:{user_id}:{session_id}"


def get_hot_keys(user_id, session_id):
    r = get_client()
    return list(r.smembers(index_key(user_id, session_id)))


def register_hot_key(r, user_id, session_id, key, ttl):
    idx_key = index_key(user_id, session_id)
    r.sadd(idx_key, key)
    r.expire(idx_key, ttl)


def delete_hot_keys(r, user_id, session_id, keys):
    if keys:
        r.delete(*keys)
    r.delete(index_key(user_id, session_id))
    r.delete(turns_key(session_id))

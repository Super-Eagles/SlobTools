import redis as _redis
from .. import config

_client = None


def get_client():
    global _client
    if _client is None:
        _client = _redis.from_url(config.REDIS_URL, decode_responses=True)
    return _client


def ping():
    try:
        return get_client().ping()
    except Exception:
        return False


def hot_key(user_id, session_id, turn, item_index=0):
    return f"mem:hot:{user_id}:{session_id}:{turn}:{item_index}"


def turns_key(session_id):
    return f"session:turns:{session_id}"


def hot_pattern(user_id, session_id):
    return f"mem:hot:{user_id}:{session_id}:*"


def scan_hot_keys(user_id, session_id):
    pattern = hot_pattern(user_id, session_id)
    return list(get_client().scan_iter(match=pattern, count=200))

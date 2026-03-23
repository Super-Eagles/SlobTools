import json
import uuid
from datetime import datetime, timezone

from ..db import redis_db
from .. import config


def write(user_id, session_id, turn, summary, keywords, embedding, raw_q="", raw_a=""):
    mem_id = str(uuid.uuid4())
    mem = {
        "id":         mem_id,
        "user_id":    user_id,
        "session_id": session_id,
        "turn":       turn,
        "summary":    summary,
        "keywords":   keywords,
        "embedding":  embedding,
        "raw_q":      raw_q,
        "raw_a":      raw_a,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    r   = redis_db.get_client()
    key = redis_db.hot_key(user_id, session_id, turn)
    r.setex(key, config.SESSION_TTL, json.dumps(mem, ensure_ascii=False))

    tkey = redis_db.turns_key(session_id)
    r.incr(tkey)
    r.expire(tkey, config.SESSION_TTL)

    return mem_id

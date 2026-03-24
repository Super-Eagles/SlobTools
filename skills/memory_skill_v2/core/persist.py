import json
import uuid

from ..db import redis_db, sqlite_db
from ..utils import vec_utils
from .. import config


def persist_session(user_id, session_id):
    r    = redis_db.get_client()
    keys = r.keys(redis_db.hot_pattern(user_id, session_id))

    if not keys:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    memories = []
    for key in keys:
        val = r.get(key)
        if val:
            memories.append(json.loads(val))
    memories.sort(key=lambda m: m["turn"])

    conn  = sqlite_db.get_conn()
    stats = {"inserted": 0, "updated": 0, "skipped": 0}

    with sqlite_db.write_lock:
        try:
            for mem in memories:
                _persist_one(conn, mem, stats)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    r.delete(*keys)
    r.delete(redis_db.turns_key(session_id))

    return stats


def _persist_one(conn, mem, stats):
    embedding = mem.get("embedding")
    if not embedding:
        stats["skipped"] += 1
        return

    vec_bytes  = vec_utils.serialize(embedding)
    merge_dist = 1.0 - config.MERGE_THRESHOLD
    similar    = _find_closest(conn, mem["user_id"], vec_bytes)

    if similar is None or similar["distance"] > merge_dist:
        _insert(conn, mem, vec_bytes)
        stats["inserted"] += 1
        return

    new_kw  = _to_list(mem.get("keywords", []))
    old_kw  = _to_list(similar["keywords"] or "[]")
    overlap = vec_utils.keyword_overlap(new_kw, old_kw)

    if overlap >= 0.4:
        _update(conn, similar["rowid"], similar["id"], mem, vec_bytes)
        stats["updated"] += 1
    else:
        _insert(conn, mem, vec_bytes)
        stats["inserted"] += 1


def _find_closest(conn, user_id, vec_bytes):
    try:
        row = conn.execute("""
            SELECT m.rowid, m.id, m.keywords, v.distance
            FROM   memories_vec v
            JOIN   memories m ON m.rowid = v.rowid
            WHERE  v.embedding MATCH ?
            AND    m.user_id = ?
            ORDER  BY v.distance ASC
            LIMIT  1
        """, (vec_bytes, user_id)).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def _insert(conn, mem, vec_bytes):
    mem_id   = mem.get("id") or str(uuid.uuid4())
    keywords = _to_json(mem.get("keywords", []))

    cursor = conn.execute("""
        INSERT INTO memories (id, user_id, session_id, turn, summary, keywords, raw_q, raw_a)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        mem_id, mem["user_id"], mem["session_id"], mem["turn"],
        mem["summary"], keywords, mem.get("raw_q", ""), mem.get("raw_a", ""),
    ))

    rowid = cursor.lastrowid
    conn.execute(
        "INSERT INTO memories_vec (rowid, embedding) VALUES (?, ?)",
        (rowid, vec_bytes),
    )


def _update(conn, rowid, mem_id, new_mem, vec_bytes):
    keywords = _to_json(new_mem.get("keywords", []))
    conn.execute("""
        UPDATE memories
        SET summary    = ?,
            keywords   = ?,
            raw_q      = ?,
            raw_a      = ?,
            version    = version + 1,
            updated_at = datetime('now')
        WHERE id = ?
    """, (new_mem["summary"], keywords,
          new_mem.get("raw_q", ""), new_mem.get("raw_a", ""), mem_id))

    conn.execute("DELETE FROM memories_vec WHERE rowid = ?", (rowid,))
    conn.execute(
        "INSERT INTO memories_vec (rowid, embedding) VALUES (?, ?)",
        (rowid, vec_bytes),
    )


def _to_list(value):
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except Exception:
        return []


def _to_json(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)

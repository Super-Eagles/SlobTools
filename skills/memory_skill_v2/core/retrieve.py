import json

from ..db import redis_db, sqlite_db
from ..utils import vec_utils
from .. import config


def retrieve(user_id, session_id, query_embedding, query_text=""):
    hot  = _get_hot(user_id, session_id)
    cold = _get_cold(user_id, query_embedding, query_text)
    return hot, cold


def _get_hot(user_id, session_id):
    r    = redis_db.get_client()
    keys = r.keys(redis_db.hot_pattern(user_id, session_id))
    if not keys:
        return []
    values   = r.mget(keys)
    memories = [json.loads(v) for v in values if v]
    memories.sort(key=lambda m: m["turn"])
    return memories


def _get_cold(user_id, query_embedding, query_text):
    conn        = sqlite_db.get_conn()
    results     = []
    vec_bytes   = vec_utils.serialize(query_embedding)
    max_dist    = 1.0 - config.SIM_THRESHOLD
    fetch_limit = config.TOP_K * 2

    try:
        rows = conn.execute("""
            SELECT m.id, m.summary, m.keywords, m.created_at, v.distance
            FROM   memories_vec v
            JOIN   memories m ON m.rowid = v.rowid
            WHERE  v.embedding MATCH ?
            AND    m.user_id   = ?
            ORDER  BY v.distance ASC
            LIMIT  ?
        """, (vec_bytes, user_id, fetch_limit)).fetchall()

        for row in rows:
            if row["distance"] <= max_dist:
                results.append({
                    "id":         row["id"],
                    "summary":    row["summary"],
                    "keywords":   json.loads(row["keywords"] or "[]"),
                    "created_at": row["created_at"],
                    "score":      1.0 - row["distance"],
                    "source":     "vec",
                })
    except Exception:
        pass

    if query_text and len(results) < config.TOP_K:
        fts_results = _fts_search(conn, user_id, query_text, config.TOP_K)
        seen_ids    = {r["id"] for r in results}
        for r in fts_results:
            if r["id"] not in seen_ids:
                results.append(r)
                seen_ids.add(r["id"])

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:config.TOP_K]


def _fts_search(conn, user_id, query_text, limit):
    safe_query = _escape_fts(query_text)
    if not safe_query:
        return []
    try:
        rows = conn.execute("""
            SELECT m.id, m.summary, m.keywords, m.created_at, rank
            FROM   memories_fts f
            JOIN   memories m ON m.rowid = f.rowid
            WHERE  memories_fts MATCH ?
            AND    m.user_id = ?
            ORDER  BY rank
            LIMIT  ?
        """, (safe_query, user_id, limit)).fetchall()
        return [{
            "id":         row["id"],
            "summary":    row["summary"],
            "keywords":   json.loads(row["keywords"] or "[]"),
            "created_at": row["created_at"],
            "score":      0.5,
            "source":     "fts",
        } for row in rows]
    except Exception:
        return []


def _escape_fts(text):
    specials = '"*^()[]{}:,-'
    cleaned  = "".join(c if c not in specials else " " for c in text)
    tokens   = [t for t in cleaned.split() if len(t) > 1]
    return " OR ".join(tokens) if tokens else ""

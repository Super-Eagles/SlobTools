import sys

from .db       import sqlite_db, redis_db
from .core     import write, retrieve, persist, inject, analyze
from .utils    import embedding
from .         import config
from .         import maintenance


def setup():
    conn = sqlite_db.get_conn()
    ver  = conn.execute("SELECT vec_version()").fetchone()[0]
    print(f"[memory-skill] SQLite ready · sqlite-vec {ver}", file=sys.stderr)

    if not redis_db.ping():
        raise RuntimeError(
            f"[memory-skill] Cannot reach Redis at {config.REDIS_URL}\n"
            "Make sure Memurai (or Redis) is running."
        )
    print("[memory-skill] Redis ready.", file=sys.stderr)
    redis_db.check_persistence()

    svc_url = getattr(config, "EMBED_SERVICE_URL", "")
    if svc_url:
        print(f"[memory-skill] Embedding service: {svc_url}", file=sys.stderr)
        if not embedding.ping_service():
            raise RuntimeError(
                f"[memory-skill] Embedding service not reachable at {svc_url}\n"
                "Run `python embed_server.py` first."
            )
        print("[memory-skill] Embedding service ready.", file=sys.stderr)
    else:
        print("[memory-skill] Loading embedding model (first run downloads ~470 MB)...", file=sys.stderr)
        embedding.embed("warmup")
        print("[memory-skill] Embedding model ready.", file=sys.stderr)

    print("[memory-skill] Setup complete.", file=sys.stderr)


def teardown():
    """显式关闭所有连接，确保进程能干净退出。"""
    try:
        redis_db.close()
    except Exception:
        pass
    try:
        sqlite_db.close()
    except Exception:
        pass
    try:
        embedding.close_session()
    except Exception:
        pass


def remember(user_id, session_id, turn, query_text):
    query_vec     = embedding.embed(query_text)
    hot, cold     = retrieve.retrieve(user_id, session_id, query_vec, query_text)
    hot_t, cold_t = inject.trim_to_budget(hot, cold)
    return inject.format_for_prompt(hot_t, cold_t)


def memorize(user_id, session_id, turn, summary, keywords, raw_q="", raw_a=""):
    items = analyze.build_memory_items(
        turn     = turn,
        summary  = summary,
        keywords = keywords,
        raw_q    = raw_q,
        raw_a    = raw_a,
    )
    if not items:
        return []

    texts      = [item["summary"] for item in items]
    embeddings = embedding.embed_batch(texts)
    for item, emb in zip(items, embeddings):
        item["embedding"] = emb

    return write.write_many(
        user_id    = user_id,
        session_id = session_id,
        turn       = turn,
        items      = items,
        raw_q      = raw_q,
        raw_a      = raw_a,
    )


def flush(user_id, session_id):
    stats = persist.persist_session(user_id, session_id)
    print(f"[memory-skill] Flushed session {session_id}: {stats}", file=sys.stderr)
    return stats


def get_stats(user_id):
    conn  = sqlite_db.get_conn()
    total = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    sess  = conn.execute(
        "SELECT COUNT(DISTINCT session_id) FROM memories WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    return {"total_memories": total, "sessions": sess}


def merge_db(target_db_path, source_db_path):
    return maintenance.merge_databases(target_db_path, source_db_path)


def rewrite_user_id(db_path, new_user_id, old_user_id=None):
    return maintenance.rewrite_user_id(db_path, new_user_id, old_user_id)

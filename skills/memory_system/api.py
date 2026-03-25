from .db       import sqlite_db, redis_db
from .core     import write, retrieve, persist, inject, analyze
from .utils    import embedding


def setup():
    conn = sqlite_db.get_conn()
    ver  = conn.execute("SELECT vec_version()").fetchone()[0]
    print(f"[memory-skill] SQLite ready · sqlite-vec {ver}")

    if not redis_db.ping():
        from . import config
        raise RuntimeError(
            f"[memory-skill] Cannot reach Redis at {config.REDIS_URL}\n"
            "Make sure Memurai (or Redis) is running."
        )
    print("[memory-skill] Redis ready.")
    redis_db.check_persistence()

    print("[memory-skill] Loading embedding model (first run downloads ~470 MB)...")
    embedding.embed("warmup")
    print("[memory-skill] Embedding model ready.")
    print("[memory-skill] Setup complete.")


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

    # 批量 embed，一次推理替代逐条调用，降低延迟
    texts      = [item["summary"] for item in items]
    embeddings = embedding.embed_batch(texts)
    for item, emb in zip(items, embeddings):
        item["embedding"] = emb

    mem_ids = write.write_many(
        user_id    = user_id,
        session_id = session_id,
        turn       = turn,
        items      = items,
        raw_q      = raw_q,
        raw_a      = raw_a,
    )
    return mem_ids


def flush(user_id, session_id):
    stats = persist.persist_session(user_id, session_id)
    print(f"[memory-skill] Flushed session {session_id}: {stats}")
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

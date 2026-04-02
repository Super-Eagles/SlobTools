import os
import uuid

from . import config
from .db import sqlite_db


def merge_databases(target_db_path, source_db_path):
    target_path = _resolve_db_path(target_db_path)
    source_path = _resolve_db_path(source_db_path)

    if target_path == source_path:
        raise ValueError("target_db_path and source_db_path must be different")
    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)

    target_conn = sqlite_db.open_conn(target_path, ensure_schema=True)
    source_conn = sqlite_db.open_conn(source_path, ensure_schema=True)
    stats = {
        "target_db_path": target_path,
        "source_db_path": source_path,
        "scanned": 0,
        "inserted": 0,
        "skipped": 0,
        "missing_embedding": 0,
        "id_regenerated": 0,
    }

    try:
        existing = {
            row["id"]: _signature(row)
            for row in target_conn.execute("""
                SELECT id, user_id, session_id, turn, item_index, kind, summary,
                       keywords, raw_q, raw_a, version, created_at, updated_at
                FROM memories
            """).fetchall()
        }

        rows = source_conn.execute("""
            SELECT m.id, m.user_id, m.session_id, m.turn, m.item_index, m.kind,
                   m.summary, m.keywords, m.raw_q, m.raw_a, m.version,
                   m.created_at, m.updated_at, v.embedding
            FROM memories m
            LEFT JOIN memories_vec v ON v.rowid = m.rowid
            ORDER BY m.created_at ASC, m.rowid ASC
        """).fetchall()

        with target_conn:
            for row in rows:
                stats["scanned"] += 1

                embedding = row["embedding"]
                if embedding is None:
                    stats["missing_embedding"] += 1
                    continue

                dim = len(embedding) // 4
                if dim != config.EMBED_DIM:
                    raise ValueError(
                        f"embedding dim mismatch: source row dim={dim}, target expects {config.EMBED_DIM}"
                    )

                mem_id = row["id"] or str(uuid.uuid4())
                row_signature = _signature(row)
                existing_signature = existing.get(mem_id)
                if existing_signature is not None:
                    if existing_signature == row_signature:
                        stats["skipped"] += 1
                        continue
                    mem_id = str(uuid.uuid4())
                    stats["id_regenerated"] += 1

                cursor = target_conn.execute("""
                    INSERT INTO memories (
                        id, user_id, session_id, turn, item_index, kind, summary,
                        keywords, raw_q, raw_a, version, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    mem_id,
                    row["user_id"],
                    row["session_id"],
                    row["turn"],
                    row["item_index"],
                    row["kind"],
                    row["summary"],
                    row["keywords"],
                    row["raw_q"],
                    row["raw_a"],
                    row["version"],
                    row["created_at"],
                    row["updated_at"],
                ))
                target_conn.execute(
                    "INSERT INTO memories_vec (rowid, embedding) VALUES (?, ?)",
                    (cursor.lastrowid, embedding),
                )

                existing[mem_id] = row_signature
                stats["inserted"] += 1
    finally:
        target_conn.close()
        source_conn.close()

    return stats


def rewrite_user_id(db_path, new_user_id, old_user_id=None):
    resolved = _resolve_db_path(db_path)
    if not os.path.exists(resolved):
        raise FileNotFoundError(resolved)
    if not str(new_user_id).strip():
        raise ValueError("new_user_id is required")

    conn = sqlite_db.open_conn(resolved, ensure_schema=True)
    try:
        before_users = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM memories"
        ).fetchone()[0]
        before_rows = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

        sql = "UPDATE memories SET user_id = ?, updated_at = datetime('now')"
        params = [str(new_user_id).strip()]
        if old_user_id not in (None, ""):
            sql += " WHERE user_id = ?"
            params.append(str(old_user_id).strip())

        with conn:
            cursor = conn.execute(sql, params)

        after_users = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM memories"
        ).fetchone()[0]
    finally:
        conn.close()

    return {
        "db_path": resolved,
        "new_user_id": str(new_user_id).strip(),
        "old_user_id": None if old_user_id in (None, "") else str(old_user_id).strip(),
        "updated_rows": cursor.rowcount,
        "total_rows": before_rows,
        "distinct_user_ids_before": before_users,
        "distinct_user_ids_after": after_users,
    }


def _resolve_db_path(db_path):
    return os.path.abspath(os.path.expanduser(str(db_path)))


def _signature(row):
    return (
        row["user_id"],
        row["session_id"],
        int(row["turn"]),
        int(row["item_index"] or 0),
        row["kind"] or "general",
        row["summary"] or "",
        row["keywords"] or "[]",
        row["raw_q"] or "",
        row["raw_a"] or "",
        int(row["version"] or 1),
        row["created_at"] or "",
        row["updated_at"] or "",
    )

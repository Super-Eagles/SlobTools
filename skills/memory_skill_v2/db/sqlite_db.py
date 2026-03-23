import sqlite3
import os
import sqlite_vec
from .. import config

_conn = None

# Resolve SQLITE_PATH relative to the skill package directory,
# not the caller's working directory.
# e.g.  ./memory.db  →  C:\Users\slob\.gemini\...\memory_skill_v2\memory.db
_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH   = config.SQLITE_PATH if os.path.isabs(config.SQLITE_PATH) \
             else os.path.join(_SKILL_DIR, config.SQLITE_PATH)


def get_conn():
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row

        _conn.enable_load_extension(True)
        sqlite_vec.load(_conn)
        _conn.enable_load_extension(False)

        _create_schema(_conn)
        print(f"[memory-skill] DB path: {_DB_PATH}")
    return _conn


def _create_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            session_id  TEXT NOT NULL,
            turn        INTEGER NOT NULL,
            summary     TEXT NOT NULL,
            keywords    TEXT DEFAULT '[]',
            raw_q       TEXT,
            raw_a       TEXT,
            version     INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_user    ON memories(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_session ON memories(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_time    ON memories(created_at DESC)")

    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(summary, keywords, content='memories', content_rowid='rowid')
    """)

    conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS fts_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, summary, keywords)
            VALUES (new.rowid, new.summary, new.keywords);
        END;

        CREATE TRIGGER IF NOT EXISTS fts_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, summary, keywords)
            VALUES ('delete', old.rowid, old.summary, old.keywords);
        END;

        CREATE TRIGGER IF NOT EXISTS fts_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, summary, keywords)
            VALUES ('delete', old.rowid, old.summary, old.keywords);
            INSERT INTO memories_fts(rowid, summary, keywords)
            VALUES (new.rowid, new.summary, new.keywords);
        END;
    """)

    conn.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec
            USING vec0(embedding float[{config.EMBED_DIM}])
    """)

    conn.commit()


def get_db_path():
    """Return the resolved absolute path to the database file."""
    return _DB_PATH


def close():
    global _conn
    if _conn:
        _conn.close()
        _conn = None

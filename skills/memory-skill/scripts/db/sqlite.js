const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const Database = require("better-sqlite3");
const { cosineDistance, deserializeVec, normalizeVector, serializeVec } = require("../utils/vec");

function nowIso() {
  return new Date().toISOString();
}

function buildFtsQuery(values) {
  const source = Array.isArray(values) ? values : [values];
  const tokens = new Set();

  for (const item of source) {
    const cleaned = String(item || "")
      .replace(/[^\p{L}\p{N}_\u4e00-\u9fff]+/gu, " ")
      .trim();
    for (const token of cleaned.split(/\s+/)) {
      if (token.length > 1) {
        tokens.add(token);
      }
    }
  }

  return Array.from(tokens).join(" OR ");
}

function discoverSqliteVecPath(config) {
  if (config.sqliteVecMode === "off") {
    return "";
  }

  if (config.sqliteVecPath) {
    return config.sqliteVecPath;
  }

  try {
    return execFileSync(
      config.pythonBin,
      [...(config.pythonArgs || ["-3"]), "-c", "import sqlite_vec; print(sqlite_vec.loadable_path())"],
      {
        encoding: "utf8"
      }
    ).trim();
  } catch (error) {
    if (config.sqliteVecMode === "on") {
      throw new Error(`Failed to discover sqlite-vec extension: ${error.message}`);
    }
    return "";
  }
}

class SQLiteStore {
  constructor(config) {
    const dir = path.dirname(config.sqlitePath);
    fs.mkdirSync(dir, { recursive: true });

    this.config = config;
    this.db = new Database(config.sqlitePath);
    this.db.pragma("journal_mode = WAL");
    this.db.pragma("foreign_keys = ON");

    this.sqliteVecPath = "";
    this.sqliteVecAvailable = false;
    this.sqliteVecVersion = null;

    this.initialize();
  }

  initialize() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS users (
        id         TEXT PRIMARY KEY,
        name       TEXT,
        config     TEXT DEFAULT '{}',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS sessions (
        id          TEXT PRIMARY KEY,
        user_id     TEXT NOT NULL REFERENCES users(id),
        status      TEXT DEFAULT 'active',
        turn_count  INTEGER DEFAULT 0,
        started_at  TEXT DEFAULT CURRENT_TIMESTAMP,
        ended_at    TEXT
      );

      CREATE TABLE IF NOT EXISTS memories (
        id         TEXT PRIMARY KEY,
        user_id    TEXT NOT NULL REFERENCES users(id),
        session_id TEXT NOT NULL REFERENCES sessions(id),
        turn       INTEGER NOT NULL,
        summary    TEXT NOT NULL,
        keywords   TEXT DEFAULT '[]',
        embedding  BLOB,
        raw_q      TEXT,
        raw_a      TEXT,
        version    INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
      );

      CREATE INDEX IF NOT EXISTS idx_mem_user    ON memories(user_id);
      CREATE INDEX IF NOT EXISTS idx_mem_session ON memories(session_id);
      CREATE INDEX IF NOT EXISTS idx_mem_time    ON memories(created_at DESC);

      CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
      USING fts5(summary, keywords, content='memories', content_rowid='rowid');

      CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
        INSERT INTO memories_fts(rowid, summary, keywords)
        VALUES (new.rowid, new.summary, new.keywords);
      END;

      CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
        INSERT INTO memories_fts(memories_fts, rowid, summary, keywords)
        VALUES('delete', old.rowid, old.summary, old.keywords);
      END;

      CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
        INSERT INTO memories_fts(memories_fts, rowid, summary, keywords)
        VALUES('delete', old.rowid, old.summary, old.keywords);
        INSERT INTO memories_fts(rowid, summary, keywords)
        VALUES (new.rowid, new.summary, new.keywords);
      END;
    `);

    this.sqliteVecPath = discoverSqliteVecPath(this.config);
    if (this.sqliteVecPath) {
      this.enableSqliteVec();
    }
  }

  enableSqliteVec() {
    try {
      this.db.loadExtension(this.sqliteVecPath);
      this.sqliteVecVersion = this.db.prepare("SELECT vec_version() AS version").get()?.version || null;
      this.db.exec(`
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec
        USING vec0(embedding float[${this.config.embeddingDimensions}])
      `);
      this.sqliteVecAvailable = true;
      this.rebuildVectorTable();
    } catch (error) {
      this.sqliteVecAvailable = false;
      this.sqliteVecVersion = null;

      if (this.config.sqliteVecMode === "on") {
        throw new Error(`Failed to enable sqlite-vec: ${error.message}`);
      }
    }
  }

  rebuildVectorTable() {
    if (!this.sqliteVecAvailable) {
      return;
    }

    const rows = this.db
      .prepare(`
        SELECT rowid, embedding
        FROM memories
        WHERE embedding IS NOT NULL
      `)
      .all();

    const clear = this.db.prepare("DELETE FROM memories_vec");
    const insert = this.db.prepare(
      "INSERT INTO memories_vec (rowid, embedding) VALUES (CAST(? AS INTEGER), ?)"
    );
    const transaction = this.db.transaction((items) => {
      clear.run();
      for (const row of items) {
        const rowId = Number(row.rowid);
        const embedding = serializeVec(
          deserializeVec(row.embedding),
          this.config.embeddingDimensions
        );
        if (Number.isInteger(rowId) && embedding) {
          insert.run(rowId, embedding);
        }
      }
    });

    transaction(rows);
  }

  buildMemoryPayload(memory, options = {}) {
    const now = nowIso();
    return {
      ...memory,
      id: memory.id,
      user_id: memory.user_id,
      session_id: memory.session_id,
      turn: memory.turn,
      summary: memory.summary,
      keywords: JSON.stringify(memory.keywords || []),
      embedding: serializeVec(memory.embedding || [], this.config.embeddingDimensions),
      raw_q: memory.raw_q || null,
      raw_a: memory.raw_a || null,
      version: memory.version || 1,
      created_at: options.keepCreatedAt ? memory.created_at || now : memory.created_at || now,
      updated_at: options.updatedAt || memory.updated_at || now
    };
  }

  upsertVectorRow(rowId, embedding) {
    const numericRowId = Number(rowId);
    if (!this.sqliteVecAvailable || !Number.isInteger(numericRowId)) {
      return;
    }

    this.db.prepare("DELETE FROM memories_vec WHERE rowid = ?").run(numericRowId);
    if (embedding) {
      this.db
        .prepare("INSERT INTO memories_vec (rowid, embedding) VALUES (CAST(? AS INTEGER), ?)")
        .run(numericRowId, embedding);
    }
  }

  deleteVectorRow(rowId) {
    const numericRowId = Number(rowId);
    if (!this.sqliteVecAvailable || !Number.isInteger(numericRowId)) {
      return;
    }

    this.db.prepare("DELETE FROM memories_vec WHERE rowid = ?").run(numericRowId);
  }

  ensureUser(userId, name = null) {
    const stmt = this.db.prepare(`
      INSERT INTO users (id, name)
      VALUES (@id, @name)
      ON CONFLICT(id) DO UPDATE SET name = COALESCE(excluded.name, users.name)
    `);
    stmt.run({
      id: userId,
      name
    });
  }

  upsertSession(sessionId, userId, status = "active", turnCount = 0) {
    const stmt = this.db.prepare(`
      INSERT INTO sessions (id, user_id, status, turn_count)
      VALUES (@id, @user_id, @status, @turn_count)
      ON CONFLICT(id) DO UPDATE SET
        status = excluded.status,
        turn_count = MAX(sessions.turn_count, excluded.turn_count)
    `);
    stmt.run({
      id: sessionId,
      user_id: userId,
      status,
      turn_count: turnCount
    });
  }

  completeSession(sessionId) {
    this.db
      .prepare(`
        UPDATE sessions
        SET status = 'ended',
            ended_at = @ended_at
        WHERE id = @id
      `)
      .run({
        id: sessionId,
        ended_at: nowIso()
      });
  }

  insertMemory(memory) {
    const payload = this.buildMemoryPayload(memory, {
      keepCreatedAt: true
    });
    const info = this.db
      .prepare(`
        INSERT INTO memories (
          id, user_id, session_id, turn, summary, keywords, embedding,
          raw_q, raw_a, version, created_at, updated_at
        ) VALUES (
          @id, @user_id, @session_id, @turn, @summary, @keywords, @embedding,
          @raw_q, @raw_a, @version, @created_at, @updated_at
        )
      `)
      .run(payload);

    this.upsertVectorRow(info.lastInsertRowid, payload.embedding);
  }

  updateMemory(memoryId, nextMemory) {
    const row = this.db.prepare("SELECT rowid FROM memories WHERE id = ?").get(memoryId);
    const payload = {
      id: memoryId,
      summary: nextMemory.summary,
      keywords: JSON.stringify(nextMemory.keywords || []),
      embedding: serializeVec(nextMemory.embedding || [], this.config.embeddingDimensions),
      raw_q: nextMemory.raw_q || null,
      raw_a: nextMemory.raw_a || null,
      version: nextMemory.version,
      updated_at: nowIso()
    };

    this.db
      .prepare(`
        UPDATE memories
        SET summary = @summary,
            keywords = @keywords,
            embedding = @embedding,
            raw_q = @raw_q,
            raw_a = @raw_a,
            version = @version,
            updated_at = @updated_at
        WHERE id = @id
      `)
      .run(payload);

    this.upsertVectorRow(row?.rowid, payload.embedding);
  }

  deleteMemory(memoryId) {
    const row = this.db.prepare("SELECT rowid FROM memories WHERE id = ?").get(memoryId);
    this.db.prepare("DELETE FROM memories WHERE id = ?").run(memoryId);
    this.deleteVectorRow(row?.rowid);
  }

  getMemory(memoryId) {
    const row = this.db.prepare("SELECT * FROM memories WHERE id = ?").get(memoryId);
    return row ? this.mapRow(row) : null;
  }

  listMemories(filters = {}) {
    const clauses = [];
    const params = {};

    if (filters.userId) {
      clauses.push("user_id = @user_id");
      params.user_id = filters.userId;
    }

    if (filters.sessionId) {
      clauses.push("session_id = @session_id");
      params.session_id = filters.sessionId;
    }

    const where = clauses.length > 0 ? `WHERE ${clauses.join(" AND ")}` : "";
    return this.db
      .prepare(`
        SELECT *
        FROM memories
        ${where}
        ORDER BY updated_at DESC, created_at DESC
      `)
      .all(params)
      .map((row) => this.mapRow(row));
  }

  updateMemoryEmbedding(memoryId, embedding) {
    const row = this.db.prepare("SELECT rowid FROM memories WHERE id = ?").get(memoryId);
    const payload = serializeVec(embedding || [], this.config.embeddingDimensions);

    this.db
      .prepare(`
        UPDATE memories
        SET embedding = @embedding,
            updated_at = @updated_at
        WHERE id = @id
      `)
      .run({
        id: memoryId,
        embedding: payload,
        updated_at: nowIso()
      });

    this.upsertVectorRow(row?.rowid, payload);
  }

  searchByKeywords(userId, keywords, limit = 5) {
    const query = buildFtsQuery(keywords);
    if (!query) {
      return [];
    }

    try {
      const rows = this.db
        .prepare(`
          SELECT m.*, bm25(memories_fts) AS rank
          FROM memories_fts
          JOIN memories m ON memories_fts.rowid = m.rowid
          WHERE memories_fts MATCH @query
            AND m.user_id = @user_id
          ORDER BY rank
          LIMIT @limit
        `)
        .all({
          query,
          user_id: userId,
          limit
        });

      return rows.map((row) => ({
        ...this.mapRow(row),
        score: 0.5,
        rank: row.rank ?? 0.5,
        source: "fts"
      }));
    } catch (error) {
      return [];
    }
  }

  searchByVector(userId, queryVec, threshold = 0.75, limit = 5) {
    const normalizedQuery = normalizeVector(queryVec, this.config.embeddingDimensions);
    if (normalizedQuery.length === 0) {
      return [];
    }

    if (this.sqliteVecAvailable) {
      const indexedHits = this.searchByVectorIndexed(userId, normalizedQuery, threshold, limit);
      if (indexedHits.length > 0) {
        return indexedHits;
      }
    }

    return this.searchByVectorFallback(userId, normalizedQuery, threshold, limit);
  }

  searchByVectorIndexed(userId, queryVec, threshold = 0.75, limit = 5) {
    try {
      const maxDistance = 1 - threshold;
      const rows = this.db
        .prepare(`
          SELECT m.*, v.distance AS distance
          FROM memories_vec v
          JOIN memories m ON m.rowid = v.rowid
          WHERE v.embedding MATCH @embedding
            AND m.user_id = @user_id
          ORDER BY distance ASC
          LIMIT @limit
        `)
        .all({
          embedding: serializeVec(queryVec, this.config.embeddingDimensions),
          user_id: userId,
          limit: Math.max(limit * 2, limit)
        });

      return rows
        .map((row) => ({
          ...this.mapRow(row),
          score: row.distance ?? 1,
          source: "vec"
        }))
        .filter((item) => item.score <= maxDistance)
        .slice(0, limit);
    } catch (error) {
      return [];
    }
  }

  searchByVectorFallback(userId, queryVec, threshold = 0.75, limit = 5) {
    const candidates = this.db
      .prepare(`
        SELECT *
        FROM memories
        WHERE user_id = @user_id
        ORDER BY updated_at DESC
        LIMIT @limit
      `)
      .all({
        user_id: userId,
        limit: this.config.memoryCandidateLimit
      })
      .map((row) => this.mapRow(row));

    return candidates
      .map((item) => ({
        ...item,
        score: cosineDistance(
          queryVec,
          normalizeVector(item.embedding || [], this.config.embeddingDimensions)
        ),
        source: "vec-fallback"
      }))
      .filter((item) => item.score <= 1 - threshold)
      .sort((a, b) => a.score - b.score)
      .slice(0, limit);
  }

  findSimilar(userId, embedding, threshold = 0.85) {
    const [top] = this.searchByVector(userId, embedding, threshold, 1);
    return top || null;
  }

  mapRow(row) {
    return {
      ...row,
      keywords: safeJsonArray(row.keywords),
      embedding: deserializeVec(row.embedding)
    };
  }

  close() {
    this.db.close();
  }
}

function safeJsonArray(value) {
  try {
    const parsed = JSON.parse(value || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    return [];
  }
}

module.exports = {
  SQLiteStore
};

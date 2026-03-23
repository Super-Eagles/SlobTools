const path = require("path");

function toInt(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function toFloat(value, fallback) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function toList(value, fallback = []) {
  const source = String(value || "").trim();
  if (!source) {
    return fallback;
  }

  return source
    .split(/\s+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function createConfig(overrides = {}) {
  const cwd = overrides.cwd || process.cwd();
  const embedProvider = process.env.EMBED_PROVIDER || "sentence-transformers";
  const defaultEmbeddingDimensions =
    embedProvider === "openai" ? 1536 : embedProvider === "ollama" ? 768 : 384;
  const summaryProvider =
    process.env.SUMMARY_PROVIDER ||
    (embedProvider === "openai" || embedProvider === "ollama" ? embedProvider : "fallback");

  return {
    cwd,
    redisUrl: process.env.REDIS_URL || "redis://localhost:6379",
    sqlitePath:
      overrides.sqlitePath ||
      process.env.SQLITE_PATH ||
      path.join(cwd, "data", "memory.db"),
    embedProvider,
    summaryProvider,
    embeddingDimensions: toInt(process.env.EMBEDDING_DIMENSIONS, defaultEmbeddingDimensions),
    openaiApiKey: process.env.OPENAI_API_KEY || "",
    openaiEmbeddingModel:
      process.env.OPENAI_EMBEDDING_MODEL || "text-embedding-3-small",
    openaiSummaryModel:
      process.env.OPENAI_SUMMARY_MODEL || "gpt-4o-mini",
    ollamaUrl: process.env.OLLAMA_URL || "http://localhost:11434",
    ollamaEmbedModel:
      process.env.OLLAMA_EMBED_MODEL || "nomic-embed-text",
    ollamaSummaryModel:
      process.env.OLLAMA_SUMMARY_MODEL || "qwen2.5:7b",
    sentenceTransformerModel:
      process.env.ST_EMBED_MODEL || "paraphrase-multilingual-MiniLM-L12-v2",
    sentenceTransformerBatchSize: toInt(process.env.ST_BATCH_SIZE, 32),
    pythonBin: process.env.ST_PYTHON_BIN || process.env.PYTHON_BIN || "py",
    pythonArgs: toList(process.env.ST_PYTHON_ARGS, ["-3"]),
    sentenceTransformerScriptPath:
      process.env.ST_EMBED_SCRIPT || path.join(cwd, "utils", "embed_sentence_transformers.py"),
    memoryTopK: toInt(process.env.MEMORY_TOP_K, 5),
    memorySimThreshold: toFloat(process.env.MEMORY_SIM_THRESHOLD, 0.75),
    memoryCandidateLimit: toInt(process.env.MEMORY_CANDIDATE_LIMIT, 200),
    sessionTtlSeconds: toInt(process.env.SESSION_TTL, 86400),
    sqliteVecMode: String(process.env.SQLITE_VEC_MODE || "auto").trim().toLowerCase(),
    sqliteVecPath: process.env.SQLITE_VEC_PATH || "",
    ...overrides
  };
}

module.exports = {
  createConfig
};

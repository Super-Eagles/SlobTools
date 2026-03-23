const { v4: uuidv4 } = require("uuid");
const { nextTurn, putHotMemory, setSessionMeta } = require("../db/redis");
const { embed } = require("../utils/embedding");
const { summarizeTurn } = require("./summarize");

async function writeMemory({
  redis,
  sqlite,
  config,
  userId,
  sessionId,
  question,
  answer,
  userName = null
}) {
  const cleanQuestion = String(question || "").trim();
  const cleanAnswer = String(answer || "").trim();

  sqlite.ensureUser(userId, userName);

  const metaTtl = config.sessionTtlSeconds * 2;
  const turn = await nextTurn(redis, sessionId, metaTtl);
  sqlite.upsertSession(sessionId, userId, "active", turn);

  const summaryResult = await summarizeTurn(cleanQuestion, cleanAnswer, config);
  const embedding = await embed(summaryResult.summary, config);
  const createdAt = new Date().toISOString();

  const memory = {
    id: uuidv4(),
    user_id: userId,
    session_id: sessionId,
    turn,
    summary: summaryResult.summary,
    keywords: summaryResult.keywords,
    embedding,
    raw_q: cleanQuestion,
    raw_a: cleanAnswer,
    created_at: createdAt,
    updated_at: createdAt,
    version: 1
  };

  await putHotMemory(redis, memory, config.sessionTtlSeconds);
  await setSessionMeta(
    redis,
    sessionId,
    {
      user_id: userId,
      last_turn: turn,
      updated_at: createdAt
    },
    metaTtl
  );

  return memory;
}

module.exports = {
  writeMemory
};

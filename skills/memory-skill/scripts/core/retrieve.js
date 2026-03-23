const { getHotMemories } = require("../db/redis");
const { embed } = require("../utils/embedding");
const { dedupById } = require("../utils/vec");
const { extractKeywords } = require("./summarize");

async function retrieveRelevantMemories({
  redis,
  sqlite,
  config,
  userId,
  sessionId,
  question
}) {
  const hotMemories = await getHotMemories(redis, userId, sessionId);
  const queryText = String(question || "").trim();

  if (!queryText) {
    return {
      hotMemories,
      coldMemories: [],
      queryVec: [],
      keywords: []
    };
  }

  const [queryVec, keywords] = await Promise.all([
    embed(queryText, config),
    Promise.resolve(extractKeywords(queryText, 6))
  ]);

  const [vectorHits, keywordHits] = await Promise.all([
    Promise.resolve(
      sqlite.searchByVector(
        userId,
        queryVec,
        config.memorySimThreshold,
        config.memoryTopK + 3
      )
    ),
    Promise.resolve(sqlite.searchByKeywords(userId, keywords, config.memoryTopK + 3))
  ]);

  const coldMemories = dedupById([...vectorHits, ...keywordHits])
    .sort((a, b) => (a.score ?? 0.5) - (b.score ?? 0.5))
    .slice(0, config.memoryTopK);

  return {
    hotMemories,
    coldMemories,
    queryVec,
    keywords
  };
}

module.exports = {
  retrieveRelevantMemories
};

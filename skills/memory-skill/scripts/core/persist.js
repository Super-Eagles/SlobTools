const { deleteHotMemories, getHotMemories } = require("../db/redis");
const { detectConflict, mergeMemory } = require("./summarize");

async function persistSessionMemories({
  redis,
  sqlite,
  config,
  userId,
  sessionId
}) {
  const memories = await getHotMemories(redis, userId, sessionId);
  if (memories.length === 0) {
    sqlite.completeSession(sessionId);
    return {
      inserted: 0,
      updated: 0,
      replaced: 0,
      deletedHot: 0
    };
  }

  let inserted = 0;
  let updated = 0;
  let replaced = 0;

  for (const memory of memories) {
    const similar = sqlite.findSimilar(userId, memory.embedding, 0.85);
    if (!similar) {
      sqlite.insertMemory(memory);
      inserted += 1;
      continue;
    }

    const conflict = await detectConflict(memory.summary, similar.summary, config);
    if (conflict.conflict) {
      sqlite.deleteMemory(similar.id);
      sqlite.insertMemory(memory);
      replaced += 1;
      continue;
    }

    const merged = await mergeMemory(similar, memory, config);
    sqlite.updateMemory(similar.id, merged);
    updated += 1;
  }

  const deletedHot = await deleteHotMemories(redis, userId, sessionId);
  sqlite.completeSession(sessionId);

  return {
    inserted,
    updated,
    replaced,
    deletedHot
  };
}

module.exports = {
  persistSessionMemories
};

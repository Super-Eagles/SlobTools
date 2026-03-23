const Redis = require("ioredis");

function hotMemoryKey(userId, sessionId, turn) {
  return `mem:hot:${userId}:${sessionId}:${turn}`;
}

function sessionMetaKey(sessionId) {
  return `session:meta:${sessionId}`;
}

function sessionTurnsKey(sessionId) {
  return `session:turns:${sessionId}`;
}

async function scanKeys(redis, pattern) {
  const keys = [];
  let cursor = "0";

  do {
    const [nextCursor, batch] = await redis.scan(
      cursor,
      "MATCH",
      pattern,
      "COUNT",
      200
    );
    cursor = nextCursor;
    keys.push(...batch);
  } while (cursor !== "0");

  return keys;
}

async function createRedisClient(config) {
  const redis = new Redis(config.redisUrl, {
    lazyConnect: true,
    maxRetriesPerRequest: 1
  });

  await redis.connect();
  return redis;
}

async function putHotMemory(redis, memory, ttlSeconds) {
  const key = hotMemoryKey(memory.user_id, memory.session_id, memory.turn);
  await redis.set(key, JSON.stringify(memory), "EX", ttlSeconds);
  return key;
}

async function getHotMemories(redis, userId, sessionId) {
  const keys = await scanKeys(redis, `mem:hot:${userId}:${sessionId}:*`);
  if (keys.length === 0) {
    return [];
  }

  const list = await Promise.all(keys.map((key) => redis.get(key)));
  return list
    .filter(Boolean)
    .map((value) => JSON.parse(value))
    .sort((a, b) => a.turn - b.turn);
}

async function deleteHotMemories(redis, userId, sessionId) {
  const keys = await scanKeys(redis, `mem:hot:${userId}:${sessionId}:*`);
  if (keys.length > 0) {
    await redis.del(...keys);
  }
  await redis.del(sessionTurnsKey(sessionId), sessionMetaKey(sessionId));
  return keys.length;
}

async function nextTurn(redis, sessionId, ttlSeconds) {
  const key = sessionTurnsKey(sessionId);
  const turn = await redis.incr(key);
  if (ttlSeconds > 0) {
    await redis.expire(key, ttlSeconds);
  }
  return turn;
}

async function setSessionMeta(redis, sessionId, payload, ttlSeconds) {
  await redis.set(
    sessionMetaKey(sessionId),
    JSON.stringify(payload || {}),
    "EX",
    ttlSeconds
  );
}

async function getSessionMeta(redis, sessionId) {
  const payload = await redis.get(sessionMetaKey(sessionId));
  return payload ? JSON.parse(payload) : null;
}

async function closeRedis(redis) {
  if (redis) {
    await redis.quit();
  }
}

module.exports = {
  createRedisClient,
  hotMemoryKey,
  sessionMetaKey,
  sessionTurnsKey,
  putHotMemory,
  getHotMemories,
  deleteHotMemories,
  nextTurn,
  setSessionMeta,
  getSessionMeta,
  closeRedis
};

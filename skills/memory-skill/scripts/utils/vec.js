function normalizeVector(vec, dimensions = 0) {
  if (!Array.isArray(vec) || vec.length === 0) {
    return [];
  }

  const normalized = vec
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value));

  if (dimensions <= 0) {
    return normalized;
  }

  if (normalized.length === dimensions) {
    return normalized;
  }

  if (normalized.length > dimensions) {
    return normalized.slice(0, dimensions);
  }

  return normalized.concat(new Array(dimensions - normalized.length).fill(0));
}

function serializeVec(vec, dimensions = 0) {
  const normalized = normalizeVector(vec, dimensions);
  if (normalized.length === 0) {
    return null;
  }

  const array = Float32Array.from(normalized);
  return Buffer.from(array.buffer);
}

function deserializeVec(blob) {
  if (!blob) {
    return [];
  }

  const view = Buffer.isBuffer(blob) ? blob : Buffer.from(blob);
  if (view.length % 4 !== 0) {
    return [];
  }

  const floatArray = new Float32Array(
    view.buffer,
    view.byteOffset,
    view.length / 4
  );
  return Array.from(floatArray);
}

function cosineSimilarity(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length === 0 || b.length === 0) {
    return 0;
  }

  const length = Math.min(a.length, b.length);
  let dot = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < length; i += 1) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  if (normA === 0 || normB === 0) {
    return 0;
  }

  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

function cosineDistance(a, b) {
  return 1 - cosineSimilarity(a, b);
}

function mergeKeywords(...lists) {
  const merged = new Set();

  for (const list of lists) {
    for (const item of list || []) {
      const value = String(item || "").trim();
      if (value) {
        merged.add(value);
      }
    }
  }

  return Array.from(merged);
}

function dedupById(items) {
  const seen = new Map();

  for (const item of items || []) {
    if (!item || !item.id) {
      continue;
    }

    const existing = seen.get(item.id);
    if (!existing || (item.score ?? Infinity) < (existing.score ?? Infinity)) {
      seen.set(item.id, item);
    }
  }

  return Array.from(seen.values());
}

module.exports = {
  normalizeVector,
  serializeVec,
  deserializeVec,
  cosineSimilarity,
  cosineDistance,
  mergeKeywords,
  dedupById
};

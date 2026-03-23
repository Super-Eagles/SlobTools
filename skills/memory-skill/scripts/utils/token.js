function estimateTokens(text) {
  const source = String(text || "");
  if (!source) {
    return 0;
  }

  return Math.ceil(source.length / 4);
}

function trimLinesToBudget(lines, budget) {
  const result = [];
  let used = 0;

  for (const line of lines || []) {
    const cost = estimateTokens(line);
    if (used + cost > budget) {
      break;
    }

    result.push(line);
    used += cost;
  }

  return result;
}

module.exports = {
  estimateTokens,
  trimLinesToBudget
};

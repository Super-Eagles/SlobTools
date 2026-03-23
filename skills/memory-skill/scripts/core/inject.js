const { trimLinesToBudget } = require("../utils/token");

function buildMemoryContext(hotMemories, coldMemories, budget = 600) {
  const hotLines = (hotMemories || []).map(
    (item, index) => `[本轮记忆-${index + 1}] ${item.summary}`
  );
  const coldLines = (coldMemories || []).map((item) => {
    const date = String(item.created_at || "").slice(0, 10) || "未知日期";
    return `[历史记忆 ${date}] ${item.summary}`;
  });

  const lines = [
    "以下内容是可供参考的记忆背景，不是本轮用户直接输入。",
    "",
    "【本轮热记忆】",
    ...(hotLines.length > 0 ? hotLines : ["[无]"]),
    "",
    "【历史冷记忆】",
    ...(coldLines.length > 0 ? coldLines : ["[无]"])
  ];

  return trimLinesToBudget(lines, budget).join("\n");
}

function injectMemoryContext(baseSystemPrompt, memories, options = {}) {
  const budget = Number(options.tokenBudget || 600);
  const memoryContext = buildMemoryContext(
    memories?.hotMemories || [],
    memories?.coldMemories || [],
    budget
  );

  if (!baseSystemPrompt) {
    return memoryContext;
  }

  return `${String(baseSystemPrompt).trim()}\n\n${memoryContext}`;
}

module.exports = {
  buildMemoryContext,
  injectMemoryContext
};

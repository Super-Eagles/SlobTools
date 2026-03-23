const OpenAI = require("openai");
const { mergeKeywords } = require("../utils/vec");

function collectTerms(text) {
  const source = String(text || "");
  const terms = [];

  const hanMatches = source.match(/[\u4e00-\u9fff]{2,8}/g) || [];
  terms.push(...hanMatches);

  const latinMatches = source.match(/[A-Za-z][A-Za-z0-9._+-]{1,31}/g) || [];
  terms.push(...latinMatches.map((item) => item.toLowerCase()));

  return terms;
}

function extractKeywords(text, limit = 6) {
  const counts = new Map();

  for (const term of collectTerms(text)) {
    const normalized = String(term || "").trim();
    if (!normalized || normalized.length < 2) {
      continue;
    }
    counts.set(normalized, (counts.get(normalized) || 0) + 1);
  }

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || b[0].length - a[0].length)
    .slice(0, limit)
    .map(([term]) => term);
}

function fallbackSummary(question, answer) {
  const q = String(question || "").trim();
  const a = String(answer || "").trim();
  const merged = [q, a].filter(Boolean).join(" | ");
  return merged.slice(0, 120) || "本轮对话涉及新的用户偏好或任务决策。";
}

function safeJsonObject(text) {
  const source = String(text || "").trim();
  if (!source) {
    return null;
  }

  const first = source.indexOf("{");
  const last = source.lastIndexOf("}");
  if (first === -1 || last === -1 || last <= first) {
    return null;
  }

  try {
    return JSON.parse(source.slice(first, last + 1));
  } catch (error) {
    return null;
  }
}

async function callOpenAIJson(prompt, config) {
  if (!config.openaiApiKey) {
    return null;
  }

  const client = new OpenAI({
    apiKey: config.openaiApiKey
  });

  const response = await client.chat.completions.create({
    model: config.openaiSummaryModel,
    temperature: 0.1,
    messages: [
      {
        role: "system",
        content: "你是一个只输出 JSON 的记忆处理助手。不要输出代码块，不要输出解释。"
      },
      {
        role: "user",
        content: prompt
      }
    ]
  });

  return safeJsonObject(response.choices?.[0]?.message?.content || "");
}

async function callOllamaJson(prompt, config) {
  const response = await fetch(`${config.ollamaUrl}/api/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: config.ollamaSummaryModel,
      prompt,
      stream: false,
      format: "json"
    })
  });

  if (!response.ok) {
    throw new Error(`Ollama summary failed: ${response.status}`);
  }

  const payload = await response.json();
  return safeJsonObject(payload.response || "");
}

async function callJsonModel(prompt, config) {
  switch (config.summaryProvider) {
    case "openai":
      return callOpenAIJson(prompt, config);
    case "ollama":
      return callOllamaJson(prompt, config);
    case "fallback":
    default:
      return null;
  }
}

function normalizeSummaryResult(result, question, answer) {
  const summary = String(result?.summary || "").trim() || fallbackSummary(question, answer);
  const keywords = mergeKeywords(
    Array.isArray(result?.keywords) ? result.keywords : [],
    extractKeywords(`${question}\n${answer}`, 6)
  ).slice(0, 8);

  return {
    summary,
    keywords
  };
}

async function summarizeTurn(question, answer, config) {
  const prompt = [
    "请将以下对话提炼为一句简洁的第三人称摘要（50字以内），并提取 3-6 个关键词。",
    "摘要需要包含：用户意图、偏好、关键决策。",
    '只回答 JSON，例如：{"summary":"...","keywords":["..."]}',
    "",
    `用户问题：${String(question || "").trim()}`,
    `助手回答：${String(answer || "").trim()}`
  ].join("\n");

  try {
    const result = await callJsonModel(prompt, config);
    return normalizeSummaryResult(result, question, answer);
  } catch (error) {
    return normalizeSummaryResult(null, question, answer);
  }
}

function heuristicConflict(newSummary, existingSummary) {
  const left = String(newSummary || "");
  const right = String(existingSummary || "");

  if (!left || !right) {
    return {
      conflict: false,
      reason: "缺少可比较文本"
    };
  }

  const denyWords = ["不", "不是", "不再", "改成", "改为", "取消", "停止", "弃用"];
  const sameTerms = mergeKeywords(extractKeywords(left, 8), extractKeywords(right, 8));
  const denyLeft = denyWords.some((word) => left.includes(word));
  const denyRight = denyWords.some((word) => right.includes(word));

  if (sameTerms.length >= 2 && denyLeft !== denyRight) {
    return {
      conflict: true,
      reason: "同一主题出现正反向表述"
    };
  }

  return {
    conflict: false,
    reason: "未检测到明显冲突"
  };
}

async function detectConflict(newSummary, existingSummary, config) {
  const prompt = [
    `新记忆：${String(newSummary || "").trim()}`,
    `现有相关记忆：${String(existingSummary || "").trim()}`,
    "",
    "判断两条记忆是否矛盾（信息互相否定或已被新信息覆盖）。",
    '只回答 JSON：{"conflict": true/false, "reason": "原因"}'
  ].join("\n");

  try {
    const result = await callJsonModel(prompt, config);
    if (result && typeof result.conflict === "boolean") {
      return {
        conflict: result.conflict,
        reason: String(result.reason || "")
      };
    }
  } catch (error) {
    // Fall through to heuristic detection.
  }

  return heuristicConflict(newSummary, existingSummary);
}

async function mergeMemory(existingMemory, newMemory, config) {
  const prompt = [
    "请将下面两条相关记忆合并成一条更新后的摘要。",
    "要求保留最新事实、用户偏好和关键决策，去掉重复信息，控制在 60 字以内。",
    '只回答 JSON：{"summary":"...","keywords":["..."]}',
    "",
    `旧记忆：${String(existingMemory?.summary || "").trim()}`,
    `新记忆：${String(newMemory?.summary || "").trim()}`
  ].join("\n");

  let merged = null;
  try {
    merged = await callJsonModel(prompt, config);
  } catch (error) {
    merged = null;
  }

  const normalized = normalizeSummaryResult(
    merged,
    [existingMemory?.raw_q, newMemory?.raw_q].filter(Boolean).join("\n"),
    [existingMemory?.raw_a, newMemory?.raw_a].filter(Boolean).join("\n")
  );

  return {
    ...existingMemory,
    ...newMemory,
    summary: normalized.summary,
    keywords: mergeKeywords(existingMemory?.keywords, newMemory?.keywords, normalized.keywords),
    version: Number(existingMemory?.version || 1) + 1,
    raw_q: newMemory?.raw_q || existingMemory?.raw_q || "",
    raw_a: newMemory?.raw_a || existingMemory?.raw_a || ""
  };
}

module.exports = {
  extractKeywords,
  summarizeTurn,
  detectConflict,
  mergeMemory
};

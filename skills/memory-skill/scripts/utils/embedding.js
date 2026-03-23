const OpenAI = require("openai");
const { spawn } = require("child_process");
const fs = require("fs/promises");
const path = require("path");
const { normalizeVector } = require("./vec");

function fallbackEmbedding(text, dims = 384) {
  const source = String(text || "");
  const values = new Array(dims).fill(0);

  for (let i = 0; i < source.length; i += 1) {
    const code = source.charCodeAt(i);
    values[i % dims] += (code % 97) / 97;
  }

  return normalizeVector(values, dims);
}

function runPythonEmbeddingProcess(config, extraArgs) {
  return new Promise((resolve, reject) => {
    const args = [
      ...(config.pythonArgs || ["-3"]),
      config.sentenceTransformerScriptPath,
      "--model",
      config.sentenceTransformerModel,
      ...extraArgs
    ];
    const child = spawn(config.pythonBin, args, {
      stdio: ["pipe", "pipe", "pipe"]
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      reject(error);
    });
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || stdout.trim() || `Python exited with code ${code}`));
        return;
      }

      try {
        const parsed = JSON.parse(stdout);
        resolve(parsed);
      } catch (error) {
        reject(new Error(`Invalid embedding payload: ${stdout.trim() || error.message}`));
      }
    });
    child.stdin.end();
  });
}

async function withBatchFile(config, texts, fn) {
  const tmpDir = path.join(config.cwd || process.cwd(), "tmp");
  const filePath = path.join(tmpDir, `st-batch-${process.pid}-${Date.now()}.json`);

  await fs.mkdir(tmpDir, { recursive: true });
  await fs.writeFile(filePath, JSON.stringify(texts), "utf8");

  try {
    return await fn(filePath);
  } finally {
    await fs.rm(filePath, { force: true });
  }
}

async function embedWithOpenAI(text, config) {
  if (!config.openaiApiKey) {
    return fallbackEmbedding(text, config.embeddingDimensions);
  }

  const client = new OpenAI({
    apiKey: config.openaiApiKey
  });

  const response = await client.embeddings.create({
    model: config.openaiEmbeddingModel,
    input: text
  });

  return normalizeVector(response.data[0].embedding, config.embeddingDimensions);
}

async function embedWithOllama(text, config) {
  const response = await fetch(`${config.ollamaUrl}/api/embeddings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: config.ollamaEmbedModel,
      prompt: text
    })
  });

  if (!response.ok) {
    throw new Error(`Ollama embedding failed: ${response.status}`);
  }

  const payload = await response.json();
  return normalizeVector(payload.embedding, config.embeddingDimensions);
}

async function embedWithSentenceTransformers(text, config) {
  const encodedText = Buffer.from(text, "utf8").toString("base64");
  const vector = await runPythonEmbeddingProcess(config, ["--text-b64", encodedText]);
  return normalizeVector(vector, config.embeddingDimensions);
}

async function embedBatchWithSentenceTransformers(texts, config) {
  const items = (texts || []).map((item) => String(item || "").trim());
  if (items.length === 0) {
    return [];
  }

  return withBatchFile(config, items, async (filePath) => {
    const vectors = await runPythonEmbeddingProcess(config, [
      "--texts-file",
      filePath,
      "--batch-size",
      String(config.sentenceTransformerBatchSize || 32)
    ]);
    return (vectors || []).map((vector) => normalizeVector(vector, config.embeddingDimensions));
  });
}

async function embed(text, config) {
  const content = String(text || "").trim();
  if (!content) {
    return [];
  }

  switch (config.embedProvider) {
    case "openai":
      return embedWithOpenAI(content, config);
    case "ollama":
      return embedWithOllama(content, config);
    case "sentence-transformers":
    case "st":
      return embedWithSentenceTransformers(content, config);
    case "fallback":
    default:
      return fallbackEmbedding(content, config.embeddingDimensions);
  }
}

async function embedBatch(texts, config) {
  const items = (texts || []).map((item) => String(item || "").trim());
  if (items.length === 0) {
    return [];
  }

  switch (config.embedProvider) {
    case "sentence-transformers":
    case "st":
      return embedBatchWithSentenceTransformers(items, config);
    default:
      return Promise.all(items.map((item) => embed(item, config)));
  }
}

module.exports = {
  embed,
  embedBatch,
  fallbackEmbedding
};

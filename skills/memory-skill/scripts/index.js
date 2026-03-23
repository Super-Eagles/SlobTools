const { createConfig } = require("./utils/config");
const { createRedisClient, closeRedis } = require("./db/redis");
const { SQLiteStore } = require("./db/sqlite");
const { retrieveRelevantMemories } = require("./core/retrieve");
const { injectMemoryContext } = require("./core/inject");
const { writeMemory } = require("./core/write");
const { persistSessionMemories } = require("./core/persist");
const { embed, embedBatch } = require("./utils/embedding");
const {
  readSessionState,
  writeSessionState,
  clearSessionState,
  requireSessionState
} = require("./utils/session_state");

async function createRuntime(overrides = {}) {
  const config = createConfig(overrides);
  const sqlite = new SQLiteStore(config);
  const redis = await createRedisClient(config);

  return {
    config,
    redis,
    sqlite,
    async retrieve(params) {
      return retrieveRelevantMemories({
        redis,
        sqlite,
        config,
        ...params
      });
    },
    async buildPrompt(params) {
      const bundle = await retrieveRelevantMemories({
        redis,
        sqlite,
        config,
        userId: params.userId,
        sessionId: params.sessionId,
        question: params.question
      });

      const prompt = injectMemoryContext(params.baseSystemPrompt || "", bundle, {
        tokenBudget: params.tokenBudget
      });

      return {
        prompt,
        ...bundle
      };
    },
    async writeTurn(params) {
      return writeMemory({
        redis,
        sqlite,
        config,
        ...params
      });
    },
    async persistSession(params) {
      return persistSessionMemories({
        redis,
        sqlite,
        config,
        ...params
      });
    },
    async reembedMemories(params = {}) {
      const memories = sqlite.listMemories({
        userId: params.userId,
        sessionId: params.sessionId
      });

      let updated = 0;
      let failed = 0;
      const errors = [];

      const batchSize = Number(config.sentenceTransformerBatchSize || 32);
      for (let index = 0; index < memories.length; index += batchSize) {
        const chunk = memories.slice(index, index + batchSize);

        try {
          const vectors = await embedBatch(
            chunk.map((memory) => memory.summary),
            config
          );

          for (let i = 0; i < chunk.length; i += 1) {
            sqlite.updateMemoryEmbedding(chunk[i].id, vectors[i] || []);
            updated += 1;
          }
        } catch (batchError) {
          for (const memory of chunk) {
            try {
              const vector = await embed(memory.summary, config);
              sqlite.updateMemoryEmbedding(memory.id, vector);
              updated += 1;
            } catch (error) {
              failed += 1;
              errors.push({
                id: memory.id,
                message: error.message
              });
            }
          }
        }
      }

      return {
        scanned: memories.length,
        updated,
        failed,
        errors
      };
    },
    async startSession(params) {
      const now = new Date().toISOString();
      const sessionState = {
        userId: params.userId,
        sessionId: params.sessionId,
        userName: params.userName || null,
        baseSystemPrompt: params.baseSystemPrompt || "",
        tokenBudget: Number(params.tokenBudget || 600),
        startedAt: now,
        updatedAt: now
      };

      sqlite.ensureUser(params.userId, params.userName || null);
      sqlite.upsertSession(params.sessionId, params.userId, "active", 0);
      writeSessionState(config, sessionState);

      return {
        mode: "session-started",
        session: sessionState
      };
    },
    getSessionState() {
      return readSessionState(config);
    },
    async buildPromptForActiveSession(params) {
      const state = requireSessionState(config);
      const bundle = await retrieveRelevantMemories({
        redis,
        sqlite,
        config,
        userId: state.userId,
        sessionId: state.sessionId,
        question: params.question
      });

      const prompt = injectMemoryContext(
        params.baseSystemPrompt ?? state.baseSystemPrompt ?? "",
        bundle,
        {
          tokenBudget: Number(params.tokenBudget || state.tokenBudget || 600)
        }
      );

      const nextState = {
        ...state,
        updatedAt: new Date().toISOString(),
        lastQuestion: String(params.question || "").trim()
      };
      writeSessionState(config, nextState);

      return {
        session: nextState,
        prompt,
        ...bundle
      };
    },
    async writeTurnForActiveSession(params) {
      const state = requireSessionState(config);
      const written = await writeMemory({
        redis,
        sqlite,
        config,
        userId: state.userId,
        sessionId: state.sessionId,
        userName: state.userName,
        question: params.question,
        answer: params.answer
      });

      const nextState = {
        ...state,
        updatedAt: new Date().toISOString(),
        lastQuestion: String(params.question || "").trim(),
        lastAnswer: String(params.answer || "").trim(),
        lastTurn: written.turn
      };
      writeSessionState(config, nextState);

      return {
        session: nextState,
        memory: written
      };
    },
    async endActiveSession(params = {}) {
      const state = requireSessionState(config);
      const result = await persistSessionMemories({
        redis,
        sqlite,
        config,
        userId: state.userId,
        sessionId: state.sessionId
      });

      if (!params.keepState) {
        clearSessionState(config);
      }

      return {
        mode: "session-ended",
        session: state,
        persist: result
      };
    },
    async close() {
      await closeRedis(redis);
      sqlite.close();
    }
  };
}

function parseArgs(argv) {
  const args = { _: [] };

  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    if (item.startsWith("--")) {
      const key = item.slice(2);
      const next = argv[i + 1];
      if (!next || next.startsWith("--")) {
        args[key] = true;
      } else {
        args[key] = next;
        i += 1;
      }
      continue;
    }

    args._.push(item);
  }

  return args;
}

function printUsage() {
  const usage = [
    "Usage:",
    "  node index.js session-start --user <uid> --session <sid> [--name <userName>] [--system <text>] [--budget <n>]",
    "  node index.js session-context --question <text> [--system <text>] [--budget <n>]",
    "  node index.js session-write --question <text> --answer <text>",
    "  node index.js session-end",
    "  node index.js session-show",
    "  node index.js retrieve --user <uid> --session <sid> --question <text>",
    "  node index.js prompt --user <uid> --session <sid> --question <text> [--system <text>] [--budget <n>]",
    "  node index.js write --user <uid> --session <sid> --question <text> --answer <text> [--name <userName>]",
    "  node index.js persist --user <uid> --session <sid>",
    "  node index.js reembed [--user <uid>] [--session <sid>]"
  ].join("\n");

  process.stdout.write(`${usage}\n`);
}

async function runCli() {
  const args = parseArgs(process.argv.slice(2));
  const [command] = args._;

  if (!command) {
    printUsage();
    process.exitCode = 1;
    return;
  }

  const runtime = await createRuntime({
    cwd: __dirname
  });

  try {
    let result = null;

    switch (command) {
      case "session-start":
        result = await runtime.startSession({
          userId: args.user,
          sessionId: args.session,
          userName: args.name || null,
          baseSystemPrompt: args.system || "",
          tokenBudget: Number(args.budget || 600)
        });
        break;
      case "session-context":
        result = await runtime.buildPromptForActiveSession({
          question: args.question,
          baseSystemPrompt: args.system,
          tokenBudget: Number(args.budget || 0)
        });
        break;
      case "session-write":
        result = await runtime.writeTurnForActiveSession({
          question: args.question,
          answer: args.answer
        });
        break;
      case "session-end":
        result = await runtime.endActiveSession();
        break;
      case "session-show":
        result = runtime.getSessionState();
        break;
      case "retrieve":
        result = await runtime.retrieve({
          userId: args.user,
          sessionId: args.session,
          question: args.question
        });
        break;
      case "prompt":
        result = await runtime.buildPrompt({
          userId: args.user,
          sessionId: args.session,
          question: args.question,
          baseSystemPrompt: args.system || "",
          tokenBudget: Number(args.budget || 600)
        });
        break;
      case "write":
        result = await runtime.writeTurn({
          userId: args.user,
          sessionId: args.session,
          question: args.question,
          answer: args.answer,
          userName: args.name || null
        });
        break;
      case "persist":
        result = await runtime.persistSession({
          userId: args.user,
          sessionId: args.session
        });
        break;
      case "reembed":
        result = await runtime.reembedMemories({
          userId: args.user || null,
          sessionId: args.session || null
        });
        break;
      default:
        throw new Error(`Unknown command: ${command}`);
    }

    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  } finally {
    await runtime.close();
  }
}

if (require.main === module) {
  runCli().catch((error) => {
    process.stderr.write(`${error.stack || error.message}\n`);
    process.exitCode = 1;
  });
}

module.exports = {
  createRuntime
};

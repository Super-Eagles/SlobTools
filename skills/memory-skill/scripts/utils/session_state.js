const fs = require("fs");
const path = require("path");

function getStateDir(config) {
  const cwd = config?.cwd || process.cwd();
  return path.join(cwd, "data");
}

function getStatePath(config) {
  return path.join(getStateDir(config), "active-session.json");
}

function ensureStateDir(config) {
  fs.mkdirSync(getStateDir(config), { recursive: true });
}

function readSessionState(config) {
  const file = getStatePath(config);
  if (!fs.existsSync(file)) {
    return null;
  }

  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    return null;
  }
}

function writeSessionState(config, payload) {
  ensureStateDir(config);
  fs.writeFileSync(getStatePath(config), JSON.stringify(payload, null, 2), "utf8");
}

function clearSessionState(config) {
  const file = getStatePath(config);
  if (fs.existsSync(file)) {
    fs.unlinkSync(file);
  }
}

function requireSessionState(config) {
  const state = readSessionState(config);
  if (!state || !state.userId || !state.sessionId) {
    throw new Error("No active memory session. Run `session-start` first.");
  }
  return state;
}

module.exports = {
  getStatePath,
  readSessionState,
  writeSessionState,
  clearSessionState,
  requireSessionState
};

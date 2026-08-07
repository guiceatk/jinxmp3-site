const fs = require('fs');
const path = require('path');

const LOG_DIR = path.join(__dirname, '..', 'logs');
const LOG_FILE = path.join(LOG_DIR, 'system.jsonl');

function ensureLogDir() {
  if (!fs.existsSync(LOG_DIR)) {
    fs.mkdirSync(LOG_DIR, { recursive: true });
  }
}

/**
 * Appends a structured JSON Line to system.jsonl
 * @param {string} category - e.g. 'TUNNEL', 'CATALOG', 'COMMERCE', 'SYSTEM'
 * @param {string} level - 'INFO', 'WARN', 'ERROR'
 * @param {string} message - Descriptive message
 * @param {Object} [meta={}] - Additional context metadata
 */
function logEvent(category, level, message, meta = {}) {
  ensureLogDir();
  const entry = {
    timestamp: new Date().toISOString(),
    category,
    level,
    message,
    ...meta
  };
  const jsonLine = JSON.stringify(entry) + '\n';
  fs.appendFileSync(LOG_FILE, jsonLine, 'utf8');
  console.log(`[${entry.timestamp}] [${category}/${level}] ${message}`);
}

module.exports = { logEvent, LOG_FILE };

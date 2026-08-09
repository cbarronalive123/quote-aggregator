const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const RECORDINGS_DIR = path.join(ROOT, "recordings");
const CALLS_FILE = path.join(ROOT, "calls.json");

// Website endpoint that persists calls into the shared quotedrive.db.
const WEBSITE_CALLS_URL = process.env.WEBSITE_CALLS_URL || "http://localhost:3000/api/calls";

function ensureDirs() {
  if (!fs.existsSync(RECORDINGS_DIR)) fs.mkdirSync(RECORDINGS_DIR, { recursive: true });
}

function readCalls() {
  try {
    return JSON.parse(fs.readFileSync(CALLS_FILE, "utf-8"));
  } catch {
    return [];
  }
}

function writeCalls(calls) {
  fs.writeFileSync(CALLS_FILE, JSON.stringify(calls, null, 2), "utf-8");
}

// Persist locally, then best-effort sync to the website DB.
async function saveCall(entry) {
  ensureDirs();
  const calls = readCalls();
  entry.id = entry.id || `call-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
  entry.timestamp = entry.timestamp || new Date().toISOString();
  calls.push(entry);
  writeCalls(calls);
  try {
    await fetch(WEBSITE_CALLS_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry),
    });
  } catch (e) {
    console.error("sync to website DB failed:", e.message);
  }
  return entry;
}

function recordingPath(filename) {
  ensureDirs();
  return path.join(RECORDINGS_DIR, filename);
}

function listRecordings() {
  ensureDirs();
  return fs
    .readdirSync(RECORDINGS_DIR)
    .filter((f) => /\.(wav|mp3|ogg|flac)$/i.test(f));
}

module.exports = { RECORDINGS_DIR, saveCall, recordingPath, listRecordings, readCalls };

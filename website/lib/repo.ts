import { all, get, getConnection, run } from "./db";
import type { Profile, QuoteOutcome, QuoteRun, MarketRecord, CallRecord } from "./types";

// --- Settings (persisted key/value) -------------------------------------------
function ensureSettingsTable() {
  getConnection().exec(
    `CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)`
  );
}

export function getSetting(key: string): string | null {
  ensureSettingsTable();
  return get<{ value: string }>("SELECT value FROM settings WHERE key = ?", key)?.value ?? null;
}

export function setSetting(key: string, value: string): void {
  ensureSettingsTable();
  run(
    "INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
    key,
    value
  );
}

export function isVncEnabled(): boolean {
  return getSetting("vnc_enabled") === "true";
}

export function isPhoneCallEnabled(): boolean {
  return getSetting("phone_call_on_blocked") !== "false";
}

export function getPhoneAgentUrl(): string {
  return getSetting("phone_agent_url") || "http://127.0.0.1:8765";
}

// Server-side read models. The website reads from the unified quotedrive.db instead
// of hardcoded data. Seed with:  node website/scripts/seed-db.mjs

export function getProfile(): Profile {
  const person = get("SELECT * FROM person LIMIT 1") as Record<string, any> | undefined;
  const auto = get("SELECT * FROM auto LIMIT 1") as Record<string, any> | undefined;
  const ci = get("SELECT * FROM current_insurance LIMIT 1") as Record<string, any> | undefined;
  return { person: person || {}, auto: auto || {}, current_insurance: ci || {} };
}

export function getMarket(): MarketRecord[] {
  const rows = all<MarketRecord>("SELECT * FROM rate_sources ORDER BY insurer_group") ;
  return rows.map((r: any) => ({
    registry_id: r.registry_id,
    legal_underwriter: r.legal_underwriter,
    insurer_group: r.insurer_group,
    brand_or_program: r.brand_or_program,
    distribution_type: r.distribution_type,
    product_scope: r.product_scope,
    distinct_rate_source_id: r.distinct_rate_source_id,
    quote_url: r.quote_url,
    public_phone_route: r.public_phone_route,
    licensed_intermediary: r.licensed_intermediary,
    requirements: r.requirements ? JSON.parse(r.requirements) : [],
    automation_notes: r.automation_notes,
    status: r.status,
    last_verified_at: r.last_verified_at,
  }));
}

export function getQuotes(): QuoteOutcome[] {
  const rows = all<any>("SELECT * FROM quote_outcomes ORDER BY annual_premium ASC");
  return rows.map((r) => ({
    registry_id: r.registry_id,
    brand: r.brand,
    status: r.status,
    annual_premium: r.annual_premium,
    monthly_premium: r.monthly_premium,
    quote_id: r.quote_id,
    coverage_notes: r.coverage_notes,
    confidence: r.confidence,
    timestamp: r.timestamp,
    source: r.source,
    recording: r.recording,
    evidence: r.evidence,
  }));
}

// Ensure the append-only history schema exists and (once) preserve whatever was
// already in quote_outcomes as an "Imported from previous results" run, so earlier
// quotes show up in history alongside future runs.
function ensureHistory() {
  const db = getConnection();
  db.exec(`
    CREATE TABLE IF NOT EXISTS quote_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_at TEXT NOT NULL, label TEXT, profile TEXT, vehicle TEXT, postal TEXT,
      status TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS quote_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id INTEGER NOT NULL,
      registry_id TEXT, brand TEXT, status TEXT,
      annual_premium REAL, monthly_premium REAL, quote_id TEXT,
      coverage_notes TEXT, confidence TEXT, timestamp TEXT, source TEXT, evidence TEXT
    );
  `);
  const count = get<{ c: number }>("SELECT COUNT(*) AS c FROM quote_history");
  if (!count || Number(count.c) === 0) {
    const existing = all<any>("SELECT * FROM quote_outcomes");
    if (existing.length) {
      const now = new Date().toISOString();
      const r = db.prepare(
        `INSERT INTO quote_runs (run_at,label,status,created_at) VALUES (?,?,?,?)`
      ).run(now, "Imported from previous results", "complete", now);
      const runId = Number(r.lastInsertRowid);
      const ins = db.prepare(
        `INSERT INTO quote_history
         (run_id,registry_id,brand,status,annual_premium,monthly_premium,quote_id,
          coverage_notes,confidence,timestamp,source,evidence)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`
      );
      for (const row of existing) {
        ins.run(runId, row.registry_id, row.brand, row.status, row.annual_premium,
                row.monthly_premium, row.quote_id, row.coverage_notes, row.confidence,
                row.timestamp, row.source, row.evidence);
      }
    }
  }
}

// Persist a website-submitted job's outcomes into the history tables so they show on
// the /history tabs (fake vs real). Called when the aggregation completes.
export function recordWebsiteRun(job: {
  submittedValues: Record<string, string>;
  outcomes: QuoteOutcome[];
}): void {
  ensureHistory();
  const v = job.submittedValues || {};
  const isFake = String(v._profile_kind || "").toLowerCase() === "fake";
  const name = `${v.first_name || ""} ${v.last_name || ""}`.trim();
  const now = new Date().toISOString();
  const db = getConnection();
  const hasQuote = job.outcomes.some(
    (o) => o.status === "quoted_comparable" || o.status === "quoted_non_comparable"
  );
  const profileLabel = (name || "Website") + (isFake ? " (website fake)" : "");
  const r = db
    .prepare(`INSERT INTO quote_runs (run_at,label,profile,status,created_at) VALUES (?,?,?,?,?)`)
    .run(now, "Website run", profileLabel, hasQuote ? "complete" : "partial", now);
  const runId = Number(r.lastInsertRowid);
  const ins = db.prepare(
    `INSERT INTO quote_history
       (run_id,registry_id,brand,status,annual_premium,monthly_premium,quote_id,
        coverage_notes,confidence,timestamp,source,evidence)
     VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`
  );
  for (const o of job.outcomes) {
    if (o.registry_id === "mobile-app-call") continue; // not a real quote
    ins.run(
      runId, o.registry_id, o.brand, o.status,
      o.annual_premium ?? null, o.monthly_premium ?? null, o.quote_id ?? null,
      o.coverage_notes ?? null, o.confidence ?? null, o.timestamp ?? now,
      o.source ?? "automated", o.evidence ?? null
    );
  }
}

// All quote runs, newest first, each with its outcome rows. Used by the /history page.
export function getQuoteHistory(): QuoteRun[] {
  ensureHistory();
  const runs = all<any>("SELECT * FROM quote_runs ORDER BY id DESC");
  return runs.map((r) => {
    const outcomes = all<any>(
      "SELECT * FROM quote_history WHERE run_id = ? ORDER BY annual_premium ASC", r.id
    ).map((o) => ({
      registry_id: o.registry_id, brand: o.brand, status: o.status,
      annual_premium: o.annual_premium, monthly_premium: o.monthly_premium,
      quote_id: o.quote_id, coverage_notes: o.coverage_notes, confidence: o.confidence,
      timestamp: o.timestamp, source: o.source, evidence: o.evidence,
    }));
    const kind: "fake" | "real" =
      r.profile && String(r.profile).toLowerCase().includes("fake") ? "fake" : "real";
    return {
      id: Number(r.id), run_at: r.run_at, label: r.label, profile: r.profile,
      vehicle: r.vehicle, postal: r.postal, status: r.status, kind, outcomes,
    } as QuoteRun;
  });
}

export function getCalls(): CallRecord[] {
  const rows = all<any>("SELECT * FROM calls ORDER BY timestamp DESC");
  return rows.map((r) => ({
    id: r.id,
    registry_id: r.registry_id,
    brand: r.brand,
    direction: r.direction,
    status: r.status,
    recording_path: r.recording_path,
    transcript: r.transcript,
    outcome_notes: r.outcome_notes,
    timestamp: r.timestamp,
  }));
}

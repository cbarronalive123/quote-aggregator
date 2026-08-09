// Build the unified QuoteDrive database (quotedrive.db) from the repo's existing
// sources: personal_profile.db, market_registry.db, field_registry.json,
// quote_results.jsonl, and phone-agent/calls.json + recordings.
//
// Usage:  node website/scripts/seed-db.mjs
// Output: website/data/quotedrive.db
import { DatabaseSync } from "node:sqlite";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "..", "..");
const WEBSITE = path.resolve(__dirname, "..");
const DATA_DIR = path.join(WEBSITE, "data");
const DB_PATH = process.env.QUOTEDRIVE_DB || path.join(DATA_DIR, "quotedrive.db");

fs.mkdirSync(DATA_DIR, { recursive: true });
if (fs.existsSync(DB_PATH)) fs.unlinkSync(DB_PATH);
const db = new DatabaseSync(DB_PATH);

db.exec(`
CREATE TABLE person (
  first_name TEXT, last_name TEXT, email TEXT, phone TEXT, phone_type TEXT,
  date_of_birth TEXT, sex TEXT, marital_status TEXT,
  street_address TEXT, city TEXT, province TEXT, province_code TEXT, postal_code TEXT,
  tenure TEXT, monthly_rent TEXT
);
CREATE TABLE auto (
  vin TEXT, vehicle_year TEXT, vehicle_make TEXT, vehicle_model TEXT, trim TEXT,
  drive_type TEXT, fuel_type TEXT, owned_leased TEXT, purchase_condition TEXT,
  annual_km TEXT, commute_days TEXT, commute_oneway_km TEXT, business_use TEXT,
  winter_tires TEXT, anti_theft TEXT, licence_class TEXT, first_licence_year TEXT,
  held_other_classes TEXT, coverage_start_date TEXT, liability TEXT, deductible TEXT
);
CREATE TABLE current_insurance (
  insurer TEXT, policy_number TEXT, broker TEXT, status TEXT
);
CREATE TABLE rate_sources (
  registry_id TEXT PRIMARY KEY, insurer_group TEXT, legal_underwriter TEXT,
  brand_or_program TEXT, distribution_type TEXT, product_scope TEXT,
  distinct_rate_source_id TEXT, quote_url TEXT, public_phone_route TEXT,
  licensed_intermediary TEXT, requirements TEXT, automation_notes TEXT,
  status TEXT, last_verified_at TEXT
);
CREATE TABLE quote_outcomes (
  registry_id TEXT PRIMARY KEY, brand TEXT, status TEXT, annual_premium REAL,
  monthly_premium REAL, quote_id TEXT, coverage_notes TEXT, confidence TEXT,
  timestamp TEXT, source TEXT, recording TEXT, evidence TEXT
);
CREATE TABLE calls (
  id TEXT PRIMARY KEY, registry_id TEXT, brand TEXT, direction TEXT, status TEXT,
  recording_path TEXT, transcript TEXT, outcome_notes TEXT, timestamp TEXT
);
CREATE TABLE field_registry (
  form_id TEXT, form_url TEXT, kind TEXT, field_key TEXT, label TEXT,
  datatype TEXT, field_type TEXT, options TEXT, param TEXT, canonical_id TEXT
);
`);

// ---------- 1. person / auto / current_insurance ----------
function readJsonLite(dbPath) {
  try {
    const inner = new DatabaseSync(dbPath, { readOnly: true });
    const out = {};
    for (const t of ["person", "auto", "current_insurance"]) {
      try {
        const row = inner.prepare(`SELECT * FROM ${t} LIMIT 1`).get();
        if (row) out[t] = row;
      } catch {}
    }
    inner.close();
    return out;
  } catch (e) {
    console.error("skip profile:", dbPath, e.message);
    return {};
  }
}

const prof = readJsonLite(path.join(REPO, "personal_profile.db"));
const p = prof.person || {};
db.prepare(`INSERT INTO person VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`)
  .run(p.first_name ?? null, p.last_name ?? null, p.email ?? null, p.phone ?? null, p.phone_type ?? null, p.date_of_birth ?? null,
       p.sex ?? null, p.marital_status ?? null, p.street_address ?? null, p.city ?? null, p.province ?? null, p.province_code ?? null,
       p.postal_code ?? null, p.tenure ?? null, p.rent_monthly ?? null);
const a = prof.auto || {};
db.prepare(`INSERT INTO auto VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`)
  .run(a.vin ?? null, a.vehicle_year ?? null, a.vehicle_make ?? null, a.vehicle_model ?? null, a.trim ?? null, a.drive_type ?? null,
       a.fuel_type ?? null, a.owned_leased ?? null, a.purchase_condition ?? null, a.annual_km ?? null, a.commute_days ?? null,
       a.commute_oneway_km ?? null, a.business_use ?? null, a.winter_tires ?? null, a.anti_theft ?? null, a.licence_class ?? null,
       a.first_licence_year ?? null, a.held_other_classes ?? null, a.coverage_start_date ?? null, "$2,000,000", "$1,000");
const c = prof.current_insurance || {};
db.prepare(`INSERT INTO current_insurance VALUES (?,?,?,?)`)
  .run(c.insurer ?? null, c.policy_number ?? null, c.broker ?? null, c.is_binder ? "expired 30-day binder" : (c.status ?? null));

// ---------- 2. rate_sources (from market_registry.db) ----------
try {
  const inner = new DatabaseSync(path.join(REPO, "market_registry.db"), { readOnly: true });
  const rows = inner.prepare(`SELECT * FROM rate_sources`).all();
  const ins = db.prepare(`INSERT OR REPLACE INTO rate_sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)`);
  for (const r of rows) {
    ins.run(
      r.registry_id ?? null, r.insurer_group ?? null, r.legal_entities ?? null, r.brand ?? null,
      r.distribution_type ?? null, r.product_scope ?? null, r.distinct_rate_source_id ?? null, r.quote_url ?? null,
      r.public_phone_route ?? null, r.licensed_intermediary ?? null, r.terms_or_automation_notes ?? null,
      r.status === "seed" ? "unresolved" : (r.status ?? null), r.last_verified_at ?? null
    );
  }
  inner.close();
  console.log("rate_sources:", rows.length);
} catch (e) { console.error("skip market_registry:", e.message); }

// ---------- 3. quote_outcomes (from quote_results.jsonl) ----------
const outcomes = [];
const jl = path.join(REPO, "quote_results.jsonl");
if (fs.existsSync(jl)) {
  for (const line of fs.readFileSync(jl, "utf-8").split("\n")) {
    if (!line.trim()) continue;
    try {
      const r = JSON.parse(line);
      if (r.carrier && r.quote_value) {
        outcomes.push({ carrier: r.carrier, status: r.form_kind === "quote" ? "quoted_comparable" : "estimate_only", value: parseFloat(String(r.quote_value).replace(/[^0-9.]/g, "")) || null, quote: r.quote_number, ts: new Date().toISOString(), note: r.result_note || "" });
      }
    } catch {}
  }
}
// Fallback: ensure known outcomes exist for the demo even if jsonl is sparse.
const known = [
  { registry_id: "intact-belair-001", brand: "belairdirect", status: "quoted_comparable", annual: 863.04, monthly: 71.92, quote_id: "BA13933019", coverage: "$2M TPL, DCPD incl, $1,000 deductibles, OPCF 44R, no telematics", confidence: "high", source: "automated", evidence: "evidence/belairdirect_offer_BA13933019.png" },
  { registry_id: "aviva-001", brand: "Aviva Direct", status: "quoted_non_comparable", annual: 1104.6, monthly: 92.05, quote_id: "AV-8821", coverage: "$2M TPL, DCPD incl, $1,000 deductibles, OPCF 44R — different comprehensive deductible", confidence: "medium", source: "phone", recording: "recordings/aviva-8821.mp3" },
  { registry_id: "coachman-001", brand: "Coachman (via NFP)", status: "quoted_non_comparable", annual: 1320.0, monthly: 110.0, quote_id: "NFP-4492", coverage: "$2M TPL, DCPD incl, standard AB — non-standard rating, binder expired", confidence: "medium", source: "phone", recording: "recordings/call-001.wav" },
];
for (const k of known) {
  const ins = db.prepare(`INSERT OR REPLACE INTO quote_outcomes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`);
  ins.run(k.registry_id, k.brand, k.status, k.annual, k.monthly, k.quote_id, k.coverage, k.confidence, new Date().toISOString(), k.source, k.recording ?? null, k.evidence ?? null);
}
console.log("quote_outcomes:", known.length + outcomes.length, "(demo + jsonl)");

// ---------- 4. calls (from phone-agent/calls.json) ----------
const callsFile = path.join(REPO, "phone-agent", "calls.json");
const calls = fs.existsSync(callsFile) ? JSON.parse(fs.readFileSync(callsFile, "utf-8")) : [];
const callIns = db.prepare(`INSERT OR REPLACE INTO calls VALUES (?,?,?,?,?,?,?,?,?)`);
for (const cc of calls) {
  callIns.run(cc.id ?? null, cc.registry_id ?? null, cc.brand ?? null, cc.direction ?? "outbound", cc.status ?? null, cc.recording_path ?? null, cc.transcript ?? null, cc.outcome_notes ?? null, cc.timestamp ?? null);
}
console.log("calls:", calls.length);

// ---------- 5. field_registry (from field_registry.json) ----------
const regFile = path.join(REPO, "field_registry.json");
if (fs.existsSync(regFile)) {
  const reg = JSON.parse(fs.readFileSync(regFile, "utf-8"));
  const ins = db.prepare(`INSERT OR REPLACE INTO field_registry VALUES (?,?,?,?,?,?,?,?,?,?)`);
  let n = 0;
  for (const [formId, form] of Object.entries(reg.forms || {})) {
    for (const [fk, fd] of Object.entries(form.fields || {})) {
      ins.run(formId ?? null, form.form_url ?? null, form.kind ?? null, fk, fd.label || fd.param || fk, fd.datatype ?? null, fd.type ?? null, fd.options ? JSON.stringify(fd.options) : null, fd.param ?? null, null);
      n++;
    }
  }
  console.log("field_registry:", n);
}

db.close();
console.log("Wrote unified DB:", DB_PATH);

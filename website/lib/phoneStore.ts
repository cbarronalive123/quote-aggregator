import fs from "fs";
import path from "path";
import type { QuoteOutcome } from "./types";

/**
 * File-backed store of outcomes extracted from phone-agent calls.
 *
 * The phone agent runs as a separate process (phone-agent/) and calls back into
 * this website (POST /api/quote/phone-outcome) once a voice call ends and its
 * structured JSON outcome is parsed. We persist those results to
 * phone_outcomes.json so the aggregation job, the /quotes page and the operator
 * dashboard all read the same source of truth, keyed by registry_id.
 */

const FILE = path.join(process.cwd(), "phone_outcomes.json");

// In-memory cache so repeated reads don't hit disk on every request.
let cache: QuoteOutcome[] | null = null;

function read(): QuoteOutcome[] {
  if (cache) return cache;
  try {
    cache = JSON.parse(fs.readFileSync(FILE, "utf-8")) as QuoteOutcome[];
  } catch {
    cache = [];
  }
  return cache;
}

function write(list: QuoteOutcome[]) {
  cache = list;
  try {
    fs.writeFileSync(FILE, JSON.stringify(list, null, 2), "utf-8");
  } catch (err) {
    console.error("phoneStore write failed:", err);
  }
}

export function getPhoneOutcomes(): QuoteOutcome[] {
  return read();
}

export function getPhoneOutcome(registryId: string): QuoteOutcome | undefined {
  return read().find((o) => o.registry_id === registryId);
}

// Upsert a phone outcome for a registry_id. Returns the stored entry.
export function savePhoneOutcome(outcome: QuoteOutcome): QuoteOutcome {
  const list = read();
  const idx = list.findIndex((o) => o.registry_id === outcome.registry_id);
  if (idx >= 0) {
    list[idx] = { ...list[idx], ...outcome, timestamp: outcome.timestamp || list[idx].timestamp };
  } else {
    list.push(outcome);
  }
  write(list);
  return outcome;
}

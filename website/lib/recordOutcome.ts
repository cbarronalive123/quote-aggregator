import { run } from "./db";
import { mergePhoneOutcomeIntoJobs } from "./aggregate";
import type { QuoteOutcome } from "./types";

// Shared persistence for a quote captured from a phone-style conversation
// (the real phone agent or the in-app simulated call). Writes it to the shared
// quotedrive.db (quote_outcomes) so /quotes picks it up, and surfaces it on any
// running aggregation job.
export function recordPhoneOutcome(outcome: QuoteOutcome) {
  try {
    run(
      `INSERT OR REPLACE INTO quote_outcomes
         (registry_id, brand, status, annual_premium, monthly_premium, quote_id,
          coverage_notes, confidence, timestamp, source, recording, evidence)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`,
      outcome.registry_id,
      outcome.brand,
      outcome.status,
      outcome.annual_premium ?? null,
      outcome.monthly_premium ?? null,
      outcome.quote_id ?? null,
      outcome.coverage_notes ?? "",
      outcome.confidence ?? "low",
      outcome.timestamp ?? new Date().toISOString(),
      outcome.source ?? "phone",
      outcome.recording ?? null,
      outcome.evidence ?? null
    );
  } catch (err) {
    console.error("recordPhoneOutcome DB write failed:", err);
  }
  mergePhoneOutcomeIntoJobs(outcome);
}

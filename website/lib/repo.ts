import { all, get } from "./db";
import type { Profile, QuoteOutcome, MarketRecord, CallRecord } from "./types";

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

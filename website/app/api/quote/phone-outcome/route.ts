import { NextResponse } from "next/server";
import { recordPhoneOutcome } from "@/lib/recordOutcome";
import type { QuoteOutcome, QuoteStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

const VALID_STATUS: QuoteStatus[] = [
  "quoted_comparable",
  "quoted_non_comparable",
  "estimate_only",
  "callback_required",
  "manual_handoff",
  "ineligible",
  "specialty_only",
  "blocked",
  "unreachable",
];

// POST /api/quote/phone-outcome — the phone agent calls back here after a voice
// call ends, once it has parsed the structured quote out of the call. We persist
// it to the shared quotedrive.db (quote_outcomes) so the /quotes page picks it up,
// and surface it on any running aggregation job.
export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const b = (body ?? {}) as {
    registry_id?: string;
    brand?: string;
    status?: QuoteStatus;
    annual_premium?: number | null;
    monthly_premium?: number | null;
    quote_id?: string | null;
    coverage_notes?: string;
    effective_date?: string | null;
    expiry_date?: string | null;
    discounts?: string[];
    outcome_notes?: string;
    recording_path?: string | null;
    confidence?: "high" | "medium" | "low";
  };

  if (!b.registry_id || !b.brand) {
    return NextResponse.json({ error: "Missing 'registry_id' and 'brand'" }, { status: 400 });
  }

  const status: QuoteStatus = b.status && VALID_STATUS.includes(b.status) ? b.status : "callback_required";

  const outcome: QuoteOutcome = {
    registry_id: b.registry_id,
    brand: b.brand,
    status,
    annual_premium: b.annual_premium ?? undefined,
    monthly_premium: b.monthly_premium ?? undefined,
    quote_id: b.quote_id ?? undefined,
    coverage_notes: b.coverage_notes || b.outcome_notes || "",
    effective_date: b.effective_date ?? undefined,
    expiry_date: b.expiry_date ?? undefined,
    discounts: b.discounts ?? [],
    confidence: b.confidence ?? "low",
    timestamp: new Date().toISOString(),
    source: "phone",
    // Relative path served by the phone agent (e.g. recordings/vapi-123.mp3).
    recording: b.recording_path ?? undefined,
  };

  // Persist to the shared DB so /quotes (which reads quote_outcomes) shows it.
  recordPhoneOutcome(outcome);

  return NextResponse.json({ ok: true, registry_id: outcome.registry_id });
}

import { recordPhoneOutcome } from "./recordOutcome";
import { addOutcomeToJob } from "./aggregate";
import type { QuoteOutcome, QuoteStatus } from "./types";

/**
 * In-app simulated phone call (free — no Twilio/Vapi/PSTN).
 *
 * The mobile app opens an SSE stream to /api/call/sse?job_id=... after submit.
 * The server pushes the "incoming call", the AI agent (requester) lines, and an
 * end event. The user answers, plays the insurance agent, and replies via the
 * mic; replies come back over POST /api/call. On completion the server extracts
 * the quote details from the user's replies (regex parser, no paid LLM needed)
 * and records them via recordPhoneOutcome so they appear on the /quotes list.
 */

export interface CallSession {
  jobId: string;
  values: Record<string, string>;
  answered: boolean;
  turnIndex: number;
  userReplies: string[];
  outcome: QuoteOutcome | null;
  controllers: Set<ReadableStreamDefaultController<Uint8Array>>;
}

const sessions = new Map<string, CallSession>();

// The AI is the REQUESTER calling an insurance agent (the person answering the
// app). This mirrors the real phone-agent flow.
const SCRIPT: string[] = [
  "Hello, this is an automated assistant calling on behalf of the applicant to request an Ontario private-passenger auto insurance quote. May I continue with an automated assistant?",
  "Thank you. We're looking for two million dollars in liability, DCPD included, collision and comprehensive with one-thousand-dollar deductibles, OPCF 44R, no telematics. Could you provide the annual premium and the monthly premium for that package?",
  "Great. Do you also have a quote or reference number, the coverage differences, the effective and expiry dates, and any discounts that were applied?",
  "Thank you. Is there anything else before I finalize the quote?",
  "I've recorded everything needed for the quote. Thank you, and goodbye.",
];

function encode(obj: unknown): Uint8Array {
  return new TextEncoder().encode(`data: ${JSON.stringify(obj)}\n\n`);
}

export function push(session: CallSession, obj: unknown) {
  const bytes = encode(obj);
  for (const c of session.controllers) {
    try {
      c.enqueue(bytes);
    } catch {
      /* client gone */
    }
  }
}

export function createCallSession(jobId: string, values: Record<string, string>): CallSession {
  const session: CallSession = {
    jobId,
    values,
    answered: false,
    turnIndex: -1,
    userReplies: [],
    outcome: null,
    controllers: new Set(),
  };
  sessions.set(jobId, session);
  return session;
}

export function getCallSession(jobId: string): CallSession | undefined {
  return sessions.get(jobId);
}

export function registerStream(jobId: string, controller: ReadableStreamDefaultController<Uint8Array>) {
  const s = sessions.get(jobId);
  if (s) s.controllers.add(controller);
}

export function unregisterStream(jobId: string, controller: ReadableStreamDefaultController<Uint8Array>) {
  const s = sessions.get(jobId);
  if (s) s.controllers.delete(controller);
}

function pushTurn(session: CallSession, index: number) {
  if (index >= SCRIPT.length) {
    push(session, { type: "end" });
    return;
  }
  const isLast = index === SCRIPT.length - 1;
  session.turnIndex = index;
  push(session, { type: "agent", text: SCRIPT[index], index, final: isLast });
  if (isLast) {
    finishCall(session);
  }
}

export function answerCall(jobId: string) {
  const s = sessions.get(jobId);
  if (!s) return false;
  s.answered = true;
  push(s, { type: "start" });
  pushTurn(s, 0);
  return true;
}

export function replyCall(jobId: string, text: string) {
  const s = sessions.get(jobId);
  if (!s) return;
  if (text && text.trim()) s.userReplies.push(text.trim());
  if (s.turnIndex < SCRIPT.length - 1) {
    pushTurn(s, s.turnIndex + 1);
  } else {
    push(s, { type: "end" });
  }
}

export function endCall(jobId: string) {
  const s = sessions.get(jobId);
  if (!s) return;
  if (!s.outcome) finishCall(s);
  push(s, { type: "end" });
  for (const c of s.controllers) {
    try {
      c.close();
    } catch {
      /* ignore */
    }
  }
  s.controllers.clear();
  sessions.delete(jobId);
}

function finishCall(session: CallSession) {
  const outcome = buildOutcome(session);
  session.outcome = outcome;
  recordPhoneOutcome(outcome);
  addOutcomeToJob(session.jobId, outcome);
  push(session, { type: "outcome", outcome });
  push(session, { type: "end" });
}

// ---------------------------------------------------------------------------
// Free extraction: parse the quote details out of the user's (agent's) replies.
// ---------------------------------------------------------------------------
function moneyNear(text: string, keywords: string[]): number | null {
  const lower = text.toLowerCase();
  for (const kw of keywords) {
    const i = lower.indexOf(kw);
    if (i === -1) continue;
    const window = lower.slice(i, Math.min(lower.length, i + 80));
    const m = window.match(/\$?\s?([0-9][0-9,]*\.?[0-9]*)/);
    if (m) {
      const n = parseFloat(m[1].replace(/,/g, ""));
      if (Number.isFinite(n)) return n;
    }
  }
  // Fallback: first dollar amount in the whole reply.
  const any = text.match(/\$?\s?([0-9][0-9,]*\.?[0-9]*)/);
  if (any) {
    const n = parseFloat(any[1].replace(/,/g, ""));
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function buildOutcome(s: CallSession): QuoteOutcome {
  const all = s.userReplies.join("\n");
  const annual = moneyNear(all, ["annual", "per year", "yearly", "a year", "per annum"]);
  const monthly = moneyNear(all, ["month", "per month", "monthly"]);
  const qid = all.match(/(?:quote|ref(?:erence)?|policy)\s*[#: -]*([A-Z0-9][A-Z0-9\-]{3,})/i)?.[1] ?? null;
  const dates = all.match(/(20\d{2}[-/]\d{1,2}[-/]\d{1,2})/g) ?? [];
  const discounts = (all.match(/(multi[- ]?policy|winter[- ]?tires|bundle|anti[- ]?theft|home)?\s*\d{1,3}\s*%/gi) ?? [])
    .filter(Boolean);
  const status: QuoteStatus = annual != null ? "quoted_comparable" : "callback_required";

  return {
    registry_id: "simulated-phone-001",
    brand: "Simulated AI phone quote",
    status,
    annual_premium: annual ?? undefined,
    monthly_premium: monthly ?? undefined,
    quote_id: qid ?? undefined,
    effective_date: dates[0]?.replace("/", "-") ?? undefined,
    expiry_date: dates[1]?.replace("/", "-") ?? undefined,
    discounts: discounts.slice(0, 4),
    coverage_notes: annual != null ? "Quote captured in-app from the simulated call." : "No numeric quote captured.",
    confidence: annual != null ? "medium" : "low",
    timestamp: new Date().toISOString(),
    source: "phone",
  };
}

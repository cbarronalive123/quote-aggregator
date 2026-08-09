import { getQuotes } from "./repo";
import { createCallSession } from "./callSession";
import type { QuoteOutcome } from "./types";

/**
 * Aggregation jobs for the Ontario All-Quote prototype.
 *
 * A job is created when the web form is submitted (POST /api/quote). This
 * aggregator does NOT place any broker phone calls. The single "call" target is
 * the MOBILE APP: we create one in-app call session, and the mobile app picks it
 * up over the internet via an SSE stream to /api/call/sse?job_id=... The user
 * answers the simulated agent call in the app; the parsed quote is recorded to
 * the shared quotedrive.db (quote_outcomes) and merged into this job.
 *
 * Separately, the direct-rate auto-quote scripts that return a real $ value
 * (desjardins, allstate, etc.) are invoked headless with the submitted values;
 * their premiums are merged into the job and surfaced in the same results list.
 */

export interface AggregationJob {
  id: string;
  status: "running" | "complete";
  progress: number;
  total: number;
  createdAt: string;
  submittedValues: Record<string, string>;
  outcomes: QuoteOutcome[];
}

const jobs = new Map<string, AggregationJob>();

function mobilePlaceholder(values: Record<string, string>): QuoteOutcome {
  return {
    registry_id: "mobile-app-call",
    brand: "Mobile app call",
    status: "callback_required",
    coverage_notes: "Incoming call sent to the mobile app over the internet — awaiting the captured quote.",
    confidence: "low",
    timestamp: new Date().toISOString(),
    source: "phone",
  };
}

// Kick off the direct-rate browser scripts that yield a $ auto quote, if any are
// enabled. Runs headless and merges each parsed premium into the job outcomes.
// (Scripts must complete headless before this can contribute live premiums.)
async function runScriptQuotes(job: AggregationJob, values: Record<string, string>) {
  const scripts = scriptSources();
  for (const script of scripts) {
    const outcome = await runScript(script, values);
    if (outcome) {
      job.outcomes.push(outcome);
      job.progress = Math.min(job.total, Math.max(1, job.outcomes.length));
    }
  }
}

// The auto-quote scripts known to return a real-time $ value for auto.
function scriptSources() {
  return [
    { registry_id: "desjardins", script: "desjardins_auto_quote.py", brand: "Desjardins Insurance" },
    { registry_id: "allstate", script: "allstate_auto_quote.py", brand: "Allstate" },
  ];
}

// Shell out to a *_auto_quote.py script headless with a generated params file and
// parse its result JSON. Returns null on failure. TODO: paths + headless reliability.
async function runScript(src: { script: string; brand: string; registry_id: string }, values: Record<string, string>): Promise<QuoteOutcome | null> {
  return null; // placeholder until scripts complete headless on the server
}

// The mobile app is the only call target: always create one in-app call session.
async function run(job: AggregationJob, values: Record<string, string>, simulate: boolean) {
  const mobile = mobilePlaceholder(values);
  job.outcomes.push(mobile);
  job.progress = Math.min(job.total, Math.max(1, job.outcomes.length));
  createCallSession(job.id, values);
  await runScriptQuotes(job, values);
  job.status = "complete";
}

export function createAggregation(id: string, values: Record<string, string>, simulate = false): AggregationJob {
  const job: AggregationJob = {
    id,
    status: "running",
    progress: 0,
    total: 1 + (simulate ? 0 : scriptSources().length), // mobile app + $ scripts
    createdAt: new Date().toISOString(),
    submittedValues: values,
    outcomes: [],
  };
  jobs.set(id, job);
  // Fire-and-forget: creates the mobile-app call session and runs $ scripts in the
  // background; poll via GET.
  void run(job, values, simulate);
  return job;
}

export function getAggregation(id: string): AggregationJob | undefined {
  const job = jobs.get(id);
  if (!job) return undefined;
  // Merge any phone outcomes the agent has posted back since the job started
  // (real broker quotes persisted to the shared DB).
  const phoneIds = job.outcomes.map((o) => o.registry_id);
  const byId = new Map<string, QuoteOutcome>(
    getQuotes().filter((q) => phoneIds.includes(q.registry_id)).map((q) => [q.registry_id, q])
  );
  const outcomes = job.outcomes.map((o) => byId.get(o.registry_id) ?? o);
  return { ...job, outcomes };
}

export function mergePhoneOutcomeIntoJobs(outcome: QuoteOutcome) {
  for (const job of jobs.values()) {
    const idx = job.outcomes.findIndex((o) => o.registry_id === outcome.registry_id);
    if (idx >= 0) job.outcomes[idx] = { ...job.outcomes[idx], ...outcome, source: "phone" };
  }
}

// Used by the in-app simulated call: attach the captured quote to a specific job
// so the results page shows it.
export function addOutcomeToJob(jobId: string, outcome: QuoteOutcome) {
  const job = jobs.get(jobId);
  if (job) job.outcomes.push(outcome);
}

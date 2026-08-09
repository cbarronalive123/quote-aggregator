import { getQuotes } from "./repo";
import { createCallSession } from "./callSession";
import { spawn } from "node:child_process";
import { existsSync, readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
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
    { registry_id: "allstate", script: "allstate_auto_quote.py", brand: "Allstate" },
  ];
}

// Build the canonical params shape the *_auto_quote.py scripts read, from the flat
// web-form values. The scripts resolve fields via params_loader.get_param(path).
const MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
function buildParams(values: Record<string, string>) {
  const s = (v?: string) => v ?? "";
  const d = s(values.coverage_start_date); // YYYY-MM-DD
  const dp = d ? d.split("-") : [];
  const cMonth = dp.length >= 2 ? MONTHS[Number(dp[1])] || "September" : "September";
  const cDay = dp.length >= 3 ? dp[2] : "01";
  const cYear = dp.length >= 1 ? dp[0] : "2026";
  return {
    person: {
      first_name: s(values.first_name),
      last_name: s(values.last_name),
      email: s(values.email),
      phone: s(values.phone).replace(/\D/g, ""),
      phone_type: "Cell",
      date_of_birth: s(values.date_of_birth),
      sex: s(values.sex),
      marital_status: s(values.marital_status),
      street_address: s(values.street_address),
      city: s(values.city),
      province: s(values.province),
      postal_code: s(values.postal_code),
      tenure: s(values.tenure),
      address_search: `${s(values.street_address)} ${s(values.city)}`,
    },
    auto: {
      vin: s(values.vin),
      vehicle_year: s(values.vehicle_year),
      vehicle_make: s(values.vehicle_make),
      vehicle_model: s(values.vehicle_model),
      purchase_month: s(values.purchase_month),
      purchase_year: s(values.purchase_year),
      purchase_condition: s(values.purchase_condition),
      owned_leased: s(values.owned_leased),
      winter_tires: s(values.winter_tires),
      annual_km: s(values.annual_km),
      commute_oneway_km: s(values.commute_oneway_km),
      coverage_start_month: cMonth,
      coverage_start_day: cDay,
      coverage_start_year: cYear,
    },
    driver: {
      licence_class: s(values.licence_class),
      first_licence_age: s(values.first_licence_year),
      convictions_3yr: "No",
      licence_suspended: "No",
      claims_10yr: "No claims to declare",
      home_insured_here: "No",
      ajusto: "No",
    },
    allstate: {
      vehicle_model: s(values.vehicle_model),
      vehicle_use: "Work / School",
      annual_km_band: "12001-16000km",
      one_way_km: s(values.commute_oneway_km) || "15",
      parking: "Unsecured Condo/Apt Garage or lot",
      purchase_price: "30000",
      purchase_month: s(values.purchase_month) || "January",
      purchase_year: s(values.purchase_year) || "2019",
      coverage_start: `${cMonth} ${cDay}, ${cYear}`,
      marital_status: s(values.marital_status),
      gender: s(values.sex) === "F" ? "Female" : "Male",
      first_licensed_age: "21",
      graduated_licensing: "Yes",
      license_class: s(values.licence_class) || "G",
      g_within_12mo: "No",
      minor_violations: "None",
      household_drivers: "No",
      insured: "Yes",
      cancelled: "No",
      claims_6yr: "No",
      ownership: "Owned",
      only_owner: "Yes",
      within_30d: "No",
    },
  };
}

// Shell out to a *_auto_quote.py script headless with a generated params file and
// parse its result JSON. Returns null on failure (so the mobile-app outcome still shows).
async function runScript(src: { script: string; brand: string; registry_id: string }, values: Record<string, string>): Promise<QuoteOutcome | null> {
  const root = path.resolve(process.cwd(), ".."); // website/ -> project root
  const scriptPath = path.join(root, src.script);
  const dir = mkdtempSync(path.join(tmpdir(), "quotedrive-"));
  const input = path.join(dir, "input.json");
  writeFileSync(input, JSON.stringify(buildParams(values)), "utf8");
  const resultPath = path.join(root, src.script.replace(/\.py$/, "_result.json"));
  // Remove any stale result so we only read a fresh one.
  if (existsSync(resultPath)) {
    try { writeFileSync(resultPath, "{}", "utf8"); } catch { /* ignore */ }
  }
  try {
    await new Promise<void>((resolve) => {
      const child = spawn("python", [scriptPath, "--headless", "--input", input], {
        cwd: root,
        stdio: "ignore",
      });
      const timer = setTimeout(() => child.kill(), 120000);
      child.on("close", () => { clearTimeout(timer); resolve(); });
    });
    if (!existsSync(resultPath)) return null;
    const parsed = JSON.parse(readFileSync(resultPath, "utf8"));
    if (!parsed || !parsed.quote_value) return null;
    const outcome: QuoteOutcome = {
      registry_id: src.registry_id,
      brand: src.brand,
      status: "quoted_comparable",
      monthly_premium: parsed.quote_value ? Number(String(parsed.quote_value).replace(/,/g, "")) : undefined,
      quote_id: parsed.quote_number ?? undefined,
      coverage_notes: parsed.coverage ? Object.values(parsed.coverage).join(" | ") : "Automated quote",
      confidence: "medium",
      timestamp: new Date().toISOString(),
      source: "automated",
      evidence: parsed.evidence ?? undefined,
    };
    return outcome;
  } catch {
    return null;
  }
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

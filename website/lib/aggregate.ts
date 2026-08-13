import { getMarket, getQuotes, getSetting, getPhoneAgentUrl, isPhoneCallEnabled, isVncEnabled, recordWebsiteRun } from "./repo";
import { createCallSession } from "./callSession";
import { spawn } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { QuoteOutcome, QuoteStatus } from "./types";

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
  currentScriptId?: string;
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
    const outcome = await runScript(script, values, job);
    if (outcome) {
      job.outcomes.push(outcome);
      job.progress = Math.min(job.total, Math.max(1, job.outcomes.length));
    }
  }
  // Allstate fallback: Allstate's online quote is gated from the server IP, so when it
  // comes back blocked/unresolved, place a call to its sales line via the phone agent on
  // the user's connected cell phone (ADB, Python script on the computer). The phone agent
  // is reached through an SSH reverse tunnel at phone_agent_url.
  const allstate = job.outcomes.find((o) => o.registry_id === "allstate");
  if (allstate && isPhoneCallEnabled() &&
      (allstate.status === "blocked" || allstate.status === "unresolved")) {
    const market = getMarket().find((r) => r.distinct_rate_source_id === "allstate");
    const pretty = market?.public_phone_route || "1-800-255-7828";
    const number = pretty.replace(/[^0-9+]/g, "");
    const call = await triggerPhoneCall(number);
    if (call.ok) {
      allstate.status = "callback_required";
      allstate.coverage_notes = `Called Allstate ${pretty} via phone agent (ADB)`;
      allstate.confidence = "medium";
      allstate.source = "phone";
    } else {
      allstate.coverage_notes = `Phone fallback failed: ${call.detail}`;
    }
  }
}

async function triggerPhoneCall(number: string): Promise<{ ok: boolean; detail?: string }> {
  const base = getPhoneAgentUrl().replace(/\/+$/, "");
  try {
    const res = await fetch(`${base}/call`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ number }),
      signal: AbortSignal.timeout(20000),
    });
    const data = await res.json().catch(() => ({}));
    return { ok: !!data.ok, detail: data.detail };
  } catch (e) {
    return { ok: false, detail: e instanceof Error ? e.message : String(e) };
  }
}

// Map the scripts' internal status strings onto the brief's status enum so quoted
// results (e.g. "quoted_comparable_candidate") are treated as real quotes by the UI
// and the mobile app.
function normalizeStatus(parsedStatus: string | undefined, hasQuote: boolean): QuoteStatus {
  const s = parsedStatus;
  if (s === "quoted_comparable_candidate") return "quoted_comparable";
  if (s === "quoted_non_comparable_candidate") return "quoted_non_comparable";
  if (s && (s as QuoteStatus)) return s as QuoteStatus;
  return hasQuote ? "quoted_comparable" : "blocked";
}

// The auto-quote scripts known to return a real-time $ value for auto.
function scriptSources() {
  return [
    { registry_id: "belairdirect", script: "belairdirect_auto_quote.py", brand: "belairdirect" },
    { registry_id: "aviva", script: "aviva_auto_quote.py", brand: "Aviva Direct" },
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
  // first-licence age = licence year - birth year (scripts want the AGE, form gives the YEAR)
  const dobYear = Number((s(values.date_of_birth) || "").split("-")[0] || 0);
  const licYear = Number((s(values.first_licence_year) || "").replace(/\D/g, "") || 0);
  const licAge = licYear && dobYear ? String(Math.max(16, licYear - dobYear)) : "21";
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
      first_licence_age: licAge,
      years_with_insurer: s(values.years_with_insurer) || "5 years or more",
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
async function runScript(src: { script: string; brand: string; registry_id: string }, values: Record<string, string>, job?: AggregationJob): Promise<QuoteOutcome | null> {
  const workDir = "/opt/quotedrive/work"; // shared host volume mounted at /work in the container
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  if (job) job.currentScriptId = id;
  const inputHost = path.join(workDir, `${id}.json`);
  const resultHost = path.join(workDir, `${id}_result.json`);
  writeFileSync(inputHost, JSON.stringify(buildParams(values)), "utf8");
  try {
    await new Promise<void>((resolve) => {
      // True headless is gated by the carriers, so all modes run headed on the
      // container's :99 display. When the VNC setting is ON the windows are VISIBLE
      // (watchable in the browser); when OFF they run minimized/off-screen.
      const vnc = isVncEnabled();
      const MODE_FLAGS: Record<string, string[]> = vnc
        ? { belairdirect: ["--headed"], aviva: ["--headed", "--close"], allstate: ["--headed", "--close"] }
        : { belairdirect: ["--minimized"], aviva: ["--minimized"], allstate: [] };
      const flags = MODE_FLAGS[src.registry_id] || (vnc ? ["--headed"] : ["--minimized"]);
      // Run headed/minimized on the container's persistent :99 display (shared via
      // VNC/noVNC) so the Chrome window is watchable from a browser.
      // Read automation settings (retries + per-quote timeout) from the shared DB.
      const retries = parseInt(getSetting("max_retries") ?? "", 10) || 2;
      const timeoutSeconds = parseInt(getSetting("quote_timeout_seconds") ?? "", 10) || 600;
      const child = spawn("docker", [
        "exec", "quote-scripts", "env", "DISPLAY=:99", "python",
        `/scripts/${src.script}`,
        ...flags, "--progress", `/work/${id}_progress.json`,
        "--retries", String(retries),
        "--input", `/work/${id}.json`, "--out", `/work/${id}_result.json`,
      ], { stdio: "ignore" });
      // Kill the script if it runs longer than the configured per-quote timeout.
      const timer = setTimeout(() => child.kill(), timeoutSeconds * 1000);
      child.on("close", () => { clearTimeout(timer); resolve(); });
    });
    if (!existsSync(resultHost)) return null;
    let parsed: any;
    try {
      parsed = JSON.parse(readFileSync(resultHost, "utf8"));
    } catch {
      return null;
    }
    if (!parsed) return null;
    // Report the real status (quoted / blocked / error) so the results page shows
    // what actually happened instead of leaving the carrier stuck on "pending".
    const hasQuote = !!parsed.quote_value;
    const premium = hasQuote ? Number(String(parsed.quote_value).replace(/[^0-9.]/g, "")) : undefined;
    const outcome: QuoteOutcome = {
      registry_id: src.registry_id,
      brand: src.brand,
      status: normalizeStatus(parsed.status, hasQuote),
      monthly_premium: premium,
      annual_premium: premium != null ? premium * 12 : undefined,
      quote_id: parsed.quote_number ?? undefined,
      coverage_notes: parsed.coverage
        ? Object.values(parsed.coverage).join(" | ")
        : parsed.error ? `Automated quote failed: ${String(parsed.error).slice(0, 120)}` : "Automated quote",
      confidence: hasQuote ? "medium" : "low",
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
  // Persist this website run into the history tables (fake vs real) so it shows on the
  // /history tabs, not just as an in-memory job.
  try {
    recordWebsiteRun(job);
  } catch (e) {
    console.error("recordWebsiteRun failed:", e);
  }
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
  const agg = { ...job, outcomes };
  // Attach the current carrier script's live % progress so the results page can show
  // how far the automation has gotten (per step) instead of only 'carrier n of N'.
  if (job.status === "running") {
    try {
      if (job.currentScriptId) {
        const progressPath = `/opt/quotedrive/work/${job.currentScriptId}_progress.json`;
        if (existsSync(progressPath)) {
          const p = JSON.parse(readFileSync(progressPath, "utf8"));
          (agg as any).progress_percent = p.percent;
          (agg as any).progress_label = p.label;
          (agg as any).progress_attempt = p.attempt;
        }
      }
    } catch { /* no progress file yet */ }
  }
  return agg;
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

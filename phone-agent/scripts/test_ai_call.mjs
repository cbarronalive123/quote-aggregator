#!/usr/bin/env node
// -----------------------------------------------------------------------------
// test_ai_call.mjs
//
// Test harness for the phone agent's AI voice quote feature.
//
// It places an OUTBOUND AI call (via the phone agent's POST /api/call -> Vapi) to
// YOUR phone, then prints a realistic "insurance agent" roleplay script so the
// person answering can act as a broker/agent and we can verify the AI collects
// everything needed for a quote. After the call it polls the phone agent and
// reports the structured quote the AI extracted and where the recording is stored.
//
// Usage:
//   node scripts/test_ai_call.mjs --to +15195550123
//   node scripts/test_ai_call.mjs --to +15195550123 --phone-agent http://localhost:3100
//   node scripts/test_ai_call.mjs --to +15195550123 --website http://localhost:3000
// -----------------------------------------------------------------------------
import process from "node:process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : def;
}

const TO = arg("--to", process.env.TEST_CALL_TO || "15194760578"); // default = applicant's number
const PHONE_AGENT = (arg("--phone-agent", process.env.PHONE_AGENT_URL) || "http://localhost:3100").replace(/\/$/, "");
const WEBSITE = (arg("--website", process.env.WEBSITE_URL) || "http://localhost:3000").replace(/\/$/, "");
const REGISTRY_ID = "test-call-001";
const BRAND = "TEST — manual AI quote";

// Applicant profile (mirrors the website intake form / personal_profile.db).
const CONTEXT = {
  source: "test_script",
  person: {
    first_name: "Corey",
    last_name: "Barron",
    email: "cormbar@msn.com",
    phone: "519-476-0578",
    date_of_birth: "1984-10-14",
    sex: "M",
    marital_status: "S",
    street_address: "10 Tecumseh Cres",
    city: "Kitchener",
    province: "Ontario",
    postal_code: "N2B 2T4",
  },
  vehicle: {
    year: 2012,
    make: "RAM",
    model: "1500 Big Horn",
    trim: "Quad Cab 4WD",
    vin: "1C6RD7GT9CS103678",
    owned: true,
    annual_km: 15000,
    commute_days: 5,
    commute_km: 15,
    winter_tires: true,
    anti_theft: true,
  },
  current_insurance: { insurer: "Coachman (SGI group)", via: "NFP Canada Corp", status: "expired 30-day binder" },
  coverage_benchmark: "$2M third-party liability, DCPD included, standard mandatory medical/rehab/attendant care, collision & comprehensive with $1,000 deductibles, OPCF 44R, no telematics",
};

// ----------------------------------------------------------------------------
// REAL-WORLD INSURANCE-AGENT ROLEPLAY SCRIPT (for the person answering the phone)
// ----------------------------------------------------------------------------
const ROLEPLAY = `
=== ROLEPLAY SCRIPT — the person ANSWERING plays the insurance agent/broker ===

The AI calls YOU. Pretend you're a licensed Ontario insurance broker at the carrier.
Goal: confirm the AI (1) discloses it's an automated assistant, (2) requests the quote,
(3) collects all the details below, (4) ends by reporting a structured quote.

Follow this flow and FEED THE AI THESE ANSWER VALUES:

1. Greeting + verify applicant:
   - Answer: "Hello, [carrier] insurance, how can I help?"
   - If the AI discloses it's automated and asks to continue, say: "Yes, that's fine to continue."
   - If asked to confirm the applicant, say: "Yes, the applicant is available if needed."

2. Coverage requested — confirm benchmark: "$2M liability, DCPD included, collision and
   comprehensive with $1,000 deductibles, OPCF 44R, no telematics." Say: "Yes, we can quote that package."

3. Give the QUOTE DETAILS the AI must capture (say these out loud):
   - Annual premium: $1,485.00
   - Monthly premium: $123.75
   - Quote / reference ID: "AI-QUOTE-TEST-001"
   - Coverage differences: "Standard AB is included; no additional income-replacement rider added."
   - Effective date: "2026-09-01"    Expiry: "2027-08-31"
   - Discounts: "Multi-policy 10% (conditional on bundling home), winter-tires 5%"
   - Validity: "Quote is valid for 30 days."

4. Close: ask "Anything else?" then "Thanks, goodbye."

AFTER the call, look below for the structured JSON the AI extracted and whether it got
all fields: annual_premium, monthly_premium, quote_id, coverage_notes, effective_date,
expiry_date, discounts, status.
`;

// ----------------------------------------------------------------------------
async function main() {
  console.log("=== AI QUOTE TEST CALL ===");
  console.log("Calling:      " + TO);
  console.log("Phone agent:  " + PHONE_AGENT);
  console.log("Website:      " + WEBSITE);
  console.log("Registry id:  " + REGISTRY_ID);
  console.log("");

  console.log(ROLEPLAY);
  console.log("");

  // 1. Place the outbound AI call.
  console.log("Placing call via " + PHONE_AGENT + "/api/call ...");
  let call;
  try {
    const r = await fetch(`${PHONE_AGENT}/api/call`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to: TO,
        registry_id: REGISTRY_ID,
        brand: BRAND,
        context: JSON.stringify(CONTEXT),
      }),
    });
    const j = await r.json();
    if (!r.ok) {
      console.error("FAILED to place call:", j.error || r.statusText);
      console.error("Check that the phone agent is running and VAPI_*/TWILIO_* are set.");
      process.exit(1);
    }
    call = j;
    console.log("Call initiated. Vapi call id:", call.vapi_call_id, "(status:", call.status + ")");
  } catch (e) {
    console.error("Could not reach phone agent at " + PHONE_AGENT + ":", e.message);
    console.error("Start it with:  cd phone-agent && npm start   (after filling .env)");
    process.exit(1);
  }

  // 2. Poll the phone agent for the finished call + extracted outcome.
  console.log("");
  console.log("Polling for the call result (Vapi webhook -> parseOutcome -> website DB) ...");
  const deadline = Date.now() + 180_000; // up to 3 minutes
  let found = null;
  while (Date.now() < deadline) {
    await sleep(5000);
    try {
      const r = await fetch(`${PHONE_AGENT}/api/calls`);
      if (r.ok) {
        const data = await r.json();
        const calls = data.calls || [];
        const match = calls
          .filter((c) => c.registry_id === REGISTRY_ID && c.brand === BRAND)
          .sort((a, b) => (b.timestamp || "").localeCompare(a.timestamp || ""))[0];
        if (match) {
          found = match;
          break;
        }
      }
    } catch {
      /* keep polling */
    }
  }

  console.log("");
  if (!found) {
    console.warn("Timed out waiting for the call result. Check the phone-agent logs / Vapi dashboard.");
    return;
  }

  console.log("=== CALL RESULT ===");
  console.log("Status:", found.status);
  console.log("Outcome notes:", found.outcome_notes || "—");

  if (found.outcome) {
    console.log("");
    console.log("Extracted quote (structured):");
    console.log(JSON.stringify(found.outcome, null, 2));
  } else {
    console.warn("No structured outcome parsed from the transcript. Review the call to see what the AI said.");
  }

  // Recording location. Prefer the outcome's path (website-relative /recordings/...)
  // over the phone agent's local absolute path.
  const rec = (found.outcome && found.outcome.recording_path) || found.recording_path || found.recording;
  console.log("");
  if (rec) {
    if (rec.startsWith("/")) {
      console.log("Recording stored ON THE WEBSITE SERVER:");
      console.log("  " + WEBSITE + rec);
    } else {
      console.log("Recording stored on the PHONE AGENT (fallback):");
      console.log("  " + PHONE_AGENT + "/" + rec);
    }
  } else {
    console.log("No recording was captured.");
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

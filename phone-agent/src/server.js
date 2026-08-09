require("dotenv").config();
const express = require("express");
const fs = require("fs");
const path = require("path");
const { buildSystemPrompt } = require("./prompts");
const { startOutboundCall, createAssistant } = require("./vapi");
const { downloadVapiRecording } = require("./recordingDownloader");
const { parseOutcome } = require("./parseOutcome");
const { saveCall, readCalls, RECORDINGS_DIR, listRecordings } = require("./recordStore");

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3100;
const WEBSITE_URL = process.env.WEBSITE_URL || "http://localhost:3000";
const LEGAL_NAME = process.env.PARTICIPANT_LEGAL_NAME || "Corey Barron";

// ---- Simple call-center UI (dark theme, matches website) ----
app.get("/", (_req, res) => {
  res.send(renderPage(readCalls(), listRecordings()));
});

app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "phone-agent" });
});

// ---- Initiate an outbound call ----
app.post("/api/call", async (req, res) => {
  const { to, registry_id, brand, context } = req.body || {};
  if (!to) return res.status(400).json({ error: "Missing 'to' number." });

  const apiKey = process.env.VAPI_PRIVATE_KEY;
  const assistantId = process.env.VAPI_ASSISTANT_ID;
  const from = process.env.TWILIO_FROM_NUMBER;
  const sid = process.env.TWILIO_ACCOUNT_SID;
  const authToken = process.env.TWILIO_AUTH_TOKEN;

  if (!apiKey || !assistantId || !from || !sid || !authToken) {
    return res.status(500).json({
      error:
        "Phone agent not configured. Set VAPI_PRIVATE_KEY, VAPI_ASSISTANT_ID, TWILIO_* in .env (see .env.example).",
    });
  }

  try {
    const dynamicVariables = {
      brand: brand || "the carrier",
      registry_id: registry_id || "",
      context: context || "",
    };
    const call = await startOutboundCall({
      privateKey: apiKey,
      assistantId,
      to,
      from,
      accountSid: sid,
      authToken,
      dynamicVariables,
      registryId: registry_id || undefined,
      brand: brand || undefined,
    });
    await saveCall({
      registry_id: registry_id || null,
      brand: brand || null,
      direction: "outbound",
      status: "callback_required",
      outcome_notes: "Outbound call initiated via Vapi.",
      vapi_call_id: call.id,
    });
    res.json({ ok: true, vapi_call_id: call.id, status: "initiated" });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ---- Vapi end-of-call webhook: record outcome + save recording locally ----
app.post("/webhooks/vapi/end-of-call", async (req, res) => {
  const body = req.body || {};
  const apiKey = process.env.VAPI_PRIVATE_KEY;
  const registryId = (body.metadata && body.metadata.registry_id) || null;
  const brand = (body.metadata && body.metadata.brand) || null;
  let localRecording = null;
  try {
    if (body.recordingUrl && apiKey) {
      localRecording = await downloadVapiRecording(body.recordingUrl, apiKey);
    }
  } catch (err) {
    console.error("recording download failed:", err.message);
  }

  // Upload the recording to the website server (public/recordings) so it is
  // stored and served from the deployed website, not just the phone agent.
  let recordingRel = null;
  if (localRecording) {
    const fileName = localRecording.split(/[\\/]/).pop();
    try {
      const buf = fs.readFileSync(localRecording);
      const r = await fetch(`${WEBSITE_URL}/api/recordings`, {
        method: "POST",
        headers: { "Content-Type": "audio/mpeg", "x-filename": fileName },
        body: buf,
      });
      if (r.ok) {
        const j = await r.json();
        if (j && j.path) recordingRel = j.path; // e.g. /recordings/vapi-123.mp3
      } else {
        console.error(`website recording upload failed: ${r.status}`);
      }
    } catch (err) {
      console.error("website recording upload failed:", err.message);
    }
    // Fallback: point at the phone agent's own /recordings static route.
    if (!recordingRel) recordingRel = `recordings/${fileName}`;
  }

  // Extract the structured quote the assistant produced (annual premium, quote_id, …).
  let outcome = null;
  try {
    outcome = parseOutcome(body.transcript, { registry_id: registryId, brand, recording_path: recordingRel });
  } catch (err) {
    console.error("outcome parse failed:", err.message);
  }

  const entry = await saveCall({
    registry_id: registryId,
    brand,
    direction: "outbound",
    status: (body.endedReason === "customer-did-not-answer") ? "unreachable" : (outcome?.status || "callback_required"),
    recording_path: localRecording,
    transcript: body.transcript || null,
    vapi_call_id: body.callId || body.id || null,
    outcome_notes: outcome?.outcome_notes || body.endedReason || null,
    outcome, // structured quote data, normalized
  });

  // Report the call record back to the website so the shared DB (calls table)
  // and the operator dashboard stay in sync.
  try {
    const r = await fetch(`${WEBSITE_URL}/api/calls`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: entry.id,
        registry_id: registryId,
        brand,
        direction: "outbound",
        status: entry.status,
        recording_path: recordingRel,
        transcript: body.transcript || null,
        outcome_notes: entry.outcome_notes || null,
        timestamp: entry.timestamp,
      }),
    });
    if (!r.ok) console.error(`website calls POST failed: ${r.status} ${await r.text()}`);
  } catch (err) {
    console.error("website calls POST failed:", err.message);
  }

  // Report the extracted quote back to the website so it lands on the aggregated
  // list for the /quotes page and any running aggregation job.
  if (outcome && registryId && brand) {
    try {
      const r = await fetch(`${WEBSITE_URL}/api/quote/phone-outcome`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(outcome),
      });
      if (!r.ok) console.error(`website outcome POST failed: ${r.status} ${await r.text()}`);
    } catch (err) {
      console.error("website outcome POST failed:", err.message);
    }
  }

  res.json({ ok: true, id: entry.id, outcome: outcome || null });
});

// ---- Static serving of saved recordings ----
app.use("/recordings", express.static(RECORDINGS_DIR));

// ---- List calls + recordings as JSON ----
app.get("/api/calls", (_req, res) => {
  res.json({ calls: readCalls(), recordings: listRecordings() });
});

app.listen(PORT, () => {
  console.log(`phone-agent listening on http://localhost:${PORT}`);
  console.log(`Recording folder: ${path.join(RECORDINGS_DIR)}`);
  if (!process.env.VAPI_PRIVATE_KEY) {
    console.log("NOTE: VAPI not configured. Set env vars to enable outbound calls (see .env.example).");
  }
});

// ---------- Tiny inline renderer (kept dependency-free) ----------
function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function renderPage(calls, recordings) {
  const rows = calls
    .map(
      (c) => `<tr>
      <td>${esc(c.brand || "—")}</td>
      <td>${esc(c.direction)}</td>
      <td><span class="badge">${esc(c.status)}</span></td>
      <td>${c.recording_path ? `<a href="/recordings/${esc(c.recording_path.split(/[\\/]/).pop())}">play</a>` : "—"}</td>
      <td>${esc(c.outcome_notes || "—")}</td>
      <td>${esc(c.timestamp)}</td>
    </tr>`
    )
    .join("");

  const recLinks = recordings
    .map((r) => `<li><a href="/recordings/${esc(r)}">${esc(r)}</a></li>`)
    .join("");

  return `<!doctype html><html><head><meta charset="utf-8"><title>Phone Agent</title>
<style>
  body{background:linear-gradient(135deg,#000 0%,#070912 60%,#0b1126 100%);color:#f5f6fa;font-family:system-ui,sans-serif;margin:0;padding:0;min-height:100vh}
  main{max-width:900px;margin:0 auto;padding:32px 24px}
  h1{font-size:22px}.muted{color:#7a8196;font-size:13px}
  .panel{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.09);border-radius:12px;padding:20px;margin-bottom:24px}
  .badge{display:inline-block;padding:3px 9px;border-radius:999px;font-size:11px;border:1px solid rgba(255,255,255,.09);color:#7f9cff}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{text-align:left;color:#7a8196;font-weight:600;font-size:11px;text-transform:uppercase;padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.09)}
  td{padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.05);color:#b6bccb}
  a{color:#7f9cff;text-decoration:none}
  input,select{width:100%;padding:9px 12px;border-radius:8px;border:1px solid rgba(255,255,255,.09);background:rgba(0,0,0,.35);color:#f5f6fa;font-size:14px;margin-bottom:12px}
  label{display:block;font-size:12px;color:#b6bccb;margin-bottom:4px}
  button{padding:9px 16px;border-radius:8px;border:none;background:linear-gradient(135deg,#4d6bff,#7f9cff);color:#fff;font-size:14px;cursor:pointer}
</style></head><body><main>
  <h1>All-Quote Phone Agent</h1>
  <p class="muted">Voice/callback agent. Outbound calls are placed via Vapi; recordings are saved to ./recordings and shown below. Configure VAPI_* and TWILIO_* in .env to enable live calls.</p>
  <div class="panel">
    <label>Destination phone (E.164, e.g. +15195550123)</label>
    <input id="to" placeholder="+1...">
    <label>Brand / route label</label>
    <input id="brand" placeholder="e.g. Coachman (via NFP)">
    <label>Context / registry_id</label>
    <input id="ctx" placeholder="coachman-001">
    <button onclick="placeCall()">Place outbound call</button>
    <p id="msg" class="muted"></p>
  </div>
  <div class="panel">
    <h2 style="font-size:15px;margin-top:0">Calls</h2>
    <table><thead><tr><th>Brand</th><th>Dir</th><th>Status</th><th>Recording</th><th>Outcome</th><th>Timestamp</th></tr></thead>
    <tbody>${rows || '<tr><td colspan="6" class="muted">No calls yet.</td></tr>'}</tbody></table>
  </div>
  <div class="panel">
    <h2 style="font-size:15px;margin-top:0">Recordings in ./recordings</h2>
    ${recLinks ? `<ul>${recLinks}</ul>` : '<p class="muted">None yet.</p>'}
  </div>
</main>
<script>
async function placeCall(){
  const to=document.getElementById('to').value.trim();
  const brand=document.getElementById('brand').value.trim();
  const ctx=document.getElementById('ctx').value.trim();
  const msg=document.getElementById('msg');
  if(!to){msg.textContent='Enter a destination number.';return;}
  msg.textContent='Placing call...';
  const r=await fetch('/api/call',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({to,brand,registry_id:ctx})});
  const j=await r.json();
  msg.textContent=j.ok?('Initiated: '+j.vapi_call_id):('Error: '+(j.error||'unknown'));
  setTimeout(()=>location.reload(),1500);
}
</script>
</body></html>`;
}

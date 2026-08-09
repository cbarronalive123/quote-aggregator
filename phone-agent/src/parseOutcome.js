// Extract the structured quote outcome from a Vapi end-of-call transcript.
//
// The assistant (src/prompts.js) is instructed to emit a JSON object at the end
// of the call. Vapi sends `transcript` either as an array of {role, message}
// turns or as a plain string. We flatten it, then scan for the last JSON object
// that contains the outcome keys (status / annual_premium / quote_id).

const OUTCOME_KEYS = ["status", "annual_premium", "monthly_premium", "quote_id", "coverage_notes"];

function toText(transcript) {
  if (typeof transcript === "string") return transcript;
  if (Array.isArray(transcript)) {
    return transcript
      .map((t) => (typeof t === "string" ? t : t?.message || t?.text || ""))
      .filter(Boolean)
      .join("\n");
  }
  return "";
}

function lastJsonObject(text) {
  if (!text) return null;
  let start = text.length;
  while ((start = text.lastIndexOf("{", start - 1)) !== -1) {
    let depth = 0;
    let inString = false;
    let escaped = false;
    for (let i = start; i < text.length; i++) {
      const ch = text[i];
      if (inString) {
        if (escaped) escaped = false;
        else if (ch === "\\") escaped = true;
        else if (ch === '"') inString = false;
        continue;
      }
      if (ch === '"') inString = true;
      else if (ch === "{") depth += 1;
      else if (ch === "}") {
        depth -= 1;
        if (depth === 0) {
          const candidate = text.slice(start, i + 1);
          try {
            const parsed = JSON.parse(candidate);
            if (parsed && typeof parsed === "object" && OUTCOME_KEYS.some((k) => k in parsed)) {
              return parsed;
            }
          } catch {
            // not valid JSON, keep scanning
          }
          break;
        }
      }
    }
  }
  return null;
}

function mapStatus(status) {
  const allowed = [
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
  return allowed.includes(status) ? status : "callback_required";
}

function num(v) {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = parseFloat(v.replace(/[$,]/g, ""));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

// Returns a normalized outcome object ready to POST back to the website, or null.
function parseOutcome(transcript, { registry_id, brand, recording_path } = {}) {
  const obj = lastJsonObject(toText(transcript));
  if (!obj) return null;

  const outcome = {
    registry_id,
    brand,
    status: mapStatus(obj.status),
    annual_premium: num(obj.annual_premium),
    monthly_premium: num(obj.monthly_premium),
    quote_id: obj.quote_id || null,
    coverage_notes: obj.coverage_notes || "",
    effective_date: obj.effective_date || null,
    expiry_date: obj.expiry_date || null,
    discounts: Array.isArray(obj.discounts) ? obj.discounts : [],
    outcome_notes: obj.outcome_notes || "",
    recording_path: recording_path || null,
    confidence: obj.status === "quoted_comparable" ? "high" : "medium",
  };
  return outcome;
}

module.exports = { parseOutcome };

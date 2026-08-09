// Vapi adapter — initiates outbound phone calls and creates an assistant.
// Provider-agnostic design: swap this file for a Retell/LiveKit/Pipecat adapter later.
// Vapi API: https://docs.vapi.ai/api-reference

const VAPI_BASE = "https://api.vapi.ai";

function authHeaders(key) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${key}`,
  };
}

async function createAssistant({ apiKey, name, systemPrompt }) {
  const res = await fetch(`${VAPI_BASE}/assistant`, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: JSON.stringify({
      name,
      model: {
        provider: "openai",
        model: "gpt-4o-mini",
        temperature: 0.3,
        messages: [{ role: "system", content: systemPrompt }],
      },
      voice: {
        provider: "elevenlabs",
        voiceId: "pNInz6obpgDQGcFmaJgB", // Adam — a clear, neutral voice
        stability: 0.5,
      },
      firstMessageMode: "assistant-speaks-first",
    }),
  });
  if (!res.ok) {
    throw new Error(`Vapi createAssistant failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

// Start an outbound call to a destination. Pass an assistantId (existing) or
// assistant config (inline) plus Twilio credentials for the telephony.
async function startOutboundCall({
  privateKey,
  assistantId,
  to,
  from,
  accountSid,
  authToken,
  dynamicVariables = {},
  registryId,
  brand,
}) {
  const body = {
    assistantId,
    customer: { number: to },
    phoneNumber: {
      provider: "twilio",
      twilioAccountSid: accountSid,
      twilioAuthToken: authToken,
      number: from,
    },
    phoneNumberId: undefined,
    // Metadata echoes back on the end-of-call webhook so we can attribute the
    // outcome to the right carrier (registry_id / brand).
    metadata: { source: "website-callback", registry_id: registryId || "", brand: brand || "" },
  };
  if (dynamicVariables && Object.keys(dynamicVariables).length) {
    body.assistantOverrides = { variableValues: dynamicVariables };
  }
  const res = await fetch(`${VAPI_BASE}/call/phone`, {
    method: "POST",
    headers: authHeaders(privateKey),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`Vapi startOutboundCall failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

module.exports = { createAssistant, startOutboundCall };

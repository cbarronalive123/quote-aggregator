const fs = require("fs");
const path = require("path");
const { recordingPath } = require("./recordStore");

// Download a remote recording (Vapi/Twilio artifact URL) into ./recordings and
// return the local path. No auth headers unless the provider requires them.
async function downloadRecording(url, filename, headers = {}) {
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`download failed: ${res.status} ${res.statusText}`);
  }
  const buffer = Buffer.from(await res.arrayBuffer());
  const dest = recordingPath(filename);
  fs.writeFileSync(dest, buffer);
  return dest;
}

// Vapi serves recordings behind an Authorization header.
async function downloadVapiRecording(url, apiKey) {
  const clean = url.replace("https://", "https://").replace(/\.vapi\.ai/, ".vapi.ai");
  const filename = `vapi-${Date.now()}.mp3`;
  return downloadRecording(clean, filename, {
    Authorization: `Bearer ${apiKey}`,
  });
}

module.exports = { downloadRecording, downloadVapiRecording };

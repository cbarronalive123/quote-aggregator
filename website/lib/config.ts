// Cross-project wiring. The phone agent runs as a separate service (phone-agent/).
// Override with the PHONE_AGENT_URL env var if the agent runs elsewhere.
export const config = {
  phoneAgentUrl: process.env.PHONE_AGENT_URL || "http://localhost:3100",
};

// Resolve a stored recording reference to a playable URL.
// - "/recordings/x.mp3"  -> same-site path (stored ON this website server).
// - "recordings/x.mp3"   -> served by the phone agent's /recordings route.
export function recordingUrl(recording?: string): string | undefined {
  if (!recording) return undefined;
  if (recording.startsWith("/")) return recording;
  return `${config.phoneAgentUrl}/${recording}`;
}

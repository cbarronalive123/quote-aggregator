# All-Quote Agent — Phone Agent

Separate voice/callback agent that reaches markets that won't quote online (broker lines,
non-standard, mutuals, HNW, residual market). Handles the compliance-safe disclosure opening,
gets recording consent, and saves call recordings to `./recordings`.

**Provider-agnostic by design.** Default adapter is **Vapi** (see `src/vapi.js`); swap the file
for Retell/LiveKit/Pipecat later. Free testing path: **Twilio free trial** (~75 voice minutes,
1 number, no credit card) for telephony + **Vapi** trial credits for the agent; **ngrok** (free)
exposes the local webhook for inbound callbacks.

## Run

```bash
npm install
cp .env.example .env      # then fill in VAPI_* and TWILIO_* credentials
npm start                 # http://localhost:3100
```

The built-in UI at `/` lets you place a test call and lists saved recordings.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/call` | Initiate an outbound call (`{ to, brand, registry_id, context }`) |
| POST | `/webhooks/vapi/end-of-call` | Vapi webhook → records outcome + downloads recording to `./recordings` |
| GET | `/api/calls` | List call records + recordings |
| GET | `/recordings/:file` | Serve a saved recording |

## Test an AI quote call (no real carrier needed)

Place an outbound AI call to your own phone and roleplay the insurance agent:

```bash
node scripts/test_ai_call.mjs --to +15195550123
```

The script prints a realistic broker/agent roleplay script for whoever answers, then
reports the structured quote the AI extracted and where the recording was saved.
Requires the phone agent running with `VAPI_*` and `TWILIO_*` configured.

## Where recordings are stored

- The phone agent first downloads the recording to `./recordings` (local).
- It then uploads it to the website server via `POST {WEBSITE_URL}/api/recordings`,
  which stores it at `website/public/recordings/<file>` and serves it at
  `/recordings/<file>` on the deployed website. This is the value stored on the
  `quote_outcomes` / `calls` rows so the `/quotes` play button points at the website.
- If the upload fails, it falls back to the phone agent's own `/recordings` route.

## Recordings

Call recordings are downloaded into `./recordings` (gitignored). The brief requires recordings
be **redacted** before inclusion in the submission — no VIN, licence, or full address, and only
kept when the other party consents to recording.

## Compliance (from the brief)

- Discloses automation at call start and identifies purpose (`src/prompts.js`).
- Asks for affirmative recording/transcription consent before recording.
- Never misrepresents as a licensed broker/agent/insurer/human applicant.
- Escalates to `manual_handoff` on identity/declaration/advice/consent requirements.
- No spoofing, no pressure, no repeated calls; stops on request.
- Test calls in the local/sandbox environment only — not production telephony.

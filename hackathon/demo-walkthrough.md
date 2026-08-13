# QuoteDrive — Demo Walkthrough

**File:** `hackathon/demo-walkthrough.md`

A narrative description of what was built and demonstrated for the Ontario All-Quote Agent Hackathon.

---

## Elevator pitch

I built **QuoteDrive** — a system that takes **one** set of Ontario auto insurance applicant details and reuses them everywhere: a deployed website, Playwright browser automations, a Flutter mobile app, a real outbound phone call to Allstate, and a simulated AI voice-agent phone call. All results flow back into one comparison dashboard.

---

## What I did (step by step)

### 1. Built and deployed the website (Next.js)

- Created a Next.js 15 web app with a comprehensive auto insurance intake form (~60 fields).
- Deployed it to a VPS so the mobile app and automation scripts could reach it over the internet.
- Built pages for: quote intake, live results with progress bar, quote history, carrier registry, automation settings, and call center.
- Wired a SQLite database (`quotedrive.db`) so every quote run is stored and reviewable later.
- Added **My profile** and **Fake profile** buttons so repeat testing doesn't hit carrier rate limits.

### 2. Automated carrier forms with Playwright + Docker

- Wrote Python Playwright scripts for three Ontario carriers: **belairdirect**, **Aviva**, and **Allstate**.
- Each script opens the carrier's real public quote form, fills every field from the submitted profile, and scrapes the returned premium.
- Created a **parent orchestrator** (`quote_runner/run_all_quotes.py`) that runs all three in sequence and writes results to the database.
- Packaged the scripts in a **Docker container** with Xvfb (virtual display), x11vnc, and noVNC so headed browsers run on a headless server — with live browser viewing via VNC tunnel.
- The website triggers the container on form submit and streams live progress (%) back to the results page.

### 3. Built the phone agent (Python + PyQt6 + ADB)

- Created a desktop PyQt6 app that controls a connected Android phone over **ADB**.
- Calls go out through the phone's own SIM/carrier (real minutes, not VoIP).
- Built an HTTP call server so the website can trigger outbound dials remotely (via SSH reverse tunnel).
- When Allstate's online quote is blocked from the server IP, the system automatically **calls Allstate's 1-800 sales line** on the connected cell phone as a fallback.
- Auto-records calls and pulls recordings back for review.

### 4. Built the mobile app (Flutter)

- Created a Flutter app that connects to the deployed website API.
- Same intake form as the website, optimized for mobile.
- **My profile / Fake profile** quick-fill buttons.
- AI speech-to-text assistant mode for hands-free form filling.
- Simulated incoming agent call UI (SSE from website).
- Results page and quote history.

### 5. Built the voice AI quote agent

- Created a voice-enabled PyQt6 app that simulates an insurance broker phone call.
- Uses **faster-whisper** (STT), **Kokoro TTS**, and **Ollama LLM** for natural conversation.
- You speak as the broker; the AI answers from the applicant profile in spoken English.
- Detects quote numbers (monthly, annual, reference ID) from the conversation.
- Saves structured call notes and quote outcomes as JSON.
- Includes a test-run script that simulates a full Allstate broker call end-to-end.

---

## Demo flow (what to show)

1. **Open the website** → fill the quote form (or click Fake profile).
2. **Click "Get my quotes"** → watch live progress as Playwright fills belairdirect, Aviva, and Allstate forms in the Docker container.
3. **See results** → premiums appear per carrier with annual/monthly price and quote reference ID.
4. **Allstate fallback** → if online quote is blocked, the phone agent dials Allstate's sales line on a connected Android phone and records the call.
5. **Mobile app** → show the same form on Flutter, fill via AI assistant, view results.
6. **Voice AI agent** → run the quote agent GUI, speak as a broker, hear the AI answer profile questions and capture a quote.
7. **History** → review every past run in the quote history page.

---

## Tech stack summary

| Component | Stack |
|-----------|-------|
| Website | Next.js 15, React 19, TypeScript, SQLite |
| Mobile app | Flutter (Dart), Android/iOS |
| Browser automation | Python, Playwright, Docker, Xvfb, noVNC |
| Phone agent | Python, PyQt6, ADB, HTTP server |
| Voice AI | Python, PyQt6, faster-whisper, Kokoro TTS, Ollama, optional RVC |
| Database | SQLite (`quotedrive.db`) |
| Deployment | VPS (Node.js website + Docker quote container) |

---

## Key integrations

```
Website form submit
    ├──▶ Docker container → Playwright → 3 carrier forms → premiums → DB
    ├──▶ Phone agent (ADB) → Allstate 1-800 call → recording → DB
    ├──▶ Mobile app (SSE) → simulated agent call
    └──▶ Voice AI agent → simulated broker Q&A → quote capture → JSON
```

All paths share the **same canonical profile schema** so one intake fills every channel.

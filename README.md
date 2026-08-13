# QuoteDrive — Ontario All-Quote Agent

An end-to-end insurance quote aggregation prototype for Ontario private-passenger auto insurance. One intake form fans out to multiple carriers — via browser automation, phone fallback, and voice AI — and stores comparable results in a shared database.

Built for the **Ontario All-Quote Agent Hackathon** (August 2026).

## Architecture overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│  Next.js Website │────▶│  Quote Runner    │────▶│  Playwright Scripts     │
│  (intake form)   │     │  (orchestrator)  │     │  belair / aviva / allstate│
└────────┬────────┘     └──────────────────┘     └─────────────────────────┘
         │
         ├──────────────────▶ Flutter Mobile App (same form + AI assistant)
         │
         ├──────────────────▶ Phone Agent (PyQt6 + ADB → real cell call)
         │
         └──────────────────▶ Voice AI Agent (STT/TTS/LLM simulated broker call)
```

## Projects in this repo

### 1. Website (`website/`)

**What it does:** Central hub for quote intake, live aggregation progress, results comparison, quote history, carrier registry, and automation settings. Submits one canonical profile to all carriers and merges premiums into a sortable results table. When Allstate's online quote is blocked (datacenter IP), triggers a phone fallback via the phone agent.

**Tech stack:**
- **Framework:** Next.js 15 (App Router), React 19, TypeScript
- **Styling:** CSS modules / global CSS (dark dashboard theme)
- **Database:** SQLite (`quotedrive.db` via `node:sqlite`) — not committed; seed with `node website/scripts/seed-db.mjs`
- **API routes:** REST endpoints for quote submission, profile management, call SSE, phone outcomes, history, settings
- **Deployment:** Node.js server (VPS-compatible)

**Key pages:** `/quote` (intake), `/quotes` (live results), `/history`, `/settings`, `/registry`, `/calls`

---

### 2. Mobile app (`mobile/`)

**What it does:** Flutter companion app that connects to the website API over the network. Provides the same quote intake form with "My profile" / "Fake profile" quick-fill, an AI speech-to-text assistant mode, simulated incoming agent call UI (SSE), quote results, and run history.

**Tech stack:**
- **Framework:** Flutter (Dart)
- **Platforms:** Android, iOS
- **HTTP client:** Custom `api_client.dart` → website REST API
- **Config:** `--dart-define=API_BASE_URL=...` (defaults to `http://localhost:3000`)

---

### 3. Quote runner + Playwright scripts (root + `quote_runner/`)

**What it does:** Parent orchestrator (`quote_runner/run_all_quotes.py`) loads a profile from the website or a JSON file, then runs three carrier automations in sequence — **belairdirect**, **Aviva**, and **Allstate** — writing premiums back to `quotedrive.db`. Each script uses Playwright to open the carrier's real quote form, fill every field from the shared profile schema, and scrape the returned rate. Designed to run headless in a Docker container with Xvfb + optional noVNC for live viewing.

**Tech stack:**
- **Language:** Python 3.11+
- **Browser automation:** Playwright (Chromium, persistent profiles for Aviva/Allstate stealth)
- **Shared params:** `params_loader.py` + `people/dummy.json` (test data)
- **Container:** Dockerfile in `server_setup/` (not committed — see local docs)
- **Output:** SQLite `quote_outcomes` table + JSON results

**Scripts included:**
| Script | Carrier |
|--------|---------|
| `belairdirect_auto_quote.py` | belairdirect (Intact) |
| `aviva_auto_quote.py` | Aviva Direct |
| `allstate_auto_quote.py` | Allstate |
| `*_headless.py` | Headless variants |
| `quote_runner/run_all_quotes.py` | Parent orchestrator |

---

### 4. Phone agent (`phone-agent/`)

**What it does:** Desktop PyQt6 app + HTTP call server that dials carrier phone numbers on a connected Android phone via ADB (uses the phone's SIM/carrier minutes). The website triggers outbound calls (e.g. Allstate 1-800 fallback) through an SSH reverse tunnel. Supports auto-recording and pulling recordings back to the server.

**Tech stack:**
- **Language:** Python 3.11+
- **GUI:** PyQt6 (`app.py`)
- **HTTP server:** `call_server.py` (stdlib `http.server`)
- **Phone control:** ADB via `backend/phone.py` (dial, hangup, record, pull recordings)
- **Integration:** Website `POST` to phone agent URL → ADB dial on physical device

---

### 5. Voice AI (`voice_ai/`)

**What it does:** Two related systems:
1. **Desktop voice chatbot** — general-purpose STT/TTS/LLM voice assistant with optional RVC voice conversion
2. **Auto Quote Agent** — voice-enabled PyQt6 app that simulates an insurance broker call: you speak as the broker, the AI answers from the applicant profile in natural spoken English, detects quote numbers from the conversation, and saves structured outcomes

**Tech stack:**
- **Language:** Python 3.11+
- **GUI:** PyQt6
- **STT:** faster-whisper
- **TTS:** Kokoro TTS
- **LLM:** Ollama (qwen3:4b default)
- **Voice conversion:** RVC (optional, `rvc_server.py`)
- **Quote logic:** Intent resolver, profile loader, conversation engine, quote outcome extractor

**Run:**
```bash
cd voice_ai
pip install -r requirements.txt
python main.py                          # general voice assistant
python auto_quote_agent/quote_agent_gui.py  # quote agent simulation
```

Copy `auto_quote_agent/profile.example.json` → `profile.json` locally with your test data (never commit real PII).

---

### 6. Hackathon materials (`hackathon/`)

Briefs, challenge deck, and demo walkthrough documentation.

---

## Quick start

### Website
```bash
cd website
npm install
node scripts/seed-db.mjs    # creates website/data/quotedrive.db
npm run dev                  # http://localhost:3000
```

### Run a single carrier script (test)
```bash
python belairdirect_auto_quote.py --headed --input people/dummy.json
python aviva_auto_quote.py    --headed --input people/dummy.json
python allstate_auto_quote.py --headed --input people/dummy.json
```

### Run all three (parent orchestrator)
```bash
python quote_runner/run_all_quotes.py --profile fake --website-url http://localhost:3000
```

### Mobile app
```bash
cd mobile
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:3000   # Android emulator
```

### Phone agent
```bash
cd phone-agent
pip install -r requirements.txt
python call_server.py    # HTTP trigger on :8765
python app.py            # PyQt6 GUI
```

---

## Privacy & security

This repo intentionally excludes:
- Personal profiles, real applicant data, and credentials
- Server deployment configs, IP addresses, and SSH keys
- Browser session profiles, evidence screenshots, and call recordings
- Other carrier scripts beyond the three working automations

Use `people/dummy.json` or the website's **Fake profile** button for testing.

---

## License

Prototype / hackathon submission. Not licensed for production use.

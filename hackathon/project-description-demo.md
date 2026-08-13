# QuoteDrive — Project Description & Demo

An Ontario All-Quote Agent demo that takes **one** set of applicant details and reuses them to
request auto-insurance quotes across multiple carriers — online and by phone — and stores the
results for later review.

## What I built (high level)

- **Next.js website** — a clean intake form + live results + history. I deployed it to a VPS.
- **Playwright / Docker automation** — a Docker container with a Python script that uses
  Playwright to open each carrier's real quote form and fill it in automatically with the
  submitted details, then scrape the returned rate.
- **Python (PyQt6) phone app** — a desktop app that talks to a connected Android phone over ADB.
- **Mobile app (Flutter)** — a phone app that fills the same form and shows results.
- **Automated phone call to Allstate** — when Allstate's online quote is gated from the server
  IP, the system places a real phone call to Allstate's sales line through the phone app on a
  connected cell phone to get a quote.
- **Simulated AI-agent phone call** — an in-app "phone call" where the app runs an AI voice agent
  (text-to-speech + speech-to-text) that asks the intake questions and the user answers as the
  insurance agent.

## How the pieces fit

1. **Website (Next.js)** — the single intake form. One set of details in, reusable everywhere.
2. **Docker + Python + Playwright** — runs the auto-quote scripts (Belairdirect, Aviva, Allstate)
   in headed/minimized mode, fills each carrier's form, and pulls the real premium back into the
   results. Live progress (%) is shown while it works.
3. **Phone agent (PyQt6 + ADB)** — dials a carrier (e.g. Allstate) on a real Android phone and can
   auto-record the call.
4. **Mobile app (Flutter)** — the same form on the phone, with "My profile" / "Fake profile"
   quick-fill, an AI speech-to-text assistant, and a results + history view.
5. **AI-agent call simulation** — a simulated call in the app where the AI agent speaks the intake
   questions and the user (as the agent) answers with the quote details.

## Demo walkthrough

- Fill the quote form once (manual, or click **My profile** / **Fake profile** to pre-fill).
- Click **Get my quotes**.
- The system runs the Python/Playwright scripts in the Docker container, fills each carrier's
  form, and streams live progress.
- Results are shown per carrier with the annual/monthly premium and quote/reference ID.
- If Allstate is blocked online, the phone agent calls Allstate's sales line on a connected phone
  and records the call.
- Optionally, run the in-app AI-agent call to practice/collect a quote by voice.
- Review every run later in **Quote history** (My profiles vs Fake profiles tabs).

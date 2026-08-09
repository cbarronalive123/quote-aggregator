# Ontario All-Quote Prototype

Aggregator prototype for Ontario private-passenger auto insurance quotes. One intake
form fans out to multiple sources and lists the results, quote-aggregator style.

This repo shares only the **app**, **website**, **phone agent**, and the **working
auto-quote scripts**. Personal data, databases, credentials, and evidence are
intentionally **not** included.

## Contents
- `website/` — Next.js web app (intake form, aggregation, results). Reads/writes a
  shared `quotedrive.db` (not committed; seed via `node website/scripts/seed-db.mjs`).
- `mobile/` — Flutter app that connects to the website over the internet and answers
  the in-app simulated agent call via SSE.
- `phone-agent/` — outbound-call service (used for broker/agent callbacks).
- `desjardins_auto_quote.py`, `allstate_auto_quote.py` — headless browser scripts that
  return a real-time `$` auto quote. Shared params loader: `params_loader.py`.
- `people/dummy.json` — dummy test data for the scripts (not a real person).

## Aggregation behavior
On form submit (`POST /api/quote`), the server does **not** call broker phone numbers.
It creates ONE in-app call session that the mobile app picks up over the internet
(`/api/call/sse`), and separately runs the `$` auto-quote scripts headless, merging
their premiums into the results list.

## Run the scripts (test)
```
python desjardins_auto_quote.py --headed --input people/dummy.json
python allstate_auto_quote.py   --headed --input people/dummy.json
```

# All-Quote Agent — Website

Operator console for the Ontario All-Quote Agent Challenge. Next.js (App Router) acting as
both frontend and backend. Dark theme: pure-black diagonal gradient to near-black blue with
white/grey text and blue accents.

## Run

```bash
npm install
node scripts/seed-db.mjs   # build the unified quotedrive.db from the repo sources
npm run dev                # http://localhost:3000
```

The site reads from the unified SQLite database (`data/quotedrive.db`, built-in `node:sqlite`)
instead of hardcoded data. Reseed anytime the underlying sources change:
`node scripts/seed-db.mjs`. Override the DB path with the `QUOTEDRIVE_DB` env var.

## Pages

- `/` — Overview + latest quotes
- `/registry` — Market registry (seeded from the brief's Appendix A)
- `/quotes` — Comparison table (coverage differences before price)
- `/calls` — Call center: routes needing a phone call, linked to the phone-agent
- `/evidence` — Redacted evidence store

## Phone-agent wiring

Routes that need a callback link to the separate `phone-agent` service. Point the website at it
with the `PHONE_AGENT_URL` env var (default `http://localhost:3100`):

```bash
PHONE_AGENT_URL=http://localhost:3100 npm run dev
```

Demo data lives in `lib/data.ts`; the real registry/profile come from the repo's SQLite DBs.

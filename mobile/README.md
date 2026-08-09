# All-Quote Agent — Mobile App (Flutter)

Flutter client for the Ontario All-Quote Agent. It renders **the same intake form
the website uses** (fetched live from the website's `/api/form-schema`), offers an
**AI-assisted mode** where the app asks you the intake questions one at a time, and
on submit **runs a free in-app simulated AI voice call** before showing the results.

## What it does

1. **Connects to the website backend** (Next.js API on the `website/` project).
2. **Manual form** — identical fields/sections to the website's `QuoteForm.tsx`.
3. **AI assistant** — the app asks questions to fill the form (voice via
   `speech_to_text` + `flutter_tts`).
4. **Simulated AI phone call (free, no phone network)** — on submit the server
   pushes an "incoming call" to the app over the internet (SSE). The app shows a
   ringing screen with **Answer / End**; the AI requester speaks each line (TTS),
   you answer as the insurance agent (speech-to-text), and the server extracts the
   quote details from your replies and records them.
5. **Aggregation** — after the call it polls `/api/quote` and shows the returned
   quotes sorted by annual cost, with coverage differences surfaced.

## Prerequisites

- Flutter SDK 3.x (install from https://flutter.dev)
- The website backend running: `cd website && npm install && npm run dev`
  (serves on `http://localhost:3000`)

## Run

```bash
cd mobile
flutter create .          # generates android/ ios/ web/ platform scaffolding
flutter pub get
flutter run
```

The app is pointed at the **deployed** website backend (`http://45.137.194.227:31207`)
by default. Override with `--dart-define=API_BASE_URL` if needed:

| Target             | API_BASE_URL              |
|--------------------|---------------------------|
| Deployed server    | `http://45.137.194.227:31207` |
| Android emulator   | `http://10.0.2.2:3000`    |
| iOS simulator      | `http://localhost:3000`   |
| Physical device    | `http://<your-lan-ip>:3000` |

> `flutter create .` generates the platform folders. It keeps the existing
> `lib/`, `pubspec.yaml`, and `analysis_options.yaml`, so no Dart code is lost.

## Backend endpoints used

| Method | Path               | Purpose                                    |
|--------|--------------------|--------------------------------------------|
| GET    | `/api/form-schema` | Fetch the intake form sections/fields       |
| POST   | `/api/quote`       | Start aggregation (with `simulate:true` for the in-app call), returns a `job_id` |
| GET    | `/api/quote?id=`   | Poll aggregation progress + results         |
| POST   | `/api/assistant`   | One AI-assist turn (asks/fills questions)   |
| GET    | `/api/call/sse?job_id=` | Server pushes the in-app call (SSE events) |
| POST   | `/api/call`        | Control the call: `{action: answer\|reply\|end, job_id, text}` |

All endpoints are live on the deployed server (`http://45.137.194.227:31207`).

Optional: set `OPENAI_API_KEY` on the website for LLM-driven question parsing;
without it the assistant uses a built-in keyword extractor so it still works.

## Project layout

```
lib/
  main.dart            # app + home (choose AI assistant or manual form)
  config.dart          # API_BASE_URL
  models.dart          # mirrors website form + quote schemas
  api_client.dart      # HTTP client + SSE call stream
  form_page.dart       # manual intake form (same fields as website)
  assistant_page.dart  # AI asks questions to fill the form
  incoming_call_page.dart # free in-app simulated AI voice call (Answer/End)
  results_page.dart    # polls aggregation, shows quotes
```

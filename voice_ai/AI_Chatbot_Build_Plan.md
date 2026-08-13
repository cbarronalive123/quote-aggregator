# AI Voice Chatbot — Build Plan (PyQt6 Desktop App)

**Created:** 2026-08-11
**Hardware:** RTX 3060, 12 GB VRAM, **Windows** — but assume only **~6 GB VRAM free** (OS + other apps consume the rest).
**Goal:** A local, free, open-source desktop app where the user types or speaks, the AI replies in text, and speaks back with a selectable/cloneable voice.

---

## 1. What we're building (feature list)
A single PyQt6 desktop application with:

1. **Chat window** — type a message OR press the microphone to speak; send to the AI; the AI replies in text **and** in voice.
2. **Microphone button** — click to record your voice, auto-stop, transcribe (STT), and send as a message.
3. **Settings → Models** — list of models to **choose from and download** (LLM, STT, TTS). Bare-minimum defaults are **pre-downloaded** so the app works out of the box.
4. **Settings → Voices** — a **checkbox list of voices** to enable on the front end, plus a voice picker in the chat.
5. **Voice cloning** — clone a voice from an uploaded reference audio file.
6. **Popular voices** — ~10 curated voices (some character-styled, some professional).
7. **Professional voices** — **at least 3** clear, trustworthy voices for AI agents that talk on the phone / do insurance quotes.

---

## 2. Hardware & VRAM budget (the hard constraint)
Only **~6 GB VRAM is reliably free** on this Windows box. Every model must fit inside that, ideally with headroom for the OS/UI. Budget:

| Role | Model (default) | Approx VRAM | Notes |
|------|-----------------|-------------|-------|
| **LLM** | Llama 3.2 **3B** (Q4_K_M) | ~2.0 GB | Fits easily; 8B would need ~4.5 GB (too tight with TTS) |
| **STT** | faster-whisper **small** (or NVIDIA **Parakeet** 0.6B) | ~0.5–1.0 GB | Run STT on GPU then **unload** to free VRAM; Parakeet can even run on CPU |
| **TTS (default)** | **Kokoro-82M** | ~0.15 GB (CPU-capable) | Near-zero VRAM; leaves room for the LLM |
| **TTS (cloning, optional)** | **XTTSv2** or **Chatterbox** (non-Turbo) | ~4–5 GB | Load **on-demand only** when cloning; unload after |
| **Total (default run)** | | **~3 GB** | Comfortable inside 6 GB |

**Rules to stay in budget:**
- Load **one heavy model at a time**; unload STT/TTS when not in use.
- Default TTS = Kokoro (tiny). Cloning models (Chatterbox/XTTS) are loaded only when the user is actively cloning or using a cloned voice.
- On Windows, install CUDA-matched PyTorch **first** (see §6).

---

## 3. Tech stack
- **UI:** PyQt6
- **LLM:** Ollama (local server) + **Llama 3.2 3B** (default), downloadable from settings.
- **STT:** `faster-whisper` (small/turbo) — OpenAI-compatible, fast on CUDA.
- **TTS:** `kokoro` (default, Apache 2.0, presets + voice blending); `TTS` (Coqui XTTSv2) or **Chatterbox** for cloning (loaded on demand).
- **Voice cloning:** XTTSv2 (6s reference) / Chatterbox (one-shot) — via Coqui TTS / Chatterbox server.
- **Audio:** `sounddevice` (mic capture), `soundfile`/`numpy` (wave I/O), `pyaudio` fallback.
- **Threading:** PyQt `QThread`/`QThreadPool` so the UI never freezes during inference/recording.

---

## 4. Architecture (folder layout)
```
voice_ai/
├─ main.py                 # Entry point; launches the PyQt app
├─ requirements.txt
├─ app/
│  ├─ window.py            # Main window (chat + tabs)
│  ├─ chat_widget.py       # Chat bubble UI (text in/out)
│  ├─ mic_widget.py        # Microphone record button + waveform
│  ├─ settings_widget.py   # Models + Voices tabs
│  ├─ model_manager.py     # Download/select LLM, STT, TTS models; VRAM tracking
│  ├─ llm.py               # Ollama client (text generation)
│  ├─ stt.py               # faster-whisper transcription
│  ├─ tts.py               # Kokoro/XTTS/Chatterbox synthesis
│  ├─ cloner.py            # Voice cloning from reference audio
│  └─ voices.py            # Voice catalog + checkboxes + professional tags
└─ models/                 # Downloaded models (LLM, STT voices, cloned .pt files)
   ├─ voices/              # preset + cloned voice files
   └─ cloned/
```
Each module is independent so STT/TTS/LLM can be loaded/unloaded separately to manage the 6 GB budget.

---

## 5. Feature implementation detail

### 5.1 Chat window
- QTextEdit for input; Enter to send; Shift+Enter for newline.
- Rendered chat history (user = right, AI = left). Sending triggers the **pipeline**:
  `user text → LLM → reply text shown in UI → TTS → audio played`.

### 5.2 Microphone (STT)
- Mic button starts/stops recording (hold-to-talk or toggle). Captures via `sounddevice`.
- On stop → transcribe with faster-whisper → text appears in the input box (editable) → user presses send.
- Option: **auto-send** after transcription (toggle in settings).

### 5.3 Models settings (download & choose)
- Tab lists: **LLM**, **STT**, **TTS**.
- For each, a dropdown of available models + a **Download** button (streams from Hugging Face / Ollama with a progress bar) and a **Select/Unload** toggle.
- **Bare-minimum defaults are bundled** so the app runs immediately (§6).

### 5.4 Voices settings (checkbox list)
- Checkbox list of every available voice.
- **Checked** voices appear in the chat's voice picker dropdown; unchecked are hidden.
- A **"Set default voice"** option; preview button (plays a sample line).
- Professional voices are flagged with a badge and pinned at the top.

### 5.5 Voice cloning
- Tab to upload a **.wav/.mp3** reference (10–30 s of clean speech recommended).
- Name the clone → generate a voice file (XTTS/Chatterbox) → it appears in the Voices list as a normal (checked) voice.
- Cloning loads the heavier model **on demand**, then unloads it.

### 5.6 Popular & professional voices (10 + 3 professional)
Curated catalog (from Kokoro-82M + XTTS presets):

**Popular / character-style (7):**
1. `am_michael` — US male, calm, deep (authority)
2. `am_onyx` — US male, deep warm (movie-trailer feel)
3. `am_fenrir` — US male, rough/upbeat (menacing/action character ≈ "Terminator" vibe)
4. `am_puck` — US male, energetic (bubbly character)
5. `af_bella` — US female, warm conversational
6. `af_heart` — US female, friendly (community favorite)
7. `bf_emma` — British female, warm

**Professional (3+) — for phone/insurance agents:**
8. `bm_george` — British male, **Professional** ✓
9. `bm_daniel` — British male, **Professional** ✓
10. `bm_lewis` — British male, **Professional** ✓
11. `bf_lily` — British female, **Professional** ✓
12. `am_adam` — US male, **Professional** ✓ (broadcast)
13. `af_sarah` — US female, clear & trustworthy

> **On "Terminator / Robin Williams":** no legitimate open model ships real celebrity voices (legal/ethical). `am_fenrir`/`am_onyx` give the deep, authoritative "character" feel. True celebrity cloning would need your own reference audio and your own consent/licensing — I recommend avoiding it for a real product.

---

## 6. Setup steps (Windows, CUDA)
1. Install Python 3.10–3.12 + Git + FFmpeg (add to PATH).
2. Create venv; **install CUDA PyTorch first** (critical on Windows to avoid CUDA-not-found):
   `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121`
3. `pip install -r requirements.txt` (PyQt6, faster-whisper, kokoro, sounddevice, soundfile, numpy, ollama).
4. Install & run **Ollama** (`ollama pull llama3.2:3b`).
5. Run `python main.py`.

---

## 7. Default (bundled) bare-minimum models
So the app "just works" on first launch:
- **LLM:** Llama 3.2 3B (Q4_K_M) via Ollama (auto-pulled on first run if missing).
- **STT:** faster-whisper **small** (or Parakeet 0.6B) — auto-downloaded once.
- **TTS:** **Kokoro-82M** + its default voices — tiny (~170 MB), auto-downloaded once.
- **Cloning:** XTTSv2 / Chatterbox downloaded **lazily** only when the user first tries to clone.

---

## 8. Milestones (build order)
1. **M0 — Skeleton:** PyQt6 window + tabs + chat UI; model_manager loads Kokoro + whisper + Ollama. *(App runs, type→AI→text reply.)*
2. **M1 — Voice out:** TTS integration; voice picker; audio playback; Voices checkbox tab. *(AI talks back.)*
3. **M2 — Voice in:** microphone widget; faster-whisper; auto-send. *(Full spoken conversation.)*
4. **M3 — Models tab:** dropdowns + download buttons + unload/load (VRAM management).
5. **M4 — Voice cloning:** clone UI (upload → clone → add to voice list).
6. **M5 — Polish:** professional voice badges, preview, default-voice setting, error handling, packaging (`pyinstaller`).

---

## 9. Risks & constraints
- **VRAM (6 GB):** solved by loading one heavy model at a time + Kokoro for default TTS. If you later add a 3090, you can default to Chatterbox/8B LLM easily (same code).
- **Windows/Triton:** Chatterbox/Fish GPU accel can be painful on Windows. Keep cloning on **XTTSv2** (works well on Windows/CUDA) and keep Kokoro as the always-on TTS.
- **Latency:** Kokoro is faster than real-time; the LLM (3B) is fast. Expect near-instant voice replies.
- **Celebrity voices:** legal/ethical limits — use character presets, not real-person clones.

---

## 10. Model choice rationale (from earlier research)
- **Kokoro-82M** (Apache 2.0) = best free default TTS; tiny VRAM, fast, has professional voices.
- **XTTSv2** = gold standard for open-source **voice cloning** on Windows/low-VRAM; 6 s reference.
- **Chatterbox** = higher-quality one-shot clone, but heavier; keep optional.
- **faster-whisper** = best STT balance on CUDA (avoid whisper.cpp, less accurate).
- **Ollama + Llama 3.2 3B** = simplest local LLM that fits 6 GB alongside TTS.

**End state:** a fully local, free, open-source PyQt6 voice-chat app that types and talks back, with model management, selectable/professional voices, and voice cloning — all running comfortably on a 3060 with ~6 GB free VRAM.

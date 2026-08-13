# Voice AI Research Report
**Date:** August 11, 2026
**Goal:** Find the best free & open-source voice AI / voice-cloning / verbal chatbot tools that run on an RTX 3060 GPU (12GB VRAM), for a project where the user talks to the app and it talks back verbally.
**GPU considered:** RTX 3060 (12GB) — researching whether it's sufficient vs RTX 3090 (24GB).

---

## Website 1: Google Search (site:reddit.com best open source voice cloning AI local 3090)
**URL:** https://www.google.com/search?q=site:reddit.com+best+open+source+voice+cloning+AI+local+3090
**Accessed:** 2026-08-11

Surfaced Reddit (r/LocalLLaMA, r/LocalLLM, r/StableDiffusion) discussions on local, open-source voice cloning/TTS. Key tools people recommend:

- **Vibevoice** — Very high quality, but *slow*. On a 3090, the Gradio interface starts streaming audio after ~15 seconds. Quality-first, not real-time.
- **Fish Audio S2** — Cited as the "top answer" for the best local, expressive TTS. Notable for *freeform emotion tags* (very impressive control).
- **XTTSv2 (Coqui)** — Very fast; fine-tuning is the current recommended path for voice cloning. Handles cloning from short audio samples and runs on free Google Colab GPUs (so it runs on low-VRAM). Good candidate for a 3060.
- **Qwen3-TTS + Whisper** — Open-source, local-first voice-cloning "studio". Good cloning from seconds of audio, low latency, fully open.
- **Chatterbox Turbo** — Open-source TTS with *instant voice cloning from ~5 seconds of audio* and **<150ms time-to-first-sound**. Designed for low latency (great for a talking chatbot).
- **Chatterbox TTS (ResembleAI)** — One of the most accessible and highest-quality voice-cloning models.
- **Kokoro** — Lightweight TTS with voice *mixing* and adaptation (e.g. via Kokoro-FastAPI, supports combinations like "bf_lily+af_nicole(2)"). Very small footprint.
- **Moss TTS 1.5 (8B)** — Called "the currently best voice cloning" model (post from Jun 2, 2026). Larger (8B params).
- **Qwen Voice Clone** — Part of the Qwen ecosystem for voice cloning.

### Notable Reddit threads found:
1. **"Best Open Source Voice Cloning if you have lots of..."** (r/LocalLLaMA, ~4 months ago) — Vibevoice discussion; noted slow on 3090.
2. **"What is The best and expressive AI TTS (running locally?)"** (r/LocalLLaMA, 50+ comments) — Top answer: **Fish Audio S2**.
3. **"Fastest open source TTS for VoiceCloning for real time responses on Nvidia 3090"** (r/LocalLLaMA) — **XTTSv2** cited as very fast.
4. **"I built an open-source, local-first voice cloning studio (Qwen3-TTS + Whisper)"** (r/LocalLLaMA, 200+ comments).
5. **"Chatterbox Turbo - open source TTS. Instant voice cloning..."** (r/LocalLLaMA, 40+ comments).
6. **"Open Source Voice Cloning at 16x real-time: Porting Chatterbox TTS..."** (r/LocalLLaMA) — Chatterbox ported for 16x real-time speed.
7. **"Best TTS for Google Colab? Where I can clone my own voice"** (r/LocalLLM) — **XTTS v2** recommended; runs on free Colab GPUs.
8. **"Looking for High-Quality Open-Source Local TTS..."** (r/LocalLLaMA) — Kokoro voice mixing mentioned.
9. **"Moss tts 1.5 8b Examples... currently best voice cloning"** (r/LocalLLaMA, Jun 2 2026).
10. **Qwen Voice Clone** demos (r/StableDiffusion, 2026).

### Early takeaway for a talking chatbot (STT → LLM → TTS):
For **real-time verbal conversation**, the best fits so far are **Chatterbox Turbo** (instant cloning, <150ms TTFS), **XTTSv2** (fast, fine-tunable, low VRAM), **Kokoro** (tiny footprint), and **Fish Audio S2** (best quality/expression). These all run on modest GPUs, so a 3060 looks viable. **Vibevoice** is quality-first but too slow for real-time chat.

---

## Website 2: Google Search (best open source voice AI local chatbot tts stt RTX 3060 2026)
**URL:** https://www.google.com/search?q=best+open+source+voice+AI+local+chatbot+tts+stt+RTX+3060+2026
**Accessed:** 2026-08-11

General web + Reddit + blog results on 2026 open-source TTS/STT. Key facts:

- **Kokoro-82M** — "Best default open-source TTS in 2026." Only **82M params**, Apache 2.0, ~**2-3 GB VRAM** (or CPU-only), **54 voices / 8 languages**, faster than real-time. Extremely 3060-friendly.
- **Best open-source STT (speech-to-text) models 2026:** **OpenAI Whisper Large V3** (1.55B params, 99+ languages, gold standard), NVIDIA **Canary**, **Parakeet**, **Moonshine** (AssemblyAI comparison, Aug 2026).
- **Step Audio EditX (StepFun)** — Best open-weight TTS, Apache 2.0.
- **Fish Audio S2 Pro** — Inline prosody tags (open weights, non-commercial license).
- **58 local TTS/speech models in 2026** include: **Dots TTS, Higgs Audio v2, MisoTTS, WavTTS, Orpheus, Kokoro, Piper** (LocalClaw, Jul 2026).
- **Other popular open-source TTS:** XTTS-v2, Mozilla TTS, ChatTTS, MeloTTS, Coqui TTS, Bark (Hyperstack, May 2026).
- **Best self-hosted TTS 2026:** Kokoro, Chatterbox-Turbo, Piper, Dia2, Fish Audio (Inworld AI, Apr 2026).
- **Whisper Large V3** = gold standard multilingual STT (Northflank, Jan 2026).

---

## Website 3: GitHub Search (chatterbox-tts repositories)
**URL:** https://github.com/search?q=chatterbox-tts&type=repositories
**Accessed:** 2026-08-11

Note: The original `resemble-ai/chatterbox-tts` repo now returns 404 (renamed/moved). The most active Chatterbox projects on GitHub:

- **devnen/Chatterbox-TTS-Server** (~1.4k stars) — Self-hosted Chatterbox TTS with a **Web UI**, flexible API endpoints incl. **OpenAI-compatible** API. Tags: python, text-to-speech, ai, **cuda**, web-ui. Updated May 2026.
- **travisvn/chatterbox-tts-api** (~665 stars) — **Local, OpenAI-compatible TTS API** using Chatterbox; generate voice-cloned speech anywhere the OpenAI API is used. Docker + CUDA. Updated Dec 2025.
- **randombk/chatterbox-vllm** (~380 stars) — **vLLM port** of Chatterbox TTS (significantly faster inference).
- **petermg/Chatterbox-TTS-Extended** (~575 stars) — Modified version accepting text files, no character restriction (audiobooks).
- **diodiogod/TTS-Audio-Suite** (~1.1k stars, active Aug 2026) — ComfyUI integration for multi-engine TTS + Voice Conversion: RVC, **Echo-TTS, Qwen3-TTS**, etc.
- **jjmlovesgit/local-chatterbox-tts** (~34 stars) — **"A streaming local chatbot"** using Chatterbox — directly relevant to a verbal chatbot.
- **Xerophayze/TTS-Story** (~313 stars) — Web-based multi-voice TTS studio supporting kokoro-tts, chatterbox-tts, indextts-2.

### Why Chatterbox is relevant:
- **OpenAI-compatible APIs** (Chatterbox-TTS-Server, chatterbox-tts-api) make integration trivial for building a talking chatbot.
- **vLLM port** gives near-real-time performance, ideal on a 3060.
- Multiple active community projects confirm it's a top real-time, voice-cloning-friendly TTS in 2026.

---

## Website 4: GitHub — jjmlovesgit/local-chatterbox-tts ("Local Chatterbox-TTS (Unified Voice AI Server)")
**URL:** https://github.com/jjmlovesgit/local-chatterbox-tts
**Accessed:** 2026-08-11

This is a **near-exact match for the user's project**: a streaming, local, *verbal* chatbot.

### What it is:
A FastAPI web app integrating:
- **Local LLM** — connects to **LM Studio or Ollama** (customizable system prompt).
- **TTS** — **Chatterbox** (high-quality, natural speech).
- **STT** — **Whisper** (push-to-talk via Spacebar).
- **Streaming** — LLM responses and TTS audio stream **sentence-by-sentence, in real time**.
- **Voice cloning** — upload a `.wav`, create a `.pt` voice embedding (10-30s of clean speech recommended), then use it as a TTS voice.
- Optional **Simli.ai** avatar (real-time video avatar lip-sync; requires paid Simli API key — optional).
- Web UI with Chat, Voice Cloning, Background Video, Advanced Settings, System Prompt, Logs tabs.
- Modes: TTS Only / LLM Only / **LLM + TTS**.
- MIT license. ~34 stars, 4 open issues. Last commit Jul 2025.

### Hardware requirements (from README):
- **GPU:** NVIDIA RTX 30 series or higher.
- **VRAM: Minimum 8 GB** (for Llama 3 8B + basic Chatterbox TTS); **Recommended 12 GB+** (for better performance, larger LLMs).
- **CPU:** modern multi-core. **RAM:** 16 GB+.
- CPU-only possible but much slower.
- Install notes: install CUDA-matched PyTorch **first**, then `pip install -r requirements.txt`.

### Verdict for a 3060:
**The RTX 3060 (12GB VRAM) meets the "Recommended 12 GB+" spec.** This project runs the full pipeline (STT→LLM→TTS + voice cloning) on a 12GB card. The 3060 is sufficient; the 3090 would only help if using a much larger LLM.

---

## Website 5: GitHub — fishaudio/fish-speech (Fish Audio S2 Pro)
**URL:** https://github.com/fishaudio/fish-speech
**Accessed:** 2026-08-11

**~32.2k stars, 2.8k forks** — one of the most popular open-source TTS projects. Actively maintained (commit Jun 2026).

### Fish Audio S2 Pro (flagship, 4B params)
- **State-of-the-art multilingual TTS** — trained on **10M+ hours** of audio, **80+ languages**.
- **Dual-Autoregressive (Dual-AR)** architecture + RL alignment for natural, realistic, emotionally rich speech.
- **Fine-grained inline control** via natural-language tags (e.g. `[whisper]`, `[excited]`, `[pitch up]`, `[pause]`, `[emphasis]`) — **15,000+ unique tags**.
- **Rapid voice cloning** from short reference samples (**10–30 s**), captures timbre/style/emotion, **no fine-tuning needed**.
- **Native multi-speaker** generation (speaker ID tokens).
- **~100 ms latency**, extreme throughput (3,000+ acoustic tokens/s, RTF < 0.5).
- Benchmarks: **best WER** (Seed-TTS Eval), best Audio Turing Test (0.515), EmergentTTS win rate 81.88% — beats Qwen3-TTS, MiniMax Speech-02, Seed-TTS (closed-source).
- Serve via **vLLM-Omni** or **SGLang** (server inference), WebUI, Docker, CLI.
- Older **Fish Speech 1.5** (0.5B) also available — much lighter, easier on a 3060.

### ⚠️ License caveat:
- Released under the **FISH AUDIO RESEARCH LICENSE** — **NOT Apache/MIT**. This is a **research/non-commercial license** with restrictions and active enforcement. Fine for personal/hobby use, but **not** a free-commercial Apache-2.0 option.
- (The Pinggy guide lists "Fish Audio S2 Pro" as having a non-commercial license; "Step Audio EditX" as Apache 2.0.)

### 3060 fit:
- **S2 Pro (4B)** is heavy for a 12GB card in full precision; best run quantized via vLLM-Omni/SGLang. A 3090 (24GB) is safer for the 4B flagship.
- **Fish Speech 1.5 (0.5B)** runs comfortably on a 3060.
- For a verbal chatbot, the ~100ms latency and zero-shot cloning are excellent — but the license is the main caveat.

---

## Website 6: GitHub — hexgrad/kokoro (Kokoro-82M)
**URL:** https://github.com/hexgrad/kokoro
**Accessed:** 2026-08-11

**Kokoro-82M** — the standout lightweight open-source TTS for a 3060.

### Facts:
- **82 million parameters** — tiny. **Apache-2.0 license** (fully free, incl. commercial).
- **Comparable quality to much larger models**, but significantly faster and cheaper.
- **Runs on CPU, low-VRAM GPU, or even Google Colab free tier** — trivially fits a 3060 (needs only ~2-3 GB VRAM).
- **54 voices, 8 languages**: American/British English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese, Mandarin Chinese.
- Great docs: usage samples, espeak-ng support (English OOD fallback + non-English), Colab notebook.
- Voice customization via `voice.pt` tensors; community `kokoro-fastapi` server adds voice *mixing* (e.g. "bf_lily+af_nicole(2)").

### Why it matters for the user's project:
- Perfect **free, open (Apache 2.0), 3060-friendly** TTS layer for a verbal chatbot.
- Faster than real-time even on weak hardware; leaves VRAM free for the LLM (e.g. a 7-8B model) on a 12GB card.

---

## Website 7: GitHub — fishaudio/fish-speech (Fish Speech 1.5 vs S2) — quick note
(Referenced on the fish-speech page; 0.5B Fish Speech 1.5 is the lighter, 3060-compatible variant.)

---

## Website 8: Google Search — Reddit local voice chat pipeline on RTX 3060/12GB
**URL:** https://www.google.com/search?q=site:reddit.com+local+voice+chat+STT+LLM+TTS+pipeline+3060+12GB+voice+chatbot
**Accessed:** 2026-08-11

Real-world reports confirming a **3060 / 12GB runs a full local voice pipeline**:

- **r/LocalLLaMA** (3060 Ti 12GB): STT with **NVIDIA "Parakeet"** — lightweight, runs on GPU *significantly faster than real-time*. (Parakeet STT + Llama LLM + TTS.)
- **r/homeassistant**: "I chose to add a second-hand 12GB RTX 3060 to my home server. Speech-to-text (**Whisper turbo**) takes ~**0.3s** for a typical command."
- **r/LocalLLM** "Minimum hardware for a voice assistant": You need STT + TTS + LLM; both TTS and STT need VRAM, but **TTS models like Piper can actually run on the CPU** — so a 3060's 12GB is plenty.
- **r/homeassistant** "You don't need a super powerful GPU": "My 3060 with 12GB can do much better [than 30s responses]" — a 3060 handles a voice assistant well.
- **r/LocalLLaMA LIVA** (local voice assistant): Author used an **RTX 3060 12GB + 32GB RAM**, with HA voice pipeline (pluggable LLM/STT/TTS).
- **r/LocalLLM** voice assistant thread: people combine **Whisper (STT) → Ollama (LLM) → TTS** successfully on a single 3060 Ti.
- **LLM suggestions for 12GB:** Gemma3, Qwen2.5 (smaller quantized), Olmo 3.1, Llama 3 8B — all fit ~12GB alongside a small TTS.

### Key conclusion for 3060 vs 3090:
Multiple real users run the full **STT → LLM → TTS** voice-chat pipeline on a **3060 (12GB)**. The **3060 is sufficient** for a verbal chatbot with a 7-8B LLM + small TTS (Kokoro/Chatterbox/XTTSv2) + Whisper/Parakeet STT. A **3090 (24GB)** would only be needed for larger LLMs (e.g. 14B+ full precision) or heavy 4B-TTS models like Fish S2 Pro.

---

## Website 9: Google Search — best open-source local voice chatbot framework/app (Whisper + Ollama + TTS)
**URL:** https://www.google.com/search?q=best+open+source+local+voice+chatbot+framework+app+whisper+llm+tts+2026+ollama
**Accessed:** 2026-08-11

**Direct answer found** (Local AI Master + related): The optimal open-source, fully-local voice-chatbot stack in 2026 is:
- **STT:** `faster-whisper` (or `whisper.cpp` with `large-v3-turbo`). Parakeet also prominent. **Qwen3-ASR 0.6B** runs even on CPU.
- **LLM brain:** **Ollama** running **Llama 3.2 (3B/8B)** or **Qwen 2.5**.
- **TTS:** **Kokoro-82M** (lightweight, natural, runs CPU or GPU).
- **Orchestration / framework:** **Pipecat** (production-ready Python framework for real-time conversational voice/multimodal pipelines) — OR a custom Python event loop with WebRTC Voice Activity Detection (VAD) for lowest latency. **Home Assistant / OpenVoiceOS** if you want pre-built UI/smart-home integrations.

### Supporting sources found:
- **r/LocalLLaMA "Best Audio Models - Feb 2026"** (100+ comments): "Whisper still holds up well locally. **Kokoro 82M is my current pick.** Open weights, runs..."
- **r/LocalLLaMA "OSS Local Voice and Automation in 2026"** (Mar 2026).
- **r/LocalLLaMA "Awesome Local LLM Speech-to-Speech Models & Frameworks"** (Oct 2025, 30 posts).
- **Services Ground "Best Local AI Models for Coding, Voice & Agents (2026)"**: The complete local voice stack = Layer 1 STT: faster-whisper large-v3-turbo (GPU) or Qwen3-ASR 0.6B (CPU); Layer 2: LLM; Layer 3: TTS. Also: `ollama pull whisper Qwen3-ASR`.
- **Dograh "Building a Voice Bot from Scratch"** (May 2026): self-hosted voice bot = **Whisper or Voxtral for STT**, Llama 3 or Qwen for LLM (via Ollama or vLLM), **Piper or Coqui XTTS for TTS**.
- **Kunal Ganglani** (Jul 2026): offline voice assistant = **Whisper STT + Piper TTS + Ollama** (+ Home Assistant).
- **InnerZero** (May 2026): Whisper/faster-whisper is the 2026 STT standard; **Kokoro and Piper are the two leading open-source TTS engines**.
- **OpenClaw, Rasa, Botpress, Leon, Jan** — open-source AI assistant frameworks (getclawdbot.com comparison).

### Summary of the best "all-in-one" frameworks for a talking chatbot:
1. **Pipecat** (pipecat-ai/pipecat) — best for real-time voice chatbots (STT+VAD+LLM+TTS orchestration).
2. **jjmlovesgit/local-chatterbox-tts** — complete pre-built FastAPI verbal chatbot (LLM+Chatterbox TTS+Whisper+voice cloning), confirmed to run on 12GB.
3. **Home Assistant Voice Pipeline / OpenVoiceOS** — pre-built UI + integrations (more smart-home oriented).
4. **Custom** faster-whisper + Ollama + Kokoro/Piper script with WebRTC VAD — lowest latency, full control.

---

## Website 10: GitHub — pipecat-ai/pipecat (Real-Time Voice & Multimodal AI framework)
**URL:** https://github.com/pipecat-ai/pipecat
**Accessed:** 2026-08-11

**The #1 open-source framework for building a real-time talking chatbot.** Extremely active (commits on Aug 11, 2026, 11k+ commits, v1.7.0).

### Facts:
- **BSD-2-Clause** license (fully free + commercial).
- Python framework for **real-time voice & multimodal conversational agents** — voice assistants, multi-agent systems, characters/companions, interactive storytelling.
- **Voice-first:** integrates speech recognition (STT), text-to-speech (TTS), and conversation handling out of the box. Pluggable services.
- **Native support for the exact open-source stack we need:**
  - **STT:** Whisper, NVIDIA (Parakeet), Moonshine, FunASR, Groq(Whisper), etc.
  - **TTS:** **Kokoro, Piper, XTTS, Fish, Resemble, NVIDIA**, etc.
  - **LLM:** Ollama, OpenAI, Google, etc.
  - **Speech-to-Speech:** Gemini Multimodal Live, Grok Voice, OpenAI Realtime.
- **Voice UI Kit** (pipecat-ai/voice-ui-kit) — pre-built components/templates for voice AI web UIs.
- VAD (Voice Activity Detection) built in for interruptible, low-latency conversations.

### Why it's the top pick for the user's project:
- You plug **Ollama (LLM) + faster-whisper (STT) + Kokoro/Piper/XTTS (TTS)** together in a few lines and get a real, low-latency, interruptible voice chat — exactly "I talk to it, it talks back."
- Free, open-source, no cloud required; runs entirely on the local 3060.

---

# 🏆 FINAL RECOMMENDATION (summary)

## Best overall choice for the user's verbal chatbot on an RTX 3060 (12GB):
Use **Pipecat** as the orchestration framework, with:
- **STT:** `faster-whisper` (small/large-v3-turbo) or NVIDIA **Parakeet** (faster than real-time on a 3060)
- **LLM:** **Ollama** running **Llama 3.2 8B** or **Qwen 2.5 7B** (quantized)
- **TTS:** **Kokoro-82M** (Apache 2.0, tiny, CPU/GPU) for instant natural speech, or **Chatterbox-TTS / XTTSv2** if you want **voice cloning**

## If you want a ready-made app instead of building it:
Use **jjmlovesgit/local-chatterbox-tts** — a complete FastAPI voice chatbot (Chatterbox TTS + Whisper + LLM + built-in **voice cloning** from a 10-30s WAV), confirmed to run on 12GB VRAM.

## Recommended TTS engines (ranked for this use case):
| Tool | License | VRAM | Latency | Voice cloning | Best for |
|------|---------|------|---------|---------------|----------|
| **Kokoro-82M** | Apache 2.0 | ~2-3 GB | real-time | No (fixed voices/mix) | Default lightweight TTS |
| **Chatterbox Turbo** | open (ResembleAI) | low | <150 ms | **Instant (~5s audio)** | Real-time cloned voice |
| **XTTSv2** (Coqui) | open | low | fast | **Yes (fine-tune)** | Cloning, low VRAM |
| **Fish Speech S2/1.5** | Research (non-commercial) | 1.5: low / S2: high | ~100 ms | **Yes (10-30s)** | Best quality, but license caveat |
| **Piper** | MIT | CPU-capable | real-time | No | Extreme-lightweight |
| **Moss TTS 1.5 (8B)** | open | higher | fast | **Best cloning (2026)** | Max-quality cloning (needs more VRAM) |

## 3060 vs 3090 — final answer:
**Use the RTX 3060 (12GB).** Real-world Reddit reports confirm the full STT → LLM → TTS pipeline runs on a 12GB 3060. The 3060 is sufficient for a 7-8B LLM + Kokoro/Chatterbox/XTTS TTS + Whisper/Parakeet STT + voice cloning. A 3090 (24GB) is only needed for: (a) a large LLM (14B+), or (b) heavy 4B TTS models like Fish S2 Pro or Moss TTS 8B at full quality.

## Recommended stack (fully free & open-source, 3060-compatible):
- **Framework:** Pipecat (BSD-2-Clause) — or the ready-made `local-chatterbox-tts`
- **STT:** faster-whisper large-v3-turbo (or NVIDIA Parakeet)
- **LLM:** Ollama + Llama 3.2 8B / Qwen 2.5 7B
- **TTS:** Kokoro-82M (default) or Chatterbox-TTS/XTTSv2 (for voice cloning)
- **VAD:** Pipecat built-in (WebRTC VAD)
- **All 100% local, no cloud, free.**

---
*Research conducted 2026-08-11 via live web browsing (Google Search, GitHub). Reddit pages themselves were behind a reCAPTCHA, so Reddit content was gathered via Google's site:reddit.com search results.*

### 2026 Reddit threads:
1. **"What is the best open-source TTS model right now? (2026)"** (r/LocalLLM, 30+ comments) — "TTS Specialist" top answer.
2. **"Best Audio Models - Feb 2026"** (r/LocalLLaMA, 106 answers).
3. **"What is The best and expressive AI TTS (running locally)"** (r/LocalLLaMA, 57 answers, May 2026).

### People-also-search tools of interest: 
**ElevenLabs** (proprietary/commercial), **Kokoro TTS**, **Qwen3-TTS**, **OmniVoice**, **Chatterbox TTS**, **Qwen TTS**, **F5-TTS**, **Orpheus TTS 3B**.

### Early takeaway for a 3060 (12GB VRAM):
- **Kokoro-82M** is ideal: tiny VRAM, CPU-capable, free (Apache 2.0) — perfect TTS base for a verbal chatbot.
- **Whisper** (STT) runs fine on a 3060, especially Whisper-small/medium/distil variants.
- Chatterbox-Turbo and F5-TTS are strong real-time, low-latency options.
- Orpheus TTS 3B and Dots TTS are higher quality but larger (need more VRAM).

---

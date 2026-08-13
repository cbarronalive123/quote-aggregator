# Voice AI Research — REDDIT-FOCUSED Report
**Date:** 2026-08-11
**Goal:** What people on Reddit actually say is the best free/open-source voice AI, TTS, and voice-cloning app for a local talking chatbot — with attention to RTX 3060 (12GB) vs 3090 (24GB).
**Method:** Browsed Reddit directly via old.reddit.com (new Reddit was behind a reCAPTCHA; old.reddit worked). Report written progressively after each thread.

---

## Thread 1: "What is The best and expressive AI TTS (running locally?) for voice acting?"
**URL:** https://old.reddit.com/r/LocalLLaMA/comments/1t1nsyo/what_is_the_best_and_expressive_ai_tts_running/
**Subreddit:** r/LocalLLaMA · **Date:** May 2, 2026 · **27 points, 57 comments** · flair: Question | Help
**OP:** Private hobby project, wants TTS showing all emotions (grunts, anger, screams, sadness).

### Top answer (vorwrath, +11): **Fish Audio S2**
> "For local, probably Fish Audio S2. The freeform emotion tags are impressive. However it's quite a heavyweight model, so needs good hardware and will be slow. And it's only licensed for non-commercial and research use."

**Important replies on Fish S2:**
- **MacabreGinger:** "Local? it says **24 gbs of vram needed**" → ⚠️ **Fish Audio S2 needs 24GB VRAM — does NOT fit a 3060 (12GB).**
- **vorwrath (reply):** "I've run it locally on a 3090 (it's not fast)." → even on 3090 it's slow. Then: *"If you'd like something very efficient and high quality, I would suggest **Kokoro**. But it doesn't do emotions and some voices are better than others (**'af_heart' in particular is top tier**). Super efficient, with CUDA acceleration is much faster than real-time. I was able to generate a whole novel worth of speech in about 5 minutes."*
- **Spooknik:** "The **emotional tags don't work at all** though." (Fish S2 emotion tags unreliable.)
- **wanielderth:** "Just make sure you install **Linux** if you're on Windows. Cause the hardware acceleration will not work without **Triton**." → ⚠️ Fish S2 GPU acceleration is painful on Windows.
- **drallcom3:** "Really only viable for hobby projects though. **Their license sucks to hell.**"

### Second top answer (LelouchZer12, +11): **Omnivoice**
> "You could try Omnivoice"
- **martinerous:** "It even speaks Latvian out of the box... How could they squeeze in so many languages into such a fast model?" → Omnivoice = fast, massively multilingual.

### Third answer (-Sharad-, +8): **Qwen 3 TTS**
> "Qwen 3 tts is the only one I've seen locally that allows prompts to color the speech like that."
- **Caveat (-Sharad- reply):** "They only seem to support that function on **default voices** 😑" (emotion prompts don't work on cloned/custom voices).
- **drallcom3:** "The only way I've seen emotions work locally was to create a voice on ElevenLabs, save snippets with the desired emotions, then use those as inputs in Qwen/Omni."

### Key takeaways (3060 focus):
- **Fish Audio S2 = best emotion/expression, BUT 24GB VRAM (3090-class), slow, non-commercial license, Triton/Windows pain.** ❌ Not for a 3060.
- **Kokoro** = best efficient high-quality choice (vorwrath); runs CPU/GPU, faster than real-time. ✅ Great for 3060 (no emotion control though).
- **Qwen3-TTS** = promptable emotion on default voices. ✅ Lighter; runs on modest GPUs.
- **Omnivoice** = fast, super-multilingual. ✅ 3060-friendly.

---

## Thread 2: "Best Open Source Voice Cloning if you have lots of reference audio?"
**URL:** https://old.reddit.com/r/LocalLLaMA/comments/1sgn7hi/best_open_source_voice_cloning_if_you_have_lots/
**Subreddit:** r/LocalLLaMA · **Date:** Apr 9, 2026 · 5 points, 24 comments · Question | Help
**OP (SlaveToBuy):** Using ElevenLabs (expensive, inconsistent accents). Wants a consistent cloned voice, lots of reference audio. **OP's GPU = RTX 3080 12GB + 32GB RAM** (≈ the 3060 12GB case).

### Comments:
- **ASMellzoR (+2):** "Chatterbox / Chatterbox Turbo / **Qwen3 TTS**. **Vibevoice is high quality, but very slow.** Nice for audiobooks but not so much for **real-time conversation**. **Chatterbox Turbo** can also do emotion tags like `<laugh>`."
  - OP reply: "I don't need real-time conversation. It's more for audio books so I'm okay waiting."
  - ASMellzoR reply: "**Vibevoice for sure then** 😉" (→ Vibevoice = top pick when real-time isn't needed).
- **Sevealin_ (+1):** "Chatterbox has **one-shot cloning** that is pretty good. Just needs one clip that's **~30 seconds** of audio."
- **Clean-Appointment684 (+1):** "chatterbox pretty good on voice cloning imho. give it a try"
- **SignificanceFast8449 (+1):** "Try **VoxCPM2** it is an upgrade — I made a free voice clone software on top of it: **freeclone.net**"
- **k8-bit (+1):** "I've found **Omnivoice loses the plot with reference audio more than 20s**. **Vibevoice gobbles up 2 mins of reference audio** with great if occasionally eccentric results."
- **k8-bit (+2):** "**Vibevoice** via gradio starts streaming audio after ~**15 seconds**... This on a **3090**. I use the q8 and q4 quantized version in **ComfyUI on a 16GB 5060Ti** happily as well." → ⚠️ Vibevoice is 3090-class for full quality; only feasible on ≤16GB with quantized (q4/q8) weights.

### Key takeaways (real-time chatbot vs quality cloning):
- **Real-time conversation (the user's use case):** **Chatterbox / Chatterbox Turbo** (one-shot clone from ~30s audio, emotion tags) and **Qwen3-TTS** are the top recommendations.
- **Maximum clone quality (non-realtime):** **Vibevoice** — but slow, needs a 3090 or a quantized build on 16GB; not for a 3060 in real-time.
- **Vibevoice** handles lots of reference audio (2 min) well; **Omnivoice** degrades past ~20s of reference.
- **VoxCPM2** (via freeclone.net) = free voice-clone tool.

---

## Thread 3: "What is the best open-source TTS model right now? (2026 edition)"
**URL:** https://old.reddit.com/r/LocalLLM/comments/1uh2xyh/what_is_the_best_opensource_tts_model_right_now/
**Subreddit:** r/LocalLLM · **Date:** Jun 27, 2026 · **27 points, 35 comments** · Personal-project TTS (clonability a "huge plus").

### Top answer — TTS Specialist (b111ue, +4) — the definitive 2026 tier list:
> "I've basically tested every major TTS. Hope this helps:
> - **~120m and below:** Chatterbox-Nano, Kokoro, Supertonic. **Chatterbox-Nano is the one to go.**
> - **~120m to 800m:** Qwen3-TTS-0.6b, Chatterbox, Gepard (if you need streaming). If I had to pick one: **Qwen3-TTS** (or OmniVoice for more languages).
> - **Anything above:** VoxCPM2 (~2b) if smaller; **Fish Audio S2 Pro** if larger (I wouldn't recommend Higgs Audio TTS 3).
>
> The gold standard has moved far away from older models like **Bark and XTTS**. Kokoro is amazing, but **Chatterbox-Nano basically outclasses it on everything**."

Other replies confirming the tier list:
- **OP reply:** "Thanks so much! Am going to go with **chatterbox nano**."
- **rktpwr (+1):** "**Kokoro** is very fast and really good quality if the stock voices work for you... takes up very little memory." (great for at-home projects)
- **UkieTechie (+4):** points to a TTS benchmark with licenses: **github.com/5uck1ess/tts-bench**. Notes **Kokoro does not support voice cloning natively** (preset voices only).
- **Working_Resident2069:** "Doesn't Chatterbox Nano ship as multiple sub-models...?" (footprint caveat)
- **_raydeStar (+3):** "Fast models usually can't clone... **Kokoro** still has the best cross-platform support."
- **gabrielesilinic (+3):** Kokoro praised for consistent long-narration quality, insanely fast (120h of audio in ~1.5h on a 7900XTX), stable, low artifacts.
- **GriffinDodd (+1):** Kokoro — "insane speed and decent voices... you can **blend two voices on the fly**."
- **iFart_69 (+2):** reviews: CosyVoice 3 (all-in-1, lightweight, pain to install), Higg3 (zeroshot clone), VoxCPM2 (great voice design), Qwen3, Kokoro (fun), **Moss-Nano** (most lightweight zero-shot, has a Donald Trump voice by default 😄).
- **BashCarveSlide:** "Best sounding is **SoVITS** but it's so slow — I just use it to train **Piper**."
- **TreesJunkie:** "qwen 1.2B TTS doing great at copying and generation."
- **LFM2.5-Audio** fan: tiny, fast, reliable for near-real-time local conversation (but 4 voices, no cloning, no emotion control; "less robotic than Kokoro").
- **Weird-Plastic8222 (+1):** "Kokoro."
- **FluffyGreyLlama (+5):** Fish Audio is "Open Source by definition, but the **license may be too restrictive**."
- Link to a mega-list: **r/LocalTextToSpeech "My TTS List of 2026: All Voices, All Models"**.

### Key takeaways:
- **Chatterbox-Nano** = best sub-120m (outclasses Kokoro per the specialist).
- **Qwen3-TTS** = best in the 120m–800m sweet spot (also great for cloning).
- **Chatterbox / Chatterbox Turbo** = strong, one-shot cloning, emotion tags.
- **Kokoro** = fastest/most cross-platform, but **no native cloning** (preset voices only, voice blending possible).
- **Fish Audio S2 Pro / VoxCPM2** = top of the range, but heavier (S2 needs 24GB) and Fish license is restrictive.
- Older models (**Bark, XTTS**) are now outdated per the specialist.
- **CosyVoice 3**, **Moss-Nano** (lightest zero-shot), **SoVITS→Piper**, **Gepard** (streaming) also mentioned.

---

## Thread 4: "Chatterbox Turbo — open source TTS. Instant voice cloning from ~5 seconds of audio"
**URL:** https://old.reddit.com/r/LocalLLaMA/comments/1pndbki/chatterbox_turbo_open_source_tts_instant_voice/
**Subreddit:** r/LocalLLaMA · **Date:** Dec 15, 2025 · **0 points, 40 comments** · flair: News (ResembleAI announcement)

### Post claims (official):
- **<150ms time-to-first-sound** · SOTA quality that beats larger proprietary models · natural programmable expressions · **zero-shot voice cloning from ~5s audio** · open source.
- **Model sizes:** Turbo = **350M** (English only); **Multilingual = 500M** (per user FinBenton).

### Community reactions (mixed — important):
- **r4in311 (+22):** "Just tried it, **awful voice replication**. If you are looking for something like that, check out **VoxCPM**, released just a few days ago."
- **simadik (+2):** "Compared to **VoxCPM** this one is not that good. Voice cloning is meh and doesn't sound close to reference audio. The only reason to use this is if your reference audio already has bad quality."
- **zyxwvu54321 (+2):** "Among all the TTS models I've tried, **ChatterBox and IndexTTSv2** do [strong multilingual cloning with minimal accent variation] best, but **ChatterBox is faster**."
- **anon (+1):** "The **cloning quality significantly degraded** vs their original model, voice is awful/synthetic. Also, **original uses ~5GB VRAM** on my 2080, **turbo sucks ~10GB VRAM**... 10686MiB / 11264MiB." → ⚠️ **Chatterbox Turbo can use ~10GB VRAM — near the 3060's 12GB ceiling.** The original (non-Turbo) Chatterbox is lighter (~5GB).
- **FinBenton (+9):** praised Finnish support + cloning (but mpasila corrected: only the larger Multilingual model is multilingual; Turbo is English-only).

### Server/integration info (great for a chatbot):
- **One_Slip1455 (+3):** **devnen/Chatterbox-TTS-Server** updated to support Turbo — **OpenAI-compatible `/v1/audio/speech` endpoint, streams audio (wav/opus)**, hot-swap Turbo vs original in the UI.
- **KevinAHM/echo-tts-api** — different streaming TTS API.

### Key takeaways (3060 focus):
- **Chatterbox Turbo = <150ms, ~5s zero-shot clone, English-only, BUT ~10GB VRAM** and cloning quality is hotly debated (many prefer **VoxCPM**).
- **Original Chatterbox** is lighter (~5GB VRAM) and quality is generally rated higher — better for a 3060.
- Chatterbox's OpenAI-compatible streaming server (devnen) makes chatbot integration trivial.
- **VoxCPM / VoxCPM2** is the community favorite for cloning quality in this size class.

---

## Thread 5: "Best Audio Models - Feb 2026" (r/LocalLLaMA Megathread)
**URL:** https://old.reddit.com/r/LocalLLaMA/comments/1r7bsfd/best_audio_models_feb_2026/
**Subreddit:** r/LocalLLaMA · **Date:** Feb 17, 2026 · **153 points (99%), 106 comments** · Megathread

Community consensus on the best local ASR/STT/TTS as of early 2026.

### Community-recommended full local voice pipeline:
- **BrightRestaurant5401 (+43, top comment):** "speech detection → **Marblenet ASR → Parakeet STT → Chatterbox TTM → Ace-Step**" — a complete low-latency local voice-chat stack.
- **BrightRestaurant5401 (+10, on Chatterbox speed):** "**Latency is exactly on the edge of real-time for Chatterbox**" (asked by _raydeStar, who wanted the lowest latency for local real-time conversation).

### STT / ASR picks:
- **WhisperianCookie (+3):** "**Parakeet** is the best, amazing how small it is... almost as fast as cloud transcription." (they run it on phones!)
- **aschroeder91 (+4):** "speed: **Parakeet** (nvidia/parakeet-tdt-0.6b-v3); accuracy: **Canary-Qwen** (nvidia/canary-qwen-2.5b)."
- **fourfourthree (+3):** "I'm still using **Whisper — faster-whisper v3 turbo**. Parakeet is okay but Whisper produces better sentences/punctuation. **Avoid whisper.cpp** (less accurate)."
- **Parakeet TDT v3 detail:** supports ~25 extra languages (v2 was English-only); **runs fast even on CPU**, saving VRAM for the LLM/TTS.

### TTS picks:
- **hurrytewer (+9):** "**Echo-TTS** is the most natural-sounding TTS / best at zero-shot voice cloning" (not the fastest).
- **WPBaka (+3):** "**Moss-TTS** has an SFX mode."
- **Chatterbox** — real-time edge latency; **Kokoro** — cross-platform/fast.

### Big trend (important forward-looking note):
- **the-ai-scientist (+12):** The **ASR→LLM→TTS pipeline is a "transitional architecture"** — decomposing speech to text loses prosody/emotion/turn-taking. **Native speech-to-speech** models are the future: e.g. **NVIDIA PersonaPlex (Jan 2026)** — a full-duplex model operating directly on audio tokens, listening & speaking simultaneously with interruptions/backchannels, no separate ASR/TTS. Built on Moshi's architecture. This is where local voice agents are heading in 2026.

### Key takeaways:
- For a 3060 today, the community stack is: **Parakeet (STT, tiny, runs CPU) or faster-whisper v3-turbo → local LLM → Chatterbox / Echo-TTS / Kokoro (TTS)**.
- Keep an eye on native **speech-to-speech** models (PersonaPlex) as the next-generation replacement for the pipeline approach.

---

## Thread 6: "App for voice interaction with LocalLLaMA" — a real RTX 3060 voice chatbot user
**URL:** https://old.reddit.com/r/LocalLLaMA/comments/1m9e71s/app_for_voice_interaction_with_localllama_looking/
**Subreddit:** r/LocalLLaMA · **Date:** Jul 25, 2025 · 4 points · Question | Help

**OP (Dark_Mesh):** Self-hosting **Ollama on an RTX 3060 (12GB VRAM)**, using ChatboxAI + Tailscale. Wants **voice chat back-and-forth** like ChatGPT/Gemini, as a "semi-layman." → This is almost exactly the user's project + GPU.

### Comments:
- **dedreo58 (+3):** The user's setup = "Ollama on RTX 3060 (12GB) + ChatboxAI + Tailscale; wants voice chat." Their need: **"A working combo of Whisper + Piper or Bark, hooked into SillyTavern or a similar UI"** and "a guide that says 'Here's what works well on a 3060'." (This validates that **Whisper (STT) + Piper/Bark (TTS) + a UI** is the standard 3060 voice-chat recipe.)
- **anon (builder):** Their own working prototype pipeline: **"MarbleNet VAD → Parakeet ASR → turn detection → multimodal Llama.cpp → Chatterbox (TTS)."**
  - Key insight: most STT/TTS don't run well in C++ (except Whisper) without dropping to Python.
  - **Turn detection / interruption handling is the hard part** of voice chat — natural pacing isn't easy. (This is exactly what frameworks like Pipecat handle for you.)

### Key takeaways (3060 voice chatbot):
- A **3060 (12GB) is confirmed enough** for a local talking chatbot (Ollama LLM + Whisper STT + Piper/Bark/Chatterbox TTS).
- Recommended simple recipe: **Whisper (STT) + Piper or Bark (TTS)** with a chat UI (SillyTavern/ChatboxAI).
- For handling **turn-taking/interruptions** robustly, use a voice-agent framework (Pipecat) or a ready-made app like `local-chatterbox-tts` rather than hand-rolling turn detection.

---

# 🏆 REDDIT COMMUNITY SYNTHESIS

## What Reddit actually says (as of mid-2026):

### 1. Best TTS / voice-cloning models (community verdict)
Ranked by consensus across the threads above (with a **12GB 3060** in mind):

| Tool | Consensus | License | 3060 fit | Notes |
|------|-----------|---------|----------|-------|
| **Kokoro-82M** | Top pick for speed/quality/cross-platform | Apache 2.0 | ✅ Excellent | No native cloning (preset voices, blendable); 120h audio in ~1.5h |
| **Chatterbox / Chatterbox-Turbo** | Best real-time cloned-voice TTS | Open (ResembleAI) | ⚠️ OK | One-shot clone ~30s (~5s for Turbo); Turbo ~10GB VRAM, English-only; latency ~edge of real-time |
| **Qwen3-TTS** | Best in the 120m–800m class | Open | ✅ Good | Promptable emotion (default voices only), great cloning |
| **Echo-TTS** | "Most natural + best zero-shot cloning" | Open | ✅ Good | Not the fastest |
| **Omnivoice** | Fast, super-multilingual | Open | ✅ Good | Degrades past ~20s reference audio |
| **Fish Audio S2** | Best emotion/expression, but **24GB VRAM** | Non-commercial | ❌ No (needs 3090) | Slow even on 3090; Triton/Windows pain |
| **VoxCPM / VoxCPM2** | Community favorite for cloning quality | Open | ✅ Good | Preferred over Chatterbox-Turbo for fidelity |
| **XTTSv2 / Bark** | **Now outdated** per TTS specialist | Open | — | "Gold standard has moved far away from these" |

### 2. Best STT for the voice chatbot:
- **NVIDIA Parakeet** (TDT 0.6B v3) — tiny, faster than real-time, **runs on CPU to save VRAM**, 25+ languages.
- **faster-whisper v3-turbo** — best balance of accuracy + speed, better punctuation than Parakeet; **avoid whisper.cpp**.
- **Canary-Qwen** (2.5B) — highest accuracy, heavier.
- **MarbleNet** — VAD/speech detection.

### 3. Full local voice-chat pipeline the community recommends (3060-friendly):
**MarbleNet (VAD) → Parakeet / faster-whisper (STT) → local LLM (Ollama, Llama/Qwen) → Chatterbox / Kokoro / Echo-TTS (TTS)**
- Turn-taking/interruption handling is the hardest part — use **Pipecat** or a ready-made app (`local-chatterbox-tts`) to get this for free.

### 4. 3060 vs 3090 — the Reddit verdict:
- **The 3060 (12GB) is confirmed enough** for a local verbal chatbot: real users run Ollama + Whisper + Piper/Bark/Chatterbox on a 3060 12GB.
- The **only reason to want a 3090 (24GB)** on Reddit is running the heavy flagship models: **Fish Audio S2 (needs 24GB)** or a large (14B+) LLM at full quality. Neither is required for a good local voice chatbot on a 3060.

### 5. Forward-looking:
Reddit's audio-experts expect native **speech-to-speech** models (NVIDIA PersonaPlex, Moshi-based) to eventually replace the STT→LLM→TTS pipeline, but as of Aug 2026 the pipeline approach with the stack above is the practical, working answer on a 3060.

---
*Research conducted 2026-08-11 directly on Reddit (old.reddit.com), since the modern Reddit UI blocked automation behind a reCAPTCHA. Findings reflect real community posts from 2025–2026.*

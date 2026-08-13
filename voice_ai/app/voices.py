"""Voice catalog: curated preset voices (Kokoro) + dynamically added clones.

Each preset maps to a Kokoro voice id. The `professional` flag is used to
badge voices suitable for phone/insurance agents. Cloned voices are added at
runtime by the cloner module and persisted via config.
"""

from __future__ import annotations

# id -> display entry
#
# Each voice is either:
#   - kind="preset" (default): uses a built-in Kokoro voice via `kokoro`.
#   - kind="rvc": synthesized with a base Kokoro voice then converted to a
#     celebrity timbre by an RVC voice model (.pth). `rvc_key` is used to look
#     up the model path in config["rvc_models"].
VOICE_CATALOG = [
    # --- RVC celebrity voices (need a downloaded .pth model; set path in Settings) ---
    {"id": "terminator", "label": "Terminator (Arnold)", "kind": "rvc",
     "rvc_base": "am_michael", "rvc_key": "terminator",
     "rvc_url": "https://huggingface.co/yraziel/Schwarzenegger/resolve/main/Schwarzenegger_e300_s27600.zip",
     "style": "Deep, gravelly action voice", "professional": False},
    {"id": "robin_williams", "label": "Robin Williams", "kind": "rvc",
     "rvc_base": "am_puck", "rvc_key": "robin",
     "rvc_url": "https://huggingface.co/Coleereer/EGadd/resolve/main/RobinWilliams.zip",
     "style": "Energetic, comedic, fast", "professional": False},

    # --- Popular / character-style ---
    {"id": "am_michael", "label": "Michael (US Male)", "kokoro": "am_michael",
     "style": "Calm, deep, authoritative", "professional": True},
    {"id": "am_onyx", "label": "Onyx (US Male)", "kokoro": "am_onyx",
     "style": "Deep, warm, movie-trailer feel", "professional": False},
    {"id": "am_fenrir", "label": "Fenrir (US Male)", "kokoro": "am_fenrir",
     "style": "Rough, upbeat action character", "professional": False},
    {"id": "am_puck", "label": "Puck (US Male)", "kokoro": "am_puck",
     "style": "Energetic, upbeat", "professional": False},
    {"id": "af_bella", "label": "Bella (US Female)", "kokoro": "af_bella",
     "style": "Warm, conversational", "professional": False},
    {"id": "af_heart", "label": "Heart (US Female)", "kokoro": "af_heart",
     "style": "Friendly, natural (community favorite)", "professional": False},
    {"id": "bf_emma", "label": "Emma (UK Female)", "kokoro": "bf_emma",
     "style": "Warm, British", "professional": False},

    # --- Professional (for phone / insurance agents) ---
    {"id": "bm_george", "label": "George (UK Male)", "kokoro": "bm_george",
     "style": "Professional, clear", "professional": True},
    {"id": "bm_daniel", "label": "Daniel (UK Male)", "kokoro": "bm_daniel",
     "style": "Professional, friendly", "professional": True},
    {"id": "bm_lewis", "label": "Lewis (UK Male)", "kokoro": "bm_lewis",
     "style": "Professional, direct", "professional": True},
    {"id": "bf_lily", "label": "Lily (UK Female)", "kokoro": "bf_lily",
     "style": "Professional, educated", "professional": True},
    {"id": "am_adam", "label": "Adam (US Male)", "kokoro": "am_adam",
     "style": "Professional, broadcast quality", "professional": True},
    {"id": "af_sarah", "label": "Sarah (US Female)", "kokoro": "af_sarah",
     "style": "Clear, trustworthy", "professional": True},
]

# Voices enabled by default (checked in Settings -> Voices).
DEFAULT_ENABLED_VOICES = ["af_heart", "am_michael", "bm_george", "bf_emma"]

DEFAULT_VOICE = "af_heart"


def voice_by_id(voice_id: str):
    for v in VOICE_CATALOG:
        if v["id"] == voice_id:
            return v
    return None


def cloned_voices(config):
    """Return voice dicts for user-created clones from config."""
    clones = config.get("cloned_voices", {})
    out = []
    for vid, info in clones.items():
        out.append(
            {
                "id": vid,
                "label": info.get("name", vid),
                "kind": "cloned",
                "reference": info.get("reference", ""),
                "style": "Cloned voice",
                "professional": False,
            }
        )
    return out


def all_voices(config):
    """Preset + RVC + cloned voices."""
    return VOICE_CATALOG + cloned_voices(config)


def resolve_voice(voice_id: str, config):
    """Find a voice (preset/RVC/cloned) by id."""
    for v in all_voices(config):
        if v["id"] == voice_id:
            return v
    return None

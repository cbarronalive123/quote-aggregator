"""Persistent configuration (JSON) for the app: enabled voices, default voice,
selected model ids. Survives restarts."""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    "enabled_voices": ["af_heart", "am_michael", "bm_george", "bf_emma"],
    "default_voice": "af_heart",
    "llm_model": "qwen3:4b",
    "stt_model": "small",
    "auto_send_speech": True,
    # rvc_key -> path to the .pth model; "<key>_index" -> optional .index file
    "rvc_models": {},
    "rvc_server_url": "http://127.0.0.1:8123",
    # cloned voice id -> {"name": str, "reference": "/abs/path.wav"}
    "cloned_voices": {},
}

SYSTEM_PROMPT = (
    "You are a friendly, concise AI assistant having a spoken conversation. "
    "Keep responses short and natural, as if talking out loud. Do not use "
    "emojis, emoticons, or special symbols."
)


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                self.data.update(loaded)
            except Exception:
                pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, indent=2), encoding="utf-8"
        )

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

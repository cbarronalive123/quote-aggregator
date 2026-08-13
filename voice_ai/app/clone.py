"""Voice cloning client for the main app.

Qwen3-TTS (Apache 2.0 - fully free including commercial) runs in the ISOLATED
Python 3.10 server (rvc_server.py) because its dependencies conflict with the
main app's stack. This module posts the reference audio path + text to the
server and gets back cloned speech.
"""

from __future__ import annotations

import io

import numpy as np
import requests
import soundfile as sf

DEFAULT_URL = "http://127.0.0.1:8123"


class CloneClient:
    def __init__(self, base_url: str = DEFAULT_URL):
        self.base_url = base_url

    def available(self) -> bool:
        try:
            r = requests.get(self.base_url + "/health", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def synthesize(self, text: str, reference_path: str, language: str = "English"):
        """Clone-speak text in the reference voice. Returns (audio, sr)."""
        r = requests.post(
            self.base_url + "/clone_tts",
            data={
                "text": text,
                "reference_path": reference_path,
                "language": language,
            },
            timeout=600,
        )
        r.raise_for_status()
        audio, sr = sf.read(io.BytesIO(r.content), dtype="float32")
        return np.asarray(audio, dtype=np.float32), sr

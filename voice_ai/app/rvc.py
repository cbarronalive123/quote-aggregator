"""RVC (Retrieval-based Voice Conversion) client for the main app.

The heavy RVC engine (rvc-python + fairseq) only works in a Python 3.10
environment, so it runs as a separate local server (`rvc_server.py`). This
module is the HTTP client that the app uses to convert a base speech WAV into
a celebrity-style voice (e.g. Terminator / Robin Williams).

The RVC model files (.pth) are NOT bundled - the user downloads them and points
the app at them in Settings -> Voices.
"""

from __future__ import annotations

import io

import numpy as np
import requests
import soundfile as sf

DEFAULT_URL = "http://127.0.0.1:8123"


class RVCClient:
    def __init__(self, base_url: str = DEFAULT_URL):
        self.base_url = base_url

    def available(self) -> bool:
        try:
            r = requests.get(self.base_url + "/health", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def convert_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
        model_path: str,
        index_path: str | None = None,
        f0up_key: int = 0,
    ):
        """Convert an in-memory float32 buffer to the target voice."""
        buf = io.BytesIO()
        sf.write(buf, audio, sample_rate, format="WAV")
        buf.seek(0)
        files = {"file": ("input.wav", buf, "audio/wav")}
        data = {
            "model_path": model_path,
            "index_path": index_path or "",
            "f0up_key": str(f0up_key),
        }
        r = requests.post(
            self.base_url + "/convert", files=files, data=data, timeout=300
        )
        r.raise_for_status()
        converted, sr = sf.read(io.BytesIO(r.content), dtype="float32")
        return np.asarray(converted, dtype=np.float32), sr

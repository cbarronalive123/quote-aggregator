"""Text-to-speech using Kokoro-82M (Apache 2.0).

Tiny (~170 MB, near-zero VRAM / CPU-capable) so it can run alongside the LLM.
Supports the preset voices in the catalog. Returns a float32 numpy array at
24 kHz for playback with sounddevice.
"""

from __future__ import annotations

import numpy as np
import torch

SAMPLE_RATE = 24000


class TTSEngine:
    def __init__(self, lang_code: str = "a"):
        self.lang_code = lang_code
        self._pipeline = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    @property
    def loaded(self) -> bool:
        return self._pipeline is not None

    def ensure(self):
        if self._pipeline is None:
            from kokoro import KPipeline

            self._pipeline = KPipeline(lang_code=self.lang_code)
        return self._pipeline

    def unload(self):
        self._pipeline = None

    def synthesize(self, text: str, voice: str = "af_heart", speed: float = 1.0):
        """Generate speech. Returns (np.ndarray float32, sample_rate)."""
        chunks = []
        for _gs, _ps, audio in self.ensure()(
            text, voice=voice, speed=speed
        ):
            if torch.is_tensor(audio):
                audio = audio.detach().cpu().numpy()
            chunks.append(np.asarray(audio, dtype=np.float32))
        if not chunks:
            return np.zeros(0, dtype=np.float32), SAMPLE_RATE
        return np.concatenate(chunks), SAMPLE_RATE

    def synthesize_spelled(self, value: str, voice: str = "af_heart", gap: float = 2.0):
        """Spell each letter/number slowly, ~`gap` seconds apart, so names and
        IDs are pronounced character-by-character and easy to write down."""
        letters = [c.upper() for c in str(value) if c.isalnum()]
        if not letters:
            return self.synthesize(str(value), voice=voice)
        chunks = []
        sr = SAMPLE_RATE
        for ch in letters:
            a, sr = self.synthesize(ch, voice=voice)
            chunks.append(a)
            chunks.append(np.zeros(int(sr * gap), dtype=np.float32))
        return np.concatenate(chunks), sr

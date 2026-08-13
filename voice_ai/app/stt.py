"""Speech-to-text using faster-whisper (CUDA on the RTX 3060 when available).

Loaded lazily and kept light (default 'small') so it fits the VRAM budget.
Pass a float32 numpy array of raw audio.
"""

from __future__ import annotations

import numpy as np
import torch


class STTEngine:
    def __init__(self, model_size: str = "small"):
        self.model_size = model_size
        self._model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def ensure(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type="int8",
            )
        return self._model

    def unload(self):
        """Free VRAM by dropping the model reference."""
        self._model = None

    def transcribe(self, audio: np.ndarray, language: str = "en") -> str:
        """audio: float32 1D array at 16 kHz."""
        segments, _info = self.ensure().transcribe(
            audio, beam_size=5, language=language
        )
        return "".join(seg.text for seg in segments).strip()

"""ModelManager: lazy loading + unload of LLM/STT/TTS backends to stay inside
the ~6 GB free-VRAM budget. Only one heavy model is held at a time when
possible (STT/TTS are unloaded on demand). Also handles RVC voice conversion
for celebrity-style voices.
"""

from __future__ import annotations

import os

from app.clone import CloneClient
from app.llm import OllamaClient
from app.rvc import RVCClient
from app.stt import STTEngine
from app.tts import TTSEngine
from app.voices import resolve_voice


class ModelManager:
    def __init__(self, config):
        self.config = config
        self.llm = OllamaClient(model=config.get("llm_model", "qwen3:4b"))
        self.stt = STTEngine(model_size=config.get("stt_model", "small"))
        self.tts = TTSEngine()
        self.rvc = RVCClient(config.get("rvc_server_url", "http://127.0.0.1:8123"))
        self.clone = CloneClient(config.get("rvc_server_url", "http://127.0.0.1:8123"))

    # --- LLM ---
    def llm_running(self) -> bool:
        return self.llm.is_running()

    # --- STT ---
    def transcribe(self, audio):
        # Keep the STT model loaded between messages: reloading it each turn
        # (~1.4s) was a major source of latency. With ~7-8 GB of free VRAM we
        # can afford to hold Whisper alongside the LLM.
        return self.stt.transcribe(audio)

    # --- TTS (dispatches preset vs RVC vs cloned) ---
    def warm_up(self):
        """Preload the local TTS/STT models in the background so the first
        message doesn't pay the one-time cold-load cost."""
        for loader in (self.tts.ensure, self.stt.ensure):
            try:
                loader()
            except Exception:
                pass

    def synthesize(self, text, voice_id="af_heart", speed=1.0):
        v = resolve_voice(voice_id, self.config)
        if v and v.get("kind") == "rvc":
            return self.synthesize_rvc(text, v, speed=speed)
        if v and v.get("kind") == "cloned":
            return self.synthesize_cloned(text, v)
        base = v.get("kokoro", "af_heart") if v else voice_id
        return self.tts.synthesize(text, voice=base, speed=speed)

    def synthesize_cloned(self, text, voice):
        reference = voice.get("reference", "")
        if not reference:
            raise RuntimeError(f"Clone '{voice.get('label')}' has no reference audio.")
        if not self.clone.available():
            raise RuntimeError(
                "The voice server is not running. Start it with:\n"
                "    rvc-env\\Scripts\\python.exe rvc_server.py"
            )
        return self.clone.synthesize(text, reference)

    def synthesize_rvc(self, text, voice, speed=1.0):
        key = voice["rvc_key"]
        model_path = self.config.get("rvc_models", {}).get(key)
        if not model_path or not os.path.exists(model_path):
            raise RuntimeError(
                f"No RVC model configured for '{voice['label']}'. Open Settings -> "
                f"Voices -> 'RVC celebrity voices' and click Download."
            )
        if not self.rvc.available():
            raise RuntimeError(
                "The RVC voice server is not running. Start it with:\n"
                "    rvc-env\\Scripts\\python.exe rvc_server.py"
            )
        index_path = self.config.get("rvc_models", {}).get(key + "_index")
        base_audio, sr = self.tts.synthesize(
            text, voice=voice.get("rvc_base", "am_michael"), speed=speed
        )
        converted, _sr = self.rvc.convert_audio(
            base_audio, sr, model_path=model_path, index_path=index_path
        )
        return converted, _sr

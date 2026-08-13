"""LLM backend using a local Ollama server.

Runs entirely on the local machine (e.g. Llama 3.2 3B quantized) to stay
inside the ~6 GB free-VRAM budget. Requires the Ollama app to be running.
"""

from __future__ import annotations

import ollama

OLLAMA_HOST = "http://localhost:11434"

# Keep the model resident in VRAM between messages (avoid ~5s reload after idle).
KEEP_ALIVE = -1


class OllamaClient:
    def __init__(self, host: str = OLLAMA_HOST, model: str = "llama3.2:3b"):
        self._host = host
        self._client = ollama.Client(host=host)
        self.model = model

    def is_running(self) -> bool:
        try:
            self._client.list()
            return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            return [m.get("name") for m in self._client.list().get("models", [])]
        except Exception:
            return []

    def pull(self, model: str, on_progress=None) -> str:
        """Download a model. Blocks until complete; on_progress(str) optional."""
        for progress in self._client.pull(model, stream=True):
            status = progress.get("status", "")
            if on_progress:
                on_progress(status)
        return model

    def generate(self, prompt: str, system: str = "") -> str:
        out = self._client.generate(
            model=self.model,
            prompt=prompt,
            system=system,
            options={"num_ctx": 2048},
            keep_alive=KEEP_ALIVE,
        )
        return (out.get("response") or "").strip()

    def chat(self, messages: list[dict]) -> str:
        out = self._client.chat(
            model=self.model,
            messages=messages,
            keep_alive=KEEP_ALIVE,
        )
        return (out.get("message") or {}).get("content", "").strip()

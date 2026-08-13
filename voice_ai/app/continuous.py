"""Continuous voice chat worker.

Runs in a background QThread: it records from the microphone, waits until the
user has been silent for ~5 seconds, transcribes (STT), gets a reply (LLM),
speaks it (TTS, interruptible), then loops back to recording so the user can
talk again.

Emits signals to update the UI (transcripts, status, live mic level, and
speech start/stop so the chat can show/hide the Stop button).
"""

from __future__ import annotations

import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QThread, pyqtSignal

from app.config import SYSTEM_PROMPT
from app.textutil import clean_reply

SAMPLE_RATE = 16000
SILENCE_SECONDS = 5.0
SILENCE_THRESHOLD = 0.008
MIN_UTTERANCE_SECONDS = 1.0
CHUNK = int(SAMPLE_RATE * 0.1)


class ContinuousChatWorker(QThread):
    user_text = pyqtSignal(str)
    ai_text = pyqtSignal(str)
    status = pyqtSignal(str)
    level = pyqtSignal(float)
    speech_started = pyqtSignal()
    speech_finished = pyqtSignal()

    def __init__(self, model_manager, voice_provider, parent=None):
        super().__init__(parent)
        self.models = model_manager
        self.voice_provider = voice_provider
        self._stop = False
        self._interrupt = False

    # ---- control ----
    def stop(self):
        self._stop = True
        self._interrupt = True
        self._silence_stream()
        try:
            sd.stop()
        except Exception:
            pass

    def interrupt_speech(self):
        self._interrupt = True
        try:
            sd.stop()
        except Exception:
            pass

    @staticmethod
    def _silence_stream():
        try:
            sd.stop()
        except Exception:
            pass

    # ---- main loop ----
    def run(self):
        self._stop = False
        try:
            while not self._stop:
                audio = self._record_until_silence()
                if self._stop:
                    break
                if audio is None or len(audio) < int(SAMPLE_RATE * MIN_UTTERANCE_SECONDS):
                    continue

                self.status.emit("Transcribing…")
                try:
                    text = self.models.transcribe(audio)
                except Exception as exc:  # noqa: BLE001
                    self.status.emit(f"STT error: {exc}")
                    continue
                if not text.strip():
                    continue
                self.user_text.emit(text.strip())

                self.status.emit("Thinking…")
                try:
                    reply = self.models.llm.generate(text.strip(), system=SYSTEM_PROMPT)
                except Exception as exc:  # noqa: BLE001
                    self.status.emit(f"LLM error: {exc}")
                    continue
                if not reply.strip():
                    continue
                reply = clean_reply(reply)
                if not reply:
                    continue
                self.ai_text.emit(reply)

                self.speech_started.emit()
                self._play(reply, self.voice_provider())
                self.speech_finished.emit()
        finally:
            self.status.emit("Continuous voice chat ended.")
            self.speech_finished.emit()

    def _record_until_silence(self):
        blocks = []
        have_speech = False
        silence = 0.0
        stream = None
        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32"
            )
            stream.start()
            while not self._stop:
                data, _overflow = stream.read(CHUNK)
                data = data.reshape(-1)
                rms = float(np.sqrt(np.mean(data**2))) if data.size else 0.0
                self.level.emit(min(1.0, rms * 60.0))
                blocks.append(data.copy())
                if rms > SILENCE_THRESHOLD:
                    have_speech = True
                    silence = 0.0
                elif have_speech:
                    silence += CHUNK / SAMPLE_RATE
                    if silence >= SILENCE_SECONDS:
                        break
            if not blocks:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(blocks)
        finally:
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass

    def _play(self, reply: str, voice: str):
        self._interrupt = False
        try:
            audio, sr = self.models.synthesize(reply, voice_id=voice)
        except Exception as exc:  # noqa: BLE001
            self.status.emit(f"TTS error: {exc}")
            return
        sd.play(audio, sr)
        while True:
            if self._stop:
                try:
                    sd.stop()
                except Exception:
                    pass
                return
            if self._interrupt:
                try:
                    sd.stop()
                except Exception:
                    pass
                return
            stream = sd.get_stream()
            if stream is None or not stream.active:
                break
            self.msleep(30)

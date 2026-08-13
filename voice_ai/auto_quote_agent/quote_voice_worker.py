"""Voice conversation worker for the quote agent.

Mirrors the main app's continuous-voice-chat loop but drives the quote engine:
the broker speaks -> STT transcribes -> the quote engine answers from the
applicant profile -> TTS speaks the answer -> the mic re-arms for the next
question. Emits signals to update the chat UI and mic volume.
"""

from __future__ import annotations

import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QThread, pyqtSignal

SAMPLE_RATE = 16000
SILENCE_SECONDS = 3.0
SILENCE_THRESHOLD = 0.008
MIN_UTTERANCE_SECONDS = 1.0
CHUNK = int(SAMPLE_RATE * 0.1)


class QuoteVoiceWorker(QThread):
    broker_text = pyqtSignal(str)
    agent_text = pyqtSignal(str)
    status = pyqtSignal(str)
    level = pyqtSignal(float)
    speech_started = pyqtSignal()
    speech_finished = pyqtSignal()

    def __init__(self, responder, stt, tts, voice, parent=None):
        super().__init__(parent)
        self.responder = responder  # callable(broker_text) -> {'text': str, 'type': str, 'quote': ...}
        self.stt = stt              # STTEngine
        self.tts = tts              # TTSEngine
        self.voice = voice          # kokoro voice id
        self._stop = False
        self._interrupt = False

    # ---- control ----
    def stop(self):
        self._stop = True
        self._interrupt = True
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
                    text = self.stt.transcribe(audio)
                except Exception as exc:  # noqa: BLE001
                    self.status.emit(f"STT error: {exc}")
                    continue
                if not text.strip():
                    continue
                self.broker_text.emit(text.strip())
                self.status.emit("Thinking…")
                result = self.responder(text.strip())
                answer = result.get("text") or ""
                self.agent_text.emit(answer)
                self.speech_started.emit()
                if result.get("type") == "spell" and result.get("spell"):
                    self._play_spelled(result["spell"], self.voice)
                else:
                    self._play(answer, self.voice)
                self.speech_finished.emit()
        finally:
            self.status.emit("Voice chat ended.")
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

    def _play(self, text: str, voice: str):
        self._interrupt = False
        try:
            audio, sr = self.tts.synthesize(text, voice=voice)
        except Exception as exc:  # noqa: BLE001
            self.status.emit(f"TTS error: {exc}")
            return
        sd.play(audio, sr)
        while True:
            if self._stop or self._interrupt:
                try:
                    sd.stop()
                except Exception:
                    pass
                return
            stream = sd.get_stream()
            if stream is None or not stream.active:
                break
            self.msleep(30)

    def _play_spelled(self, value: str, voice: str, gap: float = 2.0):
        """Speak a value slowly, one letter every `gap` seconds."""
        self._interrupt = False
        try:
            audio, sr = self.tts.synthesize_spelled(value, voice=voice, gap=gap)
        except Exception as exc:  # noqa: BLE001
            self.status.emit(f"TTS error: {exc}")
            return
        sd.play(audio, sr)
        while True:
            if self._stop or self._interrupt:
                try:
                    sd.stop()
                except Exception:
                    pass
                return
            stream = sd.get_stream()
            if stream is None or not stream.active:
                break
            self.msleep(30)

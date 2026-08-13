"""Standalone RVC conversion server.

Runs with the ISOLATED Python 3.10 environment (rvc-env) because rvc-python
requires fairseq + old numpy, which conflict with the main app's stack.

Start it (from the project root):
    rvc-env\\Scripts\\python.exe rvc_server.py

Endpoints:
    GET  /health            -> {"status":"ok"}
    POST /convert           multipart: file=<wav>, model_path, index_path, f0up_key
"""

from __future__ import annotations

import os
import tempfile

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import Response

from rvc_python.infer import RVCInference

# torch >= 2.6 defaults torch.load to weights_only=True, which breaks fairseq
# (used by RVC for HuBERT/feature extraction). These checkpoints come from the
# user's own trusted, downloaded RVC models, so loading with weights_only=False
# is safe and is the standard fix.
import torch as _torch

_original_torch_load = _torch.load


def _legacy_torch_load(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _original_torch_load(*args, **kwargs)


_torch.load = _legacy_torch_load

app = FastAPI(title="RVC Voice Server")
_cache = {}  # (model_path, index_path) -> RVCInference


def get_rvc(model_path: str, index_path: str = ""):
    key = (model_path, index_path)
    if key not in _cache:
        rvc = RVCInference(device="cuda")
        rvc.load_model(model_path, version="v2", index_path=index_path)
        _cache[key] = rvc
    return _cache[key]


@app.get("/health")
def health():
    return {"status": "ok"}


# ---- Voice cloning (Qwen3-TTS, Apache 2.0 - fully free incl. commercial) ----
_clone_model = None


def get_clone_model():
    global _clone_model
    if _clone_model is None:
        import torch
        from qwen_tts import Qwen3TTSModel

        _clone_model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
            device_map="cuda:0",
            dtype=torch.float32,
        )
    return _clone_model


@app.post("/clone_tts")
async def clone_tts(
    text: str = Form(...),
    reference_path: str = Form(...),
    language: str = Form("English"),
):
    model = get_clone_model()
    out_path = tempfile.mktemp(suffix=".wav")
    try:
        import numpy as np
        import soundfile as sf

        result = model.generate_voice_clone(
            text=text,
            ref_audio=reference_path,
            ref_text="",
            language=language,
            x_vector_only_mode=True,
        )
        # generate_voice_clone returns a tuple whose first element is a list of
        # waveforms; take the first waveform.
        wavs = result[0] if isinstance(result, tuple) else result
        wav = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
        if hasattr(wav, "detach"):
            wav = wav.detach().cpu()
        if hasattr(wav, "numpy"):
            wav = wav.numpy()
        wav = np.asarray(wav, dtype=np.float32)
        if wav.ndim > 1:
            wav = wav.reshape(-1)
        if wav.size == 0:
            raise RuntimeError("Qwen3-TTS returned empty audio.")
        sf.write(out_path, wav, 24000)
        with open(out_path, "rb") as f:
            return Response(content=f.read(), media_type="audio/wav")
    finally:
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass


@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    model_path: str = Form(...),
    index_path: str = Form(""),
    f0up_key: int = Form(0),
    index_rate: float = Form(0.75),
):
    rvc = get_rvc(model_path, index_path)
    in_path = tempfile.mktemp(suffix=".wav")
    out_path = tempfile.mktemp(suffix=".wav")
    try:
        import numpy as np
        import soundfile as sf

        data = await file.read()
        with open(in_path, "wb") as f:
            f.write(data)
        use_index = bool(index_path) and os.path.exists(index_path)
        # Call the underlying VC conversion directly (rvc-python's infer_file
        # passes a tuple to scipy wavfile.write, which fails on modern scipy).
        result = rvc.vc.vc_single(
            sid=0,
            input_audio_path=in_path,
            f0_up_key=f0up_key,
            f0_file="",
            f0_method="rmvpe",
            file_index=index_path if use_index else "",
            file_index2="",
            index_rate=index_rate if use_index else 0.0,
            filter_radius=3,
            resample_sr=0,
            rms_mix_rate=0.25,
            protect=0.33,
        )
        audio = result[0] if isinstance(result, tuple) else result
        if not isinstance(audio, np.ndarray):
            raise RuntimeError(f"RVC conversion failed: {audio!r}")
        # Normalize: vc_single may return int16 PCM (or float out of range);
        # writing it as raw float32 clips and sounds like static.
        if np.issubdtype(audio.dtype, np.integer):
            audio = audio.astype(np.float32) / 32768.0
        else:
            audio = audio.astype(np.float32)
        if audio.size:
            peak = float(np.abs(audio).max())
            if peak > 1.0:
                audio = audio / peak
        audio = np.clip(audio, -1.0, 1.0)
        sf.write(out_path, audio, rvc.vc.tgt_sr)
        with open(out_path, "rb") as f:
            return Response(content=f.read(), media_type="audio/wav")
    finally:
        for p in (in_path, out_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8123)

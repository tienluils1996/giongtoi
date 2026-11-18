"""VieNeu-TTS v3 Turbo — engine mặc định (ONNX trên CPU, không cần PyTorch, 48 kHz)."""

from __future__ import annotations

import os
import threading

import numpy as np

from .base import VoiceRef

REPO = "pnnbao-ump/VieNeu-TTS-v3-Turbo"


class VieNeuEngine:
    name = "vieneu"
    label = "VieNeu-TTS v3 Turbo"
    sample_rate = 48_000
    supports_speed = False  # app tự đổi tốc độ bằng time-stretch

    def __init__(self, precision: str | None = None, temperature: float = 0.8):
        from vieneu import Vieneu

        precision = precision or os.environ.get("GIONGTOI_VIENEU_PRECISION", "fp32")
        self.tts = Vieneu(backend="onnx", precision=precision)
        self.sample_rate = int(getattr(self.tts, "sample_rate", 48_000))
        self.temperature = temperature
        self._lock = threading.Lock()

    def synthesize(self, text: str, ref: VoiceRef, speed: float = 1.0) -> np.ndarray:
        with self._lock:
            audio = self.tts.infer(
                text,
                ref_audio=str(ref.audio_path),
                denoise=False,  # mẫu đã được khử ồn khi lưu
                temperature=self.temperature,
                apply_watermark=False,  # quyết định Q28: chỉ gắn nhãn metadata
            )
        return np.asarray(audio, dtype=np.float32).reshape(-1)


_denoiser = None
_denoiser_lock = threading.Lock()


def denoise_array(x: np.ndarray, sr: int) -> np.ndarray:
    """Khử ồn mẫu giọng bằng denoiser ONNX của VieNeu (resemble-enhance). Trả về ở `sr`."""
    global _denoiser
    from vieneu._v3_turbo_engine.onnx_denoiser import OnnxDenoiser

    with _denoiser_lock:
        if _denoiser is None:
            from huggingface_hub import hf_hub_download

            _denoiser = OnnxDenoiser(hf_hub_download(REPO, "denoiser.onnx"))
        clean = _denoiser.denoise(x, sr)  # 44.1 kHz
    from ..audio.processing import resample

    return resample(np.asarray(clean, dtype=np.float32), 44100, sr)

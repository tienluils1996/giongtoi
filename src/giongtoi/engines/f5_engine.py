"""F5-TTS-Vietnamese-ViVoice (hynt) — ứng viên bake-off. Cần extra `f5` (PyTorch).

Giấy phép mô hình: CC-BY-NC-SA-4.0 — chỉ dùng cá nhân, phi thương mại.
"""

from __future__ import annotations

import os
import random
import threading
from pathlib import Path

import numpy as np

from .base import EngineUnavailable, VoiceRef

# Checkpoint gốc của tác giả (5,4 GB, gồm cả trạng thái optimizer). Các bản mirror nhẹ hơn
# dùng định dạng .tar cũ, chỉ nạp được khi tắt weights_only (không an toàn) nên không dùng.
REPO = "hynt/F5-TTS-Vietnamese-ViVoice"
CKPT = "model_last.pt"


def _device() -> str:
    import torch

    if os.environ.get("GIONGTOI_F5_DEVICE"):
        return os.environ["GIONGTOI_F5_DEVICE"]
    return "mps" if torch.backends.mps.is_available() else "cpu"


def _patch_audio_loader() -> None:
    """torchaudio>=2.9 đọc file qua torchcodec, vốn cần ffmpeg cài hệ thống (Homebrew).
    Thay riêng hàm `load` mà f5_tts dùng bằng soundfile để không phụ thuộc Homebrew."""
    import types

    import soundfile as sf
    import torch
    import torchaudio
    from f5_tts.infer import utils_infer

    def load(path, *a, **k):
        data, sr = sf.read(str(path), dtype="float32", always_2d=True)
        return torch.from_numpy(data.T.copy()), sr

    shim = types.SimpleNamespace(load=load, transforms=torchaudio.transforms)
    utils_infer.torchaudio = shim


class F5Engine:
    name = "f5"
    label = "F5-TTS Vietnamese"
    sample_rate = 24_000
    supports_speed = True

    def __init__(self, nfe_step: int = 32):
        try:
            from f5_tts.api import F5TTS
        except ImportError as e:
            raise EngineUnavailable("Chưa cài F5-TTS: ./scripts/setup.sh --with-f5") from e
        from huggingface_hub import hf_hub_download

        _patch_audio_loader()

        ckpt = hf_hub_download(REPO, CKPT)  # torch.load(weights_only=True) trong f5_tts → an toàn
        cfg = Path(hf_hub_download(REPO, "config.json"))
        vocab = cfg.parent / "vocab.txt"  # repo này đặt bảng ký tự trong config.json
        if not vocab.exists():
            vocab.write_bytes(cfg.read_bytes())
        self.nfe_step = nfe_step
        self.tts = F5TTS(model="F5TTS_Base", ckpt_file=ckpt, vocab_file=str(vocab), device=_device())
        self._lock = threading.Lock()

    def synthesize(self, text: str, ref: VoiceRef, speed: float = 1.0) -> np.ndarray:
        if not ref.transcript:
            raise ValueError("F5-TTS cần transcript chính xác của mẫu giọng (sửa ở trang Giọng của tôi).")
        with self._lock:
            wav, sr, _ = self.tts.infer(
                ref_file=str(ref.audio_path),
                ref_text=ref.transcript.lower(),
                gen_text=text.lower(),  # mô hình được huấn luyện với chữ thường
                speed=speed,
                nfe_step=self.nfe_step,
                remove_silence=False,
                show_info=lambda *a, **k: None,
                # f5_tts ghi seed vào PYTHONHASHSEED; seed mặc định (tới sys.maxsize) vượt giới hạn
                # 2^32 và làm hỏng mọi tiến trình Python con khởi chạy sau đó.
                seed=random.randint(0, 2**32 - 1),
            )
        self.sample_rate = int(sr)
        return np.asarray(wav, dtype=np.float32).reshape(-1)

"""Giao diện chung cho mọi mô hình TTS — đổi mô hình không cần viết lại app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class VoiceRef:
    """Một mẫu giọng tham chiếu: file WAV sạch + transcript chính xác (nếu có)."""

    audio_path: Path
    transcript: str = ""


class Engine(Protocol):
    name: str
    label: str
    sample_rate: int
    supports_speed: bool  # engine tự chỉnh tốc độ (nếu không, app dùng time-stretch)

    def synthesize(self, text: str, ref: VoiceRef, speed: float = 1.0) -> np.ndarray:
        """Trả về audio mono float32 trong [-1, 1] ở self.sample_rate."""
        ...


class EngineUnavailable(RuntimeError):
    """Engine chưa được cài (vd thiếu extra `f5`)."""

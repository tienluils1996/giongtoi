"""Engine giả lập cho test: sinh âm sin, độ dài tỉ lệ số ký tự."""

from __future__ import annotations

import numpy as np

from .base import VoiceRef


class FakeEngine:
    name = "fake"
    label = "Giả lập (test)"
    sample_rate = 16000
    supports_speed = True

    def __init__(self, seconds_per_char: float = 0.01, fail_on: str | None = None):
        self.seconds_per_char = seconds_per_char
        self.fail_on = fail_on
        self.calls: list[str] = []

    def synthesize(self, text: str, ref: VoiceRef, speed: float = 1.0) -> np.ndarray:
        self.calls.append(text)
        if self.fail_on and self.fail_on in text:
            raise RuntimeError(f"lỗi giả lập với: {text}")
        n = max(1, int(len(text) * self.seconds_per_char / speed * self.sample_rate))
        t = np.arange(n) / self.sample_rate
        return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)

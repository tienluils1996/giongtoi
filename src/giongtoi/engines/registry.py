"""Danh sách engine + nạp lười. Chỉ giữ một mô hình lớn trong RAM tại một thời điểm."""

from __future__ import annotations

import threading
from typing import Callable

from .base import Engine, EngineUnavailable


def _make_vieneu() -> Engine:
    from .vieneu_engine import VieNeuEngine

    return VieNeuEngine()


def _make_f5() -> Engine:
    from .f5_engine import F5Engine

    return F5Engine()


def _make_fake() -> Engine:
    from .fake import FakeEngine

    return FakeEngine()


FACTORIES: dict[str, tuple[str, Callable[[], Engine]]] = {
    "vieneu": ("VieNeu-TTS v3 Turbo", _make_vieneu),
    "f5": ("F5-TTS Vietnamese", _make_f5),
    "fake": ("Giả lập (test)", _make_fake),
}

_lock = threading.Lock()
_current: dict[str, Engine] = {}


def available() -> dict[str, str]:
    """name → label của các engine dùng được (đã cài thư viện)."""
    out = {}
    for name, (label, _) in FACTORIES.items():
        if name == "fake":
            continue
        if is_installed(name):
            out[name] = label
    return out


def is_installed(name: str) -> bool:
    import importlib.util

    module = {"vieneu": "vieneu", "f5": "f5_tts", "fake": "numpy"}[name]
    return importlib.util.find_spec(module) is not None


def get(name: str) -> Engine:
    if name not in FACTORIES:
        raise EngineUnavailable(f"Không có engine '{name}'")
    with _lock:
        if name in _current:
            return _current[name]
        if not is_installed(name):
            raise EngineUnavailable(
                f"Engine '{name}' chưa được cài. Chạy: ./scripts/setup.sh --with-{name}"
            )
        _current.clear()  # giải phóng mô hình cũ trước khi nạp mô hình mới
        engine = FACTORIES[name][1]()
        _current[name] = engine
        return engine


def register(engine: Engine) -> None:
    """Dùng trong test: gắn sẵn một engine (vd FakeEngine) vào cache."""
    with _lock:
        _current.clear()
        _current[engine.name] = engine

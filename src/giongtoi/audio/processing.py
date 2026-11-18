"""Xử lý âm thanh: đọc/ghi, resample, cắt lặng, chuẩn hoá âm lượng, tốc độ, ghép, xuất file."""

from __future__ import annotations

import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr

from ..config import AI_TAG


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _ffmpeg(*args: str) -> None:
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg lỗi: {proc.stderr.strip()}")


# ---------------------------------------------------------------- đọc / chuyển đổi

def to_mono(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    return x.mean(axis=1) if x.ndim == 2 else x


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return x
    return soxr.resample(x, sr_in, sr_out).astype(np.float32)


def convert_to_wav(src: Path, dst: Path, sr: int | None = None) -> Path:
    """Chuyển mọi định dạng (webm, m4a, mp3...) thành WAV mono 16-bit."""
    args = ["-i", str(src), "-ac", "1"]
    if sr:
        args += ["-ar", str(sr)]
    args += ["-c:a", "pcm_s16le", str(dst)]
    _ffmpeg(*args)
    return Path(dst)


def load_audio(path: Path, target_sr: int | None = None) -> tuple[np.ndarray, int]:
    path = Path(path)
    try:
        data, sr = sf.read(path, dtype="float32", always_2d=False)
    except Exception:
        with tempfile.TemporaryDirectory() as td:
            tmp = convert_to_wav(path, Path(td) / "conv.wav")
            data, sr = sf.read(tmp, dtype="float32", always_2d=False)
    data = to_mono(data)
    if target_sr:
        data, sr = resample(data, sr, target_sr), target_sr
    return data, sr


# ---------------------------------------------------------------- xử lý tín hiệu

def trim_silence(x: np.ndarray, sr: int, top_db: float = 40, pad_ms: int = 80) -> np.ndarray:
    import librosa

    if len(x) == 0:
        return x
    _, (start, end) = librosa.effects.trim(x, top_db=top_db, frame_length=1024, hop_length=256)
    pad = int(pad_ms / 1000 * sr)
    return x[max(0, start - pad) : min(len(x), end + pad)]


def normalize_loudness(x: np.ndarray, sr: int, target_dbfs: float = -20.0) -> np.ndarray:
    rms = float(np.sqrt(np.mean(x**2))) if len(x) else 0.0
    if rms < 1e-6:
        return x
    y = x * (10 ** (target_dbfs / 20) / rms)
    peak = float(np.max(np.abs(y)))
    if peak > 0.99:
        y = y * (0.99 / peak)
    return y.astype(np.float32)


def change_speed(x: np.ndarray, sr: int, speed: float) -> np.ndarray:
    """Đổi tốc độ giữ nguyên cao độ (ffmpeg atempo)."""
    if abs(speed - 1.0) < 1e-3:
        return x
    speed = float(np.clip(speed, 0.5, 2.0))
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td) / "in.wav", Path(td) / "out.wav"
        sf.write(src, x, sr, subtype="FLOAT")
        _ffmpeg("-i", str(src), "-filter:a", f"atempo={speed:.4f}", "-c:a", "pcm_f32le", str(dst))
        y, _ = sf.read(dst, dtype="float32")
    return to_mono(y)


def silence(ms: int, sr: int) -> np.ndarray:
    return np.zeros(int(ms / 1000 * sr), dtype=np.float32)


def concat_with_pauses(clips: list[np.ndarray], sr: int, pauses_ms: list[int]) -> np.ndarray:
    """pauses_ms[i] = khoảng lặng sau clip i (len = len(clips) - 1)."""
    parts: list[np.ndarray] = []
    for i, c in enumerate(clips):
        parts.append(np.asarray(c, dtype=np.float32))
        if i < len(clips) - 1:
            parts.append(silence(pauses_ms[i] if i < len(pauses_ms) else 0, sr))
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)


def fade_edges(x: np.ndarray, sr: int, ms: int = 10) -> np.ndarray:
    n = min(len(x) // 2, int(ms / 1000 * sr))
    if n <= 0:
        return x
    y = x.copy()
    ramp = np.linspace(0, 1, n, dtype=np.float32)
    y[:n] *= ramp
    y[-n:] *= ramp[::-1]
    return y


# ---------------------------------------------------------------- xuất file + metadata

def _tag(path: Path, title: str | None) -> None:
    from mutagen.id3 import COMM, ID3, TIT2, TSSE

    if path.suffix.lower() == ".wav":
        from mutagen.wave import WAVE

        f = WAVE(path)
        if f.tags is None:
            f.add_tags()
        tags = f.tags
    else:
        try:
            tags = ID3(path)
        except Exception:
            tags = ID3()
        f = None
    tags.add(COMM(encoding=3, lang="vie", desc="", text=AI_TAG))
    tags.add(TSSE(encoding=3, text="GiọngTôi"))
    if title:
        tags.add(TIT2(encoding=3, text=title))
    if f is not None:
        f.save()
    else:
        tags.save(path)


def read_comment(path: Path) -> str:
    path = Path(path)
    if path.suffix.lower() == ".wav":
        from mutagen.wave import WAVE

        tags = WAVE(path).tags
    else:
        from mutagen.id3 import ID3

        tags = ID3(path)
    if not tags:
        return ""
    return " ".join(str(f) for f in tags.getall("COMM"))


def export_wav(x: np.ndarray, sr: int, path: Path, title: str | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.clip(x, -1, 1), sr, subtype="PCM_16")
    _tag(path, title)
    return path


def export_mp3(wav_path: Path, mp3_path: Path, title: str | None = None, bitrate: str = "192k") -> Path:
    mp3_path = Path(mp3_path)
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg("-i", str(wav_path), "-map_metadata", "-1", "-codec:a", "libmp3lame", "-b:a", bitrate, str(mp3_path))
    _tag(mp3_path, title)
    return mp3_path

import numpy as np
import soundfile as sf

from giongtoi.audio import processing as ap

SR = 16000


def tone(seconds, amp=0.3, sr=SR):
    t = np.arange(int(seconds * sr)) / sr
    return (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def test_concat_with_pauses_lengths():
    a, b = tone(1.0), tone(0.5)
    out = ap.concat_with_pauses([a, b], SR, pauses_ms=[300])
    assert len(out) == len(a) + len(b) + int(0.3 * SR)


def test_trim_silence_removes_edges_keeps_padding():
    sig = np.concatenate([np.zeros(SR), tone(1.0), np.zeros(SR)])
    out = ap.trim_silence(sig, SR, pad_ms=50)
    assert abs(len(out) - (SR + 2 * int(0.05 * SR))) < int(0.1 * SR)  # sai số ~1 khung phân tích


def test_normalize_loudness_peak_safe():
    out = ap.normalize_loudness(tone(1.0, amp=0.01), SR, target_dbfs=-20)
    rms = np.sqrt(np.mean(out**2))
    assert abs(20 * np.log10(rms) - (-20)) < 1.0
    assert np.max(np.abs(ap.normalize_loudness(tone(1.0, amp=0.9), SR, target_dbfs=0))) <= 0.99


def test_change_speed_changes_duration():
    sig = tone(2.0)
    faster = ap.change_speed(sig, SR, 1.25)
    assert abs(len(faster) / SR - 1.6) < 0.1
    assert ap.change_speed(sig, SR, 1.0) is sig


def test_resample():
    out = ap.resample(tone(1.0), SR, 48000)
    assert abs(len(out) - 48000) <= 2


def test_load_audio_mono_resampled(tmp_path):
    stereo = np.stack([tone(1.0, sr=44100), tone(1.0, sr=44100)], axis=1)
    p = tmp_path / "in.wav"
    sf.write(p, stereo, 44100)
    out, sr = ap.load_audio(p, target_sr=24000)
    assert sr == 24000 and out.ndim == 1 and abs(len(out) - 24000) <= 2


def test_export_wav_and_mp3_with_metadata(tmp_path):
    sig = tone(1.0)
    wav = ap.export_wav(sig, SR, tmp_path / "a.wav", title="Thử")
    mp3 = ap.export_mp3(wav, tmp_path / "a.mp3", title="Thử")
    assert wav.exists() and mp3.exists() and mp3.stat().st_size > 1000
    assert "AI-generated" in ap.read_comment(mp3)
    assert "AI-generated" in ap.read_comment(wav)


def test_convert_any_to_wav(tmp_path):
    src = ap.export_wav(tone(1.0), SR, tmp_path / "src.wav")
    mp3 = ap.export_mp3(src, tmp_path / "src.mp3")
    out = ap.convert_to_wav(mp3, tmp_path / "back.wav", sr=24000)
    data, sr = sf.read(out)
    assert sr == 24000 and abs(len(data) / sr - 1.0) < 0.1

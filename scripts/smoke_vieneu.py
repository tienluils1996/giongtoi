"""Chạy thử engine VieNeu thật: tạo mẫu tham chiếu từ giọng có sẵn, rồi clone lại.

uv run python scripts/smoke_vieneu.py <thư_mục_ra>
"""

import sys
import time
from pathlib import Path

import soundfile as sf

from giongtoi.engines.base import VoiceRef
from giongtoi.engines.vieneu_engine import VieNeuEngine, denoise_array
from giongtoi.text.normalize import normalize

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)

t = time.time()
eng = VieNeuEngine()
print(f"load: {time.time() - t:.1f}s, sr={eng.sample_rate}")

# 1) mẫu tham chiếu giả lập = giọng preset (thay cho giọng người dùng)
ref_text = "Xin chào, tôi đang ghi âm giọng nói của mình để tạo một trợ lý đọc văn bản."
t = time.time()
ref = eng.tts.infer(ref_text, apply_watermark=False)
sf.write(out / "ref.wav", ref, eng.sample_rate)
print(f"preset: {time.time() - t:.1f}s, {len(ref) / eng.sample_rate:.1f}s audio")

t = time.time()
d = denoise_array(ref, eng.sample_rate)
print(f"denoise: {time.time() - t:.1f}s")

text = normalize("Hôm nay là ngày 18/11/2026, tôi đăng video lên YouTube lúc 8h30 và có 1.250 lượt xem.")
print("normalized:", text)
for i in range(2):
    t = time.time()
    audio = eng.synthesize(text, VoiceRef(out / "ref.wav", ref_text))
    dur = len(audio) / eng.sample_rate
    el = time.time() - t
    print(f"clone #{i}: {el:.1f}s for {dur:.1f}s audio (RTF {el / dur:.2f})")
sf.write(out / "clone.wav", audio, eng.sample_rate)

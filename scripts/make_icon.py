"""Vẽ icon app (sóng âm trên nền cam bo góc) → assets/AppIcon.icns. Chỉ cần numpy + công cụ macOS."""

import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

import numpy as np

N = 1024
root = Path(__file__).resolve().parent.parent
out = root / "assets" / "AppIcon.icns"


def png_bytes(rgba: np.ndarray) -> bytes:
    h, w, _ = rgba.shape
    raw = b"".join(b"\x00" + rgba[y].tobytes() for y in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


yy, xx = np.mgrid[0:N, 0:N].astype(np.float32) + 0.5
img = np.zeros((N, N, 4), np.float32)

# nền bo góc kiểu macOS (lề 100px, bán kính 185px), gradient cam
m, r = 100, 185
dx = np.maximum(np.maximum(m + r - xx, xx - (N - m - r)), 0)
dy = np.maximum(np.maximum(m + r - yy, yy - (N - m - r)), 0)
inside = np.clip(r - np.sqrt(dx**2 + dy**2) + 0.5, 0, 1)
inside *= (xx > m - 1) & (xx < N - m + 1) & (yy > m - 1) & (yy < N - m + 1)
t = (yy - m) / (N - 2 * m)
top, bot = np.array([251, 146, 60]), np.array([194, 65, 12])
for c in range(3):
    img[..., c] = top[c] * (1 - t) + bot[c] * t
img[..., 3] = inside * 255

# các vạch sóng âm màu trắng
heights = [0.18, 0.34, 0.52, 0.72, 0.52, 0.86, 0.6, 0.38, 0.22]
bw, gap = 46, 30
total = len(heights) * bw + (len(heights) - 1) * gap
x0 = (N - total) / 2
for i, hgt in enumerate(heights):
    cx = x0 + i * (bw + gap) + bw / 2
    half = hgt * 280
    # vạch bo tròn hai đầu = khoảng cách tới đoạn thẳng đứng
    d = np.sqrt((xx - cx) ** 2 + np.maximum(np.abs(yy - N / 2) - half, 0) ** 2)
    a = np.clip(bw / 2 - d + 0.5, 0, 1) * inside
    for c in range(3):
        img[..., c] = img[..., c] * (1 - a) + 255 * a

base = img.clip(0, 255).astype(np.uint8)
with tempfile.TemporaryDirectory() as td:
    src = Path(td) / "icon.png"
    src.write_bytes(png_bytes(base))
    iconset = Path(td) / "AppIcon.iconset"
    iconset.mkdir()
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = size * scale
            name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
            subprocess.run(["sips", "-z", str(px), str(px), str(src), "--out", str(iconset / name)],
                           check=True, capture_output=True)
    out.parent.mkdir(exist_ok=True)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True)
    (out.parent / "icon.png").write_bytes(src.read_bytes())
print(out)
sys.exit(0)

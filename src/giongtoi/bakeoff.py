"""Bake-off: cùng một mẫu giọng, nhiều mô hình đọc cùng bộ câu → trang nghe mù A/B/C."""

from __future__ import annotations

import base64
import html
import json
import logging
import random
import shutil
import time
from pathlib import Path

import soundfile as sf

from .config import get_paths
from .engines import registry
from .engines.base import VoiceRef
from .text.normalize import normalize

log = logging.getLogger("giongtoi")

TEST_SENTENCES = [
    "Chào buổi sáng, hôm nay mình sẽ kể cho bạn nghe một câu chuyện nhỏ.",
    "Ngày 15/3/2025, nhiệt độ ở Hà Nội lên tới 32°C, cao nhất trong tuần.",
    "Mình vừa đăng video mới lên YouTube và Facebook, mọi người xem thử nhé!",
    "Bạn đã bao giờ tự hỏi vì sao con người lại mơ khi ngủ chưa?",
    "Giá vé là 150.000đ một người, trẻ em dưới 6 tuổi được miễn phí hoàn toàn.",
    "Khi mùa thu tới, những con đường ngập lá vàng, gió heo may se lạnh, và lòng người bỗng chùng xuống một cách khó tả.",
    "Ôi trời ơi, thật không thể tin được, chúng ta thắng rồi!",
    "Artificial intelligence is changing the way we work and live.",
]


def _letters(n: int) -> list[str]:
    return [chr(ord("A") + i) for i in range(n)]


def run_bakeoff(
    voice_id: str | None = None,
    engines: list[str] | None = None,
    ref_wav: Path | None = None,
    ref_text: str = "",
    sentences: list[str] | None = None,
    out_root: Path | None = None,
) -> Path:
    from .studio import Studio

    paths = get_paths().ensure()
    sentences = sentences or TEST_SENTENCES
    if ref_wav is None:
        studio = Studio(paths)
        vid = voice_id or studio.ensure_default_voice()
        ref = studio.store.default_ref(vid)
        if not ref:
            raise SystemExit("Hồ sơ giọng chưa có mẫu. Hãy ghi âm trong web UI trước.")
        ref_wav, ref_text = studio.abs(ref["audio_path"]), ref["transcript"]

    names = engines or list(registry.available())
    if "f5" in names and not ref_text:
        log.warning("Bỏ F5-TTS: mẫu giọng không có transcript.")
        names = [n for n in names if n != "f5"]
    if not names:
        raise SystemExit("Không có engine nào khả dụng.")

    run_dir = (out_root or paths.bakeoff) / time.strftime("%Y-%m-%d_%H%M%S")
    run_dir.mkdir(parents=True)
    shutil.copy(ref_wav, run_dir / "ref.wav")
    vref = VoiceRef(run_dir / "ref.wav", ref_text)

    shuffled = names[:]
    random.shuffle(shuffled)
    key: dict[str, dict] = {}
    for letter, name in zip(_letters(len(shuffled)), shuffled):
        t0 = time.time()
        engine = registry.get(name)
        load_s = time.time() - t0
        engine.synthesize("Khởi động mô hình.", vref)  # làm nóng, không tính giờ
        timings = []
        for i, s in enumerate(sentences):
            text = normalize(s)
            t = time.time()
            audio = engine.synthesize(text, vref)
            el = time.time() - t
            dur = len(audio) / engine.sample_rate
            sf.write(run_dir / f"{letter}_{i + 1}.wav", audio, engine.sample_rate, subtype="PCM_16")
            timings.append({"seconds": round(el, 2), "audio": round(dur, 2)})
            log.info("%s câu %d: %.1fs cho %.1fs audio", name, i + 1, el, dur)
        total_el = sum(t["seconds"] for t in timings)
        total_audio = sum(t["audio"] for t in timings) or 1
        key[letter] = {
            "engine": name,
            "label": registry.FACTORIES[name][0],
            "load_seconds": round(load_s, 1),
            "rtf": round(total_el / total_audio, 2),
            "timings": timings,
        }
    (run_dir / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2))
    (run_dir / "index.html").write_text(_page(sentences, key, ref_text), encoding="utf-8")
    return run_dir / "index.html"


def _page(sentences: list[str], key: dict, ref_text: str) -> str:
    letters = sorted(key)
    secret = base64.b64encode(json.dumps(key, ensure_ascii=False).encode()).decode()
    head = "".join(f"<th>{l}</th>" for l in letters)
    rows = []
    for i, s in enumerate(sentences, 1):
        cells = "".join(
            f'<td><audio controls preload="none" src="{l}_{i}.wav"></audio>'
            f'<select data-k="{l}|{i}"><option value="">–</option>'
            + "".join(f"<option>{n}</option>" for n in range(1, 6))
            + "</select></td>"
            for l in letters
        )
        rows.append(f"<tr><td class='s'><b>{i}.</b> {html.escape(s)}</td>{cells}</tr>")
    crit = "".join(
        f"<tr><td>{c}</td>"
        + "".join(
            f'<td><select data-k="{l}|{cid}"><option value="">–</option>'
            + "".join(f"<option>{n}</option>" for n in range(1, 6))
            + "</select></td>"
            for l in letters
        )
        + "</tr>"
        for cid, c in [("giong", "Giống giọng tôi"), ("tunhien", "Tự nhiên, ngữ điệu"), ("phatam", "Phát âm đúng")]
    )
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Nghe mù</title>
<style>
:root{{--bg:#f6f5f2;--card:#fff;--text:#1d1c1a;--muted:#6d6a64;--line:#e4e1da;--accent:#c2410c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161514;--card:#1f1e1c;--text:#ecebe8;--muted:#a19d95;--line:#34322e;--accent:#f97316}}}}
body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}} table{{border-collapse:collapse;width:100%;background:var(--card)}}
td,th{{border-bottom:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}} td.s{{max-width:320px}}
audio{{width:200px;height:32px;display:block;margin-bottom:4px}} select{{font:inherit}}
.wrap{{overflow-x:auto}} button{{font:inherit;font-weight:600;padding:8px 16px;border-radius:8px;border:0;background:var(--accent);color:#fff;cursor:pointer}}
.muted{{color:var(--muted)}} #result{{margin-top:16px}}
</style></head><body><main>
<h1>Nghe mù — chấm điểm từng mô hình</h1>
<p>Mẫu giọng tham chiếu: <audio controls src="ref.wav"></audio> <span class="muted">{html.escape(ref_text)}</span></p>
<p class="muted">Nghe từng câu, chấm 1 (tệ) – 5 (rất tốt). Điểm được lưu trong trình duyệt. Chấm xong mới bấm “Hiện tên mô hình”.</p>
<div class="wrap"><table><thead><tr><th>Câu</th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Đánh giá tổng thể</h2>
<div class="wrap"><table><thead><tr><th>Tiêu chí</th>{head}</tr></thead><tbody>{crit}</tbody></table></div>
<p><button id="reveal">Hiện tên mô hình</button></p><div id="result"></div>
<script>
const KEY = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob("{secret}"), c => c.charCodeAt(0))));
const store = (() => {{ try {{ return window.localStorage; }} catch (e) {{ return null; }} }})();
const SK = 'bakeoff:' + location.pathname;
let saved = {{}}; try {{ saved = JSON.parse(store.getItem(SK) || '{{}}'); }} catch (e) {{}}
document.querySelectorAll('select[data-k]').forEach(s => {{
  if (saved[s.dataset.k]) s.value = saved[s.dataset.k];
  s.addEventListener('change', () => {{ saved[s.dataset.k] = s.value; try {{ store.setItem(SK, JSON.stringify(saved)); }} catch (e) {{}} }});
}});
document.getElementById('reveal').onclick = () => {{
  const rows = Object.keys(KEY).sort().map(l => {{
    const vals = Object.entries(saved).filter(([k, v]) => k.startsWith(l + '|') && v).map(([, v]) => +v);
    const avg = vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2) : '–';
    return `<tr><td>${{l}}</td><td><b>${{KEY[l].label}}</b></td><td>${{avg}}</td><td>${{KEY[l].rtf}} (càng nhỏ càng nhanh)</td></tr>`;
  }}).join('');
  document.getElementById('result').innerHTML = `<table><thead><tr><th>Mã</th><th>Mô hình</th><th>Điểm TB</th><th>Hệ số thời gian thực</th></tr></thead><tbody>${{rows}}</tbody></table>
  <p class="muted">Chọn mô hình thắng làm mặc định ở trang “Đọc văn bản” (ô Mô hình — app nhớ lựa chọn cuối cùng).</p>`;
}};
</script></main></body></html>"""

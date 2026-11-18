"""Lớp nghiệp vụ trung tâm: hồ sơ giọng, dự án đọc, xử lý từng câu, ghép chương.

Web UI, CLI và worker nền đều gọi qua đây.
"""

from __future__ import annotations

import logging
import re
import shutil
import threading
import time
import unicodedata
from pathlib import Path
from typing import Callable

import numpy as np

from .audio import processing as ap
from .config import Paths, default_engine
from .engines.base import Engine, VoiceRef
from .storage.db import Store
from .text.normalize import normalize
from .text.segment import split_chapters, split_sentences

log = logging.getLogger("giongtoi")

REF_SR = 24000
REF_MAX_SECONDS = 15.0

DenoiseFn = Callable[[np.ndarray, int], np.ndarray]


def slugify(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "giong"


class Studio:
    def __init__(
        self,
        paths: Paths,
        engine_getter: Callable[[str], Engine] | None = None,
        denoise_fn: DenoiseFn | None = None,
    ):
        from .engines import registry

        self.paths = paths.ensure()
        self.store = Store(paths.db)
        self.get_engine = engine_getter or registry.get
        self.denoise_fn = denoise_fn
        self.store.reset_running()
        self._step_lock = threading.Lock()

    # ------------------------------------------------------------ đường dẫn
    def rel(self, p: Path) -> str:
        return str(Path(p).resolve().relative_to(self.paths.root.resolve()))

    def abs(self, rel: str | None) -> Path:
        return self.paths.root / rel if rel else self.paths.root

    # ------------------------------------------------------------ hồ sơ giọng
    def create_voice(self, name: str) -> str:
        base = slugify(name)
        vid, n = base, 2
        while self.store.get_voice(vid):
            vid, n = f"{base}-{n}", n + 1
        self.store.create_voice(vid, name)
        (self.paths.voices / vid / "refs").mkdir(parents=True, exist_ok=True)
        (self.paths.voices / vid / "raw").mkdir(parents=True, exist_ok=True)
        return vid

    def ensure_default_voice(self) -> str:
        voices = self.store.list_voices()
        return voices[0]["id"] if voices else self.create_voice("Giọng của tôi")

    def add_reference(
        self,
        voice_id: str,
        src: Path,
        transcript: str = "",
        label: str = "bình thường",
        denoise: bool = True,
    ) -> int:
        """Lưu bản gốc, rồi xử lý: mono 24 kHz → khử ồn → cắt lặng → chuẩn hoá âm lượng."""
        vdir = self.paths.voices / voice_id
        stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
        raw = vdir / "raw" / f"{stamp}{Path(src).suffix.lower() or '.wav'}"
        raw.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, raw)

        x, sr = ap.load_audio(raw, target_sr=REF_SR)
        if denoise and self.denoise_fn is not None:
            try:
                x = self.denoise_fn(x, sr)
            except Exception as e:  # khử ồn lỗi không nên chặn việc lưu mẫu
                log.warning("Khử ồn lỗi, bỏ qua: %s", e)
        x = ap.trim_silence(x, sr, top_db=35, pad_ms=150)
        x = ap.normalize_loudness(x, sr, target_dbfs=-20)
        if len(x) > REF_MAX_SECONDS * sr and not transcript:
            x = x[: int(REF_MAX_SECONDS * sr)]
        out = vdir / "refs" / f"{stamp}.wav"
        ap.export_wav(x, sr, out)
        return self.store.add_ref(
            voice_id, self.rel(out), transcript.strip(), len(x) / sr, label, raw_path=self.rel(raw)
        )

    def delete_reference(self, ref_id: int) -> None:
        ref = self.store.delete_ref(ref_id)
        if ref:
            for key in ("audio_path", "raw_path"):
                if ref.get(key):
                    self.abs(ref[key]).unlink(missing_ok=True)

    def voice_ref(self, voice_id: str | None, ref_id: int | None = None) -> VoiceRef:
        ref = self.store.get_ref(ref_id) if ref_id else None
        if ref is None and voice_id:
            ref = self.store.default_ref(voice_id)
        if ref is None:
            raise ValueError("Chưa có mẫu giọng. Hãy ghi âm hoặc tải lên mẫu giọng trước.")
        return VoiceRef(self.abs(ref["audio_path"]), ref["transcript"])

    # ------------------------------------------------------------ dự án đọc
    def create_project(
        self,
        text: str,
        voice_id: str | None,
        title: str | None = None,
        engine: str | None = None,
        speed: float = 1.0,
        pause_sentence_ms: int = 300,
        pause_paragraph_ms: int = 700,
        english_mode: str = "vietnamize",
        ref_id: int | None = None,
    ) -> int:
        chapters = split_chapters(text)
        if not chapters:
            raise ValueError("Văn bản trống.")
        data = [
            (c.title, [(s.text, s.paragraph_end) for s in split_sentences(c.body)]) for c in chapters
        ]
        data = [(t, segs) for t, segs in data if segs]
        if not title:
            if chapters[0].title not in ("Toàn văn", "Mở đầu", "Phần 1"):
                title = chapters[0].title
            else:
                first = re.sub(r"\s+", " ", text.strip())
                title = first[:60] + ("…" if len(first) > 60 else "")
        return self.store.create_project(
            title=title,
            source_text=text,
            engine=engine or default_engine(),
            voice_id=voice_id,
            ref_id=ref_id,
            speed=speed,
            pause_sentence_ms=pause_sentence_ms,
            pause_paragraph_ms=pause_paragraph_ms,
            english_mode=english_mode,
            chapters=data,
        )

    def queue(self, pid: int) -> None:
        self.store.update_project(pid, status="queued", error=None)

    def pause(self, pid: int) -> None:
        p = self.store.get_project(pid)
        if p and p["status"] in ("queued", "running"):
            self.store.update_project(pid, status="paused")

    def delete_project(self, pid: int) -> None:
        self.store.delete_project(pid)
        shutil.rmtree(self.paths.projects / str(pid), ignore_errors=True)

    def regenerate_segment(self, sid: int, new_text: str | None = None) -> None:
        seg = self.store.get_segment(sid)
        if not seg:
            raise ValueError("Không tìm thấy câu.")
        fields = {"status": "pending", "error": None}
        if new_text is not None and new_text.strip():
            fields["text"] = new_text.strip()
        self.store.update_segment(sid, **fields)
        self.queue(seg["project_id"])

    def preview_text(self, text: str, english_mode: str = "vietnamize") -> str:
        return normalize(text, english_mode=english_mode, user_lexicon=self.store.lexicon())

    # ------------------------------------------------------------ worker
    def step(self) -> bool:
        """Làm một đơn vị việc (một câu, hoặc ghép một dự án). Trả về False nếu rảnh."""
        with self._step_lock:
            project = self.store.next_queued_project()
            if not project:
                return False
            pid = project["id"]
            if project["status"] != "running":
                self.store.update_project(pid, status="running")
            seg = self.store.next_pending_segment(pid)
            if seg:
                self._synthesize_segment(project, seg)
                return True
            self._finish(project)
            return True

    def run_until_idle(self, max_steps: int = 100_000) -> None:
        for _ in range(max_steps):
            if not self.step():
                return

    def _synthesize_segment(self, project: dict, seg: dict) -> None:
        t0 = time.time()
        try:
            engine = self.get_engine(project["engine"])
            ref = self.voice_ref(project["voice_id"], project["ref_id"])
            text = normalize(
                seg["text"], english_mode=project["english_mode"], user_lexicon=self.store.lexicon()
            )
            speed = float(project["speed"])
            audio = engine.synthesize(text, ref, speed=speed if engine.supports_speed else 1.0)
            sr = engine.sample_rate
            if not engine.supports_speed:
                audio = ap.change_speed(audio, sr, speed)
            audio = ap.trim_silence(audio, sr, top_db=45, pad_ms=40)
            audio = ap.fade_edges(ap.normalize_loudness(audio, sr, -20), sr)
            pdir = self.paths.projects / str(project["id"]) / "segments"
            out = pdir / f"{seg['id']}-{int(time.time() * 1000)}.wav"
            pdir.mkdir(parents=True, exist_ok=True)
            import soundfile as sf

            sf.write(out, audio, sr, subtype="PCM_16")
            if seg["audio_path"]:
                self.abs(seg["audio_path"]).unlink(missing_ok=True)
            self.store.update_segment(
                seg["id"], status="done", audio_path=self.rel(out), duration=len(audio) / sr,
                error=None, seconds=time.time() - t0,
            )
        except Exception as e:
            log.exception("Lỗi khi đọc câu %s", seg["id"])
            self.store.update_segment(seg["id"], status="error", error=str(e), seconds=time.time() - t0)

    def _finish(self, project: dict) -> None:
        pid = project["id"]
        segs = self.store.list_segments(pid)
        errors = [s for s in segs if s["status"] == "error"]
        if errors:
            self.store.update_project(
                pid, status="error", error=f"{len(errors)} câu bị lỗi — sửa hoặc tạo lại các câu đó."
            )
            return
        try:
            for ch in self.store.list_chapters(pid):
                self._assemble_chapter(project, ch)
            self.store.update_project(pid, status="done", error=None)
        except Exception as e:
            log.exception("Lỗi khi ghép dự án %s", pid)
            self.store.update_project(pid, status="error", error=f"Lỗi ghép audio: {e}")

    def _assemble_chapter(self, project: dict, ch: dict) -> None:
        segs = self.store.list_segments(project["id"], ch["id"])
        if not segs:
            return
        clips, pauses, sr = [], [], None
        for s in segs:
            x, s_sr = ap.load_audio(self.abs(s["audio_path"]))
            if sr is None:
                sr = s_sr
            clips.append(ap.resample(x, s_sr, sr))
            pauses.append(project["pause_paragraph_ms"] if s["paragraph_end"] else project["pause_sentence_ms"])
        audio = ap.concat_with_pauses(clips, sr, pauses[:-1])
        audio = np.concatenate([ap.silence(200, sr), audio, ap.silence(400, sr)])
        name = f"{ch['idx'] + 1:02d}-{slugify(ch['title'])[:40]}"
        pdir = self.paths.projects / str(project["id"])
        for key in ("wav_path", "mp3_path"):
            if ch.get(key):
                self.abs(ch[key]).unlink(missing_ok=True)
        stamp = int(time.time())
        title = f"{project['title']} — {ch['title']}"
        wav = ap.export_wav(audio, sr, pdir / f"{name}-{stamp}.wav", title=title)
        mp3 = ap.export_mp3(wav, pdir / f"{name}-{stamp}.mp3", title=title)
        self.store.update_chapter(ch["id"], wav_path=self.rel(wav), mp3_path=self.rel(mp3), duration=len(audio) / sr)


class Worker(threading.Thread):
    """Luồng nền: chạy Studio.step() liên tục, nghỉ khi rảnh."""

    def __init__(self, studio: Studio, idle_sleep: float = 0.5):
        super().__init__(daemon=True, name="giongtoi-worker")
        self.studio = studio
        self.idle_sleep = idle_sleep
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                busy = self.studio.step()
            except Exception:
                log.exception("Worker lỗi")
                busy = False
            if not busy:
                self._stop.wait(self.idle_sleep)

    def stop(self) -> None:
        self._stop.set()

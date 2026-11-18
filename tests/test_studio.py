from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from giongtoi.config import Paths
from giongtoi.engines.fake import FakeEngine
from giongtoi.studio import Studio


@pytest.fixture
def engine():
    return FakeEngine()


@pytest.fixture
def studio(tmp_path, engine):
    return Studio(Paths(tmp_path).ensure(), engine_getter=lambda name: engine, denoise_fn=None)


def make_wav(path: Path, seconds=4.0, sr=44100):
    t = np.arange(int(seconds * sr)) / sr
    sig = 0.3 * np.sin(2 * np.pi * 180 * t)
    sig = np.concatenate([np.zeros(sr), sig, np.zeros(sr)])  # 1s lặng mỗi đầu
    sf.write(path, sig, sr)
    return path


@pytest.fixture
def voice(studio, tmp_path):
    vid = studio.create_voice("Giọng của tôi")
    studio.add_reference(vid, make_wav(tmp_path / "ref.wav"), transcript="xin chào các bạn")
    return vid


def test_create_voice_slug_unique(studio):
    a = studio.create_voice("Giọng của tôi")
    b = studio.create_voice("Giọng của tôi")
    assert a == "giong-cua-toi" and b == "giong-cua-toi-2"


def test_add_reference_processes_audio(studio, voice):
    ref = studio.store.default_ref(voice)
    data, sr = sf.read(studio.abs(ref["audio_path"]))
    assert sr == 24000
    assert 3.5 < len(data) / sr < 4.6  # đã cắt khoảng lặng hai đầu
    assert ref["transcript"] == "xin chào các bạn"
    assert studio.abs(ref["audio_path"]).parent.parent == studio.paths.voices / voice


def test_create_project_splits(studio, voice):
    pid = studio.create_project("# A\nCâu một khá là dài nhé. Câu hai cũng dài nhé!\n# B\nCâu ba dài dài dài.", voice_id=voice)
    chapters = studio.store.list_chapters(pid)
    assert [c["title"] for c in chapters] == ["A", "B"]
    assert len(studio.store.list_segments(pid)) == 3
    assert studio.store.get_project(pid)["title"] == "A"


def test_full_run_exports_chapters(studio, voice, engine):
    pid = studio.create_project("Hôm nay là ngày 15/3/2025. Trời rất đẹp và trong xanh.", voice_id=voice, title="Thử")
    studio.queue(pid)
    studio.run_until_idle()
    p = studio.store.get_project(pid)
    assert p["status"] == "done"
    ch = studio.store.list_chapters(pid)[0]
    assert studio.abs(ch["wav_path"]).exists() and studio.abs(ch["mp3_path"]).exists()
    assert ch["duration"] > 0
    assert any("mười lăm tháng ba" in c for c in engine.calls)


def test_user_lexicon_used(studio, voice, engine):
    studio.store.set_lexicon("GiọngTôi", "giọng tôi")
    pid = studio.create_project("Ứng dụng GiọngTôi chạy offline trên máy.", voice_id=voice)
    studio.queue(pid)
    studio.run_until_idle()
    assert engine.calls[-1].startswith("Ứng dụng giọng tôi chạy óp lai")


def test_pause_stops_after_current_segment_and_resume(studio, voice):
    text = " ".join(f"Đây là câu số {i} trong văn bản dài." for i in range(1, 6))
    pid = studio.create_project(text, voice_id=voice)
    studio.queue(pid)
    assert studio.step()  # xử lý 1 câu
    studio.pause(pid)
    assert not studio.step()
    segs = studio.store.list_segments(pid)
    assert sum(s["status"] == "done" for s in segs) == 1
    studio.queue(pid)
    studio.run_until_idle()
    assert studio.store.get_project(pid)["status"] == "done"


def test_error_segment_then_regenerate_with_new_text(studio, voice, engine):
    engine.fail_on = "HỎNG"
    pid = studio.create_project("Câu đầu tiên ổn định. Câu này HỎNG mất rồi. Câu cuối ổn định.", voice_id=voice)
    studio.queue(pid)
    studio.run_until_idle()
    p = studio.store.get_project(pid)
    assert p["status"] == "error"
    bad = [s for s in studio.store.list_segments(pid) if s["status"] == "error"]
    assert len(bad) == 1
    studio.regenerate_segment(bad[0]["id"], new_text="Câu này đã sửa lại rồi.")
    studio.run_until_idle()
    assert studio.store.get_project(pid)["status"] == "done"
    assert studio.store.get_segment(bad[0]["id"])["text"] == "Câu này đã sửa lại rồi."


def test_speed_applied_when_engine_lacks_support(studio, voice, engine):
    engine.supports_speed = False
    pid = studio.create_project("Một câu đủ dài để đo thời lượng nhé bạn ơi.", voice_id=voice, speed=1.5)
    studio.queue(pid)
    studio.run_until_idle()
    seg = studio.store.list_segments(pid)[0]
    expected = len(seg["text"]) * engine.seconds_per_char / 1.5
    assert abs(seg["duration"] - expected) < 0.15


def test_restart_resumes_running_project(tmp_path, engine, voice, studio):
    pid = studio.create_project("Câu một rất là dài. Câu hai rất là dài.", voice_id=voice)
    studio.store.update_project(pid, status="running")
    again = Studio(studio.paths, engine_getter=lambda n: engine, denoise_fn=None)
    again.run_until_idle()
    assert again.store.get_project(pid)["status"] == "done"


def test_voice_ref_includes_other_samples_of_same_voice(studio, voice, tmp_path):
    studio.add_reference(voice, make_wav(tmp_path / "b.wav", 5), transcript="câu hai")
    studio.add_reference(voice, make_wav(tmp_path / "c.wav", 6), transcript="câu ba")
    ref = studio.voice_ref(voice)
    assert ref.transcript == "xin chào các bạn"  # mẫu ★ vẫn là mẫu chính
    assert len(ref.extra_audio) == 2 and ref.audio_path not in ref.extra_audio
    assert all(p.exists() for p in ref.extra_audio)


def test_merge_voices_moves_samples_files_and_projects(studio, voice, tmp_path):
    other = studio.create_voice("Giọng của tôi")
    studio.add_reference(other, make_wav(tmp_path / "b.wav"), transcript="câu hai")
    pid = studio.create_project("Xin chào.", other)
    studio.merge_voices(target=voice, source=other)
    assert studio.store.get_voice(other) is None
    refs = studio.store.list_refs(voice)
    assert len(refs) == 2 and sum(r["is_default"] for r in refs) == 1
    for r in refs:
        assert r["audio_path"].startswith(f"voices/{voice}/") and studio.abs(r["audio_path"]).exists()
    assert not (studio.paths.voices / other).exists()
    assert studio.store.get_project(pid)["voice_id"] == voice


def test_merge_voice_into_itself_rejected(studio, voice):
    with pytest.raises(ValueError):
        studio.merge_voices(target=voice, source=voice)

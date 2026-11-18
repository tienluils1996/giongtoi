import io

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from giongtoi.config import Paths
from giongtoi.engines.fake import FakeEngine
from giongtoi.studio import Studio
from giongtoi.web.app import create_app


@pytest.fixture
def studio(tmp_path):
    eng = FakeEngine()
    return Studio(Paths(tmp_path).ensure(), engine_getter=lambda n: eng, denoise_fn=None)


@pytest.fixture
def client(studio):
    return TestClient(create_app(studio, start_worker=False))


def wav_bytes(seconds=3.0, sr=22050):
    t = np.arange(int(seconds * sr)) / sr
    buf = io.BytesIO()
    sf.write(buf, 0.3 * np.sin(2 * np.pi * 200 * t), sr, format="WAV")
    return buf.getvalue()


def test_pages_render(client, studio):
    vid = studio.create_voice("Giọng của tôi")
    for url in ["/", "/projects", "/voices", f"/voices/{vid}", "/lexicon", "/bakeoff", "/health"]:
        r = client.get(url)
        assert r.status_code == 200, url
    assert "Ghi âm theo câu mẫu" in client.get(f"/voices/{vid}").text


def test_full_flow_upload_ref_create_project_download(client, studio):
    vid = studio.create_voice("Giọng của tôi")
    r = client.post(f"/api/voices/{vid}/refs", files={"file": ("a.wav", wav_bytes(), "audio/wav")},
                    data={"transcript": "xin chào", "label": "bình thường", "denoise": "0"})
    assert r.status_code == 200, r.text
    assert r.json()["is_default"] == 1

    r = client.post("/projects", data={"text": "Câu thứ nhất khá dài. Câu thứ hai cũng dài.", "voice_id": vid,
                                       "engine": "fake", "speed": "1.0"}, follow_redirects=False)
    assert r.status_code == 303
    pid = int(r.headers["location"].rsplit("/", 1)[1])
    studio.run_until_idle()

    data = client.get(f"/api/projects/{pid}").json()
    assert data["project"]["status"] == "done" and data["n_done"] == 2
    ch = data["chapters"][0]
    r = client.get(f"/media/{ch['mp3_path']}?download=1")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert client.get(f"/projects/{pid}").status_code == 200

    seg = data["segments"][0]
    assert client.post(f"/api/segments/{seg['id']}/regenerate", data={"text": "Câu đã sửa nhé bạn."}).json()["ok"]
    studio.run_until_idle()
    assert client.get(f"/api/projects/{pid}").json()["segments"][0]["text"] == "Câu đã sửa nhé bạn."


def test_create_project_from_uploaded_file(client, studio):
    vid = studio.create_voice("v")
    client.post(f"/api/voices/{vid}/refs", files={"file": ("a.wav", wav_bytes(), "audio/wav")}, data={"denoise": "0"})
    md = "# Chương 1\nNội dung chương một.\n# Chương 2\nNội dung chương hai.".encode()
    r = client.post("/projects", data={"voice_id": vid, "engine": "fake"},
                    files={"file": ("truyen.md", md, "text/markdown")}, follow_redirects=False)
    pid = int(r.headers["location"].rsplit("/", 1)[1])
    p = studio.store.get_project(pid)
    assert p["title"] == "truyen"
    assert [c["title"] for c in studio.store.list_chapters(pid)] == ["Chương 1", "Chương 2"]


def test_project_requires_reference(client, studio):
    vid = studio.create_voice("v")
    r = client.post("/projects", data={"text": "Xin chào", "voice_id": vid, "engine": "fake"})
    assert r.status_code == 400


def test_media_path_traversal_blocked(client):
    assert client.get("/media/../../etc/passwd").status_code == 404
    assert client.get("/media/%2e%2e/%2e%2e/etc/passwd").status_code == 404


def test_preview_and_lexicon(client):
    client.post("/lexicon", data={"term": "Netflix", "reading": "nét phlích"})
    assert "Netflix" in client.get("/lexicon").text
    r = client.post("/api/preview", data={"text": "Xem Netflix lúc 20h"})
    assert r.json()["text"] == "Xem nét phlích lúc hai mươi giờ"
    client.post("/lexicon/delete", data={"term": "Netflix"})
    assert client.post("/api/preview", data={"text": "Netflix"}).json()["text"] == "Netflix"


def test_pause_resume_routes(client, studio):
    vid = studio.create_voice("v")
    client.post(f"/api/voices/{vid}/refs", files={"file": ("a.wav", wav_bytes(), "audio/wav")}, data={"denoise": "0"})
    r = client.post("/projects", data={"text": "Một câu dài dài dài dài.", "voice_id": vid, "engine": "fake"},
                    follow_redirects=False)
    pid = int(r.headers["location"].rsplit("/", 1)[1])
    client.post(f"/projects/{pid}/pause")
    assert studio.store.get_project(pid)["status"] == "paused"
    client.post(f"/projects/{pid}/resume")
    assert studio.store.get_project(pid)["status"] == "queued"


def test_create_voice_with_sample_in_one_step(client, studio):
    r = client.post("/api/voices", files={"file": ("rec.wav", wav_bytes(), "audio/wav")},
                    data={"name": "Giọng của tôi", "transcript": "xin chào", "denoise": "0"})
    assert r.status_code == 200, r.text
    vid = r.json()["voice_id"]
    refs = studio.store.list_refs(vid)
    assert len(refs) == 1 and refs[0]["is_default"] == 1 and refs[0]["transcript"] == "xin chào"


def test_create_voice_with_bad_audio_leaves_no_empty_profile(client, studio):
    r = client.post("/api/voices", files={"file": ("x.wav", b"not audio", "audio/wav")},
                    data={"name": "Hỏng", "denoise": "0"})
    assert r.status_code == 400
    assert studio.store.list_voices() == []


def test_voices_page_offers_mic_and_file(client):
    html = client.get("/voices").text
    assert 'id="rec-btn"' in html and 'type="file"' in html

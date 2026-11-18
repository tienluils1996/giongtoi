from giongtoi.cli import models_ready


def _repo(hub, repo, incomplete=False):
    d = hub / ("models--" + repo.replace("/", "--"))
    (d / "snapshots" / "abc").mkdir(parents=True)
    (d / "snapshots" / "abc" / "model.onnx").write_text("x")
    (d / "blobs").mkdir()
    if incomplete:
        (d / "blobs" / "123.incomplete").write_text("")


def test_models_ready(tmp_path):
    assert not models_ready(tmp_path, ["vieneu"])
    _repo(tmp_path, "pnnbao-ump/VieNeu-TTS-v3-Turbo")
    assert not models_ready(tmp_path, ["vieneu"])
    _repo(tmp_path, "OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX")
    assert models_ready(tmp_path, ["vieneu"])
    _repo(tmp_path, "hynt/F5-TTS-Vietnamese-ViVoice", incomplete=True)
    _repo(tmp_path, "charactr/vocos-mel-24khz")
    assert not models_ready(tmp_path, ["vieneu", "f5"])

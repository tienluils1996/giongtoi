"""Web UI (FastAPI + Jinja2 + JS thuần, không cần internet)."""

from __future__ import annotations

import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import __version__
from ..config import APP_NAME, default_engine, get_paths
from ..engines import registry
from ..prompts import RECORDING_PROMPTS
from ..studio import Studio, Worker
from ..text.lexicon import ABBREVIATIONS, ENGLISH

HERE = Path(__file__).parent
log = logging.getLogger("giongtoi")

STATUS_LABELS = {
    "draft": "Nháp",
    "queued": "Đang chờ",
    "running": "Đang đọc",
    "paused": "Tạm dừng",
    "done": "Hoàn tất",
    "error": "Có lỗi",
    "pending": "Chờ",
}


def _default_denoise():
    """Dùng bộ khử ồn ONNX của VieNeu nếu có (không cần torch)."""
    try:
        from ..engines.vieneu_engine import denoise_array

        return denoise_array
    except Exception:
        return None


def create_app(studio: Studio | None = None, start_worker: bool = True) -> FastAPI:
    studio = studio or Studio(get_paths(), denoise_fn=_default_denoise())
    preload = studio.store.get_setting("engine", default_engine())
    if preload not in registry.FACTORIES or not registry.is_installed(preload):
        preload = None
    worker = Worker(studio, preload=preload) if start_worker else None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if worker:
            worker.start()
        yield
        if worker:
            worker.stop()

    app = FastAPI(title=APP_NAME, lifespan=lifespan)
    app.state.studio = studio
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.globals.update(APP_NAME=APP_NAME, STATUS=STATUS_LABELS, VERSION=__version__)

    def render(request: Request, name: str, **ctx) -> HTMLResponse:
        return templates.TemplateResponse(request, name, ctx)

    def engines_for_ui() -> dict[str, str]:
        found = registry.available()
        return found or {default_engine(): registry.FACTORIES[default_engine()][0]}

    # ------------------------------------------------------------ media
    @app.get("/media/{path:path}")
    def media(path: str, download: int = 0):
        root = studio.paths.root.resolve()
        target = (root / path).resolve()
        if root not in target.parents or not target.is_file():
            raise HTTPException(404)
        return FileResponse(target, filename=target.name if download else None)

    # ------------------------------------------------------------ đọc văn bản
    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        voices = studio.store.list_voices()
        voice_refs = {v["id"]: studio.store.list_refs(v["id"]) for v in voices}
        return render(
            request, "home.html",
            voices=voices, voice_refs=voice_refs, engines=engines_for_ui(),
            default_engine=studio.store.get_setting("engine", default_engine()),
            recent=studio.store.list_projects()[:5],
        )

    @app.post("/projects")
    async def create_project(
        text: str = Form(""),
        title: str = Form(""),
        voice_id: str = Form(...),
        ref_id: str = Form(""),
        engine: str = Form(...),
        speed: float = Form(1.0),
        pause_sentence_ms: int = Form(300),
        pause_paragraph_ms: int = Form(700),
        english_mode: str = Form("vietnamize"),
        file: UploadFile | None = File(None),
    ):
        if file is not None and file.filename:
            raw = await file.read()
            text = raw.decode("utf-8-sig", errors="replace")
            if not title:
                title = Path(file.filename).stem
        if not text.strip():
            raise HTTPException(400, "Văn bản trống")
        if not studio.store.default_ref(voice_id):
            raise HTTPException(400, "Hồ sơ giọng này chưa có mẫu giọng. Vào mục Giọng của tôi để ghi âm.")
        studio.store.set_setting("engine", engine)
        pid = studio.create_project(
            text, voice_id=voice_id, title=title.strip() or None, engine=engine,
            speed=min(2.0, max(0.5, speed)),
            pause_sentence_ms=max(0, pause_sentence_ms), pause_paragraph_ms=max(0, pause_paragraph_ms),
            english_mode=english_mode, ref_id=int(ref_id) if ref_id else None,
        )
        studio.queue(pid)
        return RedirectResponse(f"/projects/{pid}", status_code=303)

    @app.post("/api/preview")
    def preview(text: str = Form(""), english_mode: str = Form("vietnamize")):
        return {"text": studio.preview_text(text, english_mode)}

    # ------------------------------------------------------------ lịch sử / dự án
    @app.get("/projects", response_class=HTMLResponse)
    def projects(request: Request):
        return render(request, "projects.html", projects=studio.store.list_projects())

    def project_payload(pid: int) -> dict:
        p = studio.store.get_project(pid)
        if not p:
            raise HTTPException(404)
        segs = studio.store.list_segments(pid)
        chapters = studio.store.list_chapters(pid)
        done = [s for s in segs if s["status"] == "done" and s["seconds"]]
        remaining = sum(1 for s in segs if s["status"] == "pending")
        avg = sum(s["seconds"] for s in done) / len(done) if done else None
        return {
            "project": p,
            "status_label": STATUS_LABELS.get(p["status"], p["status"]),
            "chapters": chapters,
            "segments": segs,
            "n_total": len(segs),
            "n_done": sum(1 for s in segs if s["status"] == "done"),
            "n_error": sum(1 for s in segs if s["status"] == "error"),
            "eta_seconds": round(avg * remaining) if avg and remaining else None,
        }

    @app.get("/projects/{pid}", response_class=HTMLResponse)
    def project_page(request: Request, pid: int):
        data = project_payload(pid)
        return render(request, "project.html", **data)

    @app.get("/api/projects/{pid}")
    def project_api(pid: int):
        return JSONResponse(project_payload(pid))

    @app.post("/projects/{pid}/pause")
    def pause(pid: int):
        studio.pause(pid)
        return RedirectResponse(f"/projects/{pid}", status_code=303)

    @app.post("/projects/{pid}/resume")
    def resume(pid: int):
        studio.queue(pid)
        return RedirectResponse(f"/projects/{pid}", status_code=303)

    @app.post("/projects/{pid}/settings")
    def project_settings(pid: int, speed: float = Form(1.0), pause_sentence_ms: int = Form(300),
                         pause_paragraph_ms: int = Form(700), regenerate_all: str = Form("")):
        studio.store.update_project(pid, speed=min(2.0, max(0.5, speed)),
                                    pause_sentence_ms=max(0, pause_sentence_ms),
                                    pause_paragraph_ms=max(0, pause_paragraph_ms))
        if regenerate_all:
            for s in studio.store.list_segments(pid):
                studio.store.update_segment(s["id"], status="pending", error=None)
        studio.queue(pid)  # ghép lại chương với khoảng nghỉ mới
        return RedirectResponse(f"/projects/{pid}", status_code=303)

    @app.post("/projects/{pid}/delete")
    def delete_project(pid: int):
        studio.delete_project(pid)
        return RedirectResponse("/projects", status_code=303)

    @app.post("/api/segments/{sid}/regenerate")
    def regenerate(sid: int, text: str = Form("")):
        try:
            studio.regenerate_segment(sid, new_text=text or None)
        except ValueError as e:
            raise HTTPException(404, str(e))
        return {"ok": True}

    # ------------------------------------------------------------ giọng
    @app.get("/voices", response_class=HTMLResponse)
    def voices(request: Request):
        vs = studio.store.list_voices()
        return render(request, "voices.html", voices=vs,
                      refs={v["id"]: studio.store.list_refs(v["id"]) for v in vs})

    @app.post("/voices")
    def create_voice(name: str = Form(...)):
        vid = studio.create_voice(name.strip() or "Giọng mới")
        return RedirectResponse(f"/voices/{vid}", status_code=303)

    @app.get("/voices/{vid}", response_class=HTMLResponse)
    def voice_page(request: Request, vid: str):
        v = studio.store.get_voice(vid)
        if not v:
            raise HTTPException(404)
        refs = studio.store.list_refs(vid)
        recorded = {r["transcript"] for r in refs}
        return render(request, "voice.html", voice=v, refs=refs, prompts=RECORDING_PROMPTS,
                      recorded=recorded)

    @app.post("/api/voices/{vid}/refs")
    async def add_ref(vid: str, file: UploadFile = File(...), transcript: str = Form(""),
                      label: str = Form("bình thường"), denoise: str = Form("1")):
        if not studio.store.get_voice(vid):
            raise HTTPException(404)
        suffix = Path(file.filename or "rec.webm").suffix or ".webm"
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / f"upload{suffix}"
            tmp.write_bytes(await file.read())
            try:
                rid = studio.add_reference(vid, tmp, transcript=transcript, label=label or "bình thường",
                                           denoise=denoise == "1")
            except Exception as e:
                log.exception("Không xử lý được file âm thanh")
                raise HTTPException(400, f"Không xử lý được file âm thanh: {e}")
        return studio.store.get_ref(rid)

    @app.post("/voices/{vid}/refs/{rid}/default")
    def set_default(vid: str, rid: int):
        studio.store.set_default_ref(rid)
        return RedirectResponse(f"/voices/{vid}", status_code=303)

    @app.post("/voices/{vid}/refs/{rid}/update")
    def update_ref(vid: str, rid: int, label: str = Form(""), transcript: str = Form("")):
        studio.store.update_ref(rid, label=label.strip() or "bình thường", transcript=transcript.strip())
        return RedirectResponse(f"/voices/{vid}", status_code=303)

    @app.post("/voices/{vid}/refs/{rid}/delete")
    def delete_ref(vid: str, rid: int):
        studio.delete_reference(rid)
        return RedirectResponse(f"/voices/{vid}", status_code=303)

    @app.post("/voices/{vid}/delete")
    def delete_voice(vid: str):
        for r in studio.store.list_refs(vid):
            studio.delete_reference(r["id"])
        studio.store.delete_voice(vid)
        return RedirectResponse("/voices", status_code=303)

    # ------------------------------------------------------------ từ điển
    @app.get("/lexicon", response_class=HTMLResponse)
    def lexicon(request: Request):
        return render(request, "lexicon.html", entries=studio.store.lexicon(),
                      defaults_en=ENGLISH, defaults_abbr=ABBREVIATIONS)

    @app.post("/lexicon")
    def add_lexicon(term: str = Form(...), reading: str = Form(...)):
        if term.strip() and reading.strip():
            studio.store.set_lexicon(term, reading)
        return RedirectResponse("/lexicon", status_code=303)

    @app.post("/lexicon/delete")
    def del_lexicon(term: str = Form(...)):
        studio.store.delete_lexicon(term)
        return RedirectResponse("/lexicon", status_code=303)

    # ------------------------------------------------------------ bake-off
    @app.get("/bakeoff", response_class=HTMLResponse)
    def bakeoff(request: Request):
        runs = sorted(
            (p for p in studio.paths.bakeoff.glob("*/index.html")), key=lambda p: p.stat().st_mtime, reverse=True
        )
        return render(request, "bakeoff.html", runs=[studio.rel(p) for p in runs],
                      voices=studio.store.list_voices())

    @app.get("/health")
    def health():
        return {"ok": True, "engines": registry.available()}

    return app

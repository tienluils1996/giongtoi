"""Dòng lệnh: giongtoi serve | app | bakeoff | say."""

from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
from pathlib import Path


def _setup_env() -> None:
    from .config import get_paths

    paths = get_paths().ensure()
    # mô hình tải về nằm trong ~/VoiceCloneData/models (ngoài OneDrive)
    os.environ.setdefault("HF_HOME", str(paths.models))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def free_port(preferred: int) -> int:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def cmd_serve(args) -> None:
    import uvicorn

    from .web.app import create_app

    port = free_port(args.port)
    print(f"GiọngTôi đang chạy: http://127.0.0.1:{port}")
    if args.open:
        import threading
        import webbrowser

        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


def cmd_app(args) -> None:
    from .desktop import run_desktop

    run_desktop(port=free_port(args.port))


def cmd_bakeoff(args) -> None:
    from .bakeoff import run_bakeoff

    out = run_bakeoff(
        voice_id=args.voice,
        engines=args.engines.split(",") if args.engines else None,
        ref_wav=Path(args.ref) if args.ref else None,
        ref_text=args.ref_text or "",
    )
    print(f"Mở trang nghe mù: {out}")


def cmd_say(args) -> None:
    """Đọc nhanh một câu ra file (không cần web)."""
    from .config import get_paths
    from .studio import Studio

    studio = Studio(get_paths())
    voice = args.voice or studio.ensure_default_voice()
    pid = studio.create_project(args.text, voice_id=voice, engine=args.engine, speed=args.speed)
    studio.queue(pid)
    studio.run_until_idle()
    p = studio.store.get_project(pid)
    if p["status"] != "done":
        sys.exit(f"Lỗi: {p['error']}")
    for ch in studio.store.list_chapters(pid):
        print(studio.abs(ch["wav_path"]))
        print(studio.abs(ch["mp3_path"]))


def main(argv: list[str] | None = None) -> None:
    _setup_env()
    p = argparse.ArgumentParser(prog="giongtoi", description="GiọngTôi — clone giọng nói, đọc tiếng Việt offline")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("serve", help="chạy web UI ở localhost")
    s.add_argument("--port", type=int, default=7861)
    s.add_argument("--open", action="store_true", help="tự mở trình duyệt")
    s.set_defaults(func=cmd_serve)

    a = sub.add_parser("app", help="mở cửa sổ ứng dụng (pywebview)")
    a.add_argument("--port", type=int, default=7861)
    a.set_defaults(func=cmd_app)

    b = sub.add_parser("bakeoff", help="so sánh mô hình (nghe mù)")
    b.add_argument("--voice", help="id hồ sơ giọng (mặc định: hồ sơ đầu tiên)")
    b.add_argument("--engines", help="vd: vieneu,f5 (mặc định: tất cả engine đã cài)")
    b.add_argument("--ref", help="file WAV tham chiếu thay cho hồ sơ giọng")
    b.add_argument("--ref-text", help="transcript của --ref")
    b.set_defaults(func=cmd_bakeoff)

    y = sub.add_parser("say", help="đọc một đoạn văn bản ra file WAV/MP3")
    y.add_argument("text")
    y.add_argument("--voice")
    y.add_argument("--engine", default=None)
    y.add_argument("--speed", type=float, default=1.0)
    y.set_defaults(func=cmd_say)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        args = p.parse_args(["serve", "--open"])
    args.func(args)


if __name__ == "__main__":
    main()

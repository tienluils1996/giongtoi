"""Cửa sổ ứng dụng macOS: chạy server trong luồng nền, hiển thị bằng WebKit (pywebview)."""

from __future__ import annotations

import threading
import time
import urllib.request

from .config import APP_NAME


def _wait_ready(url: str, timeout: float = 30) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url + "/health", timeout=1)
            return
        except Exception:
            time.sleep(0.2)


def run_desktop(port: int) -> None:
    import uvicorn

    from .web.app import create_app

    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    _wait_ready(url)

    try:
        import webview
    except ImportError:  # không có pywebview → mở trình duyệt mặc định
        import webbrowser

        webbrowser.open(url)
        print(f"{APP_NAME}: {url} (Ctrl+C để thoát)")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return

    webview.create_window(APP_NAME, url, width=1100, height=820, min_size=(720, 560))
    webview.start()
    server.should_exit = True

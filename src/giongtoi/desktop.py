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


MIC_REASON = "GiọngTôi cần micro để ghi mẫu giọng nói của bạn (xử lý hoàn toàn trên máy)."


def enable_webkit_mic(origin_host: str = "127.0.0.1") -> None:
    """Cho phép getUserMedia trong cửa sổ pywebview (macOS).

    WebKit chỉ bật navigator.mediaDevices khi Info.plist của tiến trình có
    NSMicrophoneUsageDescription — tiến trình python không có bundle, nên ghi giá trị
    vào infoDictionary lúc chạy. pywebview cũng không xử lý yêu cầu quyền micro,
    nên thêm phương thức WKUIDelegate tự cấp quyền cho riêng server cục bộ của app.
    """
    import AppKit
    import objc
    from webview.platforms.cocoa import BrowserView

    info = AppKit.NSBundle.mainBundle().infoDictionary()
    info["NSMicrophoneUsageDescription"] = MIC_REASON

    WK_GRANT, WK_DENY = 1, 2  # WKPermissionDecision

    class BrowserDelegate(objc.Category(BrowserView.BrowserDelegate)):
        def webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_(
            self, webview, origin, frame, media_type, handler
        ):
            handler(WK_GRANT if str(origin.host()) in (origin_host, "localhost") else WK_DENY)

    del BrowserDelegate  # category đã được gắn vào lớp gốc khi định nghĩa


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

    import sys

    if sys.platform == "darwin":
        try:
            enable_webkit_mic()
        except Exception:  # không để lỗi micro chặn việc mở app
            import logging

            logging.getLogger("giongtoi").exception("Không bật được micro cho cửa sổ app")

    webview.create_window(APP_NAME, url, width=1100, height=820, min_size=(720, 560))
    webview.start()
    server.should_exit = True

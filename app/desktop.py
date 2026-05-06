"""
Desktop launcher for Interview Flow.

Starts the FastAPI server in a background thread and opens a native webview window
(Edge WebView2 on Windows, WKWebView on Mac, WebKitGTK on Linux).

Falls back to browser mode automatically when no GUI backend is available
(e.g. WSL, headless servers, missing GTK/Qt packages).

Usage:
    python -m app.desktop
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

TITLE = "Interview Flow"
PREFERRED_PORT = 8000


def _find_port(preferred: int) -> int:
    """Return preferred port if free, otherwise a random free port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", preferred))
            return preferred
    except OSError:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    """Poll until the HTTP server responds or the timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def _run_server(port: int) -> None:
    """Start uvicorn in a background thread with its own event loop."""
    # Windows requires ProactorEventLoop for subprocess-based transports (used by claude SDK)
    if os.name == "nt":
        loop: asyncio.AbstractEventLoop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    import uvicorn
    from app.main import app as fastapi_app

    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=port,
        reload=False,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())


def _is_wsl() -> bool:
    """Return True when running inside Windows Subsystem for Linux."""
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def _open_browser(url: str) -> None:
    """Best-effort: open url in the system browser."""
    try:
        if _is_wsl():
            # wslview (from wslu) is the clean way; fall back to explorer.exe
            try:
                subprocess.Popen(["wslview", url])
            except FileNotFoundError:
                subprocess.Popen(["explorer.exe", url])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url])
        elif sys.platform == "win32":
            os.startfile(url)
        else:
            subprocess.Popen(["xdg-open", url])
    except Exception:
        pass  # User will see the URL printed in the terminal


def _fatal(message: str) -> None:
    """Show an error dialog (or stderr fallback) and exit."""
    try:
        import tkinter.messagebox as mb
        mb.showerror(TITLE, message)
    except Exception:
        print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def _run_browser_mode(url: str) -> None:
    """Keep the server alive and direct the user to the browser."""
    _open_browser(url)
    print(f"  Open in your browser: {url}")
    print("  Press Ctrl+C to stop\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


class _JsApi:
    """Exposed to the webview page as window.pywebview.api.*"""

    def open_external(self, url: str) -> None:
        _open_browser(url)

    def open_folder_dialog(self, initial_dir: str = '') -> str | None:
        import webview
        result = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER, directory=initial_dir)
        return result[0] if result else None


def main() -> None:
    # When frozen by PyInstaller, resolve user data dir so state is saved next to
    # the executable rather than inside the read-only extraction temp dir.
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        os.environ.setdefault("INTERVIEW_DATA_DIR", str(exe_dir / "data"))

    port = _find_port(PREFERRED_PORT)
    url = f"http://127.0.0.1:{port}"

    server_thread = threading.Thread(target=_run_server, args=(port,), daemon=True)
    server_thread.start()

    if not _wait_for_server(port, timeout=30.0):
        _fatal("Server failed to start within 30 seconds.\nCheck the terminal for error details.")

    try:
        import webview
        webview.create_window(
            TITLE,
            url=url,
            js_api=_JsApi(),
            width=1400,
            height=900,
            min_size=(900, 600),
        )
        # webview.start() blocks on the main thread and runs the native event loop.
        # The server thread is a daemon, so it exits automatically when this returns.
        webview.start(debug=False)
    except Exception:
        # GUI backend unavailable — WSL, headless server, or missing GTK/Qt/WebView2.
        print(f"\n  {TITLE} - running in browser mode (no GUI backend available)")
        _run_browser_mode(url)


if __name__ == "__main__":
    main()

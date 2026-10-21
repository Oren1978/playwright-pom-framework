"""Starts the bundled Harbor Hotel app on a free local port for the test session."""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import uvicorn

from app.main import app


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def running_app(timeout_s: float) -> Iterator[str]:
    """Yield the base URL of a running app; stop it cleanly afterwards.

    Readiness is event-driven (uvicorn's `started` flag polled with a bounded
    wait on a threading.Event), not a fixed sleep.
    """
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    ready = threading.Event()
    deadline_checks = int(timeout_s / 0.05)
    for _ in range(deadline_checks):
        if server.started:
            ready.set()
            break
        ready.wait(0.05)  # bounded poll on startup only, never inside tests
    if not ready.is_set():
        server.should_exit = True
        raise RuntimeError(f"Harbor app did not start within {timeout_s}s")

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=timeout_s)

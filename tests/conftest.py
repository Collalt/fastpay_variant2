from __future__ import annotations

import logging
import threading
from http.server import ThreadingHTTPServer

import pytest

from fastpay.app import FastPayHandler


@pytest.fixture(scope="session")
def fastpay_server():
    """Start a real HTTP FastPay server on localhost for integration tests."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), FastPayHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://{host}:{port}"

    server.shutdown()
    thread.join(timeout=3)
    server.server_close()


@pytest.fixture(autouse=True)
def configure_logging(caplog):
    caplog.set_level(logging.INFO, logger="fastpay")

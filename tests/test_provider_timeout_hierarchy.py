"""Adversarial transport tests for the live model runner.

These tests never contact a provider.  They use a local HTTP/1.1 chunked
server to prove that a response cannot defeat the total request deadline by
dribbling bytes just before the socket timeout.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from benchmark import ab_local_runner as runner


class ChunkHandler(BaseHTTPRequestHandler):
    mode = "stall"
    calls = 0
    interval = 0.0

    def log_message(self, *_args):
        return

    def do_POST(self):  # noqa: N802
        type(self).calls += 1
        self.protocol_version = "HTTP/1.1"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def chunk(data: bytes):
            self.wfile.write(f"{len(data):X}\r\n".encode() + data + b"\r\n")
            self.wfile.flush()

        if self.mode in {"stall", "slow"}:
            chunk(b"{\"choices\":[")
            if self.mode == "stall":
                time.sleep(2.0)
            else:
                for byte in b'{"message":{"content":"ok"}}],"usage":{}}':
                    chunk(bytes([byte]))
                    time.sleep(self.interval)
        else:
            payload = {"choices": [{"message": {"content": "ok"}}], "usage": {}}
            chunk(json.dumps(payload).encode())
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()


@pytest.fixture
def chunk_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), ChunkHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    old_url = runner.API_URL
    runner.API_URL = f"http://127.0.0.1:{server.server_port}/chat"
    ChunkHandler.calls = 0
    yield server
    runner.API_URL = old_url
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def call_with_short_deadlines(monkeypatch, timeout=0.20, socket_timeout=0.05):
    monkeypatch.setattr(runner, "CHAT_TIMEOUT", timeout)
    monkeypatch.setattr(runner, "CHAT_SOCKET_TIMEOUT", socket_timeout)
    return runner.chat("test-key", [], 0.0, 0.0)


def test_response_that_never_sends_next_chunk_is_censored(chunk_server, monkeypatch):
    ChunkHandler.mode = "stall"
    started = time.monotonic()
    with pytest.raises(runner.ProviderCensoredError):
        call_with_short_deadlines(monkeypatch)
    elapsed = time.monotonic() - started
    assert elapsed < 1.0


def test_slow_chunks_cannot_reset_total_request_deadline(chunk_server, monkeypatch):
    ChunkHandler.mode = "slow"
    ChunkHandler.interval = 0.06
    started = time.monotonic()
    with pytest.raises(runner.ProviderCensoredError):
        call_with_short_deadlines(monkeypatch, timeout=0.24, socket_timeout=0.10)
    elapsed = time.monotonic() - started
    assert elapsed < 0.8


def test_read_timeout_can_be_retried_without_exceeding_retry_budget(chunk_server, monkeypatch):
    # The first two attempts stall; the third returns a complete response.
    class RetryHandler(ChunkHandler):
        def do_POST(self):  # noqa: N802
            if type(self).calls < 2:
                type(self).mode = "stall"
            else:
                type(self).mode = "ok"
            super().do_POST()

    # Swap the server's handler without changing the endpoint.  A separate
    # server keeps the test state local and avoids any provider dependency.
    server = ThreadingHTTPServer(("127.0.0.1", 0), RetryHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    old_url = runner.API_URL
    runner.API_URL = f"http://127.0.0.1:{server.server_port}/chat"
    RetryHandler.calls = 0
    monkeypatch.setattr(runner, "CHAT_TIMEOUT", 0.12)
    monkeypatch.setattr(runner, "CHAT_SOCKET_TIMEOUT", 0.04)
    started = time.monotonic()
    attempts = 0
    try:
        while attempts < 3:
            attempts += 1
            try:
                result, _ = runner.chat("test-key", [], 0.0, 0.0)
                break
            except runner.ProviderCensoredError:
                if attempts == 3:
                    raise
        assert result["message"]["content"] == "ok"
        assert attempts == 3
        assert time.monotonic() - started < 1.5
    finally:
        runner.API_URL = old_url
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_outer_process_observes_provider_censor_before_task_budget(chunk_server):
    # This is the process-level invariant: a stalled response cannot keep the
    # task process alive until the much larger task/run budget.
    code = """
import sys
from benchmark import ab_local_runner as r
r.API_URL = sys.argv[1]
r.CHAT_TIMEOUT = 0.20
r.CHAT_SOCKET_TIMEOUT = 0.05
try:
    r.chat('test-key', [], 0.0, 0.0)
except r.ProviderCensoredError:
    print('PROVIDER_CENSORED')
"""
    ChunkHandler.mode = "stall"
    started = time.monotonic()
    proc = subprocess.run([sys.executable, "-c", code, runner.API_URL], capture_output=True, text=True, timeout=2)
    assert proc.returncode == 0
    assert "PROVIDER_CENSORED" in proc.stdout
    assert time.monotonic() - started < 1.2

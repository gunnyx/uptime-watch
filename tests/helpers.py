"""Test helpers: fake targets, fake webhook, temp databases, app starter."""
import json
import os
import shutil
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeHTTPTarget:
    """Local HTTP server with configurable status and delay."""

    def __init__(self, status=200, delay=0.0):
        self.status = status
        self.delay = delay
        self.hits = 0
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.hits += 1
                if outer.delay:
                    time.sleep(outer.delay)
                self.send_response(outer.status)
                if outer.status in (301, 302):
                    self.send_header("Location", "/elsewhere")
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.handle_error = lambda *a: None  # clients may time out mid-response
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.url = "http://127.0.0.1:%d/" % self.port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class FakeTCPTarget:
    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(50)
        self.port = self.sock.getsockname()[1]

    def stop(self):
        self.sock.close()


def closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class FakeWebhook:
    """Records POST bodies (decoded JSON when possible)."""

    def __init__(self, status=204, delay=0.0):
        self.bodies = []
        self.status = status
        self.delay = delay
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n)
                try:
                    outer.bodies.append(json.loads(raw))
                except ValueError:
                    outer.bodies.append(raw)
                if outer.delay:
                    time.sleep(outer.delay)
                self.send_response(outer.status)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        self.url = "http://127.0.0.1:%d/webhook/SECRET" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class TempDir:
    def __init__(self):
        self.path = tempfile.mkdtemp(prefix="uptimewatch-test-")

    def file(self, name):
        return os.path.join(self.path, name)

    def cleanup(self):
        shutil.rmtree(self.path, ignore_errors=True)


def make_db_path():
    """Return (path, cleanup) for a fresh temp-dir database."""
    t = TempDir()
    return t.file("test.db"), t.cleanup


def wait_for(cond, timeout=5.0, step=0.02):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(step)
    return cond()


def base_config(db_path, targets=None, **over):
    cfg = {
        "database": db_path,
        "default_timeout": 2,
        "retention_days": 30,
        "discord_webhook_url": "",
        "server": {"host": "127.0.0.1", "port": 1},
        "targets": targets or [],
    }
    cfg.update(over)
    return cfg


def start_app(config, env_token=None):
    """Start the real app on port 0. config is a validated Config object.

    Returns (base_url, stop, app).
    """
    from uptimewatch.cli import Application

    config.port = 0  # ephemeral port (config validation requires >= 1)
    app = Application(config)
    app.start()
    return "http://127.0.0.1:%d" % app.port, app.stop, app


def request(method, url, body=None, token=None, headers=None, raw=None):
    """Return (status, parsed_json_or_text, headers)."""
    data = raw
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token is not None:
        req.add_header("Authorization", "Bearer " + token)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            status, payload, hdrs = r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        status, payload, hdrs = e.code, e.read(), e.headers
    text = payload.decode("utf-8", "replace")
    try:
        return status, json.loads(text), hdrs
    except ValueError:
        return status, text, hdrs

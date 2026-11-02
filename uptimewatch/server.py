"""HTTP server: dashboard, status, health and (later) target API."""
import hmac
import json
import logging
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .db import DatabaseError
from .status import build_status
from .targets import clean_target_input, validate_target_input

MAX_BODY = 10240
MAX_UI_TARGETS = 200
API_ITEM = re.compile(r"^/api/targets/([^/]+)$")

log = logging.getLogger("uptimewatch.server")


class Handler(BaseHTTPRequestHandler):
    server_version = "uptimewatch"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # never log headers
        log.info("%s %s", self.address_string(), fmt % args)

    def _send(self, code, body=b"", ctype="application/json", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj).encode())

    def _err(self, code, msg, fields=None):
        o = {"error": msg}
        if fields:
            o["fields"] = fields
        self._json(code, o)

    def _path(self):
        return self.path.split("?", 1)[0]

    def _known(self, path):
        return path in ("/", "/health", "/status", "/api/targets") or bool(API_ITEM.match(path))

    def do_GET(self):
        path = self._path()
        ctx = self.server.ctx
        if path == "/":
            self._send(200, ctx.dashboard, "text/html; charset=utf-8")
        elif path == "/health":
            self._json(200, {"status": "ok"})
        elif path == "/status":
            targets = ctx.targets()
            self._json(200, build_status(ctx.db, targets, int(time.time()), bool(ctx.admin_token)))
        elif self._known(path):
            self._err(405, "method not allowed")
        else:
            self._err(404, "not found")

    # --- write API -------------------------------------------------
    def _route_write(self, method):
        path = self._path()
        if path == "/api/targets":
            return "collection" if method == "POST" else "bad-method"
        m = API_ITEM.match(path)
        if m:
            return ("item", m.group(1)) if method in ("PUT", "DELETE") else "bad-method"
        return "bad-method" if self._known(path) else None

    def _authorized(self):
        token = self.server.ctx.admin_token
        if not token:
            self._err(403, "target management is disabled (no admin token configured)")
            return False
        header = self.headers.get("Authorization", "")
        scheme, _, given = header.partition(" ")
        if scheme != "Bearer" or not hmac.compare_digest(given.encode(), token.encode()):
            self._send(401, json.dumps({"error": "missing or invalid admin token"}).encode(),
                       extra={"WWW-Authenticate": "Bearer"})
            return False
        return True

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0:
            self._err(400, "invalid Content-Length")
            return None
        if length > MAX_BODY:
            remaining = min(length, 65536)  # drain a bounded amount so the client sees our reply
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 8192))
                if not chunk:
                    break
                remaining -= len(chunk)
            self.close_connection = True
            self._err(413, "request body too large (max %d bytes)" % MAX_BODY)
            return None
        raw = self.rfile.read(length) if length else b""
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._err(400, "body must be valid JSON")
            return None
        if not isinstance(data, dict):
            self._err(400, "body must be a JSON object")
            return None
        return data

    def _target_json(self, id_):
        row = self.server.ctx.db.get_ui_target(id_)
        return {"id": row["id"], "name": row["name"], "type": row["type"], "source": "ui", "url": row["url"],
                "expected_status": row["expected_status"], "host": row["host"], "port": row["port"],
                "interval": row["interval"], "paused": bool(row["paused"])}

    def _name_taken(self, name, exclude_id=None):
        for t in self.server.ctx.targets():
            if t.name.lower() == name.lower() and not (t.source == "ui" and t.id == exclude_id):
                return True
        return False

    def _write(self, method):
        # The request body is not read on early errors, so don't reuse the connection afterwards.
        self.close_connection = True
        route = self._route_write(method)
        if route is None:
            return self._err(404, "not found")
        if route == "bad-method":
            return self._err(405, "method not allowed")
        if not self._authorized():
            return
        ctx = self.server.ctx
        item_id = None
        if route != "collection":
            raw_id = route[1]
            if not raw_id.isdigit() or int(raw_id) < 1:
                return self._err(404, "target not found")
            item_id = int(raw_id)
        if method == "DELETE":
            if not ctx.db.delete_ui_target(item_id):
                return self._err(404, "target not found")
            return self._send(204)
        data = self._read_json()
        if data is None:
            return
        self.close_connection = False
        now = int(time.time())
        if method == "POST":
            return self._create(data, now)
        if ctx.db.get_ui_target(item_id) is None:
            return self._err(404, "target not found")
        self._update(item_id, data, now)

    def _create(self, data, now):
        ctx = self.server.ctx
        errs = validate_target_input(data)
        if errs:
            return self._err(400, "invalid target: " + ", ".join(sorted(errs)), errs)
        fields = clean_target_input(data)
        if ctx.db.count_ui_targets() >= MAX_UI_TARGETS:
            return self._err(409, "limit of %d UI targets reached" % MAX_UI_TARGETS)
        if self._name_taken(fields["name"]):
            return self._err(409, "a target with this name already exists", {"name": "already in use"})
        try:
            id_ = ctx.db.add_ui_target(fields, now)
        except DatabaseError:
            return self._err(409, "a target with this name already exists", {"name": "already in use"})
        self._json(201, self._target_json(id_))

    def _update(self, id_, data, now):
        ctx = self.server.ctx
        if set(data) == {"paused"}:
            if not isinstance(data["paused"], bool):
                return self._err(400, "invalid target: paused", {"paused": "must be true or false"})
            ctx.db.set_paused(id_, data["paused"], now)
            return self._json(200, self._target_json(id_))
        errs = validate_target_input(data, allow_paused=True)
        if errs:
            return self._err(400, "invalid target: " + ", ".join(sorted(errs)), errs)
        fields = clean_target_input(data)
        if self._name_taken(fields["name"], exclude_id=id_):
            return self._err(409, "a target with this name already exists", {"name": "already in use"})
        try:
            ctx.db.update_ui_target(id_, fields, now)
        except DatabaseError:
            return self._err(409, "a target with this name already exists", {"name": "already in use"})
        if "paused" in data:
            ctx.db.set_paused(id_, data["paused"], now)
        self._json(200, self._target_json(id_))

    def do_POST(self):
        self._write("POST")

    def do_PUT(self):
        self._write("PUT")

    def do_DELETE(self):
        self._write("DELETE")


class Context:
    def __init__(self, db, config, dashboard, targets_fn):
        self.db = db
        self.admin_token = config.admin_token
        self.dashboard = dashboard
        self.targets = targets_fn


def make_server(host, port, ctx):
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    srv.ctx = ctx
    return srv

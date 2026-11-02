"""Command line entry point and application wiring."""
import argparse
import logging
import os
import signal
import sys
import threading
import time

from .alerts import Alerter
from .checker import Checker
from .config import ConfigError, load_config
from .db import Database, DatabaseError
from .server import Context, make_server
from .status import build_status
from .targets import merge_targets

log = logging.getLogger("uptimewatch")
DASHBOARD = os.path.join(os.path.dirname(__file__), "dashboard.html")


def fmt_table(rows, headers):
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)] if rows else [len(h) for h in headers]
    line = lambda r: "  ".join(str(c).ljust(w) for c, w in zip(r, widths)).rstrip()
    return "\n".join([line(headers)] + [line(r) for r in rows])


class Application:
    def __init__(self, config):
        self.config = config
        self.db = Database(config.database)
        with open(DASHBOARD, "r", encoding="utf-8") as f:
            self.dashboard = f.read().encode("utf-8")
        alerter = Alerter(self.db, config.discord_webhook_url) if config.discord_webhook_url else None
        self.checker = Checker(self.db, config.targets, config.default_timeout, config.retention_days,
                               alerter=alerter)
        self.server = None
        self.port = None
        self._thread = None

    def targets(self):
        return merge_targets(self.config.targets, self.db.list_ui_targets())[0]

    def start(self):
        ctx = Context(self.db, self.config, self.dashboard, self.targets)
        self.server = make_server(self.config.host, self.config.port, ctx)
        self.port = self.server.server_address[1]
        self._thread = threading.Thread(target=self.server.serve_forever, name="http", daemon=True)
        self._thread.start()
        self.checker.start()

    def stop(self):
        self.checker.stop()
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()


def cmd_status(config):
    db = Database(config.database)
    targets = merge_targets(config.targets, db.list_ui_targets())[0]
    st = build_status(db, targets, int(time.time()))
    rows = []
    for t in st["targets"]:
        lat = "%.0f ms" % t["latency_ms"] if t["latency_ms"] is not None else "-"
        up = "%.1f%%" % t["uptime_24h"] if t["uptime_24h"] is not None else "-"
        rows.append([t["name"], t["source"], t["state"], lat, t["last_check"] or "-", up])
    print(fmt_table(rows, ["NAME", "SOURCE", "STATE", "LATENCY", "LAST CHECK", "24H"]))
    return 1 if any(t["state"] == "down" for t in st["targets"]) else 0


def cmd_serve(config):
    app = Application(config)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    app.start()
    log.info("listening on %s:%s", config.host, app.port)
    stop.wait()
    app.stop()
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="uptimewatch")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("serve", "status"):
        sp = sub.add_parser(name)
        sp.add_argument("--config", default="config.json")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        config = load_config(args.config)
        return cmd_serve(config) if args.command == "serve" else cmd_status(config)
    except (ConfigError, DatabaseError, OSError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2

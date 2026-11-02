"""State-transition alerts to a Discord webhook. The URL is never logged."""
import json
import logging
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("uptimewatch.alerts")


class Alerter:
    def __init__(self, db, webhook_url, timeout=5):
        self.db = db
        self._url = webhook_url or ""
        self.timeout = timeout
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="alert") if self._url else None

    def observe(self, target, ok, error=""):
        """Record the latest result; alert once on an up<->down transition."""
        try:
            new = "up" if ok else "down"
            prev = self.db.get_state(target)
            now = int(time.time())
            if prev is None:
                self.db.upsert_state(target, new, now)
                return
            if prev["state"] == new:
                return
            self.db.upsert_state(target, new, now)
            if new == "down":
                msg = "\U0001F534 **%s** is DOWN: %s" % (target, error or "check failed")
            else:
                msg = "\U0001F7E2 **%s** is UP again" % target
            self._send(msg)
        except Exception:  # noqa: BLE001 - alerting must never break checking
            log.exception("alert processing failed")

    def _send(self, text):
        if not self._pool:
            return
        try:
            self._pool.submit(self._post, text)
        except RuntimeError:
            pass

    def _post(self, text):
        try:
            req = urllib.request.Request(
                self._url, data=json.dumps({"content": text[:1900]}).encode(), method="POST",
                headers={"Content-Type": "application/json", "User-Agent": "uptimewatch"})
            with urllib.request.urlopen(req, timeout=self.timeout):
                pass
        except Exception as e:  # noqa: BLE001 - never include the URL
            log.warning("discord alert failed: %s", type(e).__name__)

    def close(self):
        if self._pool:
            self._pool.shutdown(wait=True)

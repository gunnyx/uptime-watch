"""Scheduler: runs due checks on a thread pool and records results."""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .checks import run_check
from .targets import merge_targets

log = logging.getLogger("uptimewatch.checker")
PRUNE_EVERY = 3600


class Checker:
    def __init__(self, db, config_targets, timeout, retention_days, tick=1.0, clock=time.time, ui_poll=2.0, alerter=None):
        self.db = db
        self.config_targets = list(config_targets)
        self.timeout = timeout
        self.retention_days = retention_days
        self.tick = tick
        self.clock = clock
        self._stop = threading.Event()
        self.thread = None
        self._pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="check")
        self._due = {}
        self._running = set()
        self._lock = threading.Lock()
        self.ui_poll = ui_poll
        self.alerter = alerter
        self._targets = list(self.config_targets)
        self._next_poll = 0.0
        self._versions = {}
        self._warned = set()

    def start(self):
        self.prune()
        self.thread = threading.Thread(target=self._loop, name="checker", daemon=True)
        self.thread.start()

    def stop(self):
        self._stop.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
        self._pool.shutdown(wait=False, cancel_futures=True)
        if self.alerter is not None:
            self.alerter.close()

    def prune(self):
        try:
            n = self.db.prune(self.retention_days, self.clock())
            if n:
                log.info("pruned %d old results", n)
        except Exception:  # noqa: BLE001
            log.exception("prune failed")

    def current_targets(self):
        """Merged config + UI targets; UI rows are re-read at most every ui_poll seconds."""
        now = time.monotonic()
        if now >= self._next_poll:
            self._next_poll = now + self.ui_poll
            try:
                merged, collisions = merge_targets(self.config_targets, self.db.list_ui_targets())
            except Exception:  # noqa: BLE001 - keep the last known list
                log.exception("could not read UI targets")
                return self._targets
            for name in collisions:
                if name.lower() not in self._warned:
                    self._warned.add(name.lower())
                    log.warning("UI target %r ignored: name collides with a config target", name)
            self._targets = merged
            self._sync(merged)
        return self._targets

    def _sync(self, targets):
        """Drop schedules of removed/paused targets and reschedule edited ones."""
        active = {t.name for t in targets if not t.paused}
        with self._lock:
            for name in list(self._due):
                if name not in active:
                    del self._due[name]
            for t in targets:
                if self._versions.get(t.name) != t.updated_at:
                    self._versions[t.name] = t.updated_at
                    self._due.pop(t.name, None)
            for name in list(self._versions):
                if name not in {t.name for t in targets}:
                    del self._versions[name]

    def _loop(self):
        last_prune = time.monotonic()
        while not self._stop.is_set():
            try:
                self._tick()
                if time.monotonic() - last_prune >= PRUNE_EVERY:
                    last_prune = time.monotonic()
                    self.prune()
            except Exception:  # noqa: BLE001
                log.exception("scheduler tick failed")
            self._stop.wait(self.tick)

    def _tick(self):
        now = time.monotonic()
        for t in self.current_targets():
            if t.paused:
                continue
            with self._lock:
                if t.name in self._running or self._due.get(t.name, 0) > now:
                    continue
                self._running.add(t.name)
                self._due[t.name] = now + t.interval
            try:
                self._pool.submit(self._run, t)
            except RuntimeError:
                with self._lock:
                    self._running.discard(t.name)

    def _run(self, t):
        try:
            res = run_check(t, self.timeout)
            if self._stop.is_set():
                return
            self.db.insert_result(self.clock(), t.name, res.ok, res.latency_ms, res.error)
            if self.alerter is not None:
                self.alerter.observe(t.name, res.ok, res.error)
        except Exception:  # noqa: BLE001
            log.exception("check failed for %s", t.name)
        finally:
            with self._lock:
                self._running.discard(t.name)

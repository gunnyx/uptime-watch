"""HTTP and TCP checks."""
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

ERROR_MAX = 200


@dataclass
class CheckResult:
    ok: bool
    latency_ms: Optional[float]
    error: str = ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _err(e):
    text = "%s: %s" % (type(e).__name__, e) if str(e) else type(e).__name__
    return text.replace("\n", " ")[:ERROR_MAX]


def check_http(url, expected_status, timeout):
    start = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "uptimewatch"})
        try:
            with _opener.open(req, timeout=timeout) as r:
                status = r.status
        except urllib.error.HTTPError as e:
            status = e.code
            e.close()
        ms = round((time.monotonic() - start) * 1000, 1)
        if status == expected_status:
            return CheckResult(True, ms, "")
        return CheckResult(False, ms, ("unexpected status %d (expected %d)" % (status, expected_status))[:ERROR_MAX])
    except Exception as e:  # noqa: BLE001 - any failure is a failed check
        return CheckResult(False, None, _err(e))


def check_tcp(host, port, timeout):
    start = time.monotonic()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return CheckResult(True, round((time.monotonic() - start) * 1000, 1), "")
    except Exception as e:  # noqa: BLE001
        return CheckResult(False, None, _err(e))


def run_check(target, timeout):
    if target.type == "http":
        return check_http(target.url, target.expected_status or 200, timeout)
    return check_tcp(target.host, target.port, timeout)

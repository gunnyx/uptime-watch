"""Build the /status payload."""
from datetime import datetime, timezone


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_status(db, targets, now, management_enabled=False):
    out = []
    for t in targets:
        last = db.latest_result(t.name)
        if t.paused:
            state = "paused"
        elif last is None:
            state = "unknown"
        else:
            state = "up" if last["ok"] else "down"
        ok, n = db.uptime_counts(t.name, now - 86400)
        out.append({
            "id": t.id, "name": t.name, "type": t.type, "source": t.source, "state": state,
            "latency_ms": last["latency_ms"] if last else None,
            "last_check": iso(last["ts"]) if last else None,
            "uptime_24h": round(100.0 * ok / n, 1) if n else None,
            "paused": bool(t.paused), "interval": t.interval, "url": t.url,
            "expected_status": t.expected_status, "host": t.host, "port": t.port,
            "error": (last["error"] if last and not last["ok"] else ""),
        })
    active = [x["state"] for x in out if x["state"] != "paused"]
    if not active:
        overall = "none"
    elif "down" in active:
        overall = "down"
    elif "unknown" in active:
        overall = "unknown"
    else:
        overall = "up"
    return {"generated_at": iso(now), "overall": overall,
            "management_enabled": bool(management_enabled), "targets": out}

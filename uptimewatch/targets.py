"""Target model, input validation and config/UI merging."""
from dataclasses import dataclass
from typing import Optional

NAME_MAX = 64
MIN_INTERVAL = 5
DEFAULT_INTERVAL = 60
EDITABLE = ("name", "type", "interval", "url", "expected_status", "host", "port")


@dataclass
class Target:
    name: str
    type: str
    interval: float = DEFAULT_INTERVAL
    url: Optional[str] = None
    expected_status: Optional[int] = None
    host: Optional[str] = None
    port: Optional[int] = None
    source: str = "config"
    id: Optional[int] = None
    paused: bool = False
    updated_at: int = 0


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate_target_input(data, allow_paused=False, interval_required=True):
    """Validate a target body. Returns dict of field -> message (empty = valid)."""
    errors = {}
    if not isinstance(data, dict):
        return {"body": "must be a JSON object"}
    allowed = set(EDITABLE) | ({"paused"} if allow_paused else set())
    for k in data:
        if k not in allowed:
            errors[str(k)] = "unknown field"
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= NAME_MAX:
        errors["name"] = "must be a string of 1-%d characters" % NAME_MAX
    typ = data.get("type")
    if typ not in ("http", "tcp"):
        errors["type"] = "must be 'http' or 'tcp'"
    if "interval" in data or interval_required:
        iv = data.get("interval")
        if not _is_int(iv) or iv < MIN_INTERVAL:
            errors["interval"] = "must be an integer >= %d" % MIN_INTERVAL
    if allow_paused and "paused" in data and not isinstance(data["paused"], bool):
        errors["paused"] = "must be true or false"
    if typ == "http":
        url = data.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")) \
                or not url.split("://", 1)[1]:
            errors["url"] = "must start with http:// or https://"
        if "expected_status" in data:
            es = data["expected_status"]
            if not _is_int(es) or not 100 <= es <= 599:
                errors["expected_status"] = "must be an integer 100-599"
        for k in ("host", "port"):
            if k in data:
                errors[k] = "not allowed for http targets"
    elif typ == "tcp":
        host = data.get("host")
        if not isinstance(host, str) or not host.strip():
            errors["host"] = "is required for tcp targets"
        port = data.get("port")
        if not _is_int(port) or not 1 <= port <= 65535:
            errors["port"] = "must be an integer 1-65535"
        for k in ("url", "expected_status"):
            if k in data:
                errors[k] = "not allowed for tcp targets"
    return errors


def clean_target_input(data):
    """Normalised editable fields for a valid body (applies defaults)."""
    out = {
        "name": data["name"].strip(),
        "type": data["type"],
        "interval": data["interval"],
        "url": None, "expected_status": None, "host": None, "port": None,
    }
    if data["type"] == "http":
        out["url"] = data["url"]
        out["expected_status"] = data.get("expected_status", 200)
    else:
        out["host"] = data["host"].strip()
        out["port"] = data["port"]
    return out


def merge_targets(config_targets, ui_rows):
    """Merge config targets and UI rows. Config wins on (case-insensitive) name collision.

    Returns (targets, collisions) where collisions lists ignored UI target names.
    """
    out = list(config_targets)
    seen = {t.name.lower() for t in out}
    collisions = []
    for r in ui_rows:
        if r["name"].lower() in seen:
            collisions.append(r["name"])
            continue
        seen.add(r["name"].lower())
        out.append(Target(
            name=r["name"], type=r["type"], interval=r["interval"], url=r["url"],
            expected_status=r["expected_status"], host=r["host"], port=r["port"],
            source="ui", id=r["id"], paused=bool(r["paused"]), updated_at=r["updated_at"]))
    return out, collisions

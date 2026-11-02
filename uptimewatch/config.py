"""Strict JSON config loading. Never echoes secret values in errors."""
import json
import os
from dataclasses import dataclass, field

from .targets import DEFAULT_INTERVAL, Target, clean_target_input, validate_target_input

TOP_KEYS = {"database", "default_timeout", "retention_days", "discord_webhook_url",
            "admin_token", "server", "targets"}
SERVER_KEYS = {"host", "port"}
SECRET_KEYS = {"admin_token", "discord_webhook_url"}


class ConfigError(Exception):
    pass


@dataclass
class Config:
    database: str = "uptime.db"
    default_timeout: float = 10
    retention_days: int = 30
    discord_webhook_url: str = ""
    admin_token: str = ""
    host: str = "127.0.0.1"
    port: int = 8080
    targets: list = field(default_factory=list)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def load_config(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except OSError as e:
        raise ConfigError("cannot read config %s: %s" % (path, e.strerror or "error")) from None
    except ValueError:
        raise ConfigError("config %s is invalid JSON" % path) from None
    return parse_config(raw)


def parse_config(raw):
    if not isinstance(raw, dict):
        raise ConfigError("config must be a JSON object")
    for k in raw:
        if k not in TOP_KEYS:
            raise ConfigError("unknown config key: %s" % k)
    c = Config()
    if "database" in raw:
        if not isinstance(raw["database"], str) or not raw["database"]:
            raise ConfigError("database must be a non-empty string")
        c.database = raw["database"]
    if "default_timeout" in raw:
        v = raw["default_timeout"]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            raise ConfigError("default_timeout must be a number > 0")
        c.default_timeout = v
    if "retention_days" in raw:
        v = raw["retention_days"]
        if not _int(v) or v < 1:
            raise ConfigError("retention_days must be an integer >= 1")
        c.retention_days = v
    for key in ("discord_webhook_url", "admin_token"):
        if key in raw:
            if not isinstance(raw[key], str):
                raise ConfigError("%s must be a string" % key)
            setattr(c, key, raw[key])
    srv = raw.get("server", {})
    if not isinstance(srv, dict):
        raise ConfigError("server must be an object")
    for k in srv:
        if k not in SERVER_KEYS:
            raise ConfigError("unknown config key: server.%s" % k)
    if "host" in srv:
        if not isinstance(srv["host"], str) or not srv["host"]:
            raise ConfigError("server.host must be a non-empty string")
        c.host = srv["host"]
    if "port" in srv:
        if not _int(srv["port"]) or not 1 <= srv["port"] <= 65535:
            raise ConfigError("server.port must be an integer 1-65535")
        c.port = srv["port"]
    targets = raw.get("targets", [])
    if not isinstance(targets, list):
        raise ConfigError("targets must be a list")
    seen = set()
    for i, t in enumerate(targets):
        where = "targets[%d]" % i
        if not isinstance(t, dict):
            raise ConfigError("%s must be an object" % where)
        data = dict(t)
        data.setdefault("interval", DEFAULT_INTERVAL)
        errs = validate_target_input(data)
        if errs:
            field_, msg = next(iter(errs.items()))
            raise ConfigError("%s.%s: %s" % (where, field_, msg))
        cl = clean_target_input(data)
        key = cl["name"].lower()
        if key in seen:
            raise ConfigError("%s.name: duplicate target name" % where)
        seen.add(key)
        c.targets.append(Target(source="config", **cl))
    env = os.environ.get("UPTIME_ADMIN_TOKEN")
    if env:
        c.admin_token = env
    return c

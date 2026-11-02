# Uptime Watch

A small self-hosted uptime monitor. It checks HTTP and TCP targets on an interval, keeps history in SQLite, serves a phone-friendly dashboard, and can alert a Discord channel when a target goes down or recovers. Python standard library only, with no third-party packages.

## Requirements

- Python 3.11 or newer
- Docker (optional)

## Quick start

```sh
cp config.example.json config.json      # edit targets, server.port, ...
UPTIME_ADMIN_TOKEN=change-me python -m uptimewatch serve --config config.json
```

Open `http://localhost:8080/`. Check the API with `curl localhost:8080/health` and `curl localhost:8080/status`.

## Configuration (`config.json`)

| Key | Default | Notes |
|---|---|---|
| `database` | `uptime.db` | SQLite file path |
| `default_timeout` | `10` | seconds, number > 0 |
| `retention_days` | `30` | integer >= 1; older results are pruned at startup and hourly |
| `discord_webhook_url` | `""` | empty disables alerts |
| `admin_token` | `""` | enables target management; overridden by `UPTIME_ADMIN_TOKEN` when that is non-empty |
| `server.host` / `server.port` | `127.0.0.1` / `8080` | |
| `targets[]` | `[]` | see below |

Targets: `name` (1-64 chars, unique case-insensitively), `type` (`http` or `tcp`), `interval` (integer seconds >= 5, default 60).
- `http`: `url` (must start with `http://` or `https://`), optional `expected_status` (100-599, default 200). Redirects are not followed, so the first response status is compared.
- `tcp`: `host` and `port` (1-65535).

Unknown keys, wrong types and duplicate names stop startup with a message naming the key. Secret values are never echoed in errors.

Config targets are read-only at runtime and show as source `config`. Targets added in the dashboard have source `ui` and are stored in the same SQLite database. If a config target and a UI target share a name, the config target wins and the UI one is ignored (a warning is logged).

## Dashboard and admin token

`GET /` serves one self-contained HTML page with no external requests. It refreshes every 15 seconds and shows an overall banner plus a badge, latency, 24-hour uptime and last check per target.

If an admin token is configured, the page offers Add target and, on UI rows only, Edit, Pause/Resume and Delete (with confirmation). The token is asked for once and kept in `sessionStorage` for the browser session. With no token configured all management controls are hidden and the write API returns 403.

### Security notes

- The server speaks plain HTTP. The token travels in clear text unless you put a TLS-terminating reverse proxy in front. Do that before exposing it.
- `GET /`, `/status` and `/health` are unauthenticated, so target URLs and hosts are visible to anyone who can reach the server. Restrict network access.
- A token holder can make the monitor request arbitrary URLs and hosts, including internal ones (SSRF-like). That is accepted because only the token holder can add targets.
- The token and Discord webhook URL are never written to logs, error messages or API responses. Request logs omit headers.

## HTTP API

| Request | Auth | Result |
|---|---|---|
| `GET /health` | none | `{"status":"ok"}` |
| `GET /status` | none | overall state and per-target details |
| `POST /api/targets` | Bearer | 201, create a UI target |
| `PUT /api/targets/<id>` | Bearer | 200, replace fields, or `{"paused": true/false}` |
| `DELETE /api/targets/<id>` | Bearer | 204 |

Send `Authorization: Bearer <admin_token>`. No token configured gives 403, a missing or wrong token gives 401, then 413 (body over 10 KB), 400, 404 and 409 (duplicate name or more than 200 UI targets). Details are in `specs/001-uptime-monitor/contracts/http-api.md`.

## CLI

```sh
python -m uptimewatch serve  [--config config.json]
python -m uptimewatch status [--config config.json]
```

`status` prints NAME, SOURCE, STATE, LATENCY, LAST CHECK, 24H. Exit codes: `0` no target is down (unknown targets are not down), `1` at least one target is down, `2` config or database error (message on stderr). `serve` exits `0` on SIGINT/SIGTERM and `2` on a config or database error.

## Alerts

With `discord_webhook_url` set, one message is sent when a target goes up to down and one when it recovers, never per failed check. The first result after the very first start only sets the baseline. Last known state is stored, so restarts do not repeat alerts. Delivery failures are logged (without the URL) and never stop checking.

## Docker

```sh
docker build -t uptime-watch .
docker run -d -p 8080:8080 -v uptime-data:/data uptime-watch
```

The image runs as non-root user `uptime` (uid 10001) and expects `/data/config.json`. In that file set `"database": "/data/uptime.db"` and `"server": {"host": "0.0.0.0", "port": 8080}` so the port is reachable from outside the container. Pass the token with `-e UPTIME_ADMIN_TOKEN=...`.

Volume permissions: `/data` must be writable by uid 10001. A fresh named volume inherits that from the image. For a bind mount run `chown 10001:10001 ./data` on the host first.

A health check calls `/health` inside the container.

## Tests

```sh
python -m unittest discover -s tests
```

Tests run offline using local fake HTTP/TCP targets and a fake webhook on 127.0.0.1.

## Limitations

Single shared admin token, no user accounts, no HTTPS termination, Discord is the only alert channel, no history charts, and config changes need a restart.

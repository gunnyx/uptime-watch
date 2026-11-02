# HTTP API Contract

All responses are JSON (`Content-Type: application/json`) except `/` (`text/html; charset=utf-8`). Errors: `{"error": "message", "fields": {"name": "reason"}}` (`fields` optional). Responses never contain the token or webhook URL.

| Method & path | Auth | Success | Errors |
|---|---|---|---|
| `GET /` | none | 200 HTML dashboard | — |
| `GET /health` | none | 200 `{"status":"ok"}` | — |
| `GET /status` | none | 200 (below) | — |
| `POST /api/targets` | Bearer | 201 target object | 400 invalid JSON/validation, 401, 403, 409 duplicate name or limit (200) reached, 413 body > 10 KB |
| `PUT /api/targets/<id>` | Bearer | 200 target object | 400, 401, 403, 404, 409 duplicate name, 413 |
| `DELETE /api/targets/<id>` | Bearer | 204 | 401, 403, 404 |

Auth order: no admin token configured → 403; missing/incorrect `Authorization: Bearer <token>` → 401; then 413/400/404/409 checks. Unknown paths → 404; wrong method → 405. Request bodies must have `Content-Length` ≤ 10240.

## GET /status

```json
{
  "generated_at": "2026-11-02T12:00:00Z",
  "overall": "up | down | unknown | none",
  "management_enabled": true,
  "targets": [
    {"id": null, "name": "api", "type": "http", "source": "config", "state": "up",
     "latency_ms": 41.2, "last_check": "2026-11-02T11:59:50Z", "uptime_24h": 99.9,
     "paused": false, "interval": 30, "url": "https://x/health", "expected_status": 200,
     "host": null, "port": null, "error": ""}
  ]
}
```

`overall`: `down` if any active target is down; `up` if all active targets are up; `unknown` if some are unknown and none down; `none` if no active targets.

## Target body (POST / PUT)

```json
{"name": "My site", "type": "http", "url": "https://example.com", "expected_status": 200, "interval": 30}
{"name": "DB", "type": "tcp", "host": "db.local", "port": 5432, "interval": 30}
{"paused": true}
```

Validation: name 1–64 chars, unique (case-insensitive, across config and UI); type `http|tcp`; http requires `url` starting `http://` or `https://`; tcp requires `host` and integer `port` 1–65535; `interval` integer ≥ 5; `expected_status` integer 100–599 (default 200); unknown fields rejected; max 200 UI targets. PUT with only `paused` toggles pause; otherwise full replacement of editable fields (`paused` optional, default unchanged).

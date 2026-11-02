# Implementation Plan: Self-Hosted Uptime Monitor

**Branch**: `001-uptime-monitor` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-uptime-monitor/spec.md`

## Summary

A single-process Python application using only the standard library. One process runs (a) a checker thread that merges config and UI targets every ~2 s and runs due checks on a small thread pool, (b) a `ThreadingHTTPServer` serving `/`, `/status`, `/health` and the `/api/targets` write API, and (c) an optional Discord notifier invoked on state transitions. SQLite (WAL mode) stores check results, UI targets and last-known per-target state. A separate CLI entry point reads the same database and config to print a status table. The dashboard is one static HTML file with inline CSS/JS, read from disk at startup and served from memory.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib only)

**Primary Dependencies**: None at runtime (`http.server`, `socketserver`, `sqlite3`, `urllib.request`, `socket`, `threading`, `json`, `argparse`, `hmac`, `concurrent.futures`). Tests use `unittest` (no pytest). No dependency is added, so no justification is needed.

**Storage**: SQLite file at config `database` (WAL, `check_same_thread=False` with one connection per thread via a small helper). Tables: `results`, `ui_targets`, `target_state`.

**Testing**: `python -m unittest discover -s tests`; API tests start the real server on `127.0.0.1:0` in a thread against a temp-dir database; fake targets are a local `ThreadingHTTPServer` (configurable status/delay) and a local listening socket; a fake Discord receiver is another local server.

**Target Platform**: Linux (also works elsewhere); container `python:3.12-slim`.

**Project Type**: single project — service + CLI + one static HTML page.

**Performance Goals**: ≤ 200 UI targets plus config targets; `/status` answers < 1 s; target changes visible to the checker ≤ 5 s.

**Constraints**: stdlib only; dashboard single file, inline CSS/JS, zero external requests; body ≤ 10 KB; token and webhook URL never logged; non-root container with writable `/data`.

**Scale/Scope**: one operator, tens to a few hundred targets, ~1 write per second per target at most (interval ≥ 5 s).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is still the unfilled spec-kit template (placeholders only), so it defines no enforceable gates. Self-imposed gates derived from the brief are used instead:

| Gate | Status |
|------|--------|
| Standard library only, no runtime dependencies | PASS |
| Test-first ordering in tasks.md | PASS (enforced in tasks.md) |
| Secrets (token, webhook URL) never logged | PASS (never passed to the logger or error text; one sentinel test) |
| Smallest viable structure (one package, no framework) | PASS |

Post-design re-check: PASS — no violations, Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-uptime-monitor/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── http-api.md
│   ├── config-schema.md
│   └── cli.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
uptimewatch/
├── __init__.py
├── __main__.py        # `python -m uptimewatch serve|status`
├── config.py          # load + strict validation of JSON config, token resolution
├── db.py              # connect, schema, results/ui_targets/target_state access, pruning
├── targets.py         # Target dataclass, validate_target_input(), merge_targets()
├── checks.py          # check_http(), check_tcp() -> CheckResult
├── checker.py         # scheduler loop: merge, due-check selection, thread pool, record, prune
├── alerts.py          # transition detection + Discord webhook sender
├── status.py          # build status payload (state, latency, last check, 24h uptime)
├── server.py          # ThreadingHTTPServer handler: /, /status, /health, /api/targets
├── cli.py             # argparse, `serve` and `status` commands, table output, logging setup
└── dashboard.html     # single-file UI (inline CSS + JS)

tests/
├── helpers.py         # fake HTTP target, fake TCP target, fake webhook, test app factory
├── test_config.py
├── test_merge.py
├── test_target_validation.py
├── test_api_auth.py
├── test_api_crud.py
├── test_checks.py
├── test_checker.py
├── test_retention.py
├── test_alerts.py
├── test_status.py
├── test_cli.py
├── test_db.py
├── test_api_status.py
├── test_checker_live.py
├── test_logging_secrets.py
└── test_dashboard.py  # static assertions: no external URLs, required elements present

config.example.json
Dockerfile
.dockerignore
README.md
```

**Structure Decision**: Single project, one flat package. No web framework or ORM; raw `sqlite3` with parameterised queries. The CLI and server share `config.py`, `db.py`, `status.py`.

## Key Design Decisions

1. **Process model**: `serve` starts checker thread + HTTP server in one process. `status` is a separate short-lived process reading the DB (WAL allows concurrent reads). If the DB has no results yet the CLI reports `unknown` and does not fail on it; it fails only on `down`.
2. **Live merge**: each scheduler tick (1 s) calls `merge_targets(config_targets, ui_rows)`. UI rows are re-read from SQLite every 2 s (cheap for ≤ 200 rows; no `data_version` tracking), giving ≤ 5 s propagation without in-process signalling—so edits made by any writer are noticed. Merge is a pure function: config wins on name collision; paused UI targets are kept in the list but flagged and never scheduled; deleted ones vanish and their schedule entries are dropped; an edited target (changed `updated_at`) is rescheduled immediately.
3. **Scheduling**: dict of `name → next_due`; due targets run on a `ThreadPoolExecutor` (max 16 workers) so slow targets don't block others; a target is never run concurrently with itself.
4. **Checks**: HTTP via `urllib.request` with a no-redirect opener and `GET`; success iff status == expected_status (HTTPError statuses are compared, not treated as exceptions). TCP via `socket.create_connection`. Latency via `time.monotonic()`. Error text truncated to 200 chars.
5. **Auth**: `hmac.compare_digest` on the bearer token; check order: token not configured → 403; missing/wrong → 401; then body-size, JSON parse, validation. Token and webhook URL are never passed to logging or error text (no masking layer; guarded by one sentinel test); request logging is overridden to omit headers.
6. **Validation** lives in `targets.validate_target_input()` (pure, unit-testable) returning a dict of field → message; used for POST and PUT. PUT is a full replacement of editable fields plus optional `paused`; a body of only `{"paused": bool}` is allowed for pause/resume.
7. **Alerts**: `target_state` table holds last known up/down per target; a transition is alerted only when previous state is known and differs. Discord sent in a worker thread with a 5 s timeout; failures logged without the URL.
8. **Dashboard**: `textContent`-only DOM updates (no `innerHTML` with data), CSS grid/flex responsive layout with a `<meta viewport>`, system font stack, `fetch('/status')` on a 15 s `setInterval`, token in `sessionStorage`, management controls driven by a `management_enabled` flag returned in `/status` (no secret exposed).
9. **Retention**: prune on startup and then hourly, `DELETE FROM results WHERE ts < ?`, indexed on `(target, ts)`.
10. **Docker**: `python:3.12-slim`, creates user `uptime` (uid 10001), `/data` owned by that user, `VOLUME /data`, `ENV` for config path `/data/config.json`, `EXPOSE 8080`, `HEALTHCHECK` using `python -c` against `/health`, `USER uptime`.

## Complexity Tracking

No constitution violations; nothing to justify.

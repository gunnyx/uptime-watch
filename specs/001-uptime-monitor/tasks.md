# Tasks: Self-Hosted Uptime Monitor

**Input**: Design documents from `/specs/001-uptime-monitor/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md

**Tests**: Requested by the spec (FR-023) and ordered test-first: within every phase, each `Test` task must be written and observed FAILING before the implementation task that follows it. Run: `python -m unittest discover -s tests`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- Paths are relative to the repository root. Stdlib only — add no dependencies.

---

## Phase 1: Setup

- [X] T001 Create package skeleton `uptimewatch/__init__.py`, `uptimewatch/__main__.py` (calls `cli.main`), empty `tests/__init__.py`
- [X] T002 [P] Create `config.example.json` per contracts/config-schema.md and `.gitignore` (ignore `*.db`, `config.json`, `__pycache__`)
- [X] T003 [P] Write test helpers in `tests/helpers.py`: fake HTTP target server (configurable status/delay, port 0), fake TCP listener, fake webhook receiver recording bodies, temp-dir database factory, `start_app(config)` returning base URL and stop function (helpers only; the app module does not exist yet)

---

## Phase 2: Foundational (blocks all stories)

- [X] T004 Write failing tests in `tests/test_config.py`: defaults, unknown key rejected at top level / `server` / target (error names the key path), wrong types, http/tcp field rules, duplicate names, name length 1–64, interval ≥ 5, `UPTIME_ADMIN_TOKEN` overrides `admin_token`, errors never echo token or webhook URL
- [X] T005 Implement `uptimewatch/config.py` (`load_config(path)` → validated `Config`, `ConfigError`) (never logs or echoes the token/webhook URL) until T004 passes
- [X] T006 Write failing tests in `tests/test_target_validation.py` for `validate_target_input`: name 1–64 after trim, http URL must start `http://`/`https://`, port 1–65535 integer (reject bool/strings), interval integer ≥ 5, expected_status 100–599 default 200, tcp requires host+port, http rejects host/port, unknown fields rejected, returns field→message dict
- [X] T007 Implement `Target` dataclass and `validate_target_input()` in `uptimewatch/targets.py` until T006 passes
- [X] T008 Write failing tests for the schema and data access in `tests/test_db.py`: tables/indexes in data-model.md created idempotently, WAL enabled, insert/query results, ui_targets CRUD with case-insensitive unique name, `target_state` upsert
- [X] T009 Implement `uptimewatch/db.py` (schema, per-thread connection helper, result/ui_target/target_state functions) until T008 passes

**Checkpoint**: config, validation and storage ready.

---

## Phase 3: User Story 1 — Monitor config targets and read status (P1) 🎯 MVP

**Goal**: Config targets are checked on interval, stored, pruned; `/status`, `/health` and the CLI report them.
**Independent Test**: run with one up and one down fake target; `/status` shows up/down; CLI exits non-zero.

- [X] T010 [P] [US1] Write failing tests in `tests/test_checks.py` using fake targets: HTTP ok on expected status, fail on other status (incl. 404/500 and an un-followed 301), fail on timeout, fail on refused connection, TCP ok/fail/timeout, latency recorded in ms, error text ≤ 200 chars
- [X] T011 [US1] Implement `uptimewatch/checks.py` (`check_http`, `check_tcp` → `CheckResult`, no-redirect opener) until T010 passes
- [X] T012 [P] [US1] Write failing tests in `tests/test_status.py`: states `up`/`down`/`unknown`/`paused`, latest latency and `last_check` ISO UTC, 24 h uptime = ok/total over trailing 86400 s rounded to 1 decimal, null when no checks, `overall` rules (`down`/`up`/`unknown`/`none`), old results excluded
- [X] T013 [US1] Implement `uptimewatch/status.py` (`build_status(db, targets, now)`) until T012 passes
- [X] T014 [P] [US1] Write failing tests in `tests/test_retention.py`: `prune(db, retention_days, now)` deletes only older rows, keeps boundary rows, returns count
- [X] T015 [US1] Implement pruning in `uptimewatch/db.py` until T014 passes
- [X] T016 [US1] Write failing tests in `tests/test_checker.py` (config targets only): each target checked on its interval (use short intervals via an injectable clock/min-interval override in tests), results recorded, slow target does not delay a fast one, a target is never run concurrently with itself, prune runs at startup, clean `stop()`
- [X] T017 [US1] Implement `uptimewatch/checker.py` (scheduler loop, `ThreadPoolExecutor(16)`, due-time dict, record results, periodic prune) until T016 passes
- [X] T018 [P] [US1] Write failing tests in `tests/test_api_status.py`: `GET /health` → 200 `{"status":"ok"}`, `GET /status` shape per contracts/http-api.md, unknown path 404, wrong method 405, no secrets in any response
- [X] T019 [US1] Implement `uptimewatch/server.py` read-only routes (`/health`, `/status`, `/`, 404/405) with request logging that omits headers, until T018 passes
- [X] T020 [P] [US1] Write failing tests in `tests/test_cli.py`: `status` prints table with NAME/SOURCE/STATE/LATENCY/LAST CHECK/24H, exit 1 when any target down, 0 when all up (unknown not counted as down), 2 on bad config or unreadable DB with message on stderr
- [X] T021 [US1] Implement `uptimewatch/cli.py` (`serve`, `status`, signal handling for clean shutdown, wiring checker + server) until T020 passes

**Checkpoint**: MVP — monitoring, status API, CLI.

---

## Phase 4: User Story 2 — Live dashboard (P1)

**Goal**: Single-file responsive dashboard with 15 s refresh, badges and banner.
**Independent Test**: serve `/` and verify static properties plus refresh logic.

- [X] T022 [US2] Write failing tests in `tests/test_dashboard.py`: `GET /` returns `text/html`; body contains no absolute `http://`/`https://` URLs (use only a plain-text placeholder such as `example.com` in form hints), no `<link`, no `src="http`, no `@import`, no `url(http`; contains `<meta name="viewport"`, `setInterval(` with `15000`, `fetch('/status'`; no use of `innerHTML` with dynamic data (assert `textContent` used and `innerHTML` absent); contains banner and table elements
- [X] T023 [US2] Create `uptimewatch/dashboard.html` (inline CSS/JS, system fonts, responsive layout down to 360 px, green/red/grey badges with text labels not colour only, banner, last check/latency/uptime columns, "cannot reach monitor" notice keeping last data); server loads it once at startup, until T022 passes
- [ ] T024 [US2] Manual check per quickstart steps 5 (resize to 360 px, observe 15 s refresh); record result in PR description _(NOT DONE: no browser available in the headless run; layout verified by CSS review only)_

**Checkpoint**: dashboard viewable and self-refreshing.

---

## Phase 5: User Story 3 — Manage targets from the dashboard (P2)

**Goal**: Token-protected add/edit/pause/delete of UI targets, live merge into the checker.
**Independent Test**: via API with fake targets and via dashboard manual steps.

- [X] T025 [P] [US3] Write failing tests in `tests/test_merge.py` for pure `merge_targets(config_targets, ui_rows)`: union with correct sources, config wins on name collision (case-insensitive) and collision is reported, paused UI flagged, deleted removed, edits reflected, order stable (config first), config targets never paused or editable
- [X] T026 [US3] Implement `merge_targets()` in `uptimewatch/targets.py` until T025 passes
- [X] T027 [P] [US3] Write failing tests in `tests/test_api_auth.py` (real server on port 0, fake targets): POST/PUT/DELETE with no header → 401, wrong token → 401, wrong scheme → 401, correct → success; no admin token configured → 403 for all three (even with a header); token never present in responses or captured log output; `UPTIME_ADMIN_TOKEN` env works
- [X] T028 [P] [US3] Write failing tests in `tests/test_api_crud.py`: add http and tcp (201, appears in `/status` with source `ui` and an id), duplicate name (case-insensitive, also vs config target) → 409, each validation rule from FR-017 → 400 with `fields`, 201st target → 409, body > 10 KB → 413, malformed JSON / non-object → 400, edit (200, values changed, rename collision → 409), edit/pause/delete of config target or unknown id → 404, pause then resume via `{"paused": bool}`, delete → 204 and gone from `/status`
- [X] T029 [US3] Implement write routes in `uptimewatch/server.py` (`POST /api/targets`, `PUT/DELETE /api/targets/<id>`) with auth order 403→401→413→400→404/409, `hmac.compare_digest`, size limit before reading body, until T027 and T028 pass
- [X] T030 [US3] Write failing tests in `tests/test_checker_live.py`: a UI target added while running is first checked within 5 s; an edit changes the checked URL within 5 s; pause stops new results; resume restarts them; delete stops checks and removes schedule; config targets unaffected; config/UI name collision keeps config target only
- [X] T031 [US3] Extend `uptimewatch/checker.py` to re-merge each tick (poll `ui_targets` at most every 2 s, reschedule edited targets immediately, drop deleted/paused) until T030 passes
- [X] T032 [US3] Extend `tests/test_dashboard.py` (failing first): page contains Add target form fields (name, type, url, host, port, interval, expected status), Delete uses `confirm(`, token stored via `sessionStorage`, controls gated on `management_enabled`, edit/pause/delete rendered only when `source === 'ui'`
- [X] T033 [US3] Extend `uptimewatch/dashboard.html` with Add form, per-row Edit/Pause-Resume/Delete (UI rows only), one-time token prompt stored in `sessionStorage`, server error messages shown per field, 401 clears the stored token and re-prompts; hide everything when `management_enabled` is false; until T032 passes
- [X] T034 [US3] Make `/status` expose `management_enabled`, `id`, `paused`, and editable fields (see contracts/http-api.md); extend `tests/test_status.py` first (failing), then `uptimewatch/status.py`

**Checkpoint**: full target management.

---

## Phase 6: User Story 4 — Discord alerts (P3)

**Goal**: One alert per state transition, never per failed check.
**Independent Test**: fake webhook receiver sees exactly one down and one up message.

- [X] T035 [US4] Write failing tests in `tests/test_alerts.py`: first observation sets state without alert; up→down sends exactly one message; repeated failures send none; down→up sends one; state persisted so a restart does not re-alert; webhook failure/timeout does not raise or stop checking; no webhook configured → no calls; webhook URL absent from captured logs; message names target, new state, error
- [X] T036 [US4] Implement `uptimewatch/alerts.py` (transition detection via `target_state`, sender with 5 s timeout in worker thread) and call it from `uptimewatch/checker.py` after each recorded result, until T035 passes

---

## Phase 7: User Story 5 — Container and docs (P3)

- [X] T037 [US5] Create `Dockerfile` (python:3.12-slim, non-root uid 10001, `/data` owned by it, config at `/data/config.json`, healthcheck via `python -c` urllib to `/health`) and `.dockerignore`
- [X] T038 [US5] Write `README.md`: overview, requirements, config reference, quick start, admin token and security notes (plain HTTP, SSRF caveat, unauthenticated reads), API summary, CLI usage/exit codes, Docker usage with volume permissions, tests, limitations
- [ ] T039 [US5] Build and run the image if Docker is available (`docker build`, run with `/data` volume, confirm non-root and `/health`); otherwise note it was not verified _(NOT DONE: Docker is not installed in this environment; Dockerfile unverified)_

---

## Phase 8: Polish

- [X] T040 [P] Add a test in `tests/test_logging_secrets.py` that runs a full session (including failures and alert delivery) with a sentinel token and webhook URL and asserts neither appears in captured logs or stderr; fix any leak
- [X] T041 [P] Verify the full suite is green offline (`python -m unittest discover -s tests`, no network beyond 127.0.0.1)
- [X] T042 Walk through every step of `quickstart.md` and correct code or docs where they disagree _(steps 3,4,6,9 run against a live server; steps 5 and 10 need a browser/Docker and were not run)_

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → stories. US1 and US2 can proceed in parallel after Phase 2 (US2 needs the server route from T019). US3 depends on US1 (server, checker, status) and US2 (dashboard). US4 depends on US1 checker. US5 can start after US1 but README must be finalised last.
- Within each phase: Test task → failing run → implementation task, in listed order.
- Same-file tasks are not [P]: `server.py` (T019, T029), `checker.py` (T017, T031, T036), `targets.py` (T007, T026), `dashboard.html` (T023, T033), `status.py` (T013, T034).

## Parallel Examples

- After T009: T010, T012, T014, T018, T020 (tests in distinct files) can be written together.
- In US3: T025, T027, T028 in parallel.
- Polish: T040 and T041.

## Implementation Strategy

1. MVP: Phases 1–3 (monitor + status API + CLI) → validate with fake targets.
2. Add US2 dashboard → validate on a phone-width viewport.
3. Add US3 management → validate quickstart steps 6–8.
4. Add US4 alerts, then US5 packaging/docs, then Polish.

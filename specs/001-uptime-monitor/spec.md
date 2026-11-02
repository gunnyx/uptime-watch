# Feature Specification: Self-Hosted Uptime Monitor

**Feature Branch**: `001-uptime-monitor`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "A small self-hosted uptime monitor in Python using only the standard library, with a web dashboard that can manage targets (JSON config, checker with SQLite history and retention, config + UI target sources merged live, status CLI, HTTP status/health/dashboard, token-protected target management, optional Discord alerts, phone-friendly single-file dashboard, tests, Docker, README)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Monitor targets from a config file and see their state (Priority: P1)

An operator writes a JSON config listing HTTP and TCP targets, starts the monitor, and every target is checked on its own interval. Each result is stored, old results are pruned, and the operator can see current state through a status JSON endpoint, a health endpoint, and a command-line status table.

**Why this priority**: Checking targets and recording results is the core value; everything else builds on it.

**Independent Test**: Start the monitor with a config containing one reachable and one unreachable target; within one interval both have recorded results, `/status` reports up/down correctly, and the CLI exits non-zero.

**Acceptance Scenarios**:

1. **Given** a valid config with an HTTP and a TCP target, **When** the monitor runs, **Then** each target is checked every `interval` seconds and every result (timestamp, target, ok/fail, latency in ms, error message) is stored.
2. **Given** a config containing an unknown key (top level, `server`, or inside a target), **When** the monitor or CLI loads it, **Then** it refuses to start and names the offending key.
3. **Given** an HTTP target whose response status differs from `expected_status`, or a target that exceeds the timeout, **When** it is checked, **Then** the result is recorded as failed with a readable error message.
4. **Given** results older than `retention_days`, **When** pruning runs, **Then** those results are removed and newer ones are kept.
5. **Given** at least one target is down, **When** the operator runs the CLI status command, **Then** a table of all targets is printed and the exit code is non-zero; if all are up, exit code is 0.
6. **Given** a running monitor, **When** a client requests `GET /status`, **Then** it receives JSON with, per target: name, state, latency, last check time, 24-hour uptime percent, and source. `GET /health` returns a simple success response while the process is serving.

---

### User Story 2 - Live dashboard (Priority: P1)

An operator opens the dashboard (on desktop or phone) and sees an overall banner and one row per target with a green/red/grey badge, last check time, latency and 24-hour uptime. The page refreshes itself every 15 seconds.

**Why this priority**: The dashboard is the primary way the operator consumes status.

**Independent Test**: Open `/` against a monitor with up, down and not-yet-checked targets; verify badge colours, banner text, and that a change in state appears within ~15 seconds without manual reload.

**Acceptance Scenarios**:

1. **Given** targets in states up, down and unknown (no result yet or paused), **When** the page loads, **Then** badges are green, red and grey respectively and the banner says whether everything is up.
2. **Given** the page is open, **When** 15 seconds pass, **Then** it re-fetches `/status` and updates rows and banner without a full reload.
3. **Given** a phone-sized screen, **When** the page is viewed, **Then** content is readable and usable without horizontal scrolling.
4. **Given** the page is loaded, **Then** it makes no requests to any host other than the monitor itself and is served as one self-contained HTML document.
5. **Given** `/status` cannot be fetched, **When** the refresh fails, **Then** the page shows a visible "cannot reach monitor" notice and keeps the last known data.

---

### User Story 3 - Manage targets from the dashboard (Priority: P2)

An operator with the admin token adds, edits, pauses/resumes and deletes targets through the dashboard. Config-file targets are shown as read-only. Changes take effect on the checker within a few seconds without a restart.

**Why this priority**: Adds convenience and the config/UI merge, but the monitor is useful without it.

**Independent Test**: With an admin token set, add a target through the form, observe it checked within a few seconds, edit it, pause it (state grey, no new checks), resume it, then delete it with confirmation.

**Acceptance Scenarios**:

1. **Given** an admin token is configured, **When** the page loads, **Then** the Add target form is shown, and Edit, Pause/Resume and Delete controls appear only on rows with source "ui". Config rows show no such controls.
2. **Given** the token has not been entered in this browser session, **When** the operator first uses a management action, **Then** the page asks for it once and keeps it in session storage for the rest of the session.
3. **Given** a valid Add form, **When** submitted, **Then** the target appears in the list with source "ui" and is first checked within a few seconds.
4. **Given** a write request without a valid `Authorization: Bearer <admin_token>` header, **Then** the server returns 401 and changes nothing.
5. **Given** no admin token is configured (neither config nor environment), **When** any write endpoint is called, **Then** it returns 403, and the page hides all management controls.
6. **Given** a UI target, **When** the operator clicks Delete, **Then** a confirmation is requested and the target (and its future checks) is removed only after confirming.
7. **Given** invalid input (see requirements), **When** submitted, **Then** the server rejects it with a 4xx status and a message naming the invalid field, and the page shows that message.

---

### User Story 4 - Discord alerts on state changes (Priority: P3)

If a Discord webhook is configured, the operator is notified once when a target goes from up to down and once when it recovers, never on each failed check.

**Why this priority**: Valuable but optional.

**Independent Test**: With a fake webhook receiver, make a target fail repeatedly then recover; exactly one "down" and one "up" message are sent.

**Acceptance Scenarios**:

1. **Given** a webhook is configured and a target transitions up→down, **Then** exactly one alert is sent.
2. **Given** a target stays down across many checks, **Then** no further alerts are sent.
3. **Given** a target transitions down→up, **Then** exactly one recovery alert is sent.
4. **Given** no webhook is configured, or the webhook call fails, **Then** checking continues unaffected and the webhook URL never appears in logs.

---

### User Story 5 - Deploy in a container (Priority: P3)

An operator builds the container image and runs it with a writable data volume, as a non-root user, following the README.

**Independent Test**: Build the image, run with a mounted `/data` volume and a config, and reach `/health`.

**Acceptance Scenarios**:

1. **Given** the image, **When** run, **Then** the process is not root and can create/write its database in `/data`.
2. **Given** the README, **When** followed from scratch, **Then** the operator can configure, run locally, run tests, and run via container.

---

### Edge Cases

- Config file missing, unreadable, invalid JSON, wrong value types, or duplicate target names: startup fails with a clear message (CLI exits non-zero).
- A UI target name equals a config target name: rejected (names are unique across both sources).
- A config-file target name colliding with an existing UI target at load time: config wins; the UI target is ignored (and reported in logs) until renamed or deleted.
- Edit/Pause/Delete of an unknown id or of a config target: 404 (config targets have no ids in the UI table, so they are not editable).
- Request body larger than 10 KB, not valid JSON, or not an object: rejected (413 / 400).
- 201st UI target: rejected.
- Pausing a target: no checks run, state shown grey ("paused"); history is kept; uptime % covers only checks actually made.
- A target with no results yet: state "unknown" (grey), uptime percent null.
- Target removed or edited: history for the old definition is retained until pruned but is not shown for a deleted target.
- Slow or hanging target does not delay other targets' checks.
- Database unwritable at startup: clear error, non-zero exit.
- Admin token comparison must not leak via timing; the token is never logged or returned by any endpoint.

## Requirements *(mandatory)*

### Functional Requirements

**Configuration**

- **FR-001**: The system MUST read a JSON config with keys: `database`, `default_timeout`, `retention_days`, `discord_webhook_url`, `server.host`, `server.port`, `admin_token` (optional), and `targets[]` with `name`, `type` (`http`|`tcp`), `interval`, `url`, `expected_status`, `host`, `port`.
- **FR-002**: The system MUST reject any unknown key at any level, and wrong types or missing required per-type fields (http needs `url`; tcp needs `host` and `port`), with an error naming the key.
- **FR-003**: The admin token MUST be taken from `UPTIME_ADMIN_TOKEN` if set (non-empty), otherwise from `admin_token`; if neither is present, management is disabled.
- **FR-004**: Config targets MUST be read-only at runtime and reported with source `"config"`.

**Checking and storage**

- **FR-005**: The system MUST check each active target on its own `interval`, applying `default_timeout`, concurrently so one slow target does not delay others.
- **FR-006**: HTTP checks MUST pass only if the response status equals `expected_status` (default 200); TCP checks MUST pass only if a connection opens within the timeout.
- **FR-007**: Every check MUST be stored with timestamp, target, ok/fail, latency in ms, and error message (empty on success).
- **FR-008**: Results older than `retention_days` MUST be pruned automatically and periodically.
- **FR-009**: The checker MUST merge config targets and UI targets and MUST pick up additions, edits, pauses and deletions within a few seconds (≤ 5 s) without restart.

**Status surface**

- **FR-010**: `GET /status` MUST return JSON with an overall summary and, per target: name, type, source, state (`up`|`down`|`unknown`|`paused`), latency (ms), last check time, and 24-hour uptime percent.
- **FR-011**: `GET /health` MUST return a success response without requiring authentication.
- **FR-012**: A CLI command MUST print a status table of all targets and exit non-zero if any target is down (exit 0 otherwise; a distinct non-zero for config/DB errors).
- **FR-013**: `GET /` MUST serve a single HTML file with inline CSS and JavaScript, no external requests (no CDNs, web fonts, remote images), responsive for phone screens.
- **FR-014**: The dashboard MUST fetch `/status` every 15 seconds and show per row: green/red/grey badge, last check time, latency, 24-hour uptime; plus an overall banner stating whether everything is up. Dynamic text MUST be inserted safely (no HTML injection from target names or error text).

**Target management**

- **FR-015**: `POST /api/targets`, `PUT /api/targets/<id>`, `DELETE /api/targets/<id>` MUST require `Authorization: Bearer <admin_token>`; missing/wrong → 401; no token configured → 403 (takes precedence over 401).
- **FR-016**: Pause and resume MUST be performed via PUT (a `paused` boolean) and be supported only for UI targets.
- **FR-017**: The server MUST validate: name 1–64 characters (after trimming) and unique across config and UI targets; type is `http` or `tcp`; http URL starts with `http://` or `https://`; tcp requires host and port; port integer 1–65535; interval integer ≥ 5 seconds; expected_status an integer 100–599; at most 200 UI targets; JSON body under 10 KB.
- **FR-018**: UI targets MUST be stored in a table separate from the check results, with source `"ui"`; deleting a UI target removes it from monitoring.
- **FR-019**: When an admin token is configured the page MUST offer an Add form, and Edit, Pause/Resume, Delete (with confirmation) on UI rows only; when no token is configured these controls MUST be hidden. The page MUST ask for the token once and keep it in `sessionStorage`.
- **FR-020**: The token and the Discord webhook URL MUST never be written to logs, error messages, or API responses.

**Alerts**

- **FR-021**: If `discord_webhook_url` is set, the system MUST send an alert only on up→down and down→up transitions, never on each failed check. Alert delivery failures MUST NOT interrupt checking.

**Packaging and quality**

- **FR-022**: The system MUST use only the Python standard library at runtime.
- **FR-023**: The repository MUST include unit tests for the target API (auth, validation, add, edit, pause, delete) and the merge logic, using a local test server and fake targets (no external network).
- **FR-024**: The repository MUST include a Dockerfile that runs as a non-root user and works with a writable `/data` volume, and a README with setup instructions.

### Key Entities

- **Config**: Validated settings read from the JSON file plus the effective admin token.
- **Target**: A monitored endpoint: id (UI only), name, type, interval, URL/expected status or host/port, source (`config`|`ui`), paused flag (UI only).
- **Check Result**: One recorded observation: timestamp, target name, ok/fail, latency ms, error message.
- **Target State**: Derived per target: up/down/unknown/paused, last result, 24-hour uptime percent.
- **Alert Transition**: Change of a target's up/down state that triggers one notification.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can go from a fresh checkout to a running monitor showing their targets in under 5 minutes using only the README.
- **SC-002**: A target added, edited, paused, resumed or deleted through the dashboard is reflected in checking behaviour within 5 seconds, with no restart.
- **SC-003**: A target outage appears on the dashboard within one target interval plus 15 seconds of it starting.
- **SC-004**: 100% of unauthenticated or wrongly authenticated write attempts are rejected and change no data.
- **SC-005**: During a sustained outage of N checks, exactly one down alert and (on recovery) one up alert are sent.
- **SC-006**: The dashboard is fully usable on a 360 px wide screen without horizontal scrolling and issues zero requests to other hosts.
- **SC-007**: The status command's exit code correctly reflects down/up for 100% of tested combinations.
- **SC-008**: The monitor with 200 UI targets plus config targets keeps the status endpoint responsive (under 1 second) on modest hardware.
- **SC-009**: The automated test suite for the target API and merge logic passes offline.

## Assumptions

- **Single operator / single admin token**: no user accounts; one shared bearer token. Serving over HTTPS is left to a reverse proxy; the README warns that the token is sent in clear text over plain HTTP.
- **Defaults** (chosen conservatively when unspecified): `database` = `uptime.db`; `default_timeout` = 10 s; `retention_days` = 30; `server.host` = `127.0.0.1`; `server.port` = 8080; `expected_status` = 200; per-target `interval` default 60 s (minimum 5 s); `discord_webhook_url` empty = alerts off. In the container the README config uses host `0.0.0.0` and database `/data/uptime.db`.
- **Per-target timeout** uses `default_timeout` (no per-target timeout key, as unknown keys are rejected).
- **Config path**: given by a `--config` CLI argument, defaulting to `config.json`; `UPTIME_ADMIN_TOKEN` is the only environment override.
- **Admin token precedence**: environment variable wins over the config file.
- **Name collisions** between UI and config targets are rejected at creation; if a config reload ever causes one, the config target wins.
- **Config changes** require a restart (the config file is read-only input); only UI targets are live-editable. Hot reload of the config file is out of scope.
- **Unknown state**: a target with no result yet shows "unknown" (grey); a paused target shows "paused" (grey). The overall banner is "all up" only when every active target is up; paused targets are ignored; with no active targets it states that none are monitored.
- **24-hour uptime** = passing checks ÷ total checks in the trailing 24 hours for that target name, rounded to one decimal; null if no checks.
- **Reading `/status`, `/health`, `/` is unauthenticated** (the brief requires auth only for writes). Operators should restrict network exposure; target URLs are visible to anyone who can reach the server.
- **Security of outgoing checks**: UI-added URLs may point to internal hosts (SSRF-like). This is accepted because only the token holder can add targets; documented in the README.
- **HTTP redirects** are not followed (conservative): the first response status is compared with `expected_status`, so a 301 passes only if `expected_status` is 301.
- **Alert baseline**: the first result for a target after startup establishes state and does not itself alert; a first-ever result of "down" after restart does not alert, to avoid restart storms. Last known state is persisted so restarts do not duplicate alerts.
- **Pause** is persisted in the UI target table; deleting a UI target keeps its historic results until pruned.
- **Platform**: Python 3.11+ on Linux; SQLite is available through the standard library.
- **Out of scope**: user accounts, multiple tokens, HTTPS termination, email/Slack alerts, per-target alert settings, graphs/history charts, config hot reload, i18n.

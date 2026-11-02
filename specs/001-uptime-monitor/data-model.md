# Data Model

## SQLite schema

```sql
CREATE TABLE IF NOT EXISTS results (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      INTEGER NOT NULL,          -- unix seconds, UTC
  target  TEXT    NOT NULL,          -- target name
  ok      INTEGER NOT NULL CHECK (ok IN (0,1)),
  latency_ms REAL,                   -- NULL if no connection was made
  error   TEXT NOT NULL DEFAULT ''   -- '' on success, <= 200 chars
);
CREATE INDEX IF NOT EXISTS idx_results_target_ts ON results(target, ts);
CREATE INDEX IF NOT EXISTS idx_results_ts ON results(ts);

CREATE TABLE IF NOT EXISTS ui_targets (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  name            TEXT NOT NULL UNIQUE COLLATE NOCASE,  -- 1..64 chars
  type            TEXT NOT NULL CHECK (type IN ('http','tcp')),
  url             TEXT,              -- http only, starts with http:// or https://
  expected_status INTEGER,           -- http only, 100..599, default 200
  host            TEXT,              -- tcp only
  port            INTEGER,           -- tcp only, 1..65535
  interval        INTEGER NOT NULL CHECK (interval >= 5),
  paused          INTEGER NOT NULL DEFAULT 0,
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS target_state (
  target TEXT PRIMARY KEY,
  state  TEXT NOT NULL CHECK (state IN ('up','down')),
  since  INTEGER NOT NULL
);
```

## Entities

- **Config**: `database`, `default_timeout` (number > 0), `retention_days` (int ≥ 1), `discord_webhook_url` (str, empty = off), `server{host,port}`, `admin_token` (optional str), `targets[]`. Unknown keys rejected at every level.
- **Target** (in-memory): `name`, `type`, `interval`, `url`, `expected_status`, `host`, `port`, `source` (`config`|`ui`), `id` (UI only, else null), `paused` (UI only; config always false), `updated_at`.
- **CheckResult**: `ts`, `target`, `ok`, `latency_ms`, `error`.
- **TargetStatus** (derived): `name`, `type`, `source`, `id`, `paused`, `state` (`up|down|unknown|paused`), `latency_ms`, `last_check` (ISO-8601 UTC or null), `uptime_24h` (float 0–100, 1 decimal, or null), plus display detail (`url` or `host:port`, `interval`, `expected_status`) for the edit form.

## Rules

- Names are unique case-insensitively across both sources; trimmed; 1–64 characters.
- State = `paused` if paused; `unknown` if no result; else `up`/`down` from latest result.
- 24 h uptime = `100 * sum(ok) / count` over `ts >= now-86400` for the target name.
- State transitions (`target_state`): no row → insert, no alert; differing state → update, alert once; same → no change.
- Deleting a UI target removes the `ui_targets` row and its `target_state` row; results remain until pruned.
- Pruning: `DELETE FROM results WHERE ts < now - retention_days*86400`.

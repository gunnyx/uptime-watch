# Research: Self-Hosted Uptime Monitor

No `NEEDS CLARIFICATION` items remain. Decisions:

| Topic | Decision | Rationale | Alternatives considered |
|-------|----------|-----------|-------------------------|
| HTTP server | `http.server.ThreadingHTTPServer` | stdlib, adequate for one operator | `wsgiref` (no benefit), asyncio (more code) |
| Concurrency | Scheduler thread + `ThreadPoolExecutor(16)` | Blocking checks with timeouts are simple in threads | asyncio streams (rewrite of urllib usage) |
| HTTP client | `urllib.request` with custom no-redirect handler | stdlib; HTTPError exposes status | `http.client` (more manual), following redirects (hides real status) |
| Storage | SQLite, WAL, per-thread connections | Concurrent CLI reads while server writes | JSON files (no queries), one shared connection with lock (slower under load) |
| Live updates | Poll `ui_targets` each tick | Meets ≤ 5 s without IPC; robust to external writers | In-process event/queue (does not cover other writers), file watch (not stdlib-portable) |
| Auth | Static bearer token, `hmac.compare_digest` | Required by brief; timing-safe | Basic auth, sessions (out of scope) |
| Token in browser | `sessionStorage` | Required; cleared with tab | `localStorage` (persists too long), cookies (CSRF) |
| Bearer header vs cookies | Header only | Immune to CSRF | — |
| Tests | `unittest` + real server on port 0 | No deps; real HTTP path covered | pytest (dependency), mocks of handler (misses wiring) |
| Dashboard escaping | `textContent` only | Avoids XSS from names/errors | Template escaping helper |
| Config unknown keys | Explicit allow-lists per level | Required by brief | JSON Schema library (dependency) |
| Redirects | Not followed | Honest status comparison | Follow (surprising passes) |
| Alert baseline | First observation sets state, no alert; state persisted | Avoids restart storms/duplicates | Alert on first down (noisy) |
| Constitution | Template unfilled; self-imposed gates used | Nothing enforceable exists | Fill constitution (outside this stage) |

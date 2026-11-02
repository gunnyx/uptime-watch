# Quickstart / Validation Guide

Prerequisites: Python 3.11+, optionally Docker.

1. Copy `config.example.json` to `config.json`; set `server.port` and (optionally) `UPTIME_ADMIN_TOKEN`.
2. Run tests: `python -m unittest discover -s tests` — all pass offline.
3. Start: `UPTIME_ADMIN_TOKEN=secret python -m uptimewatch serve --config config.json`.
4. Verify `curl localhost:8080/health` succeeds and `curl localhost:8080/status` lists config targets with source `config`.
5. Open `http://localhost:8080/`: banner, rows, 15 s refresh; resize to 360 px wide.
6. Without token: `curl -i -X POST localhost:8080/api/targets -d '{}'` → 401; with the token and a valid body → 201; the target is checked within 5 s.
7. Edit, pause, resume, delete via the dashboard (delete asks for confirmation).
8. Start without any token: write calls → 403 and the page hides management controls.
9. `python -m uptimewatch status --config config.json; echo $?` → table; exit non-zero if any target is down.
10. Docker: `docker build -t uptime-watch .` then `docker run -v uptime-data:/data -p 8080:8080 uptime-watch`; confirm `docker exec ... id -u` is non-zero and `/health` works.
11. Alerts: point `discord_webhook_url` at a local listener; make a target fail for several checks → one message; recover → one message.

Contracts: [http-api](./contracts/http-api.md), [config](./contracts/config-schema.md), [cli](./contracts/cli.md). Data: [data-model](./data-model.md).

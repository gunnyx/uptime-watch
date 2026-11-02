# CLI Contract

`python -m uptimewatch serve [--config PATH]` — run checker + HTTP server (default config `config.json`).

`python -m uptimewatch status [--config PATH]` — print a table (columns: NAME, SOURCE, STATE, LATENCY, LAST CHECK, 24H) from the database and merged targets.

Exit codes for `status`: `0` no target down; `1` at least one target down; `2` config or database error (message on stderr). `serve` exits `2` on config/database error, `0` on clean shutdown (SIGINT/SIGTERM).

# Config File Contract

```json
{
  "database": "uptime.db",
  "default_timeout": 10,
  "retention_days": 30,
  "discord_webhook_url": "",
  "admin_token": "",
  "server": {"host": "127.0.0.1", "port": 8080},
  "targets": [
    {"name": "site", "type": "http", "interval": 60, "url": "https://example.com", "expected_status": 200},
    {"name": "db", "type": "tcp", "interval": 30, "host": "127.0.0.1", "port": 5432}
  ]
}
```

- Allowed top-level keys: `database`, `default_timeout`, `retention_days`, `discord_webhook_url`, `admin_token`, `server`, `targets`. Allowed `server` keys: `host`, `port`. Allowed target keys: `name`, `type`, `interval`, `url`, `expected_status`, `host`, `port`. Anything else → error naming the key path.
- Types: `default_timeout` number > 0; `retention_days` int ≥ 1; `server.port` int 1–65535; target rules identical to the API (name 1–64 and unique, interval ≥ 5, URL scheme, port range). `http` targets must not set `host`/`port`; `tcp` targets must not set `url`/`expected_status`.
- `UPTIME_ADMIN_TOKEN` (non-empty) overrides `admin_token`.
- Errors are reported without echoing secret values.

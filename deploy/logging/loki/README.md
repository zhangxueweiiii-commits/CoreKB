# CoreKB Loki / Promtail

This is the minimal real Loki setup for CoreKB JSON logs. It is optional and is not started by the default compose file.

Start it with:

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability up -d loki promtail
```

Loki binds to `127.0.0.1:3100` and should only be accessed from localhost, an internal network, or VPN. Do not expose Loki directly to the public internet.

Promtail reads Docker container logs and parses CoreKB JSON fields:

- `timestamp`
- `level`
- `request_id`
- `trace_id`
- `user_id`
- `module`
- `message`
- `error`

Query examples:

```logql
{service="backend"} |= "request completed"
{service="worker", trace_id="TRACE_ID_HERE"}
{trace_id="TRACE_ID_HERE"}
```

Promtail should collect runtime logs from backend, worker, beat, nginx/reverse proxy, and supporting services. Do not collect `.env`, uploaded source files, database dumps, backup archives, API keys, or raw document content.

# CoreKB Jaeger APM 示例

这是 CoreKB 的最小可运行 Jaeger APM 示例，仅用于内网、开发或试运行环境。它不会并入主 `docker-compose.yml`。

## 启动 Jaeger

```bash
cd deploy/apm/jaeger
docker compose -f docker-compose.jaeger.example.yml up -d
```

Jaeger UI:

```text
http://localhost:16686
```

示例端口只绑定 `127.0.0.1`，不要直接暴露公网。

## 推荐链路

```text
CoreKB API / Worker
  -> OTEL Collector
  -> Jaeger
```

如果使用 `deploy/otel` 的 Collector 示例，可以在 `deploy/otel/otel-collector-config.yml` 中启用 OTLP exporter 到 Jaeger：

```yaml
exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      exporters: [logging, otlp/jaeger]
```

也可以在开发环境让 CoreKB 直接发送到 Jaeger 的 OTLP gRPC 端口：

```env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
OTEL_SERVICE_NAME=corekb-api
OTEL_WORKER_SERVICE_NAME=corekb-worker
JAEGER_URL=http://localhost:16686
```

## 查询 trace

1. 打开 Jaeger UI。
2. 选择 `corekb-api` 或 `corekb-worker` service。
3. 使用日志中的 `trace_id` 在 Jaeger 搜索框查询。

CoreKB 已为 Chat、Search、文档索引、批量索引任务和备份任务创建 span。

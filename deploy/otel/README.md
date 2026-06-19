# CoreKB OpenTelemetry Collector 示例

这是 CoreKB 的最小可用 OTEL Collector 示例。它不会并入主 `docker-compose.yml`，也不接任何云厂商。

## 启动

```bash
cd deploy/otel
docker compose -f docker-compose.otel.example.yml up -d
```

Collector 监听：

- OTLP gRPC: `4317`
- OTLP HTTP: `4318`
- Prometheus exporter: `9464`

这些端口示例中只绑定 `127.0.0.1`，生产环境建议仅内网或 VPN 访问。

## CoreKB 配置

API 服务：

```env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=corekb-api
```

Worker 服务可以覆盖：

```env
OTEL_SERVICE_NAME=corekb-worker
```

CoreKB 会在日志中输出 `trace_id`，并为 HTTP request、Chat、Search、文档索引和备份任务创建 span。

## 查看输出

当前 Collector 使用 logging exporter，直接查看 collector 容器日志：

```bash
docker logs -f otel-otel-collector-1
```

生产环境可在 `otel-collector-config.yml` 中打开 Jaeger、Tempo、Datadog、OpenSearch APM 等 exporter。示例配置只保留占位注释，不接真实云厂商。

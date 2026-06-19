# CoreKB 外部日志接入模板

CoreKB 后端、worker、beat 会输出结构化 JSON 日志，字段包括 `timestamp`、`level`、`request_id`、`user_id`、`module`、`message`、`error`，请求日志还包含 `method`、`path`、`status_code`、`duration_ms`、`ip`。

本目录只提供模板，不会接入主 `docker-compose.yml`。

## Loki + Promtail

适合轻量部署，和 Grafana 配合查看日志。

```bash
cd deploy/logging
docker compose -f docker-compose.loki.example.yml up -d
```

`loki-promtail.example.yml` 使用 Docker service discovery 采集 backend、worker、beat、flower、frontend、postgres、redis、qdrant 容器日志，并解析 JSON 字段为 label。

## ELK / Elasticsearch + Filebeat

适合已有 Elasticsearch / Kibana 的企业环境。将 `filebeat.elk.example.yml` 放入 Filebeat 配置目录，按实际 Elasticsearch 地址修改 `output.elasticsearch.hosts`。

## OpenSearch + Fluent Bit

适合使用 OpenSearch 的环境。`fluentbit-opensearch.example.conf` 示例会读取 Docker container log，解析 CoreKB JSON 日志并写入 OpenSearch。

## 采集注意事项

- 可以采集 backend、worker、beat、nginx/reverse proxy 的 stdout/stderr 或访问日志。
- 不要采集 `.env`、数据库 dump、备份包、上传原始文件内容。
- 不要把 API Key、密码、JWT、模型供应商密钥写入业务日志。
- 如果接入 nginx，建议保留 `X-Request-ID` 并转发给 backend，便于跨日志关联。
- 生产环境建议设置日志保留周期，例如 30-180 天，并按合规要求归档或删除。

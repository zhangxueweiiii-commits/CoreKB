import { useEffect, useState } from "react";
import { indexJobsApi, type IndexJobStats, type IndexJobSummary } from "../api/indexJobs";
import { systemApi, type HealthStatus, type QueueStatus } from "../api/system";

export function SystemStatus() {
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [jobStats, setJobStats] = useState<IndexJobStats | null>(null);
  const [jobs, setJobs] = useState<IndexJobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [queue, healthStatus, stats, latestJobs] = await Promise.all([
        systemApi.queueStatus(),
        systemApi.health(),
        indexJobsApi.stats(),
        indexJobsApi.list({ limit: 20 }),
      ]);
      setQueueStatus(queue);
      setHealth(healthStatus);
      setJobStats(stats);
      setJobs(latestJobs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载系统状态失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>系统状态</h2>
        <button type="button" onClick={load}>刷新</button>
      </div>
      {loading && <p className="muted">加载中...</p>}
      {error && <p className="error">{error}</p>}

      <div className="metric-grid">
        <span>API: {health?.api ? "正常" : "未知"}</span>
        <span>PostgreSQL: {health?.postgres ? "正常" : "异常"}</span>
        <span>Redis: {health?.redis ? "正常" : "异常"}</span>
        <span>Qdrant: {health?.qdrant ? "正常" : "异常"}</span>
        <span>Celery: {health?.celery ? "正常" : "不可用"}</span>
        <span>状态: {health?.status ?? "unknown"}</span>
      </div>

      {queueStatus && (
        <div className="subtle-block">
          <h3>基础统计</h3>
          <div className="metric-grid">
            <span>今日 Chat: {queueStatus.chat_today_count}</span>
            <span>今日 Search: {queueStatus.search_today_count}</span>
            <span>今日上传: {queueStatus.document_upload_today_count}</span>
            <span>Running jobs: {queueStatus.running_index_jobs}</span>
            <span>Pending jobs: {queueStatus.pending_index_jobs}</span>
            <span>最近错误: {queueStatus.recent_error_count}</span>
          </div>
          <div className="metric-grid">
            <span>最近备份状态: {queueStatus.latest_backup_status ?? "暂无"}</span>
            <span>
              最近备份时间:{" "}
              {queueStatus.latest_backup_time ? new Date(queueStatus.latest_backup_time).toLocaleString() : "暂无"}
            </span>
            <span>最近失败告警: {queueStatus.latest_failed_alert ?? "暂无"}</span>
          </div>
          <div className="metric-grid">
            <span>Tracing: {queueStatus.tracing_enabled ? "已开启" : "未开启"}</span>
            <span>APM: {queueStatus.apm_enabled ? "已开启" : "未开启"}</span>
            <span>OTEL Collector: {queueStatus.otlp_endpoint ?? "未配置"}</span>
            <span>
              Jaeger:{" "}
              {queueStatus.jaeger_url ? (
                <a href={queueStatus.jaeger_url} target="_blank" rel="noreferrer">
                  {queueStatus.jaeger_url}
                </a>
              ) : (
                "未配置"
              )}
            </span>
            <span>Loki: {queueStatus.loki_enabled ? "已开启" : "未开启"}</span>
            <span>Loki 状态: {queueStatus.loki_status ?? "未检测"}</span>
          </div>
          <p className="muted">可复制日志中的 trace_id 到 Jaeger 搜索框查看请求链路。</p>
          {queueStatus.flower_url && (
            <p>
              <a href={queueStatus.flower_url} target="_blank" rel="noreferrer">打开 Flower 面板</a>
            </p>
          )}
        </div>
      )}

      {jobStats && (
        <div className="subtle-block">
          <h3>索引任务统计</h3>
          <div className="metric-grid">
            <span>Pending: {jobStats.pending_count}</span>
            <span>Running: {jobStats.running_count}</span>
            <span>Completed: {jobStats.completed_count}</span>
            <span>Partial failed: {jobStats.partial_failed_count}</span>
            <span>Failed: {jobStats.failed_count}</span>
            <span>Failed recent: {jobStats.failed_recent_count}</span>
          </div>
        </div>
      )}

      <div className="subtle-block">
        <h3>最近失败任务</h3>
        {!jobStats || jobStats.latest_failed_jobs.length === 0 ? (
          <p className="muted">暂无失败任务</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>任务</th>
                <th>类型</th>
                <th>状态</th>
                <th>知识库</th>
                <th>失败数</th>
                <th>创建时间</th>
              </tr>
            </thead>
            <tbody>
              {jobStats.latest_failed_jobs.map((job) => (
                <tr key={job.id}>
                  <td>{job.id.slice(0, 8)}</td>
                  <td>{job.job_type}</td>
                  <td>{job.status}</td>
                  <td>{job.knowledge_base_id}</td>
                  <td>{job.failed_count}</td>
                  <td>{new Date(job.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="subtle-block">
        <h3>最近索引任务</h3>
        {jobs.length === 0 ? (
          <p className="muted">暂无任务记录</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>任务</th>
                <th>类型</th>
                <th>状态</th>
                <th>总数</th>
                <th>成功</th>
                <th>失败</th>
                <th>待处理</th>
                <th>创建时间</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>{job.id.slice(0, 8)}</td>
                  <td>{job.job_type}</td>
                  <td>{job.status}</td>
                  <td>{job.total_count}</td>
                  <td>{job.success_count}</td>
                  <td>{job.failed_count}</td>
                  <td>{job.pending_count}</td>
                  <td>{new Date(job.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

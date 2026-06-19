import { useEffect, useState, type MouseEvent } from "react";
import {
  indexJobsApi,
  type IndexJobStatus,
  type IndexJobSummary,
  type IndexJobType,
} from "../api/indexJobs";

interface Props {
  onOpenJob: (jobId: string) => void;
}

export function IndexJobsPage({ onOpenJob }: Props) {
  const [jobs, setJobs] = useState<IndexJobSummary[]>([]);
  const [status, setStatus] = useState<IndexJobStatus | "">("");
  const [jobType, setJobType] = useState<IndexJobType | "">("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setJobs(await indexJobsApi.list({ status, job_type: jobType, limit: 50 }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载索引任务失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [status, jobType]);

  async function retryFailed(job: IndexJobSummary, event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    const confirmed = window.confirm("将为该任务中的失败文档创建一个新的重试任务，原任务记录不会被覆盖。");
    if (!confirmed) return;
    setError("");
    setMessage("");
    try {
      const response = await indexJobsApi.retryFailed(job.id);
      if (response.job) {
        onOpenJob(response.job.id);
      } else {
        setMessage(response.message);
        await load();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "重试失败项失败");
    }
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>索引任务</h2>
        <button type="button" onClick={load}>刷新</button>
      </div>
      <div className="filters">
        <label>
          状态
          <select value={status} onChange={(event) => setStatus(event.target.value as IndexJobStatus | "")}>
            <option value="">全部</option>
            <option value="pending">pending</option>
            <option value="running">running</option>
            <option value="paused">paused</option>
            <option value="completed">completed</option>
            <option value="partial_failed">partial_failed</option>
            <option value="failed">failed</option>
            <option value="cancelled">cancelled</option>
          </select>
        </label>
        <label>
          类型
          <select value={jobType} onChange={(event) => setJobType(event.target.value as IndexJobType | "")}>
            <option value="">全部</option>
            <option value="document_index">document_index</option>
            <option value="kb_reindex">kb_reindex</option>
            <option value="retry_failed">retry_failed</option>
          </select>
        </label>
      </div>
      {loading && <p className="muted">加载中...</p>}
      {message && <p className="muted">{message}</p>}
      {error && <p className="error">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>任务类型</th>
            <th>状态</th>
            <th>知识库</th>
            <th>总数</th>
            <th>成功</th>
            <th>失败</th>
            <th>待处理</th>
            <th>创建时间</th>
            <th>完成时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {jobs.length === 0 ? (
            <tr><td colSpan={10}>暂无索引任务</td></tr>
          ) : (
            jobs.map((job) => (
              <tr key={job.id} className="clickable-row" onClick={() => onOpenJob(job.id)}>
                <td>{job.job_type}</td>
                <td>{job.status}</td>
                <td>{job.knowledge_base_id}</td>
                <td>{job.total_count}</td>
                <td>{job.success_count}</td>
                <td>{job.failed_count}</td>
                <td>{job.pending_count}</td>
                <td>{new Date(job.created_at).toLocaleString()}</td>
                <td>{job.finished_at ? new Date(job.finished_at).toLocaleString() : ""}</td>
                <td>
                  {["partial_failed", "failed"].includes(job.status) && job.failed_count > 0 && (
                    <button type="button" onClick={(event) => retryFailed(job, event)}>
                      重试失败项
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}

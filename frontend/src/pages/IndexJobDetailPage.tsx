import { useEffect, useMemo, useState } from "react";
import { indexJobsApi, type IndexJobDetail } from "../api/indexJobs";

interface Props {
  jobId: string | null;
  onBack: () => void;
  onOpenJob?: (jobId: string) => void;
}

export function IndexJobDetailPage({ jobId, onBack, onOpenJob }: Props) {
  const [job, setJob] = useState<IndexJobDetail | null>(null);
  const [onlyFailed, setOnlyFailed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const visibleItems = useMemo(
    () => (onlyFailed && job ? job.items.filter((item) => item.status === "failed") : job?.items ?? []),
    [job, onlyFailed],
  );

  async function load() {
    if (!jobId) return;
    setLoading(true);
    setError("");
    try {
      setJob(await indexJobsApi.get(jobId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载任务详情失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [jobId]);

  async function retryFailed() {
    if (!job) return;
    const confirmed = window.confirm("将为该任务中的失败文档创建一个新的重试任务，原任务记录不会被覆盖。");
    if (!confirmed) return;
    setError("");
    setMessage("");
    try {
      const response = await indexJobsApi.retryFailed(job.id);
      if (response.job) onOpenJob?.(response.job.id);
      else setMessage(response.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重试失败项失败");
    }
  }

  async function cancelJob() {
    if (!job) return;
    const confirmed = window.confirm("确认取消该任务？当前正在处理的文档不会被强制中断，worker 会在下一个文档前停止。");
    if (!confirmed) return;
    setError("");
    try {
      const response = await indexJobsApi.cancel(job.id);
      setMessage(response.message);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "取消任务失败");
    }
  }

  async function pauseJob() {
    if (!job) return;
    setError("");
    try {
      const response = await indexJobsApi.pause(job.id);
      setMessage(response.message);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "暂停任务失败");
    }
  }

  async function resumeJob() {
    if (!job) return;
    setError("");
    try {
      const response = await indexJobsApi.resume(job.id);
      setMessage(response.message);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "恢复任务失败");
    }
  }

  if (!jobId) {
    return (
      <section className="panel">
        <h2>索引任务详情</h2>
        <p className="muted">请选择一个索引任务。</p>
        <button type="button" onClick={onBack}>返回任务列表</button>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>索引任务详情</h2>
        <div className="actions">
          <button type="button" onClick={load}>刷新</button>
          <button type="button" onClick={onBack}>返回</button>
        </div>
      </div>
      {loading && <p className="muted">加载中...</p>}
      {message && <p className="muted">{message}</p>}
      {error && <p className="error">{error}</p>}
      {job && (
        <>
          <div className="actions detail-actions">
            {["partial_failed", "failed"].includes(job.status) && job.failed_count > 0 && (
              <button type="button" onClick={retryFailed}>重试失败项</button>
            )}
            {["pending", "running"].includes(job.status) && (
              <button type="button" onClick={pauseJob}>暂停任务</button>
            )}
            {job.status === "paused" && (
              <button type="button" onClick={resumeJob}>恢复任务</button>
            )}
            {["pending", "running", "paused"].includes(job.status) && (
              <button type="button" onClick={cancelJob}>取消任务</button>
            )}
          </div>
          <dl className="detail-list">
            <dt>任务 ID</dt>
            <dd>{job.id}</dd>
            <dt>任务类型</dt>
            <dd>{job.job_type}</dd>
            <dt>状态</dt>
            <dd>{job.status}</dd>
            <dt>知识库</dt>
            <dd>{job.knowledge_base_id}</dd>
            <dt>总数</dt>
            <dd>{job.total_count}</dd>
            <dt>成功 / 失败 / 待处理</dt>
            <dd>{job.success_count} / {job.failed_count} / {job.pending_count}</dd>
            <dt>开始时间</dt>
            <dd>{job.started_at ? new Date(job.started_at).toLocaleString() : "未开始"}</dd>
            <dt>完成时间</dt>
            <dd>{job.finished_at ? new Date(job.finished_at).toLocaleString() : "未完成"}</dd>
            <dt>错误信息</dt>
            <dd>{job.error_message || "无"}</dd>
          </dl>

          <div className="subtle-block">
            <div className="section-heading">
              <h3>文档处理明细</h3>
              <button type="button" onClick={() => setOnlyFailed(!onlyFailed)}>
                {onlyFailed ? "显示全部" : "只看失败项"}
              </button>
            </div>
            <table>
              <thead>
                <tr>
                  <th>文档</th>
                  <th>状态</th>
                  <th>错误信息</th>
                  <th>开始时间</th>
                  <th>完成时间</th>
                </tr>
              </thead>
              <tbody>
                {visibleItems.length === 0 ? (
                  <tr><td colSpan={5}>暂无明细</td></tr>
                ) : (
                  visibleItems.map((item) => (
                    <tr key={item.id} className={item.status === "failed" ? "failed-row" : ""}>
                      <td>{item.filename || item.document_id}</td>
                      <td>{item.status}</td>
                      <td>{item.error_message || ""}</td>
                      <td>{item.started_at ? new Date(item.started_at).toLocaleString() : ""}</td>
                      <td>{item.finished_at ? new Date(item.finished_at).toLocaleString() : ""}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

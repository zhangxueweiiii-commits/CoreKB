import { useEffect, useState } from "react";
import { backupsApi, type BackupJob, type BackupJobStatus, type BackupJobType } from "../api/backups";

function formatSize(value?: number | null) {
  if (!value) return "-";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export function BackupsPage() {
  const [backups, setBackups] = useState<BackupJob[]>([]);
  const [status, setStatus] = useState<BackupJobStatus | "">("");
  const [jobType, setJobType] = useState<BackupJobType | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [verifyResult, setVerifyResult] = useState<Record<string, boolean>>({});

  async function load() {
    setLoading(true);
    setError("");
    try {
      setBackups(await backupsApi.list({ status, job_type: jobType, limit: 50 }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载备份历史失败");
    } finally {
      setLoading(false);
    }
  }

  async function verify(backupId: string) {
    setError("");
    try {
      const result = await backupsApi.verify(backupId);
      setVerifyResult((prev) => ({ ...prev, [backupId]: result.verified }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "校验备份失败");
    }
  }

  useEffect(() => {
    load();
  }, [status, jobType]);

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>备份历史</h2>
        <button type="button" onClick={load}>刷新</button>
      </div>

      <div className="filters">
        <select value={status} onChange={(event) => setStatus(event.target.value as BackupJobStatus | "")}>
          <option value="">全部状态</option>
          <option value="running">running</option>
          <option value="completed">completed</option>
          <option value="failed">failed</option>
        </select>
        <select value={jobType} onChange={(event) => setJobType(event.target.value as BackupJobType | "")}>
          <option value="">全部类型</option>
          <option value="all">all</option>
          <option value="postgres">postgres</option>
          <option value="qdrant">qdrant</option>
          <option value="uploads">uploads</option>
        </select>
      </div>

      {loading && <p className="muted">加载中...</p>}
      {error && <p className="error">{error}</p>}
      {!loading && backups.length === 0 ? (
        <p className="muted">暂无备份记录</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>类型</th>
              <th>状态</th>
              <th>大小</th>
              <th>Checksum</th>
              <th>开始时间</th>
              <th>完成时间</th>
              <th>错误</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {backups.map((backup) => (
              <tr key={backup.id}>
                <td>{backup.job_type}</td>
                <td>{backup.status}</td>
                <td>{formatSize(backup.file_size)}</td>
                <td title={backup.checksum ?? ""}>{backup.checksum ? `${backup.checksum.slice(0, 12)}...` : "-"}</td>
                <td>{backup.started_at ? new Date(backup.started_at).toLocaleString() : "-"}</td>
                <td>{backup.finished_at ? new Date(backup.finished_at).toLocaleString() : "-"}</td>
                <td className={backup.error_message ? "error" : ""}>{backup.error_message ?? "-"}</td>
                <td>
                  <button type="button" onClick={() => verify(backup.id)} disabled={!backup.checksum}>
                    校验
                  </button>
                  {verifyResult[backup.id] !== undefined && (
                    <span className={verifyResult[backup.id] ? "success" : "error"}>
                      {verifyResult[backup.id] ? "通过" : "失败"}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

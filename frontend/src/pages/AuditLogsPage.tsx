import { FormEvent, useEffect, useState } from "react";
import { auditLogsApi, type AuditLog } from "../api/auditLogs";

export function AuditLogsPage() {
  const [items, setItems] = useState<AuditLog[]>([]);
  const [action, setAction] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("");
  const [actorUserId, setActorUserId] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setItems(await auditLogsApi.list({
        action,
        resource_type: resourceType,
        knowledge_base_id: knowledgeBaseId,
        actor_user_id: actorUserId,
        start_time: startTime ? new Date(startTime).toISOString() : undefined,
        end_time: endTime ? new Date(endTime).toISOString() : undefined,
        limit: 100,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载审计日志失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function submit(event: FormEvent) {
    event.preventDefault();
    load();
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>审计日志</h2>
        <button type="button" onClick={load}>刷新</button>
      </div>
      <form className="filters" onSubmit={submit}>
        <label>
          Action
          <input value={action} onChange={(event) => setAction(event.target.value)} placeholder="chat.ask" />
        </label>
        <label>
          Resource
          <input value={resourceType} onChange={(event) => setResourceType(event.target.value)} placeholder="document" />
        </label>
        <label>
          KB ID
          <input value={knowledgeBaseId} onChange={(event) => setKnowledgeBaseId(event.target.value)} />
        </label>
        <label>
          Actor ID
          <input value={actorUserId} onChange={(event) => setActorUserId(event.target.value)} />
        </label>
        <label>
          Start
          <input type="datetime-local" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
        </label>
        <label>
          End
          <input type="datetime-local" value={endTime} onChange={(event) => setEndTime(event.target.value)} />
        </label>
        <button type="submit">筛选</button>
      </form>
      {loading && <p className="muted">加载中...</p>}
      {error && <p className="error">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>Actor</th>
            <th>Action</th>
            <th>Resource</th>
            <th>Status</th>
            <th>IP</th>
            <th>Request ID</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr><td colSpan={7}>暂无审计日志</td></tr>
          ) : (
            items.map((item) => (
              <tr key={item.id}>
                <td>{new Date(item.created_at).toLocaleString()}</td>
                <td>{item.actor_user_id || ""}</td>
                <td>{item.action}</td>
                <td>{item.resource_type}:{item.resource_id || ""}</td>
                <td>{item.status}</td>
                <td>{item.ip_address || ""}</td>
                <td>{item.request_id || ""}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}

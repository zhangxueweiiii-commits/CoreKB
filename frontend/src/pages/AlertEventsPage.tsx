import { useEffect, useState } from "react";
import { alertsApi, type AlertEvent, type AlertStatus } from "../api/alerts";

export function AlertEventsPage() {
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [status, setStatus] = useState<AlertStatus | "">("open");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setAlerts(await alertsApi.list({ status, limit: 50 }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载告警事件失败");
    } finally {
      setLoading(false);
    }
  }

  async function update(alertId: string, action: "resolve" | "ignore") {
    setError("");
    try {
      if (action === "resolve") await alertsApi.resolve(alertId);
      else await alertsApi.ignore(alertId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新告警状态失败");
    }
  }

  useEffect(() => {
    load();
  }, [status]);

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>告警事件</h2>
        <button type="button" onClick={load}>刷新</button>
      </div>

      <div className="filters">
        <select value={status} onChange={(event) => setStatus(event.target.value as AlertStatus | "")}>
          <option value="">全部状态</option>
          <option value="open">open</option>
          <option value="resolved">resolved</option>
          <option value="ignored">ignored</option>
        </select>
      </div>

      {loading && <p className="muted">加载中...</p>}
      {error && <p className="error">{error}</p>}
      {!loading && alerts.length === 0 ? (
        <p className="muted">暂无告警事件</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>类型</th>
              <th>级别</th>
              <th>状态</th>
              <th>标题</th>
              <th>Webhook</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert) => (
              <tr key={alert.id}>
                <td>{alert.alert_type}</td>
                <td>{alert.severity}</td>
                <td>{alert.status}</td>
                <td title={alert.message}>{alert.title}</td>
                <td>{alert.webhook_sent ? "已发送" : alert.webhook_error ? "失败" : "未启用"}</td>
                <td>{new Date(alert.created_at).toLocaleString()}</td>
                <td>
                  {alert.status === "open" ? (
                    <>
                      <button type="button" onClick={() => update(alert.id, "resolve")}>resolve</button>
                      <button type="button" onClick={() => update(alert.id, "ignore")}>ignore</button>
                    </>
                  ) : (
                    <span className="muted">已处理</span>
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

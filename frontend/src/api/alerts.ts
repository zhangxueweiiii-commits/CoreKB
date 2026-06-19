import { request } from "./client";

export type AlertStatus = "open" | "resolved" | "ignored";

export interface AlertEvent {
  id: string;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  resource_type?: string | null;
  resource_id?: string | null;
  status: AlertStatus;
  webhook_sent: boolean;
  webhook_error?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  resolved_at?: string | null;
}

export const alertsApi = {
  list: (params: { status?: AlertStatus | ""; severity?: string; alert_type?: string; limit?: number; offset?: number } = {}) => {
    const search = new URLSearchParams();
    if (params.status) search.set("status", params.status);
    if (params.severity) search.set("severity", params.severity);
    if (params.alert_type) search.set("alert_type", params.alert_type);
    if (params.limit) search.set("limit", String(params.limit));
    if (params.offset) search.set("offset", String(params.offset));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<AlertEvent[]>(`/alerts${suffix}`);
  },
  resolve: (alertId: string) => request<AlertEvent>(`/alerts/${alertId}/resolve`, { method: "PATCH" }),
  ignore: (alertId: string) => request<AlertEvent>(`/alerts/${alertId}/ignore`, { method: "PATCH" }),
};

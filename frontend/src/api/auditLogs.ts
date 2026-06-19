import { request } from "./client";

export interface AuditLog {
  id: string;
  actor_user_id?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  knowledge_base_id?: string | null;
  document_id?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  request_id?: string | null;
  status: string;
  error_message?: string | null;
  meta: Record<string, unknown>;
  created_at: string;
}

export const auditLogsApi = {
  list: (
    params: {
      action?: string;
      resource_type?: string;
      knowledge_base_id?: string;
      actor_user_id?: string;
      start_time?: string;
      end_time?: string;
      limit?: number;
      offset?: number;
    } = {},
  ) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") search.set(key, String(value));
    });
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<AuditLog[]>(`/audit-logs${suffix}`);
  },
};

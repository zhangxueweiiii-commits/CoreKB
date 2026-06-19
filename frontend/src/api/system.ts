import { request } from "./client";

export interface QueueStatus {
  redis_connected: boolean;
  celery_available: boolean;
  pending_task_count: number | null;
  active_task_count: number | null;
  failed_recent_count: number | null;
  api_healthy: boolean;
  postgres_connected: boolean | null;
  qdrant_connected: boolean | null;
  running_index_jobs: number;
  pending_index_jobs: number;
  chat_today_count: number;
  search_today_count: number;
  document_upload_today_count: number;
  recent_error_count: number;
  flower_url?: string | null;
  latest_backup_status?: string | null;
  latest_backup_time?: string | null;
  latest_failed_alert?: string | null;
  tracing_enabled: boolean;
  otlp_endpoint?: string | null;
  apm_enabled: boolean;
  jaeger_url?: string | null;
  loki_enabled: boolean;
  loki_status?: string | null;
}

export interface HealthStatus {
  status: string;
  api: boolean;
  postgres: boolean;
  redis: boolean;
  qdrant: boolean;
  celery: boolean;
  timestamp: string;
}

export const systemApi = {
  queueStatus: () => request<QueueStatus>("/system/queue-status"),
  health: () => request<HealthStatus>("/health"),
};

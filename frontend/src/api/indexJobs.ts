import { request } from "./client";

export type IndexJobType = "document_index" | "kb_reindex" | "retry_failed";
export type IndexJobStatus =
  | "pending"
  | "running"
  | "paused"
  | "completed"
  | "partial_failed"
  | "failed"
  | "cancelled";

export interface IndexJobSummary {
  id: string;
  job_type: IndexJobType;
  status: IndexJobStatus;
  knowledge_base_id: string;
  document_id?: string | null;
  created_by?: string | null;
  total_count: number;
  success_count: number;
  failed_count: number;
  pending_count: number;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
}

export interface IndexJobItem {
  id: string;
  document_id: string;
  filename?: string | null;
  status: "pending" | "running" | "completed" | "failed" | "skipped" | "cancelled";
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface IndexJobDetail extends IndexJobSummary {
  error_message?: string | null;
  items: IndexJobItem[];
}

export interface IndexJobStats {
  running_count: number;
  pending_count: number;
  completed_count: number;
  partial_failed_count: number;
  failed_count: number;
  failed_recent_count: number;
  latest_failed_jobs: IndexJobSummary[];
}

export interface IndexJobActionResponse {
  message: string;
  job: IndexJobSummary | null;
}

export const indexJobsApi = {
  list: (
    params: {
      knowledge_base_id?: string;
      status?: IndexJobStatus | "";
      job_type?: IndexJobType | "";
      limit?: number;
      offset?: number;
    } = {},
  ) => {
    const search = new URLSearchParams();
    if (params.knowledge_base_id) search.set("knowledge_base_id", params.knowledge_base_id);
    if (params.status) search.set("status", params.status);
    if (params.job_type) search.set("job_type", params.job_type);
    if (params.limit) search.set("limit", String(params.limit));
    if (params.offset) search.set("offset", String(params.offset));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<IndexJobSummary[]>(`/index-jobs${suffix}`);
  },
  get: (jobId: string) => request<IndexJobDetail>(`/index-jobs/${jobId}`),
  stats: () => request<IndexJobStats>("/index-jobs/stats"),
  retryFailed: (jobId: string) =>
    request<IndexJobActionResponse>(`/index-jobs/${jobId}/retry-failed`, { method: "POST" }),
  cancel: (jobId: string) =>
    request<IndexJobActionResponse>(`/index-jobs/${jobId}/cancel`, { method: "POST" }),
  pause: (jobId: string) =>
    request<IndexJobActionResponse>(`/index-jobs/${jobId}/pause`, { method: "POST" }),
  resume: (jobId: string) =>
    request<IndexJobActionResponse>(`/index-jobs/${jobId}/resume`, { method: "POST" }),
  reindexKb: (kbId: string, payload: { document_ids?: string[]; force?: boolean } = { force: true }) =>
    request<IndexJobSummary>(`/kb/${kbId}/reindex`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

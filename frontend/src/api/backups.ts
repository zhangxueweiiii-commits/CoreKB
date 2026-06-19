import { request } from "./client";

export type BackupJobStatus = "running" | "completed" | "failed";
export type BackupJobType = "postgres" | "qdrant" | "uploads" | "all";

export interface BackupJob {
  id: string;
  job_type: BackupJobType;
  status: BackupJobStatus;
  backup_path?: string | null;
  file_size?: number | null;
  checksum?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
  created_at: string;
}

export interface BackupVerifyResponse {
  backup_id: string;
  verified: boolean;
  expected_checksum?: string | null;
  actual_checksum?: string | null;
}

export const backupsApi = {
  list: (params: { status?: BackupJobStatus | ""; job_type?: BackupJobType | ""; limit?: number; offset?: number } = {}) => {
    const search = new URLSearchParams();
    if (params.status) search.set("status", params.status);
    if (params.job_type) search.set("job_type", params.job_type);
    if (params.limit) search.set("limit", String(params.limit));
    if (params.offset) search.set("offset", String(params.offset));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<BackupJob[]>(`/backups${suffix}`);
  },
  verify: (backupId: string) =>
    request<BackupVerifyResponse>(`/backups/${backupId}/verify`, { method: "POST" }),
};

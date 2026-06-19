import { request } from "./client";

export type KbPermissionRole = "owner" | "editor" | "viewer";

export interface KbPermission {
  id: string;
  knowledge_base_id: string;
  user_id: string;
  username: string;
  email?: string | null;
  role: KbPermissionRole;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export const permissionsApi = {
  list: (kbId: string) => request<KbPermission[]>(`/kb/${kbId}/permissions`),
  create: (kbId: string, payload: { user_id: string; role: KbPermissionRole }) =>
    request<KbPermission>(`/kb/${kbId}/permissions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (kbId: string, permissionId: string, role: KbPermissionRole) =>
    request<KbPermission>(`/kb/${kbId}/permissions/${permissionId}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),
  remove: (kbId: string, permissionId: string) =>
    request<void>(`/kb/${kbId}/permissions/${permissionId}`, { method: "DELETE" }),
};

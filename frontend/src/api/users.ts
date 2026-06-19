import { request, type UserRole } from "./client";

export interface UserSearchResult {
  id: string;
  name: string;
  email?: string | null;
  role: UserRole;
  created_at: string;
}

export const usersApi = {
  search: (q: string, kbId: string, limit = 20) => {
    const params = new URLSearchParams({
      q,
      kb_id: kbId,
      limit: String(limit),
    });
    return request<UserSearchResult[]>(`/users/search?${params.toString()}`);
  },
};

import { request } from "./client";

export interface MetadataDictionaryEntry {
  id: string;
  field_name: string;
  canonical_value: string;
  aliases: string[];
  status: "active" | "inactive";
  description?: string | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export const metadataDictionaryApi = {
  list: (params: { field_name?: string; status?: string; keyword?: string } = {}) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) search.set(key, String(value));
    });
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<MetadataDictionaryEntry[]>(`/metadata-dictionary${suffix}`);
  },
  create: (payload: {
    field_name: string;
    canonical_value: string;
    aliases: string[];
    status?: "active" | "inactive";
    description?: string;
  }) =>
    request<MetadataDictionaryEntry>("/metadata-dictionary", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (entryId: string, payload: { canonical_value?: string; aliases?: string[]; status?: string; description?: string }) =>
    request<MetadataDictionaryEntry>(`/metadata-dictionary/${entryId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  addAlias: (entryId: string, alias: string) =>
    request<MetadataDictionaryEntry>(`/metadata-dictionary/${entryId}/aliases`, {
      method: "POST",
      body: JSON.stringify({ alias }),
    }),
  deleteAlias: (entryId: string, alias: string) =>
    request<MetadataDictionaryEntry>(`/metadata-dictionary/${entryId}/aliases/${encodeURIComponent(alias)}`, {
      method: "DELETE",
    }),
};

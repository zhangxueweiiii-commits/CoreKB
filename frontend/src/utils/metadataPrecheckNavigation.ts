import type { MetadataPrecheckItem } from "../api/metadataPrecheck";

export interface MetadataReviewFocus {
  documentId: string;
  tab?: string | null;
  focusField?: string | null;
  currentValue?: string | null;
  suggestedValue?: string | null;
  precheckStatus?: string | null;
  from?: string | null;
  precheckReturn?: string | null;
}

export function parseMetadataReviewFocus(pathname: string, search: string): MetadataReviewFocus | null {
  const match = pathname.match(/^\/documents\/([^/]+)$/);
  if (!match) return null;
  const params = new URLSearchParams(search);
  return {
    documentId: decodeURIComponent(match[1]),
    tab: params.get("tab"),
    focusField: params.get("focus_field"),
    currentValue: params.get("current_value"),
    suggestedValue: params.get("suggested_value"),
    precheckStatus: params.get("precheck_status"),
    from: params.get("from"),
    precheckReturn: params.get("precheck_return"),
  };
}

export function buildMetadataReviewUrl(item: MetadataPrecheckItem, currentSearch = ""): string {
  const params = new URLSearchParams();
  params.set("tab", "metadata");
  params.set("focus_field", item.field_name);
  if (item.current_value) params.set("current_value", item.current_value);
  if (item.suggested_value) params.set("suggested_value", item.suggested_value);
  params.set("precheck_status", item.status);
  params.set("from", "metadata_precheck");
  if (currentSearch) params.set("precheck_return", currentSearch.startsWith("?") ? currentSearch.slice(1) : currentSearch);
  return `/documents/${encodeURIComponent(item.document_id)}?${params.toString()}`;
}

export function buildMetadataPrecheckReturnUrl(precheckReturn?: string | null): string {
  return precheckReturn ? `/metadata/precheck?${precheckReturn}` : "/metadata/precheck";
}

import { apiV1Request } from "@/api/client";
import type {
  CsvFilterResult,
  ImportResult,
  ListVerifyResult,
  Subscriber,
  SubscriberList,
  SubscriberStats,
  SubscriberStatus,
} from "@/types/subscribers";

export async function fetchStats(): Promise<{ stats: SubscriberStats }> {
  return apiV1Request("/subscribers/stats/");
}

export async function fetchLists(): Promise<{ lists: SubscriberList[] }> {
  return apiV1Request("/subscribers/lists/");
}

export async function createList(data: {
  name: string;
  description?: string;
}): Promise<{ list: SubscriberList }> {
  return apiV1Request("/subscribers/lists/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteList(listId: string): Promise<void> {
  await apiV1Request(`/subscribers/lists/${listId}/`, { method: "DELETE" });
}

export async function fetchSubscribers(params?: {
  list_id?: string;
  status?: SubscriberStatus;
  search?: string;
}): Promise<{ subscribers: Subscriber[]; columns?: string[] }> {
  const query = new URLSearchParams();
  if (params?.list_id) query.set("list_id", params.list_id);
  if (params?.status) query.set("status", params.status);
  if (params?.search) query.set("search", params.search);
  const qs = query.toString();
  return apiV1Request(`/subscribers/${qs ? `?${qs}` : ""}`);
}

export async function createSubscriber(data: {
  email: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  status?: SubscriberStatus;
  list_ids?: string[];
}): Promise<{ subscriber: Subscriber }> {
  return apiV1Request("/subscribers/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteSubscriber(id: string): Promise<void> {
  await apiV1Request(`/subscribers/${id}/`, { method: "DELETE" });
}

export async function bulkDeleteSubscribers(ids: string[]): Promise<{ deleted: number }> {
  return apiV1Request("/subscribers/bulk-delete/", {
    method: "POST",
    body: JSON.stringify({ ids }),
  });
}

export async function importSubscribers(
  file: File,
  listId?: string,
): Promise<{ import: ImportResult }> {
  const form = new FormData();
  form.append("file", file);
  if (listId) form.append("list_id", listId);
  return apiV1Request("/subscribers/import/", { method: "POST", body: form });
}

export async function verifyList(listId: string): Promise<{ verify: ListVerifyResult }> {
  return apiV1Request("/subscribers/verify-list/", {
    method: "POST",
    body: JSON.stringify({ list_id: listId }),
  });
}

export async function filterCsvWithReacher(file: File): Promise<{ filter: CsvFilterResult }> {
  const form = new FormData();
  form.append("file", file);
  return apiV1Request("/subscribers/filter-csv/", { method: "POST", body: form });
}

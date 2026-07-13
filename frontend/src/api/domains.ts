import { apiV1Request } from "@/api/client";
import type {
  DomainStats,
  DomainStatus,
  DomainVerifyResult,
  SendingDomain,
} from "@/types/domains";

export async function fetchDomainStats(): Promise<{ stats: DomainStats }> {
  return apiV1Request("/domains/stats/");
}

export async function fetchDomains(params?: {
  search?: string;
  status?: DomainStatus;
}): Promise<{ domains: SendingDomain[] }> {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return apiV1Request(`/domains/${qs ? `?${qs}` : ""}`);
}

export async function createDomain(data: {
  domain: string;
  is_active?: boolean;
  is_default?: boolean;
}): Promise<{ domain: SendingDomain }> {
  return apiV1Request("/domains/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateDomain(
  id: string,
  data: Partial<{ is_active: boolean; is_default: boolean }>,
): Promise<{ domain: SendingDomain }> {
  return apiV1Request(`/domains/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteDomain(id: string): Promise<void> {
  await apiV1Request(`/domains/${id}/`, { method: "DELETE" });
}

export async function setDefaultDomain(id: string): Promise<{ domain: SendingDomain }> {
  return apiV1Request(`/domains/${id}/default/`, { method: "POST" });
}

export async function verifyDomain(id: string): Promise<DomainVerifyResult> {
  return apiV1Request(`/domains/${id}/verify/`, { method: "POST" });
}

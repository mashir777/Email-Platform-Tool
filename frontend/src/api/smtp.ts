import { apiV1Request } from "@/api/client";
import type { SmtpEncryption, SmtpServer, SmtpStats, SmtpTestResult } from "@/types/smtp";

export async function fetchSmtpStats(): Promise<{ stats: SmtpStats }> {
  return apiV1Request("/smtp/stats/");
}

export async function fetchSmtpServers(params?: {
  search?: string;
}): Promise<{ servers: SmtpServer[] }> {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  const qs = query.toString();
  return apiV1Request(`/smtp/${qs ? `?${qs}` : ""}`);
}

export async function createSmtpServer(data: {
  name: string;
  host: string;
  port?: number;
  username?: string;
  password?: string;
  encryption?: SmtpEncryption;
  from_email: string;
  from_name?: string;
  is_active?: boolean;
  is_default?: boolean;
  hourly_limit?: number;
  daily_limit?: number;
}): Promise<{ server: SmtpServer }> {
  return apiV1Request("/smtp/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSmtpServer(
  id: string,
  data: Partial<{
    name: string;
    host: string;
    port: number;
    username: string;
    password: string;
    encryption: SmtpEncryption;
    from_email: string;
    from_name: string;
    is_active: boolean;
    is_default: boolean;
    hourly_limit: number;
    daily_limit: number;
  }>,
): Promise<{ server: SmtpServer }> {
  return apiV1Request(`/smtp/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteSmtpServer(id: string): Promise<void> {
  await apiV1Request(`/smtp/${id}/`, { method: "DELETE" });
}

export async function setDefaultSmtpServer(id: string): Promise<{ server: SmtpServer }> {
  return apiV1Request(`/smtp/${id}/default/`, { method: "POST" });
}

export async function testSmtpServer(id: string): Promise<SmtpTestResult> {
  return apiV1Request(`/smtp/${id}/test/`, { method: "POST" });
}

export async function importSmtpServers(
  file: File,
): Promise<{
  import: {
    created: number;
    updated: number;
    skipped: number;
    errors: string[];
  };
}> {
  const form = new FormData();
  form.append("file", file);
  return apiV1Request("/smtp/import/", { method: "POST", body: form });
}

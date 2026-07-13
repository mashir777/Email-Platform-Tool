import { apiV1Request } from "@/api/client";
import type { CampaignReport, ReportOverview } from "@/types/reports";

export async function fetchReportOverview(): Promise<{ overview: ReportOverview }> {
  return apiV1Request("/reports/overview/");
}

export async function fetchCampaignReports(params?: {
  search?: string;
  status?: string;
}): Promise<{ reports: CampaignReport[] }> {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return apiV1Request(`/reports/campaigns/${qs ? `?${qs}` : ""}`);
}

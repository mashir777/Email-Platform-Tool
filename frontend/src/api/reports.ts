import { apiV1Request } from "@/api/client";
import type {
  CampaignReport,
  DailyReport,
  DailyReportDetail,
  ReportOverview,
} from "@/types/reports";

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

export async function fetchDailyReport(params?: {
  from?: string;
  to?: string;
}): Promise<{ daily: DailyReport }> {
  const query = new URLSearchParams();
  if (params?.from) query.set("from", params.from);
  if (params?.to) query.set("to", params.to);
  const qs = query.toString();
  return apiV1Request(`/reports/daily/${qs ? `?${qs}` : ""}`);
}

export async function fetchDailyReportDetail(
  day: string,
): Promise<{ day: DailyReportDetail }> {
  return apiV1Request(`/reports/daily/${day}/`);
}

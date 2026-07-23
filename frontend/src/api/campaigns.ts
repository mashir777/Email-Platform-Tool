import { apiV1Request, getTrackingBaseUrl } from "@/api/client";
import type { Campaign, CampaignStats, CampaignStatus } from "@/types/campaigns";

export async function fetchCampaignStats(): Promise<{ stats: CampaignStats }> {
  return apiV1Request("/campaigns/stats/");
}

export async function fetchCampaigns(params?: {
  status?: CampaignStatus;
  search?: string;
}): Promise<{ campaigns: Campaign[] }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.search) query.set("search", params.search);
  const qs = query.toString();
  return apiV1Request(`/campaigns/${qs ? `?${qs}` : ""}`);
}

export async function createCampaign(data: {
  name: string;
  subject?: string;
  from_name?: string;
  from_email?: string;
  html_content?: string;
  text_content?: string;
  subscriber_list_id?: string;
  message_version_id?: string | null;
  smtp_server_ids?: string[];
  emails_per_sender?: number | null;
}): Promise<{ campaign: Campaign }> {
  return apiV1Request("/campaigns/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCampaign(
  id: string,
  data: Partial<{
    name: string;
    subject: string;
    from_name: string;
    from_email: string;
    html_content: string;
    text_content: string;
    subscriber_list_id: string | null;
    message_version_id: string | null;
    smtp_server_ids: string[];
    emails_per_sender: number | null;
  }>,
): Promise<{ campaign: Campaign }> {
  return apiV1Request(`/campaigns/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteCampaign(id: string): Promise<void> {
  await apiV1Request(`/campaigns/${id}/`, { method: "DELETE" });
}

export async function scheduleCampaign(
  id: string,
  scheduledAt: string,
): Promise<{ campaign: Campaign }> {
  return apiV1Request(`/campaigns/${id}/schedule/`, {
    method: "POST",
    body: JSON.stringify({ scheduled_at: scheduledAt }),
  });
}

export async function cancelCampaign(id: string): Promise<{ campaign: Campaign }> {
  return apiV1Request(`/campaigns/${id}/cancel/`, { method: "POST" });
}

export async function pauseCampaign(id: string): Promise<{ campaign: Campaign }> {
  return apiV1Request(`/campaigns/${id}/pause/`, { method: "POST" });
}

export async function sendCampaign(
  id: string,
  options?: { resume_delay_seconds?: number },
): Promise<{
  campaign: Campaign;
  send_summary?: {
    sent: number;
    failed: number;
    pending?: number;
    send_interval_seconds?: number;
    next_send_in_seconds?: number;
    active_smtp_servers?: number;
    is_rate_limited?: boolean;
    errors?: { email: string; error: string }[];
  };
}> {
  const trackingBase = getTrackingBaseUrl();
  const headers: Record<string, string> = {};
  if (trackingBase && !/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(trackingBase)) {
    headers["X-Tracking-Base-Url"] = trackingBase;
  }
  const body =
    options?.resume_delay_seconds != null
      ? JSON.stringify({ resume_delay_seconds: options.resume_delay_seconds })
      : undefined;
  return apiV1Request(`/campaigns/${id}/send/`, {
    method: "POST",
    headers,
    body,
  });
}

export async function duplicateCampaign(id: string): Promise<{ campaign: Campaign }> {
  return apiV1Request(`/campaigns/${id}/duplicate/`, { method: "POST" });
}

export async function sendCampaignTestEmail(
  id: string,
  toEmail: string,
): Promise<{ to_email: string; from_email: string }> {
  return apiV1Request(`/campaigns/${id}/test-send/`, {
    method: "POST",
    body: JSON.stringify({ to_email: toEmail }),
  });
}

export interface CampaignRecipientTracking {
  email: string;
  queue_status: string;
  delivered: boolean;
  opened: boolean;
  opened_at: string | null;
  folder: string;
  folder_label: string;
  sent_at: string | null;
  confirm_url: string | null;
}

export interface CampaignDeliveryTracking {
  campaign_id: string;
  campaign_name: string;
  total_recipients: number;
  delivered: number;
  opened: number;
  not_opened: number;
  open_rate: number;
  note: string;
  recipients: CampaignRecipientTracking[];
}

export async function fetchCampaignDeliveryStatus(
  id: string,
): Promise<{
  tracking: CampaignDeliveryTracking;
  send_summary?: {
    sent: number;
    failed: number;
    pending?: number;
    send_interval_seconds?: number;
    next_send_in_seconds?: number;
    active_smtp_servers?: number;
    is_rate_limited?: boolean;
  };
}> {
  return apiV1Request(`/campaigns/${id}/delivery-status/`);
}

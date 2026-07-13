export type CampaignStatus =
  | "draft"
  | "scheduled"
  | "sending"
  | "sent"
  | "paused"
  | "cancelled";

export interface Campaign {
  id: string;
  name: string;
  subject: string;
  from_name: string;
  from_email: string;
  html_content: string;
  text_content: string;
  status: CampaignStatus;
  subscriber_list: {
    id: string;
    name: string;
    subscriber_count?: number;
  } | null;
  scheduled_at: string | null;
  sent_at: string | null;
  recipient_count: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignStats {
  total: number;
  draft: number;
  scheduled: number;
  sent: number;
  cancelled: number;
}

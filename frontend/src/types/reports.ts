export interface ReportOverview {
  sent: number;
  delivered: number;
  opened: number;
  clicked: number;
  bounced: number;
  complaints: number;
  unsubscribed: number;
  campaigns_tracked: number;
  open_rate: number;
  click_rate: number;
  bounce_rate: number;
}

export interface CampaignReport {
  campaign_id: string;
  campaign_name: string;
  subject: string;
  status: string;
  recipient_count: number;
  sent_at: string | null;
  sent: number;
  delivered: number;
  opened: number;
  clicked: number;
  bounced: number;
  complaints: number;
  unsubscribed: number;
  open_rate: number;
  click_rate: number;
  bounce_rate: number;
}

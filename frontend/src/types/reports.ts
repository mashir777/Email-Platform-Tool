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

export interface DailyReportDay {
  date: string;
  sent: number;
  opened: number;
  waiting: number;
  open_rate: number;
}

export interface DailyReport {
  date_from: string;
  date_to: string;
  days: DailyReportDay[];
}

export interface DailyReportEmail {
  queue_item_id: string;
  email: string;
  campaign_id: string;
  campaign_name: string;
  sent_at: string;
  opened: boolean;
  status: "opened" | "waiting" | string;
}

export interface DailyReportDetail {
  date: string;
  sent: number;
  opened: number;
  waiting: number;
  open_rate: number;
  emails: DailyReportEmail[];
}

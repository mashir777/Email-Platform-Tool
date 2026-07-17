export type SubscriberStatus = "subscribed" | "unsubscribed" | "bounced" | "complained";
export type EmailSendStatus = "sent" | "waiting";

export interface SubscriberList {
  id: string;
  name: string;
  description: string;
  source_filename?: string;
  is_active: boolean;
  is_verified?: boolean;
  subscriber_count: number;
  deliverable_count?: number;
  total_emails?: number;
  sent_emails?: number;
  waiting_emails?: number;
  created_at: string;
  updated_at: string;
}

export interface Subscriber {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  company?: string;
  industrial_company?: string;
  phone: string;
  status: SubscriberStatus;
  send_status?: EmailSendStatus;
  lists: SubscriberList[];
  subscribed_at: string;
  unsubscribed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubscriberStats {
  total: number;
  subscribed: number;
  unsubscribed: number;
  bounced: number;
  complained: number;
  lists: number;
}

export interface ImportResult {
  created: number;
  updated: number;
  skipped: number;
  rejected?: number;
  lists_created?: number;
  source_filename?: string;
  lists_touched?: number;
  list_id?: string | null;
  list_name?: string | null;
}

export interface ListVerifyResult {
  list_id: string;
  list_name: string;
  total: number;
  kept: number;
  removed: number;
  removed_breakdown: Record<string, number>;
  is_verified?: boolean;
}

export interface CsvFilterResult {
  import: ImportResult;
  verify: ListVerifyResult;
  list_id: string;
  list_name: string;
  is_verified: boolean;
}

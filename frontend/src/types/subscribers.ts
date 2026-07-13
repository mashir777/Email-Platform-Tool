export type SubscriberStatus = "subscribed" | "unsubscribed" | "bounced" | "complained";

export interface SubscriberList {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
  subscriber_count: number;
  deliverable_count?: number;
  created_at: string;
  updated_at: string;
}

export interface Subscriber {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone: string;
  status: SubscriberStatus;
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
}

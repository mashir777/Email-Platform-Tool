export type SmtpEncryption = "none" | "tls" | "ssl";

export interface SmtpServer {
  id: string;
  name: string;
  host: string;
  port: number;
  username: string;
  encryption: SmtpEncryption;
  from_email: string;
  from_name: string;
  reply_to_email: string;
  is_active: boolean;
  is_default: boolean;
  verify_ssl: boolean;
  save_copy_to_sent: boolean;
  imap_host: string;
  imap_port: number;
  hourly_limit: number;
  daily_limit: number;
  warmup_enabled: boolean;
  warmup_start_daily: number;
  warmup_target_daily: number;
  warmup_increase_daily: number;
  warmup_current_daily: number;
  warmup_started_at: string | null;
  last_tested_at: string | null;
  last_test_success: boolean | null;
  last_test_message: string;
  created_at: string;
  updated_at: string;
}

export interface SmtpStats {
  total: number;
  active: number;
  inactive: number;
  default_configured: boolean;
}

export interface SmtpTestResult {
  success: boolean;
  message: string;
  server: SmtpServer;
}

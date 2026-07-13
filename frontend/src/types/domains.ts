export type DomainStatus = "pending" | "verified" | "failed";

export interface DnsRecord {
  type: string;
  purpose: string;
  host: string;
  host_label?: string;
  value: string;
  verified: boolean;
  required?: boolean;
  note?: string;
}

export interface SendingDomain {
  id: string;
  domain: string;
  is_active: boolean;
  is_default: boolean;
  status: DomainStatus;
  dkim_selector: string;
  spf_verified: boolean;
  dkim_verified: boolean;
  dmarc_verified: boolean;
  dns_records: DnsRecord[];
  last_verified_at: string | null;
  last_verification_message: string;
  created_at: string;
  updated_at: string;
}

export interface DomainStats {
  total: number;
  verified: number;
  pending: number;
  failed: number;
  default_configured: boolean;
}

export interface DomainVerifyResult {
  success: boolean;
  message: string;
  domain: SendingDomain;
}

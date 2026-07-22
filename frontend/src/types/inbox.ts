export interface InboxMailbox {
  id: string;
  name: string;
  email: string;
  imap_host: string;
  imap_port: number;
  username: string;
  verify_ssl: boolean;
  is_active: boolean;
  last_synced_at: string | null;
  last_sync_message: string;
  created_at: string;
}

export interface InboxMessage {
  id: string;
  mailbox: string | null;
  smtp_server: string | null;
  mailbox_email: string;
  mailbox_name: string;
  message_id: string;
  from_email: string;
  from_name: string;
  to_email: string;
  subject: string;
  snippet: string;
  body_text: string;
  received_at: string | null;
  is_read: boolean;
  created_at: string;
}

import { apiV1Request } from "@/api/client";
import type { InboxMailbox, InboxMessage } from "@/types/inbox";

export async function fetchInboxMessages(params?: {
  unread?: boolean;
  limit?: number;
}): Promise<{ messages: InboxMessage[]; unread_count: number }> {
  const query = new URLSearchParams();
  if (params?.unread) query.set("unread", "1");
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiV1Request(`/inbox/${qs ? `?${qs}` : ""}`);
}

export async function fetchInboxMailboxes(): Promise<{ mailboxes: InboxMailbox[] }> {
  return apiV1Request("/inbox/mailboxes/");
}

export async function createInboxMailbox(data: {
  name?: string;
  email: string;
  imap_host: string;
  imap_port?: number;
  username?: string;
  password: string;
  verify_ssl?: boolean;
}): Promise<{ mailbox: InboxMailbox; new_messages: number }> {
  return apiV1Request("/inbox/mailboxes/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteInboxMailbox(id: string): Promise<void> {
  await apiV1Request(`/inbox/mailboxes/${id}/`, { method: "DELETE" });
}

export async function syncInbox(): Promise<{ mailboxes: number; new_messages: number }> {
  return apiV1Request("/inbox/sync/", { method: "POST" });
}

export async function markInboxMessageRead(id: string): Promise<{ message: InboxMessage }> {
  return apiV1Request(`/inbox/${id}/read/`, { method: "POST" });
}

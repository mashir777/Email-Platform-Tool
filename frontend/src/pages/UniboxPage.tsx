import { FormEvent, useCallback, useEffect, useState } from "react";

import { ApiClientError } from "@/api/client";
import * as inboxApi from "@/api/inbox";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import type { InboxMailbox, InboxMessage } from "@/types/inbox";

function formatWhen(value: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

const emptyMailboxForm = {
  name: "",
  email: "",
  imap_host: "",
  imap_port: "993",
  username: "",
  password: "",
  verify_ssl: false,
};

export function UniboxPage() {
  const [messages, setMessages] = useState<InboxMessage[]>([]);
  const [mailboxes, setMailboxes] = useState<InboxMailbox[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedMailboxId, setSelectedMailboxId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSavingMailbox, setIsSavingMailbox] = useState(false);
  const [showAddInbox, setShowAddInbox] = useState(false);
  const [mailboxForm, setMailboxForm] = useState(emptyMailboxForm);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [msgData, boxData] = await Promise.all([
        inboxApi.fetchInboxMessages({ limit: 100 }),
        inboxApi.fetchInboxMailboxes(),
      ]);
      setMessages(msgData.messages);
      setUnreadCount(msgData.unread_count);
      setMailboxes(boxData.mailboxes);
      setSelectedId((prev) => prev ?? msgData.messages[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load Unibox");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filteredMessages = selectedMailboxId
    ? messages.filter((m) => m.mailbox === selectedMailboxId)
    : messages;
  const selected =
    filteredMessages.find((m) => m.id === selectedId) ?? filteredMessages[0] ?? null;

  function handleSelectMailbox(id: string) {
    setSelectedMailboxId((prev) => (prev === id ? null : id));
    setSelectedId(null);
  }

  async function handleSync() {
    setIsSyncing(true);
    setError("");
    setNotice("");
    try {
      const result = await inboxApi.syncInbox();
      setNotice(
        `Synced ${result.new_messages} new message(s) from ${result.mailboxes} inbox(es).`,
      );
      await load();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Sync failed");
    } finally {
      setIsSyncing(false);
    }
  }

  async function handleAddInbox(e: FormEvent) {
    e.preventDefault();
    setIsSavingMailbox(true);
    setError("");
    setNotice("");
    try {
      const result = await inboxApi.createInboxMailbox({
        name: mailboxForm.name.trim(),
        email: mailboxForm.email.trim(),
        imap_host: mailboxForm.imap_host.trim(),
        imap_port: Number(mailboxForm.imap_port) || 993,
        username: mailboxForm.username.trim() || mailboxForm.email.trim(),
        password: mailboxForm.password,
        verify_ssl: mailboxForm.verify_ssl,
      });
      setNotice(
        `Inbox ${result.mailbox.email} added. ${result.new_messages} reply(ies) pulled.`,
      );
      setMailboxForm(emptyMailboxForm);
      setShowAddInbox(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Could not add inbox");
    } finally {
      setIsSavingMailbox(false);
    }
  }

  async function handleDeleteMailbox(id: string) {
    setError("");
    try {
      await inboxApi.deleteInboxMailbox(id);
      setNotice("Inbox removed.");
      if (selectedMailboxId === id) setSelectedMailboxId(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Could not remove inbox");
    }
  }

  async function handleSelect(msg: InboxMessage) {
    setSelectedId(msg.id);
    if (!msg.is_read) {
      try {
        await inboxApi.markInboxMessageRead(msg.id);
        setMessages((prev) =>
          prev.map((m) => (m.id === msg.id ? { ...m, is_read: true } : m)),
        );
        setUnreadCount((n) => Math.max(0, n - 1));
      } catch {
        // ignore
      }
    }
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {notice && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700">
          {notice}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-400">
          Replies land in this project from inboxes you add here. Unread:{" "}
          <span className="text-slate-800">{unreadCount}</span>
        </p>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="ghost" onClick={() => setShowAddInbox((v) => !v)}>
            {showAddInbox ? "Cancel" : "Add Inbox"}
          </Button>
          <Button type="button" onClick={handleSync} isLoading={isSyncing}>
            Sync inboxes
          </Button>
        </div>
      </div>

      {showAddInbox && (
        <Card
          title="Add Inbox"
          description="Add a mailbox (e.g. leads@datrixworld.com). Its replies will show in Unibox."
        >
          <form onSubmit={handleAddInbox} className="grid gap-3 sm:grid-cols-2">
            <Input
              label="Inbox email"
              type="email"
              required
              placeholder="leads@datrixworld.com"
              value={mailboxForm.email}
              onChange={(e) => setMailboxForm((f) => ({ ...f, email: e.target.value }))}
            />
            <Input
              label="Display name (optional)"
              value={mailboxForm.name}
              onChange={(e) => setMailboxForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Leads / Shared replies"
            />
            <Input
              label="IMAP host"
              required
              placeholder="mail.datrixworld.com"
              value={mailboxForm.imap_host}
              onChange={(e) => setMailboxForm((f) => ({ ...f, imap_host: e.target.value }))}
            />
            <Input
              label="IMAP port"
              type="number"
              value={mailboxForm.imap_port}
              onChange={(e) => setMailboxForm((f) => ({ ...f, imap_port: e.target.value }))}
            />
            <Input
              label="Username"
              value={mailboxForm.username}
              onChange={(e) => setMailboxForm((f) => ({ ...f, username: e.target.value }))}
              placeholder="Same as email if empty"
            />
            <Input
              label="Password"
              type="password"
              required
              value={mailboxForm.password}
              onChange={(e) => setMailboxForm((f) => ({ ...f, password: e.target.value }))}
            />
            <label className="flex items-center gap-2 text-sm text-slate-700 sm:col-span-2">
              <input
                type="checkbox"
                checked={mailboxForm.verify_ssl}
                onChange={(e) =>
                  setMailboxForm((f) => ({ ...f, verify_ssl: e.target.checked }))
                }
                className="rounded border-slate-600 bg-slate-50"
              />
              Verify SSL (off for many shared hosts)
            </label>
            <div className="sm:col-span-2">
              <Button type="submit" isLoading={isSavingMailbox}>
                Save inbox
              </Button>
            </div>
          </form>
        </Card>
      )}

      {mailboxes.length > 0 && (
        <Card
          title="Connected inboxes"
          description="Click an inbox to view only its replies (click again for all)"
        >
          <ul className="space-y-2">
            {mailboxes.map((box) => {
              const isSelected = selectedMailboxId === box.id;
              return (
                <li key={box.id}>
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => handleSelectMailbox(box.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleSelectMailbox(box.id);
                      }
                    }}
                    className={`flex cursor-pointer flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm transition ${
                      isSelected
                        ? "border-indigo-500/50 bg-indigo-50 ring-1 ring-indigo-300"
                        : "border-slate-200 hover:border-slate-300 hover:bg-white"
                    }`}
                  >
                    <div>
                      <p className={isSelected ? "text-indigo-800" : "text-slate-800"}>
                        {box.name || box.email}
                      </p>
                      <p className="text-xs text-slate-500">
                        {box.email} · {box.imap_host}:{box.imap_port}
                        {box.last_sync_message ? ` · ${box.last_sync_message}` : ""}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteMailbox(box.id);
                      }}
                    >
                      Remove
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Card
          title="Inbox"
          description={
            selectedMailboxId
              ? `Showing ${mailboxes.find((b) => b.id === selectedMailboxId)?.email || "selected inbox"}`
              : "Add an inbox above, then Sync"
          }
        >
          {isLoading ? (
            <div className="flex justify-center py-10">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
            </div>
          ) : filteredMessages.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-500">
              {mailboxes.length === 0
                ? "No inbox yet. Click Add Inbox (e.g. leads@…), then Sync."
                : selectedMailboxId
                  ? "No replies in this inbox yet. Click Sync inboxes."
                  : "No replies yet. Click Sync inboxes."}
            </p>
          ) : (
            <ul className="max-h-[70vh] space-y-1 overflow-y-auto">
              {filteredMessages.map((msg) => (
                <li key={msg.id}>
                  <button
                    type="button"
                    onClick={() => handleSelect(msg)}
                    className={`w-full rounded-lg px-3 py-2.5 text-left transition ${
                      selected?.id === msg.id
                        ? "bg-indigo-50 ring-1 ring-indigo-300"
                        : "hover:bg-slate-100"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p
                        className={`truncate text-sm ${
                          msg.is_read ? "text-slate-700" : "font-semibold text-slate-900"
                        }`}
                      >
                        {msg.from_name || msg.from_email || "Unknown"}
                      </p>
                      {!msg.is_read && (
                        <span className="h-2 w-2 shrink-0 rounded-full bg-indigo-400" />
                      )}
                    </div>
                    <p className="truncate text-xs text-slate-400">
                      {msg.subject || "(no subject)"}
                    </p>
                    <p className="truncate text-[11px] text-slate-500">
                      {msg.mailbox_name || msg.mailbox_email} · {formatWhen(msg.received_at)}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Message" description={selected?.mailbox_email || "Select a message"}>
          {!selected ? (
            <p className="py-12 text-center text-sm text-slate-500">Select a message on the left.</p>
          ) : (
            <div className="space-y-3">
              <div>
                <p className="text-lg font-medium text-slate-900">
                  {selected.subject || "(no subject)"}
                </p>
                <p className="mt-1 text-sm text-slate-400">
                  From {selected.from_name ? `${selected.from_name} ` : ""}
                  &lt;{selected.from_email}&gt;
                </p>
                <p className="text-xs text-slate-500">{formatWhen(selected.received_at)}</p>
              </div>
              <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white/60 p-4 text-sm text-slate-800">
                {selected.body_text || selected.snippet || "(empty)"}
              </pre>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

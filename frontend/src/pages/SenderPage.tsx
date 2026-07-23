import { FormEvent, useCallback, useEffect, useState } from "react";

import { ApiClientError } from "@/api/client";
import * as smtpApi from "@/api/smtp";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import type { SmtpEncryption, SmtpServer } from "@/types/smtp";

const encryptionOptions: { value: SmtpEncryption; label: string }[] = [
  { value: "tls", label: "TLS (STARTTLS)" },
  { value: "ssl", label: "SSL" },
  { value: "none", label: "None" },
];

const emptyForm = {
  name: "",
  host: "",
  port: "587",
  username: "",
  password: "",
  encryption: "tls" as SmtpEncryption,
  from_email: "",
  from_name: "",
  reply_to_email: "",
  is_active: true,
  is_default: false,
  hourly_limit: "100",
  daily_limit: "1000",
  verify_ssl: false,
  save_copy_to_sent: true,
  imap_host: "",
  imap_port: "993",
};

function formatSendInterval(hourlyLimit: number): string {
  const intervalSeconds = Math.max(60, Math.floor(3600 / Math.max(hourlyLimit, 1)));
  const minutes = Math.max(1, Math.round(intervalSeconds / 60));
  return `~1 email every ${minutes} minute(s)`;
}

export function SenderPage() {
  const [servers, setServers] = useState<SmtpServer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await smtpApi.fetchSmtpServers();
      setServers(data.servers);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load senders");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function openAdd() {
    setEditingId(null);
    setForm(emptyForm);
    setShowAdd(true);
    setError("");
    setNotice("");
  }

  function openEdit(server: SmtpServer) {
    setEditingId(server.id);
    setForm({
      name: server.name,
      host: server.host,
      port: String(server.port),
      username: server.username,
      password: "",
      encryption: server.encryption,
      from_email: server.from_email,
      from_name: server.from_name,
      reply_to_email: server.reply_to_email ?? "",
      is_active: server.is_active,
      is_default: server.is_default,
      hourly_limit: String(server.hourly_limit),
      daily_limit: String(server.daily_limit),
      verify_ssl: server.verify_ssl,
      save_copy_to_sent: server.save_copy_to_sent ?? true,
      imap_host: server.imap_host ?? "",
      imap_port: String(server.imap_port ?? 993),
    });
    setShowAdd(true);
    setError("");
    setNotice("");
  }

  function closeForm() {
    setShowAdd(false);
    setEditingId(null);
    setForm(emptyForm);
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setIsSaving(true);
    setError("");
    setNotice("");
    try {
      const payload = {
        name: form.name.trim(),
        host: form.host.trim(),
        port: Number(form.port) || 587,
        username: form.username.trim(),
        encryption: form.encryption,
        from_email: form.from_email.trim(),
        from_name: form.from_name.trim(),
        reply_to_email: form.reply_to_email.trim(),
        is_active: form.is_active,
        is_default: form.is_default,
        hourly_limit: Number(form.hourly_limit) || 100,
        daily_limit: Number(form.daily_limit) || 1000,
        verify_ssl: form.verify_ssl,
        save_copy_to_sent: form.save_copy_to_sent,
        imap_host: form.imap_host.trim(),
        imap_port: Number(form.imap_port) || 993,
        ...(form.password ? { password: form.password } : {}),
      };
      if (editingId) {
        await smtpApi.updateSmtpServer(editingId, payload);
        setNotice(`Sender ${form.from_email} updated.`);
      } else {
        if (!form.password) {
          setError("Password is required for a new sender.");
          return;
        }
        await smtpApi.createSmtpServer({ ...payload, password: form.password });
        setNotice(`Sender ${form.from_email} added.`);
      }
      closeForm();
      await load();
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : editingId
            ? "Could not update sender"
            : "Could not add sender",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(id: string, email: string) {
    if (!window.confirm(`Delete sender ${email}?`)) return;
    setError("");
    setNotice("");
    try {
      await smtpApi.deleteSmtpServer(id);
      setNotice(`Sender ${email} deleted.`);
      if (editingId === id) closeForm();
      await load();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Could not delete sender");
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
        <p className="text-sm text-slate-500">
          Same SMTP fields as SMTP page — add From addresses for campaigns.
        </p>
        <Button
          type="button"
          variant="ghost"
          onClick={() => (showAdd ? closeForm() : openAdd())}
        >
          {showAdd ? "Cancel" : "+ Add Sender"}
        </Button>
      </div>

      {showAdd && (
        <Card
          title={editingId ? "Edit Sender" : "Add Sender"}
          description="Same fields as SMTP (without warmup)"
        >
          <form onSubmit={handleSave} className="grid gap-3 sm:grid-cols-2">
            <Input
              label="Server name"
              required
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
            <Input
              label="Host"
              required
              value={form.host}
              onChange={(e) => setForm((f) => ({ ...f, host: e.target.value }))}
              placeholder="smtp.example.com"
            />
            <Input
              label="Port"
              type="number"
              required
              value={form.port}
              onChange={(e) => setForm((f) => ({ ...f, port: e.target.value }))}
            />
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">
                Encryption
              </label>
              <select
                value={form.encryption}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    encryption: e.target.value as SmtpEncryption,
                  }))
                }
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900"
              >
                {encryptionOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <Input
              label="Username"
              value={form.username}
              onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
            />
            <Input
              label={editingId ? "Password (leave blank to keep)" : "Password"}
              type="password"
              required={!editingId}
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            />
            <Input
              label="From email (your domain mailbox)"
              type="email"
              required
              value={form.from_email}
              onChange={(e) => setForm((f) => ({ ...f, from_email: e.target.value }))}
              placeholder="info@datrixworld.com"
            />
            <p className="sm:col-span-2 -mt-1 text-xs text-slate-500">
              This is the sender address recipients see. Must be @yourdomain.com — not Gmail.
            </p>
            <Input
              label="From name"
              value={form.from_name}
              onChange={(e) => setForm((f) => ({ ...f, from_name: e.target.value }))}
            />
            <Input
              label="Reply-To (optional override)"
              type="email"
              value={form.reply_to_email}
              onChange={(e) => setForm((f) => ({ ...f, reply_to_email: e.target.value }))}
              placeholder="Leave blank to use Settings → Shared Reply-To"
            />
            <p className="sm:col-span-2 -mt-1 text-xs text-slate-500">
              Replies go here for this sender only. Prefer Settings → Shared Reply-To
              so all senders share one inbox.
            </p>
            <Input
              label="Hourly limit"
              type="number"
              required
              value={form.hourly_limit}
              onChange={(e) => setForm((f) => ({ ...f, hourly_limit: e.target.value }))}
            />
            <p className="text-xs text-slate-500 sm:col-span-2">
              At {form.hourly_limit || "60"}/hour ={" "}
              {formatSendInterval(Number(form.hourly_limit) || 60)} between sends
            </p>
            <Input
              label="Daily limit"
              type="number"
              required
              value={form.daily_limit}
              onChange={(e) => setForm((f) => ({ ...f, daily_limit: e.target.value }))}
            />
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.verify_ssl}
                onChange={(e) => setForm((f) => ({ ...f, verify_ssl: e.target.checked }))}
                className="rounded border-slate-600 bg-slate-50"
              />
              Verify SSL certificate (disable for shared hosting mail servers)
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700 sm:col-span-2">
              <input
                type="checkbox"
                checked={form.save_copy_to_sent}
                onChange={(e) =>
                  setForm((f) => ({ ...f, save_copy_to_sent: e.target.checked }))
                }
                className="rounded border-slate-600 bg-slate-50"
              />
              Save copy to Namecheap Sent folder (via IMAP after each send)
            </label>
            {form.save_copy_to_sent && (
              <>
                <Input
                  label="IMAP host (optional)"
                  value={form.imap_host}
                  onChange={(e) => setForm((f) => ({ ...f, imap_host: e.target.value }))}
                  placeholder="Same as SMTP host if empty (e.g. mail.datrixworld.com)"
                />
                <Input
                  label="IMAP port"
                  type="number"
                  value={form.imap_port}
                  onChange={(e) => setForm((f) => ({ ...f, imap_port: e.target.value }))}
                />
              </>
            )}
            <label className="flex items-center gap-2 text-sm text-slate-700 sm:col-span-2">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                className="rounded border-slate-600 bg-slate-50"
              />
              Active
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700 sm:col-span-2">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(e) => setForm((f) => ({ ...f, is_default: e.target.checked }))}
                className="rounded border-slate-600 bg-slate-50"
              />
              Set as default
            </label>
            <div className="sm:col-span-2">
              <Button type="submit" isLoading={isSaving}>
                {editingId ? "Update sender" : "Save sender"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card title="Senders" description="Mailboxes used as From when sending">
        {isLoading ? (
          <div className="flex justify-center py-10">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
          </div>
        ) : servers.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">
            No senders yet. Click Add Sender.
          </p>
        ) : (
          <ul className="space-y-2">
            {servers.map((server) => (
              <li
                key={server.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2.5 text-sm"
              >
                <div>
                  <p className="font-medium text-slate-900">
                    {server.from_name ? `${server.from_name} ` : ""}
                    <span className="font-mono text-slate-800">&lt;{server.from_email}&gt;</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {server.name} · {server.host}:{server.port}
                    {server.is_active ? " · Active" : " · Inactive"}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  <Button type="button" variant="ghost" onClick={() => openEdit(server)}>
                    Edit
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => handleDelete(server.id, server.from_email)}
                  >
                    Delete
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

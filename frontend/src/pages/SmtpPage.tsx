import { FormEvent, useCallback, useEffect, useState } from "react";

import * as smtpApi from "@/api/smtp";
import { ApiClientError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import type { SmtpEncryption, SmtpServer, SmtpStats } from "@/types/smtp";

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
  is_active: true,
  is_default: false,
  hourly_limit: "100",
  daily_limit: "1000",
  verify_ssl: false,
  save_copy_to_sent: true,
  imap_host: "",
  imap_port: "993",
};

function formatTestStatus(server: SmtpServer): string {
  if (!server.last_tested_at) return "Not tested";
  return server.last_test_success ? "Passed" : "Failed";
}

function formatSendInterval(hourlyLimit: number): string {
  const intervalSeconds = Math.max(60, Math.floor(3600 / Math.max(hourlyLimit, 1)));
  const minutes = Math.max(1, Math.round(intervalSeconds / 60));
  return `~1 email every ${minutes} minute(s)`;
}

export function SmtpPage() {
  const [stats, setStats] = useState<SmtpStats | null>(null);
  const [servers, setServers] = useState<SmtpServer[]>([]);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [selectedServerIds, setSelectedServerIds] = useState<string[]>([]);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [statsRes, serversRes] = await Promise.all([
        smtpApi.fetchSmtpStats(),
        smtpApi.fetchSmtpServers({ search: search || undefined }),
      ]);
      setStats(statsRes.stats);
      setServers(serversRes.servers);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load SMTP servers");
    } finally {
      setIsLoading(false);
    }
  }, [search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  function openCreate() {
    setEditingId(null);
    setForm(emptyForm);
    setShowForm(true);
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
      is_active: server.is_active,
      is_default: server.is_default,
      hourly_limit: String(server.hourly_limit),
      daily_limit: String(server.daily_limit),
      verify_ssl: server.verify_ssl,
      save_copy_to_sent: server.save_copy_to_sent ?? true,
      imap_host: server.imap_host ?? "",
      imap_port: String(server.imap_port ?? 993),
    });
    setShowForm(true);
    setNotice("");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const payload = {
        name: form.name,
        host: form.host,
        port: Number(form.port),
        username: form.username,
        encryption: form.encryption,
        from_email: form.from_email,
        from_name: form.from_name,
        is_active: form.is_active,
        is_default: form.is_default,
        hourly_limit: Number(form.hourly_limit),
        daily_limit: Number(form.daily_limit),
        verify_ssl: form.verify_ssl,
        save_copy_to_sent: form.save_copy_to_sent,
        imap_host: form.imap_host.trim(),
        imap_port: Number(form.imap_port) || 993,
        ...(form.password ? { password: form.password } : {}),
      };

      if (editingId) {
        await smtpApi.updateSmtpServer(editingId, payload);
        setNotice("SMTP server updated.");
      } else {
        await smtpApi.createSmtpServer(payload);
        setNotice("SMTP server created.");
      }
      setShowForm(false);
      setForm(emptyForm);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Save failed");
    }
  }

  async function handleImport(file: File) {
    setIsImporting(true);
    setError("");
    setNotice("");
    try {
      const result = await smtpApi.importSmtpServers(file);
      const { created, updated, skipped, errors } = result.import;
      setNotice(
        `SMTP import: ${created} created, ${updated} updated, ${skipped} skipped.`,
      );
      if (errors.length > 0) {
        setError(errors.slice(0, 3).join(" "));
      }
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "CSV import failed");
    } finally {
      setIsImporting(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this SMTP server?")) return;
    try {
      await smtpApi.deleteSmtpServer(id);
      setNotice("SMTP server deleted.");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Delete failed");
    }
  }

  async function handleDeleteSelected() {
    if (
      !selectedServerIds.length ||
      !confirm(`Delete ${selectedServerIds.length} selected SMTP server(s)?`)
    ) return;
    try {
      await Promise.all(selectedServerIds.map((id) => smtpApi.deleteSmtpServer(id)));
      setSelectedServerIds([]);
      setNotice("Selected SMTP servers deleted.");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to delete selected servers");
      await loadData();
    }
  }

  async function handleSetDefault(id: string) {
    try {
      await smtpApi.setDefaultSmtpServer(id);
      setNotice("Default SMTP server updated.");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Could not set default");
    }
  }

  async function handleTest(id: string) {
    setTestingId(id);
    setError("");
    setNotice("");
    try {
      const result = await smtpApi.testSmtpServer(id);
      setNotice(result.message);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Connection test failed");
    } finally {
      setTestingId(null);
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}
      {notice && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          {notice}
        </div>
      )}

      {servers.length > 0 && (
        <Card title="Sending Email (From Address)">
          {(() => {
            const defaultServer =
              servers.find((s) => s.is_default && s.is_active) ??
              servers.find((s) => s.is_active);
            if (!defaultServer) {
              return (
                <p className="text-sm text-amber-300">No active SMTP server. Add one below.</p>
              );
            }
            return (
              <div className="space-y-2 text-sm">
                <p className="text-slate-300">
                  Campaigns send <strong>from</strong> this domain mailbox:
                </p>
                <p className="font-mono text-lg text-emerald-400">{defaultServer.from_email}</p>
                <p className="text-xs text-slate-500">
                  Recipients can be Gmail (@gmail.com). Do not use Gmail as From email.
                  {defaultServer.save_copy_to_sent && (
                    <span className="mt-1 block text-indigo-300">
                      Sent copies are saved to your Namecheap mailbox Sent folder via IMAP.
                    </span>
                  )}
                  {defaultServer.hourly_limit < 30 && (
                    <span className="mt-1 block text-amber-400">
                      Hourly limit is {defaultServer.hourly_limit} — increase to 60+ for faster
                      sending.
                    </span>
                  )}
                </p>
                <Button type="button" variant="ghost" onClick={() => openEdit(defaultServer)}>
                  Edit sending email
                </Button>
              </div>
            );
          })()}
        </Card>
      )}

      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Card>
            <p className="text-sm text-slate-400">Total Servers</p>
            <p className="mt-2 text-3xl font-bold text-white">{stats.total}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Active</p>
            <p className="mt-2 text-3xl font-bold text-emerald-400">{stats.active}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Inactive</p>
            <p className="mt-2 text-3xl font-bold text-slate-400">{stats.inactive}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Default Set</p>
            <p className="mt-2 text-3xl font-bold text-indigo-400">
              {stats.default_configured ? "Yes" : "No"}
            </p>
          </Card>
        </div>
      )}

      <Card title="SMTP Providers">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <input
            type="search"
            placeholder="Search servers..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
          />
          <Button onClick={openCreate}>+ Add Server</Button>
          {selectedServerIds.length > 0 && (
            <Button variant="danger" onClick={() => void handleDeleteSelected()}>
              Delete Selected ({selectedServerIds.length})
            </Button>
          )}
          <label className="cursor-pointer">
            <span className="inline-flex items-center justify-center rounded-lg border border-slate-600 bg-slate-800 px-4 py-2.5 text-sm font-medium text-slate-100 hover:bg-slate-700">
              {isImporting ? "Importing..." : "Import CSV (20 mailboxes)"}
            </span>
            <input
              type="file"
              accept=".csv"
              className="hidden"
              disabled={isImporting}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleImport(file);
                e.target.value = "";
              }}
            />
          </label>
        </div>

        <div className="mb-4 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-200">
          <p className="font-medium">Multi-domain setup (5 domains × 4 mailboxes = 20 sends)</p>
          <p className="mt-1 text-xs text-indigo-300/90">
            Import CSV with columns: name, host, port, username, password, from_email.
            Set hourly_limit=60 for 1 email/minute per mailbox. Recipients can be Gmail
            addresses — but From must be your domain email, not @gmail.com.
            Template: docs/smtp_mailboxes_template.csv
          </p>
        </div>

        {showForm && (
          <form
            onSubmit={handleSubmit}
            className="mb-6 rounded-lg border border-slate-700 bg-slate-900/50 p-4"
          >
            <h3 className="mb-4 text-sm font-semibold text-white">
              {editingId ? "Edit SMTP Server" : "New SMTP Server"}
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
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
                <label className="mb-1.5 block text-sm font-medium text-slate-300">
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
                  className="w-full rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100"
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
                Gmail addresses go in Emails / Campaign recipient list.
              </p>
              <Input
                label="From name"
                value={form.from_name}
                onChange={(e) => setForm((f) => ({ ...f, from_name: e.target.value }))}
              />
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
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="checkbox"
                  checked={form.verify_ssl}
                  onChange={(e) => setForm((f) => ({ ...f, verify_ssl: e.target.checked }))}
                  className="rounded border-slate-600 bg-slate-900"
                />
                Verify SSL certificate (disable for shared hosting mail servers)
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-300 sm:col-span-2">
                <input
                  type="checkbox"
                  checked={form.save_copy_to_sent}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, save_copy_to_sent: e.target.checked }))
                  }
                  className="rounded border-slate-600 bg-slate-900"
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
              <label className="flex items-center gap-2 text-sm text-slate-300 sm:col-span-2">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                  className="rounded border-slate-600 bg-slate-900"
                />
                Active
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-300 sm:col-span-2">
                <input
                  type="checkbox"
                  checked={form.is_default}
                  onChange={(e) => setForm((f) => ({ ...f, is_default: e.target.checked }))}
                  className="rounded border-slate-600 bg-slate-900"
                />
                Set as default
              </label>
            </div>
            <div className="mt-4 flex gap-2">
              <Button type="submit">{editingId ? "Update" : "Create"}</Button>
              <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </form>
        )}

        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
          </div>
        ) : servers.length === 0 ? (
          <p className="py-12 text-center text-sm text-slate-500">
            No SMTP servers configured. Add your first delivery server.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500">
                  <th className="pb-3 pr-3">
                    <input
                      type="checkbox"
                      aria-label="Select all SMTP servers"
                      checked={servers.length > 0 && selectedServerIds.length === servers.length}
                      onChange={(event) =>
                        setSelectedServerIds(
                          event.target.checked ? servers.map((server) => server.id) : [],
                        )
                      }
                    />
                  </th>
                  <th className="pb-3 pr-4 font-medium">Name</th>
                  <th className="pb-3 pr-4 font-medium">Host</th>
                  <th className="pb-3 pr-4 font-medium">From</th>
                  <th className="pb-3 pr-4 font-medium">Limits</th>
                  <th className="pb-3 pr-4 font-medium">Status</th>
                  <th className="pb-3 pr-4 font-medium">Last Test</th>
                  <th className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {servers.map((server) => (
                  <tr key={server.id} className="border-b border-slate-800/60">
                    <td className="py-3 pr-3">
                      <input
                        type="checkbox"
                        aria-label={`Select ${server.name}`}
                        checked={selectedServerIds.includes(server.id)}
                        onChange={(event) =>
                          setSelectedServerIds((current) =>
                            event.target.checked
                              ? [...current, server.id]
                              : current.filter((id) => id !== server.id),
                          )
                        }
                      />
                    </td>
                    <td className="py-3 pr-4">
                      <div className="font-medium text-slate-200">{server.name}</div>
                      {server.is_default && (
                        <span className="mt-1 inline-block rounded-full bg-indigo-500/10 px-2 py-0.5 text-xs text-indigo-400">
                          Default
                        </span>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-slate-400">
                      {server.host}:{server.port}
                      <div className="text-xs uppercase text-slate-500">{server.encryption}</div>
                    </td>
                    <td className="py-3 pr-4 text-slate-400">
                      {server.from_name ? `${server.from_name} ` : ""}
                      &lt;{server.from_email}&gt;
                    </td>
                    <td className="py-3 pr-4 text-slate-500">
                      {server.hourly_limit}/hr · {server.daily_limit}/day
                    </td>
                    <td className="py-3 pr-4">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          server.is_active
                            ? "bg-emerald-500/10 text-emerald-400"
                            : "bg-slate-500/10 text-slate-400"
                        }`}
                      >
                        {server.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <div
                        className={
                          server.last_test_success === true
                            ? "text-emerald-400"
                            : server.last_test_success === false
                              ? "text-red-400"
                              : "text-slate-500"
                        }
                      >
                        {formatTestStatus(server)}
                      </div>
                      {server.last_test_message && (
                        <div className="max-w-[180px] truncate text-xs text-slate-500">
                          {server.last_test_message}
                        </div>
                      )}
                    </td>
                    <td className="py-3">
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => openEdit(server)}
                          className="text-xs text-indigo-400 hover:underline"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleTest(server.id)}
                          disabled={testingId === server.id}
                          className="text-xs text-indigo-400 hover:underline disabled:opacity-50"
                        >
                          {testingId === server.id ? "Testing..." : "Test"}
                        </button>
                        {!server.is_default && server.is_active && (
                          <button
                            type="button"
                            onClick={() => handleSetDefault(server.id)}
                            className="text-xs text-slate-400 hover:underline"
                          >
                            Set default
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleDelete(server.id)}
                          className="text-xs text-red-400 hover:underline"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

import { FormEvent, useCallback, useEffect, useState } from "react";

import { ApiClientError } from "@/api/client";
import * as smtpApi from "@/api/smtp";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import type { SmtpEncryption, SmtpServer } from "@/types/smtp";

const emptyForm = {
  name: "",
  from_email: "",
  host: "",
  port: "587",
  username: "",
  password: "",
  encryption: "tls" as SmtpEncryption,
  warmup_start_daily: "5",
  warmup_target_daily: "40",
  warmup_increase_daily: "5",
  daily_limit: "100",
  hourly_limit: "20",
};

function effectiveCap(server: SmtpServer): number {
  if (!server.warmup_enabled) return server.daily_limit;
  const current = server.warmup_current_daily || server.warmup_start_daily || 5;
  return Math.min(server.daily_limit, current);
}

export function WarmupPage() {
  const [servers, setServers] = useState<SmtpServer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [isSaving, setIsSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await smtpApi.fetchSmtpServers();
      setServers(data.servers);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load mailboxes");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    setIsSaving(true);
    setError("");
    setNotice("");
    try {
      await smtpApi.createSmtpServer({
        name: form.name.trim() || form.from_email.trim(),
        from_email: form.from_email.trim(),
        host: form.host.trim(),
        port: Number(form.port) || 587,
        username: form.username.trim() || form.from_email.trim(),
        password: form.password,
        encryption: form.encryption,
        is_active: true,
        warmup_enabled: true,
        warmup_start_daily: Number(form.warmup_start_daily) || 5,
        warmup_target_daily: Number(form.warmup_target_daily) || 40,
        warmup_increase_daily: Number(form.warmup_increase_daily) || 5,
        daily_limit: Number(form.daily_limit) || 100,
        hourly_limit: Number(form.hourly_limit) || 20,
        save_copy_to_sent: false,
        verify_ssl: false,
      });
      setNotice(`Mailbox ${form.from_email} added with warmup on.`);
      setForm(emptyForm);
      setShowAdd(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Could not add mailbox");
    } finally {
      setIsSaving(false);
    }
  }

  async function toggleWarmup(server: SmtpServer, enabled: boolean) {
    setBusyId(server.id);
    setError("");
    try {
      await smtpApi.updateSmtpServer(server.id, {
        warmup_enabled: enabled,
        ...(enabled
          ? {
              warmup_start_daily: server.warmup_start_daily || 5,
              warmup_target_daily: server.warmup_target_daily || 40,
              warmup_increase_daily: server.warmup_increase_daily || 5,
            }
          : {}),
      });
      setNotice(
        enabled
          ? `Warmup started for ${server.from_email}`
          : `Warmup stopped for ${server.from_email}`,
      );
      await load();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Update failed");
    } finally {
      setBusyId(null);
    }
  }

  async function saveRamp(
    server: SmtpServer,
    values: {
      warmup_start_daily: number;
      warmup_target_daily: number;
      warmup_increase_daily: number;
    },
  ) {
    setBusyId(server.id);
    setError("");
    try {
      await smtpApi.updateSmtpServer(server.id, {
        warmup_enabled: true,
        ...values,
      });
      setNotice(`Warmup settings saved for ${server.from_email}`);
      await load();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Could not save settings");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(server: SmtpServer) {
    if (!window.confirm(`Delete mailbox ${server.from_email}?`)) return;
    setBusyId(server.id);
    setError("");
    setNotice("");
    try {
      await smtpApi.deleteSmtpServer(server.id);
      setNotice(`Mailbox ${server.from_email} deleted.`);
      await load();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Could not delete mailbox");
    } finally {
      setBusyId(null);
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
          Add mailboxes here and turn warmup on — daily send cap ramps up gradually.
        </p>
        <Button type="button" onClick={() => setShowAdd((v) => !v)}>
          {showAdd ? "Cancel" : "Add mailbox"}
        </Button>
      </div>

      {showAdd && (
        <Card title="Add mailbox for warmup" description="SMTP mailbox — warmup starts enabled">
          <form onSubmit={handleAdd} className="grid gap-3 sm:grid-cols-2">
            <Input
              label="From email"
              type="email"
              required
              placeholder="info@datrixworld.com"
              value={form.from_email}
              onChange={(e) => setForm((f) => ({ ...f, from_email: e.target.value }))}
            />
            <Input
              label="Name (optional)"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
            <Input
              label="SMTP host"
              required
              placeholder="mail.datrixworld.com"
              value={form.host}
              onChange={(e) => setForm((f) => ({ ...f, host: e.target.value }))}
            />
            <Input
              label="Port"
              type="number"
              value={form.port}
              onChange={(e) => setForm((f) => ({ ...f, port: e.target.value }))}
            />
            <Input
              label="Username"
              value={form.username}
              onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
              placeholder="Same as email if empty"
            />
            <Input
              label="Password"
              type="password"
              required
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            />
            <Input
              label="Warmup start / day"
              type="number"
              value={form.warmup_start_daily}
              onChange={(e) => setForm((f) => ({ ...f, warmup_start_daily: e.target.value }))}
            />
            <Input
              label="Warmup target / day"
              type="number"
              value={form.warmup_target_daily}
              onChange={(e) => setForm((f) => ({ ...f, warmup_target_daily: e.target.value }))}
            />
            <Input
              label="Increase per day"
              type="number"
              value={form.warmup_increase_daily}
              onChange={(e) => setForm((f) => ({ ...f, warmup_increase_daily: e.target.value }))}
            />
            <div className="sm:col-span-2">
              <Button type="submit" isLoading={isSaving}>
                Add & start warmup
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card title="Warmup mailboxes" description="Enable or adjust ramp per mailbox">
        {isLoading ? (
          <div className="flex justify-center py-10">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
          </div>
        ) : servers.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">
            No mailboxes yet. Click Add mailbox to start warmup.
          </p>
        ) : (
          <ul className="space-y-3">
            {servers.map((server) => (
              <WarmupRow
                key={server.id}
                server={server}
                busy={busyId === server.id}
                onToggle={(on) => toggleWarmup(server, on)}
                onSaveRamp={(values) => saveRamp(server, values)}
                onDelete={() => handleDelete(server)}
              />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function WarmupRow({
  server,
  busy,
  onToggle,
  onSaveRamp,
  onDelete,
}: {
  server: SmtpServer;
  busy: boolean;
  onToggle: (enabled: boolean) => void;
  onSaveRamp: (values: {
    warmup_start_daily: number;
    warmup_target_daily: number;
    warmup_increase_daily: number;
  }) => void;
  onDelete: () => void;
}) {
  const [start, setStart] = useState(String(server.warmup_start_daily || 5));
  const [target, setTarget] = useState(String(server.warmup_target_daily || 40));
  const [increase, setIncrease] = useState(String(server.warmup_increase_daily || 5));

  useEffect(() => {
    setStart(String(server.warmup_start_daily || 5));
    setTarget(String(server.warmup_target_daily || 40));
    setIncrease(String(server.warmup_increase_daily || 5));
  }, [server]);

  const cap = effectiveCap(server);

  return (
    <li className="rounded-lg border border-slate-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium text-slate-900">{server.from_email}</p>
          <p className="text-xs text-slate-500">
            {server.name} · {server.host}:{server.port}
          </p>
          <p className="mt-1 text-sm text-slate-400">
            {server.warmup_enabled ? (
              <>
                Warmup <span className="text-emerald-600">ON</span> — today&apos;s cap{" "}
                <span className="text-slate-800">{cap}</span> / target{" "}
                {server.warmup_target_daily || 40}
              </>
            ) : (
              <>
                Warmup <span className="text-slate-500">OFF</span> — full daily limit{" "}
                {server.daily_limit}
              </>
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant={server.warmup_enabled ? "ghost" : undefined}
            isLoading={busy}
            onClick={() => onToggle(!server.warmup_enabled)}
          >
            {server.warmup_enabled ? "Stop warmup" : "Start warmup"}
          </Button>
          <Button type="button" variant="ghost" isLoading={busy} onClick={onDelete}>
            Delete
          </Button>
        </div>
      </div>

      {server.warmup_enabled && (
        <div className="mt-3 grid gap-2 sm:grid-cols-4">
          <Input
            label="Start / day"
            type="number"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
          <Input
            label="Target / day"
            type="number"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
          <Input
            label="Increase / day"
            type="number"
            value={increase}
            onChange={(e) => setIncrease(e.target.value)}
          />
          <div className="flex items-end">
            <Button
              type="button"
              isLoading={busy}
              onClick={() =>
                onSaveRamp({
                  warmup_start_daily: Number(start) || 5,
                  warmup_target_daily: Number(target) || 40,
                  warmup_increase_daily: Number(increase) || 5,
                })
              }
            >
              Save
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

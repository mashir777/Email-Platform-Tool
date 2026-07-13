import { FormEvent, useCallback, useEffect, useState } from "react";

import * as campaignsApi from "@/api/campaigns";
import type { CampaignDeliveryTracking } from "@/api/campaigns";
import { createSubscriber, fetchLists, importSubscribers } from "@/api/subscribers";
import * as smtpApi from "@/api/smtp";
import { ApiClientError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import type { Campaign, CampaignStats } from "@/types/campaigns";
import type { SubscriberList } from "@/types/subscribers";

const statusColors: Record<string, string> = {
  draft: "text-slate-400 bg-slate-400/10",
  scheduled: "text-indigo-400 bg-indigo-400/10",
  sending: "text-amber-400 bg-amber-400/10",
  sent: "text-emerald-400 bg-emerald-400/10",
  paused: "text-yellow-400 bg-yellow-400/10",
  cancelled: "text-red-400 bg-red-400/10",
};

const emptyForm = {
  name: "",
  subject: "",
  from_name: "",
  from_email: "",
  html_content: "<h1>Hello!</h1>\n<p>Your email content here...</p>",
  subscriber_list_id: "",
};

function simplifySmtpError(error: string): string {
  if (error.includes("gmail.com is not allowed") || error.includes("not allowed in header")) {
    return "From email must be your domain mailbox (e.g. info@datrixworld.com), not Gmail.";
  }
  if (error.includes("CERTIFICATE_VERIFY_FAILED") || error.includes("certificate verify failed")) {
    return "SSL certificate error — disable 'Verify SSL' on SMTP server for shared hosting.";
  }
  if (error.includes("could not deliver mail") || error.includes("may not exist")) {
    return "Recipient email invalid or does not exist. Use real Gmail addresses in CSV.";
  }
  const quoted = error.match(/b'([^']+)'/);
  if (quoted) {
    return quoted[1].replace(/\\n/g, " ").trim();
  }
  return error;
}

function formatSendResult(result: {
  send_summary?: {
    sent: number;
    failed: number;
    skipped?: number;
    pending?: number;
    send_interval_seconds?: number;
    active_smtp_servers?: number;
    is_rate_limited?: boolean;
    errors?: { email: string; error: string }[];
  };
}): string {
  const summary = result.send_summary;
  if (!summary) return "Campaign sent.";
  const skipped = summary.skipped ?? 0;
  const base =
    skipped > 0
      ? `Delivered: ${summary.sent}, Failed: ${summary.failed}, Skipped: ${skipped}`
      : `Delivered: ${summary.sent}, Failed: ${summary.failed}`;
  if (skipped > 0 && summary.sent === 0) {
    return `${base}. Add a real Gmail below — @example.com cannot receive mail.`;
  }
  if (skipped > 0 && summary.sent > 0) {
    return `${base}. Only real addresses receive mail; fake CSV data was skipped.`;
  }
  if (summary.is_rate_limited && (summary.pending ?? 0) > 0) {
    const minutes = Math.max(1, Math.round((summary.send_interval_seconds ?? 60) / 60));
    const servers = summary.active_smtp_servers ?? 1;
    const rateMsg =
      servers > 1
        ? `Queued: ${summary.pending}. ~${servers} mailboxes sending in parallel (~1 every ${minutes} min each).`
        : `Queued: ${summary.pending}. Sending ~1 email every ${minutes} minute(s).`;
    return `${base}. ${rateMsg}`;
  }
  const firstError = summary.errors?.[0]?.error;
  if (summary.failed > 0 && firstError) {
    return `${base}. ${simplifySmtpError(firstError)}`;
  }
  return summary.sent > 0 ? `${base}.` : base;
}

function formatSendInterval(hourlyLimit: number): string {
  const intervalSeconds = Math.max(60, Math.floor(3600 / Math.max(hourlyLimit, 1)));
  const minutes = Math.max(1, Math.round(intervalSeconds / 60));
  return `~1 email every ${minutes} minute(s) at ${hourlyLimit}/hour`;
}

export function CampaignsPage() {
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [lists, setLists] = useState<SubscriberList[]>([]);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [scheduleId, setScheduleId] = useState<string | null>(null);
  const [scheduleAt, setScheduleAt] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [defaultFromEmail, setDefaultFromEmail] = useState("");
  const [defaultHourlyLimit, setDefaultHourlyLimit] = useState(60);
  const [fromEmailOptions, setFromEmailOptions] = useState<string[]>([]);
  const [recipientEmail, setRecipientEmail] = useState("");
  const [isAddingRecipient, setIsAddingRecipient] = useState(false);
  const [isImportingCsv, setIsImportingCsv] = useState(false);
  const [testEmail, setTestEmail] = useState("");
  const [isTestSending, setIsTestSending] = useState(false);
  const [trackingId, setTrackingId] = useState<string | null>(null);
  const [trackingData, setTrackingData] = useState<CampaignDeliveryTracking | null>(null);
  const [isTrackingLoading, setIsTrackingLoading] = useState(false);

  const selectedList = lists.find((l) => l.id === form.subscriber_list_id);
  const recipientCount = selectedList?.subscriber_count ?? 0;
  const deliverableCount = selectedList?.deliverable_count ?? recipientCount;
  const fakeRecipientCount = Math.max(0, recipientCount - deliverableCount);
  const sendingDomain = defaultFromEmail.split("@")[1] ?? "";

  function resolveFromEmail(email: string): string {
    if (!defaultFromEmail) return email.trim();
    const domain = defaultFromEmail.split("@")[1]?.toLowerCase();
    const fromDomain = email.split("@")[1]?.toLowerCase();
    if (!domain || fromDomain === domain) return email.trim();
    return defaultFromEmail;
  }

  function buildCampaignPayload() {
    return {
      ...form,
      from_email: resolveFromEmail(form.from_email),
      subscriber_list_id: form.subscriber_list_id,
    };
  }

  const reloadLists = useCallback(async () => {
    try {
      const listsRes = await fetchLists();
      setLists(listsRes.lists);
      return listsRes.lists;
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load subscriber lists");
      return [];
    }
  }, []);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [statsRes, campaignsRes, listsRes] = await Promise.all([
        campaignsApi.fetchCampaignStats(),
        campaignsApi.fetchCampaigns({ search: search || undefined }),
        fetchLists(),
      ]);
      setStats(statsRes.stats);
      setCampaigns(campaignsRes.campaigns);
      setLists(listsRes.lists);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load campaigns");
    } finally {
      setIsLoading(false);
    }
  }, [search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const loadTracking = useCallback(async (id: string, showSpinner = true) => {
    if (showSpinner) setIsTrackingLoading(true);
    try {
      const result = await campaignsApi.fetchCampaignDeliveryStatus(id);
      setTrackingData(result.tracking);
    } catch (err) {
      if (showSpinner) {
        setError(err instanceof ApiClientError ? err.message : "Could not load tracking");
        setTrackingId(null);
      }
    } finally {
      if (showSpinner) setIsTrackingLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!trackingId) return;
    const timer = window.setInterval(() => {
      void loadTracking(trackingId, false);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [trackingId, loadTracking]);

  useEffect(() => {
    const hasSending = campaigns.some((campaign) => campaign.status === "sending");
    if (!hasSending) return;

    const intervalId = window.setInterval(() => {
      loadData();
    }, 15000);

    return () => window.clearInterval(intervalId);
  }, [campaigns, loadData]);

  useEffect(() => {
    if (showForm) {
      reloadLists();
    }
  }, [showForm, reloadLists]);

  async function loadDefaultSmtp() {
    try {
      const { servers } = await smtpApi.fetchSmtpServers();
      const active = servers.filter((server) => server.is_active);
      const defaultServer =
        active.find((server) => server.is_default) ?? active[0];
      const fromEmails = [
        ...new Set(active.map((s) => s.from_email).filter(Boolean)),
      ];
      setFromEmailOptions(fromEmails);
      setDefaultFromEmail(defaultServer?.from_email ?? fromEmails[0] ?? "");
      setDefaultHourlyLimit(defaultServer?.hourly_limit ?? 60);
      return defaultServer;
    } catch {
      return null;
    }
  }

  async function openCreate() {
    const [latestLists, defaultServer] = await Promise.all([reloadLists(), loadDefaultSmtp()]);
    setEditingId(null);
    setForm({
      ...emptyForm,
      subscriber_list_id: latestLists[0]?.id ?? "",
      from_email: defaultServer?.from_email ?? "",
      from_name: defaultServer?.from_name ?? "",
    });
    setShowForm(true);
    setError("");
  }

  async function openEdit(campaign: Campaign) {
    const [latestLists, defaultServer] = await Promise.all([reloadLists(), loadDefaultSmtp()]);
    const smtpDomain = defaultServer?.from_email?.split("@")[1] ?? "";
    const campaignDomain = campaign.from_email?.split("@")[1] ?? "";
    const fromEmailMismatch = Boolean(
      smtpDomain && campaignDomain && smtpDomain !== campaignDomain,
    );
    setEditingId(campaign.id);
    setForm({
      name: campaign.name,
      subject: campaign.subject,
      from_name: campaign.from_name || defaultServer?.from_name || "",
      from_email: fromEmailMismatch
        ? defaultServer?.from_email ?? campaign.from_email
        : campaign.from_email || defaultServer?.from_email || "",
      html_content: campaign.html_content || "<h1>Hello!</h1>\n<p>Your email content here...</p>",
      subscriber_list_id: campaign.subscriber_list?.id ?? latestLists[0]?.id ?? "",
    });
    if (fromEmailMismatch) {
      setNotice(`From email updated to ${defaultServer?.from_email} — Gmail cannot be used with your mail server.`);
    }
    setShowForm(true);
    setError("");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.subscriber_list_id) {
      setError("Please select a subscriber list.");
      return;
    }
    const payload = buildCampaignPayload();
    if (payload.from_email !== form.from_email.trim()) {
      setNotice(`From email set to ${payload.from_email} (domain mailbox required).`);
    }
    try {
      if (editingId) {
        await campaignsApi.updateCampaign(editingId, payload);
      } else {
        await campaignsApi.createCampaign(payload);
      }
      setShowForm(false);
      setForm(emptyForm);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Save failed");
    }
  }

  async function handleSchedule(e: FormEvent) {
    e.preventDefault();
    if (!scheduleId || !scheduleAt) return;
    try {
      await campaignsApi.scheduleCampaign(
        scheduleId,
        new Date(scheduleAt).toISOString(),
      );
      setScheduleId(null);
      setScheduleAt("");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Schedule failed");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this campaign?")) return;
    try {
      await campaignsApi.deleteCampaign(id);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Delete failed");
    }
  }

  async function handleCancel(id: string) {
    try {
      await campaignsApi.cancelCampaign(id);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Cancel failed");
    }
  }

  async function saveCampaignFromForm(id: string): Promise<boolean> {
    if (!form.subscriber_list_id) {
      setError("Select a subscriber list.");
      return false;
    }
    if (!form.subject.trim()) {
      setError("Subject is required.");
      return false;
    }
    if (!form.html_content.trim()) {
      setError("HTML content is required.");
      return false;
    }
    try {
      await campaignsApi.updateCampaign(id, {
        name: form.name,
        subject: form.subject,
        from_name: form.from_name,
        from_email: resolveFromEmail(form.from_email),
        html_content: form.html_content,
        subscriber_list_id: form.subscriber_list_id,
      });
      return true;
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to save campaign");
      return false;
    }
  }

  async function handleSaveAndSend(e: FormEvent) {
    e.preventDefault();
    if (!editingId) return;
    setError("");
    setNotice("");
    setIsSending(true);
    try {
      const saved = await saveCampaignFromForm(editingId);
      if (!saved) return;
      const result = await campaignsApi.sendCampaign(editingId);
      setShowForm(false);
      setEditingId(null);
      setForm(emptyForm);
      setNotice(formatSendResult(result));
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Send failed");
    } finally {
      setIsSending(false);
    }
  }

  async function handleSend(id: string) {
    setError("");
    setNotice("");

    if (showForm && editingId === id) {
      setIsSending(true);
      try {
        const saved = await saveCampaignFromForm(id);
        if (!saved) return;
      } finally {
        setIsSending(false);
      }
    }

    let campaign = campaigns.find((c) => c.id === id);
    try {
      const refreshed = await campaignsApi.fetchCampaigns();
      campaign = refreshed.campaigns.find((c) => c.id === id) ?? campaign;
      setCampaigns(refreshed.campaigns);
    } catch {
      // Use cached campaign if refresh fails.
    }

    if (!campaign) return;

    if (!campaign.subscriber_list) {
      setError("Subscriber list is required. Edit the campaign, select a list, and click Update.");
      return;
    }
    const listCount =
      campaign.subscriber_list.subscriber_count ??
      lists.find((l) => l.id === campaign.subscriber_list?.id)?.subscriber_count ??
      0;
    if (listCount === 0) {
      setError("This list has no subscribers. Add contacts from the Subscribers page first.");
      return;
    }
    if (!campaign.subject?.trim()) {
      setError("Subject is required. Edit the campaign and click Update before sending.");
      return;
    }
    if (!campaign.html_content?.trim() && !campaign.text_content?.trim()) {
      setError("Email content is missing. Click Edit, add HTML content, then use Save & Send.");
      openEdit(campaign);
      return;
    }
    setIsSending(true);
    try {
      const result = await campaignsApi.sendCampaign(id);
      setShowForm(false);
      setEditingId(null);
      setForm(emptyForm);
      setNotice(formatSendResult(result));
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Send failed");
    } finally {
      setIsSending(false);
    }
  }

  async function handleAddRecipient(e: FormEvent) {
    e.preventDefault();
    if (!form.subscriber_list_id) {
      setError("Select a subscriber list first.");
      return;
    }
    const email = recipientEmail.trim().toLowerCase();
    if (!email || !email.includes("@")) {
      setError("Enter a valid recipient email (e.g. yourname@gmail.com).");
      return;
    }
    setIsAddingRecipient(true);
    setError("");
    try {
      await createSubscriber({
        email,
        list_ids: [form.subscriber_list_id],
        status: "subscribed",
      });
      setRecipientEmail("");
      setNotice(`Recipient added: ${email}`);
      await reloadLists();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Could not add recipient");
    } finally {
      setIsAddingRecipient(false);
    }
  }

  async function handleCsvImport(file: File) {
    if (!form.subscriber_list_id) {
      setError("Select a subscriber list before importing CSV.");
      return;
    }
    setIsImportingCsv(true);
    setError("");
    try {
      const result = await importSubscribers(file, form.subscriber_list_id);
      const { created, updated, skipped, rejected = 0 } = result.import;
      const rejectedNote =
        rejected > 0 ? ` ${rejected} fake/test addresses (@example.com) rejected.` : "";
      setNotice(
        `CSV imported: ${created} created, ${updated} updated, ${skipped} skipped.${rejectedNote}`,
      );
      await reloadLists();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "CSV import failed");
    } finally {
      setIsImportingCsv(false);
    }
  }

  async function openTracking(id: string) {
    setTrackingId(id);
    setTrackingData(null);
    setError("");
    await loadTracking(id, true);
  }

  async function handleDuplicate(id: string) {
    try {
      await campaignsApi.duplicateCampaign(id);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Duplicate failed");
    }
  }

  async function handleSendAgain(id: string) {
    await handleEditCopy(id, "Draft copy ready — review below and click Save & Send.");
  }

  async function handleEditCopy(id: string, successNotice?: string) {
    setError("");
    setNotice("");
    try {
      const result = await campaignsApi.duplicateCampaign(id);
      await loadData();
      await openEdit(result.campaign);
      setNotice(
        successNotice ??
          "Editing a draft copy. The original sent campaign is unchanged.",
      );
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Could not open editor");
    }
  }

  async function handleCreateAndSend(e: FormEvent) {
    e.preventDefault();
    if (!form.subscriber_list_id) {
      setError("Please select a subscriber list.");
      return;
    }
    if (!form.subject.trim()) {
      setError("Subject is required.");
      return;
    }
    if (!form.html_content.trim()) {
      setError("HTML content is required.");
      return;
    }
    if (recipientCount === 0) {
      setError("This list has no subscribers. Add contacts from the Subscribers page first.");
      return;
    }
    if (deliverableCount === 0) {
      setError(
        "This list has only fake @example.com addresses. Add a real Gmail in the recipient field below.",
      );
      return;
    }
    setError("");
    setNotice("");
    setIsSending(true);
    try {
      const payload = buildCampaignPayload();
      const created = await campaignsApi.createCampaign(payload);
      const result = await campaignsApi.sendCampaign(created.campaign.id);
      setShowForm(false);
      setForm(emptyForm);
      setEditingId(null);
      setNotice(formatSendResult(result));
      if (result.send_summary?.failed) {
        setError(formatSendResult(result));
      }
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Send failed");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="space-y-6">
      {!defaultFromEmail && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          <p className="font-medium">Step 1: Add your domain sending email</p>
          <p className="mt-1 text-xs text-amber-300/90">
            Go to <strong>SMTP</strong> → Add server → set <strong>From email</strong> to your
            mailbox (e.g. info@datrixworld.com) → Test → Set default. Then create a campaign here.
          </p>
        </div>
      )}

      {defaultFromEmail && (
        <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-200">
          <p className="font-medium">Domain → Gmail sending</p>
          <p className="mt-1 text-xs text-indigo-300/90">
            <strong>From (sender):</strong>{" "}
            <span className="font-mono text-indigo-100">{defaultFromEmail}</span> — your domain
            mailbox only, not @gmail.com.
            <br />
            <strong>To (recipients):</strong> Gmail or any email — add below or import CSV with
            real addresses (not @example.com).
          </p>
        </div>
      )}

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

      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Card>
            <p className="text-sm text-slate-400">Total Campaigns</p>
            <p className="mt-2 text-3xl font-bold text-white">{stats.total}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Drafts</p>
            <p className="mt-2 text-3xl font-bold text-slate-300">{stats.draft}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Scheduled</p>
            <p className="mt-2 text-3xl font-bold text-indigo-400">{stats.scheduled}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Sent</p>
            <p className="mt-2 text-3xl font-bold text-emerald-400">{stats.sent}</p>
          </Card>
        </div>
      )}

      <Card title="Campaigns">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <input
            type="search"
            placeholder="Search campaigns..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
          />
          <Button onClick={openCreate}>+ New Campaign</Button>
        </div>

        {!isLoading && campaigns.length > 0 && campaigns.every((c) => c.status === "sent") && (
          <div className="mb-4 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-200">
            Your campaign was already sent. Click the green{" "}
            <span className="font-semibold text-emerald-300">Send Again</span> button in the
            table to resend, or use <span className="font-semibold">+ New Campaign</span> above.
          </div>
        )}

        {showForm && (
          <form
            onSubmit={handleSubmit}
            className="mb-6 rounded-lg border border-slate-700 bg-slate-900/50 p-4"
          >
            <h3 className="mb-4 text-sm font-semibold text-white">
              {editingId ? "Edit Campaign" : "New Campaign"}
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label="Campaign name"
                required
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
              <Input
                label="Subject"
                value={form.subject}
                onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
              />
              <Input
                label="From name"
                value={form.from_name}
                onChange={(e) => setForm((f) => ({ ...f, from_name: e.target.value }))}
              />
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-300">
                  From email (sender) <span className="text-red-400">*</span>
                </label>
                {fromEmailOptions.length > 0 ? (
                  <select
                    required
                    value={form.from_email || defaultFromEmail}
                    onChange={(e) => setForm((f) => ({ ...f, from_email: e.target.value }))}
                    className="w-full rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100"
                  >
                    {fromEmailOptions.map((email) => (
                      <option key={email} value={email}>
                        {email}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="email"
                    required
                    value={form.from_email}
                    onChange={(e) => setForm((f) => ({ ...f, from_email: e.target.value }))}
                    placeholder="info@yourdomain.com"
                    className="w-full rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100"
                  />
                )}
                {sendingDomain && (
                  <p className="mt-1 text-xs text-slate-500">
                    Must be @{sendingDomain} — configured on SMTP page. Recipients can be Gmail.
                  </p>
                )}
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1.5 block text-sm font-medium text-slate-300">
                  Subscriber list <span className="text-red-400">*</span>
                </label>
                {lists.length > 0 && (
                  <select
                    required
                    value={form.subscriber_list_id}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, subscriber_list_id: e.target.value }))
                    }
                    className="mb-3 w-full rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100"
                  >
                    <option value="">Select a list</option>
                    {lists.map((list) => (
                      <option key={list.id} value={list.id}>
                        {list.name} ({list.deliverable_count ?? list.subscriber_count} sendable)
                      </option>
                    ))}
                  </select>
                )}
                {lists.length === 0 && (
                  <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
                    No subscriber lists found. Create lists and add contacts from the
                    Subscribers page.
                  </p>
                )}
                {form.subscriber_list_id && (
                  <div className="mt-3 rounded-lg border border-slate-700 bg-slate-900/40 p-3">
                    <p className="text-sm text-slate-300">
                      Recipients in list:{" "}
                      <span className={deliverableCount > 0 ? "text-emerald-400" : "text-amber-400"}>
                        {deliverableCount} sendable
                      </span>
                      {fakeRecipientCount > 0 && (
                        <span className="text-amber-400">
                          {" "}
                          ({fakeRecipientCount} fake @example.com — will not receive mail)
                        </span>
                      )}
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <label className="cursor-pointer">
                        <span className="inline-flex items-center justify-center rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-xs font-medium text-slate-100 hover:bg-slate-700">
                          {isImportingCsv ? "Importing..." : "Import CSV to this list"}
                        </span>
                        <input
                          type="file"
                          accept=".csv"
                          className="hidden"
                          disabled={isImportingCsv}
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) handleCsvImport(file);
                            e.target.value = "";
                          }}
                        />
                      </label>
                      <span className="text-xs text-slate-500">
                        CSV must include an <span className="font-mono">email</span> column
                      </span>
                    </div>
                    {deliverableCount === 0 && (
                      <p className="mt-2 text-xs text-amber-400">
                        Add a Gmail recipient below — @example.com CSV demo data cannot receive mail.
                      </p>
                    )}
                    <form
                      onSubmit={handleAddRecipient}
                      className="mt-3 flex flex-wrap items-end gap-2 border-t border-slate-700/60 pt-3"
                    >
                      <div className="min-w-[220px] flex-1">
                        <label className="mb-1 block text-xs font-medium text-slate-400">
                          Add recipient (To) — Gmail OK
                        </label>
                        <input
                          type="email"
                          value={recipientEmail}
                          onChange={(e) => setRecipientEmail(e.target.value)}
                          placeholder="yourname@gmail.com"
                          className="w-full rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100"
                        />
                      </div>
                      <Button type="submit" isLoading={isAddingRecipient} className="shrink-0">
                        Add to list
                      </Button>
                    </form>
                  </div>
                )}
                <p className="mt-2 text-xs text-slate-500">
                  Send rate: {formatSendInterval(defaultHourlyLimit)} (set on SMTP page)
                </p>
                {editingId && (
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      const email = testEmail.trim().toLowerCase();
                      if (!email || !email.includes("@")) {
                        setError("Enter your Gmail for a test send.");
                        return;
                      }
                      setIsTestSending(true);
                      setError("");
                      try {
                        await campaignsApi.sendCampaignTestEmail(editingId, email);
                        setNotice(`Test email sent to ${email}. Check inbox and spam folder.`);
                      } catch (err) {
                        setError(
                          err instanceof ApiClientError ? err.message : "Test send failed",
                        );
                      } finally {
                        setIsTestSending(false);
                      }
                    }}
                    className="mt-3 flex flex-wrap items-end gap-2 rounded-lg border border-indigo-500/30 bg-indigo-500/5 p-3"
                  >
                    <div className="min-w-[220px] flex-1">
                      <label className="mb-1 block text-xs font-medium text-indigo-200">
                        Send test email (before full campaign)
                      </label>
                      <input
                        type="email"
                        value={testEmail}
                        onChange={(e) => setTestEmail(e.target.value)}
                        placeholder="yourname@gmail.com"
                        className="w-full rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100"
                      />
                    </div>
                    <Button type="submit" isLoading={isTestSending} className="shrink-0">
                      Send test
                    </Button>
                  </form>
                )}
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1.5 block text-sm font-medium text-slate-300">
                  HTML content
                </label>
                <textarea
                  rows={5}
                  value={form.html_content}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, html_content: e.target.value }))
                  }
                  className="w-full rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none"
                  placeholder={'<h1>Hello!</h1>\n<p>Watch our video: <a href="https://youtu.be/YOUR_ID">Click here</a></p>'}
                />
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button type="submit">{editingId ? "Update" : "Create"}</Button>
              {editingId ? (
                <Button
                  type="button"
                  onClick={handleSaveAndSend}
                  isLoading={isSending}
                  className="bg-emerald-600 hover:bg-emerald-500"
                >
                  Save & Send
                </Button>
              ) : (
                <Button
                  type="button"
                  onClick={handleCreateAndSend}
                  isLoading={isSending}
                  className="bg-emerald-600 hover:bg-emerald-500"
                >
                  Create & Send
                </Button>
              )}
              <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </form>
        )}

        {scheduleId && (
          <form
            onSubmit={handleSchedule}
            className="mb-6 rounded-lg border border-indigo-500/30 bg-indigo-500/5 p-4"
          >
            <h3 className="mb-3 text-sm font-semibold text-indigo-300">Schedule Campaign</h3>
            <Input
              label="Send at"
              type="datetime-local"
              required
              value={scheduleAt}
              onChange={(e) => setScheduleAt(e.target.value)}
            />
            <div className="mt-3 flex gap-2">
              <Button type="submit">Schedule</Button>
              <Button type="button" variant="ghost" onClick={() => setScheduleId(null)}>
                Cancel
              </Button>
            </div>
          </form>
        )}

        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
          </div>
        ) : campaigns.length === 0 ? (
          <p className="py-12 text-center text-sm text-slate-500">
            No campaigns yet. Create your first email campaign.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500">
                  <th className="pb-3 pr-4 font-medium">Name</th>
                  <th className="pb-3 pr-4 font-medium">Subject</th>
                  <th className="pb-3 pr-4 font-medium">List</th>
                  <th className="pb-3 pr-4 font-medium">Status</th>
                  <th className="pb-3 pr-4 font-medium">Recipients</th>
                  <th className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr key={c.id} className="border-b border-slate-800/60">
                    <td className="py-3 pr-4 font-medium text-slate-200">{c.name}</td>
                    <td className="py-3 pr-4 text-slate-400">{c.subject || "—"}</td>
                    <td className="py-3 pr-4 text-slate-500">
                      {c.subscriber_list?.name ?? (
                        <span className="text-amber-400">No list — edit to add</span>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusColors[c.status]}`}
                      >
                        {c.status}
                      </span>
                      {c.status === "sending" && (
                        <p className="mt-1 text-xs text-amber-300">Sending in background…</p>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-slate-400">
                      {c.recipient_count ||
                        c.subscriber_list?.subscriber_count ||
                        "—"}
                    </td>
                    <td className="py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        {c.status === "draft" && (
                          <>
                            <button
                              type="button"
                              onClick={() => openEdit(c)}
                              className="text-xs text-indigo-400 hover:underline"
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSend(c.id)}
                              disabled={isSending}
                              className="rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                            >
                              Send Now
                            </button>
                            <button
                              type="button"
                              onClick={() => setScheduleId(c.id)}
                              className="text-xs text-indigo-400 hover:underline"
                            >
                              Schedule
                            </button>
                          </>
                        )}
                        {c.status === "scheduled" && (
                          <>
                            <button
                              type="button"
                              onClick={() => openEdit(c)}
                              className="text-xs text-indigo-400 hover:underline"
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSend(c.id)}
                              disabled={isSending}
                              className="rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                            >
                              Send Now
                            </button>
                            <button
                              type="button"
                              onClick={() => handleCancel(c.id)}
                              className="text-xs text-amber-400 hover:underline"
                            >
                              Cancel
                            </button>
                          </>
                        )}
                        {c.status === "sending" && (
                          <>
                            <button
                              type="button"
                              onClick={() => openTracking(c.id)}
                              className="text-xs text-indigo-400 hover:underline"
                            >
                              Tracking
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSend(c.id)}
                              disabled={isSending}
                              className="rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                            >
                              Resume Send
                            </button>
                          </>
                        )}
                        {c.status === "sent" && (
                          <>
                            <button
                              type="button"
                              onClick={() => openTracking(c.id)}
                              className="text-xs text-indigo-400 hover:underline"
                            >
                              Tracking
                            </button>
                            <button
                              type="button"
                              onClick={() => handleEditCopy(c.id)}
                              className="text-xs text-indigo-400 hover:underline"
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSendAgain(c.id)}
                              disabled={isSending}
                              className="rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                            >
                              Send Again
                            </button>
                          </>
                        )}
                        <button
                          type="button"
                          onClick={() => handleDuplicate(c.id)}
                          className="text-xs text-slate-400 hover:underline"
                        >
                          Duplicate
                        </button>
                        {c.status !== "sending" && (
                          <button
                            type="button"
                            onClick={() => handleDelete(c.id)}
                            className="text-xs text-red-400 hover:underline"
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {trackingId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="max-h-[85vh] w-full max-w-3xl overflow-hidden rounded-xl border border-slate-700 bg-slate-900 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
              <div>
                <h3 className="text-lg font-semibold text-white">Email Tracking</h3>
                {trackingData && (
                  <p className="text-sm text-slate-400">
                    {trackingData.campaign_name} — {trackingData.opened}/{trackingData.delivered}{" "}
                    opened ({trackingData.open_rate}%)
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => trackingId && loadTracking(trackingId, true)}
                className="mr-3 text-xs text-indigo-400 hover:underline"
              >
                Refresh
              </button>
              <button
                type="button"
                onClick={() => {
                  setTrackingId(null);
                  setTrackingData(null);
                }}
                className="text-slate-400 hover:text-white"
              >
                Close
              </button>
            </div>
            <div className="max-h-[65vh] overflow-auto p-5">
              {isTrackingLoading ? (
                <p className="text-center text-sm text-slate-400">Loading tracking…</p>
              ) : trackingData ? (
                <>
                  <p className="mb-4 text-xs text-slate-500">{trackingData.note}</p>
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-500">
                        <th className="pb-2 pr-3 font-medium">Email</th>
                        <th className="pb-2 pr-3 font-medium">Inbox / Spam</th>
                        <th className="pb-2 font-medium">Opened</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trackingData.recipients.map((row) => (
                        <tr key={row.email} className="border-b border-slate-800/60">
                          <td className="py-2 pr-3 text-slate-200">{row.email}</td>
                          <td className="py-2 pr-3">
                            <span
                              className={
                                row.folder === "inbox"
                                  ? "text-emerald-400"
                                  : row.folder === "failed"
                                    ? "text-red-400"
                                    : "text-amber-300"
                              }
                            >
                              {row.folder_label}
                            </span>
                          </td>
                          <td className="py-2">
                            {row.opened ? (
                              <span className="text-emerald-400">Yes</span>
                            ) : row.delivered ? (
                              <div className="space-y-1">
                                <span className="text-slate-400">No</span>
                                {row.confirm_url && (
                                  <p className="text-xs text-slate-500">
                                    Recipient must click{" "}
                                    <span className="text-slate-400">Confirm you received this email</span>{" "}
                                    in the message.
                                  </p>
                                )}
                              </div>
                            ) : (
                              <span className="text-slate-500">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

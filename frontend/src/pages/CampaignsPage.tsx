import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import * as campaignsApi from "@/api/campaigns";
import type { CampaignDeliveryTracking } from "@/api/campaigns";
import { fetchMessagePurposes } from "@/api/messages";
import { fetchLists, fetchSubscribers } from "@/api/subscribers";
import * as smtpApi from "@/api/smtp";
import { ApiClientError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import type { Campaign, CampaignStats } from "@/types/campaigns";
import type { MessagePurpose } from "@/types/messages";
import type { Subscriber, SubscriberList } from "@/types/subscribers";

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
  html_content: `Hi {{name}},<br><br>
Quick question — is {{Company}} still handling [client onboarding and scheduling] manually?<br><br>
Most {{Industrial Company}} teams I speak to are. It usually costs them 8–12 hours a week and a lot of avoidable errors.<br><br>
Just curious if that's something you've been looking to fix, or if you've already got it sorted.<br><br>
Either way, happy to share what's worked for similar teams.<br><br>
Best,<br>
David Wilson<br>
Datrix World | datrixworld.com`,
  subscriber_list_id: "",
  message_version_id: "",
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
    return `${base}. Add real emails on the Emails page — @example.com cannot receive mail.`;
  }
  if (skipped > 0 && summary.sent > 0) {
    return `${base}. Only real addresses receive mail; fake addresses were skipped.`;
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

const SEND_DELAY_STORAGE_KEY = "campaign_send_delay_seconds";

function loadSendDelaySeconds(): number {
  const raw = Number(localStorage.getItem(SEND_DELAY_STORAGE_KEY) || "60");
  if (!Number.isFinite(raw)) return 60;
  return Math.min(900, Math.max(60, Math.round(raw)));
}

export function CampaignsPage() {
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [lists, setLists] = useState<SubscriberList[]>([]);
  const [messagePurposes, setMessagePurposes] = useState<MessagePurpose[]>([]);
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
  const [defaultSmtpId, setDefaultSmtpId] = useState<string | null>(null);
  const [fromEmailOptions, setFromEmailOptions] = useState<string[]>([]);
  const [listRecipients, setListRecipients] = useState<Subscriber[]>([]);
  const [isLoadingRecipients, setIsLoadingRecipients] = useState(false);
  const [testEmail, setTestEmail] = useState("");
  const [isTestSending, setIsTestSending] = useState(false);
  const [trackingId, setTrackingId] = useState<string | null>(null);
  const [trackingData, setTrackingData] = useState<CampaignDeliveryTracking | null>(null);
  const [isTrackingLoading, setIsTrackingLoading] = useState(false);
  const [selectedCampaignIds, setSelectedCampaignIds] = useState<string[]>([]);
  const [sendDelaySeconds, setSendDelaySeconds] = useState(loadSendDelaySeconds);
  const [sendProgress, setSendProgress] = useState<{
    campaignId: string;
    campaignName: string;
    sent: number;
    pending: number;
    intervalSeconds: number;
    nextInSeconds: number;
  } | null>(null);
  /** Seconds left on the timer when Stop was pressed — Resume continues from here. */
  const stoppedAtSecondsRef = useRef<{ campaignId: string; nextInSeconds: number } | null>(
    null,
  );

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
      message_version_id: form.message_version_id || null,
    };
  }

  const reloadLists = useCallback(async () => {
    try {
      const listsRes = await fetchLists();
      setLists(listsRes.lists);
      return listsRes.lists;
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load email lists");
      return [];
    }
  }, []);

  const reloadMessages = useCallback(async () => {
    try {
      const messagesRes = await fetchMessagePurposes();
      setMessagePurposes(messagesRes.purposes);
      return messagesRes.purposes;
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load messages");
      return [];
    }
  }, []);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [statsRes, campaignsRes, listsRes, messagesRes] = await Promise.all([
        campaignsApi.fetchCampaignStats(),
        campaignsApi.fetchCampaigns({ search: search || undefined }),
        fetchLists(),
        fetchMessagePurposes(),
      ]);
      setStats(statsRes.stats);
      setCampaigns(campaignsRes.campaigns);
      setLists(listsRes.lists);
      setMessagePurposes(messagesRes.purposes);
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
      const campaignName =
        result.tracking.campaign_name ||
        campaigns.find((c) => c.id === id)?.name ||
        "Campaign";
      applySendSummaryToProgress(id, campaignName, result.send_summary);
    } catch (err) {
      if (showSpinner) {
        setError(err instanceof ApiClientError ? err.message : "Could not load tracking");
        setTrackingId(null);
      }
    } finally {
      if (showSpinner) setIsTrackingLoading(false);
    }
  }, [campaigns]);

  useEffect(() => {
    if (!trackingId) return;
    const timer = window.setInterval(() => {
      void loadTracking(trackingId, false);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [trackingId, loadTracking]);

  useEffect(() => {
    const sendingCampaign = campaigns.find((campaign) => campaign.status === "sending");
    if (!sendingCampaign) {
      setSendProgress((current) =>
        current && campaigns.some((c) => c.id === current.campaignId && c.status === "sending")
          ? current
          : null,
      );
      return;
    }

    const poll = () => {
      void loadData();
      void campaignsApi
        .fetchCampaignDeliveryStatus(sendingCampaign.id)
        .then((result) => {
          applySendSummaryToProgress(
            sendingCampaign.id,
            sendingCampaign.name,
            result.send_summary,
          );
        })
        .catch(() => undefined);
    };

    poll();
    const intervalId = window.setInterval(poll, 5000);
    return () => window.clearInterval(intervalId);
  }, [campaigns, loadData]);

  // Local countdown (e.g. 60→59→58→0) then restart until queue is empty
  useEffect(() => {
    if (!sendProgress || sendProgress.pending <= 0) return;
    const tick = window.setInterval(() => {
      setSendProgress((current) => {
        if (!current || current.pending <= 0) return current;
        if (current.nextInSeconds <= 0) {
          return { ...current, nextInSeconds: current.intervalSeconds };
        }
        return { ...current, nextInSeconds: current.nextInSeconds - 1 };
      });
    }, 1000);
    return () => window.clearInterval(tick);
  }, [sendProgress?.campaignId, sendProgress?.pending]);

  useEffect(() => {
    void loadDefaultSmtp();
  }, []);

  useEffect(() => {
    if (showForm) {
      reloadLists();
    }
  }, [showForm, reloadLists]);

  useEffect(() => {
    if (!form.subscriber_list_id) {
      setListRecipients([]);
      return;
    }
    let cancelled = false;
    setIsLoadingRecipients(true);
    fetchSubscribers({ list_id: form.subscriber_list_id, status: "subscribed" })
      .then((res) => {
        if (!cancelled) setListRecipients(res.subscribers);
      })
      .catch(() => {
        if (!cancelled) setListRecipients([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingRecipients(false);
      });
    return () => {
      cancelled = true;
    };
  }, [form.subscriber_list_id]);

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
      setDefaultSmtpId(defaultServer?.id ?? null);
      return defaultServer;
    } catch {
      return null;
    }
  }

  async function applySendDelaySeconds(seconds: number) {
    const delay = Math.min(900, Math.max(60, Math.round(seconds) || 60));
    setSendDelaySeconds(delay);
    localStorage.setItem(SEND_DELAY_STORAGE_KEY, String(delay));
    // hourly_limit such that 3600/hourly ≈ delay (backend also enforces min 60s)
    const hourly = Math.max(1, Math.floor(3600 / delay));
    if (!defaultSmtpId) {
      const server = await loadDefaultSmtp();
      if (!server?.id) return delay;
      await smtpApi.updateSmtpServer(server.id, { hourly_limit: hourly });
      return delay;
    }
    try {
      await smtpApi.updateSmtpServer(defaultSmtpId, { hourly_limit: hourly });
    } catch {
      // Keep local delay even if SMTP update fails; queue still uses SMTP limits.
    }
    return delay;
  }

  function applySendSummaryToProgress(
    campaignId: string,
    campaignName: string,
    summary?: {
      sent?: number;
      pending?: number;
      send_interval_seconds?: number;
      next_send_in_seconds?: number;
      is_rate_limited?: boolean;
    },
  ) {
    if (!summary) return;
    const pending = summary.pending ?? 0;
    if (pending > 0) {
      const interval = summary.send_interval_seconds ?? sendDelaySeconds;
      const serverNext = summary.next_send_in_seconds ?? interval;
      setSendProgress((current) => {
        const same = current?.campaignId === campaignId;
        const emailJustSent = Boolean(same && pending < (current?.pending ?? 0));
        const stoppedAt =
          stoppedAtSecondsRef.current?.campaignId === campaignId
            ? stoppedAtSecondsRef.current.nextInSeconds
            : null;

        let nextIn = serverNext > 0 ? serverNext : interval;

        // After Stop → Resume: continue from the exact second where user stopped.
        if (stoppedAt != null && !emailJustSent) {
          if (same && (current?.nextInSeconds ?? 0) > 0) {
            nextIn = current!.nextInSeconds;
          } else {
            nextIn = stoppedAt;
          }
        } else if (same && !emailJustSent && (current?.nextInSeconds ?? 0) > 0) {
          // Keep smooth local countdown between polls unless an email just left
          if (Math.abs((current?.nextInSeconds ?? 0) - serverNext) <= 5) {
            nextIn = current!.nextInSeconds;
          }
        }

        if (emailJustSent) {
          nextIn = serverNext > 0 ? serverNext : interval;
          if (stoppedAtSecondsRef.current?.campaignId === campaignId) {
            stoppedAtSecondsRef.current = null;
          }
        }

        return {
          campaignId,
          campaignName,
          sent: summary.sent ?? 0,
          pending,
          intervalSeconds: interval,
          nextInSeconds: Math.max(0, nextIn),
        };
      });
    } else {
      setSendProgress((current) => (current?.campaignId === campaignId ? null : current));
    }
  }

  async function openCreate() {
    const [latestLists, defaultServer] = await Promise.all([
      reloadLists(),
      loadDefaultSmtp(),
      reloadMessages(),
    ]);
    setEditingId(null);
    setForm({
      ...emptyForm,
      subscriber_list_id: latestLists[0]?.id ?? "",
      message_version_id: "",
      from_email: defaultServer?.from_email ?? "",
      from_name: defaultServer?.from_name ?? "",
    });
    setShowForm(true);
    setError("");
  }

  async function openEdit(campaign: Campaign) {
    const [latestLists, defaultServer] = await Promise.all([
      reloadLists(),
      loadDefaultSmtp(),
      reloadMessages(),
    ]);
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
      html_content: campaign.html_content || emptyForm.html_content,
      subscriber_list_id: campaign.subscriber_list?.id ?? latestLists[0]?.id ?? "",
      message_version_id: campaign.message_version?.id ?? "",
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
      setError("Please select an email list.");
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

  async function handleDeleteSelected() {
    if (
      !selectedCampaignIds.length ||
      !confirm(`Delete ${selectedCampaignIds.length} selected campaign(s)?`)
    ) return;
    try {
      await Promise.all(selectedCampaignIds.map((id) => campaignsApi.deleteCampaign(id)));
      setSelectedCampaignIds([]);
      setNotice("Selected campaigns deleted.");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to delete selected campaigns");
      await loadData();
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

  async function handleStopSending(id: string) {
    const remaining =
      sendProgress?.campaignId === id ? sendProgress.nextInSeconds : null;
    try {
      setError("");
      if (remaining != null) {
        stoppedAtSecondsRef.current = {
          campaignId: id,
          nextInSeconds: Math.max(0, remaining),
        };
      }
      await campaignsApi.pauseCampaign(id);
      // Stop timer UI immediately even if a later loadData poll fails.
      setCampaigns((prev) =>
        prev.map((c) => (c.id === id ? { ...c, status: "paused" as const } : c)),
      );
      setSendProgress(null);
      setNotice("Sending stopped. Use Resume Send to continue.");
      await loadData();
      // Successful stop — don't keep a refresh/poll 500 banner over the Stop result.
      setError("");
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Stop failed");
    }
  }

  async function saveCampaignFromForm(id: string): Promise<boolean> {
    if (!form.subscriber_list_id) {
      setError("Select an email list.");
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
        message_version_id: form.message_version_id || null,
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
      await applySendDelaySeconds(sendDelaySeconds);
      const result = await campaignsApi.sendCampaign(editingId);
      const sentId = editingId;
      setShowForm(false);
      setEditingId(null);
      setForm(emptyForm);
      setNotice(formatSendResult(result));
      applySendSummaryToProgress(sentId, form.name || "Campaign", result.send_summary);
      await loadData();
      await openTracking(sentId);
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
      setError("Email list is required. Edit the campaign, select a list, and click Update.");
      return;
    }
    const listCount =
      campaign.subscriber_list.subscriber_count ??
      lists.find((l) => l.id === campaign.subscriber_list?.id)?.subscriber_count ??
      0;
    if (listCount === 0) {
      setError("This list has no emails. Add emails from the Emails page first.");
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
      await applySendDelaySeconds(sendDelaySeconds);
      const result = await campaignsApi.sendCampaign(id);
      setShowForm(false);
      setEditingId(null);
      setForm(emptyForm);
      setNotice(formatSendResult(result));
      applySendSummaryToProgress(
        id,
        campaign.name,
        result.send_summary,
      );
      await loadData();
      await openTracking(id);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Send failed");
    } finally {
      setIsSending(false);
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
      setError("Please select an email list.");
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
      setError("This list has no emails. Add emails from the Emails page first.");
      return;
    }
    if (deliverableCount === 0) {
      setError(
        "This list has only fake @example.com addresses. Add real emails on the Emails page.",
      );
      return;
    }
    setError("");
    setNotice("");
    setIsSending(true);
    try {
      await applySendDelaySeconds(sendDelaySeconds);
      const payload = buildCampaignPayload();
      const created = await campaignsApi.createCampaign(payload);
      const result = await campaignsApi.sendCampaign(created.campaign.id);
      setShowForm(false);
      setForm(emptyForm);
      setEditingId(null);
      setNotice(formatSendResult(result));
      applySendSummaryToProgress(
        created.campaign.id,
        created.campaign.name,
        result.send_summary,
      );
      if (result.send_summary?.failed) {
        setError(formatSendResult(result));
      }
      await loadData();
      await openTracking(created.campaign.id);
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
            <strong>To (emails):</strong> Pick an email list below. Emails send one by
            one. Manage emails on the Emails page (not @example.com).
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

      {sendProgress && sendProgress.pending > 0 && (
        <div className="fixed right-4 top-24 z-40 w-56 rounded-xl border border-amber-500/40 bg-slate-950/95 p-4 shadow-xl shadow-black/40">
          <p className="text-xs font-medium uppercase tracking-wide text-amber-300">
            Send timer
          </p>
          <p className="mt-1 truncate text-sm text-slate-300">{sendProgress.campaignName}</p>
          <p className="mt-3 text-center text-5xl font-bold tabular-nums text-white">
            {sendProgress.nextInSeconds}
          </p>
          <p className="mt-1 text-center text-xs text-slate-400">
            next email in seconds
          </p>
          <p className="mt-3 text-center text-xs text-slate-500">
            Sent {sendProgress.sent} · Queued {sendProgress.pending}
            <br />
            Delay {sendProgress.intervalSeconds}s (
            {Math.max(1, Math.round(sendProgress.intervalSeconds / 60))} min)
          </p>
          <button
            type="button"
            onClick={() => handleStopSending(sendProgress.campaignId)}
            className="mt-4 w-full rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-500"
          >
            Stop
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-400">
            Wait between each email (seconds)
          </label>
          <input
            type="number"
            min={60}
            max={900}
            step={30}
            value={sendDelaySeconds}
            onChange={(e) => {
              const value = Number(e.target.value);
              setSendDelaySeconds(
                Number.isFinite(value) ? Math.min(900, Math.max(60, Math.round(value))) : 60,
              );
            }}
            onBlur={(e) => {
              const value = Number(e.target.value);
              void applySendDelaySeconds(
                Number.isFinite(value) ? value : sendDelaySeconds,
              );
            }}
            className="w-32 rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-400">
            Or minutes
          </label>
          <input
            type="number"
            min={1}
            max={15}
            step={1}
            value={Math.max(1, Math.round(sendDelaySeconds / 60))}
            onChange={(e) => {
              const minutes = Number(e.target.value);
              const secs = Number.isFinite(minutes)
                ? Math.min(900, Math.max(60, Math.round(minutes) * 60))
                : 60;
              setSendDelaySeconds(secs);
            }}
            onBlur={(e) => {
              const minutes = Number(e.target.value);
              const secs = Number.isFinite(minutes)
                ? Math.min(900, Math.max(60, Math.round(minutes) * 60))
                : sendDelaySeconds;
              void applySendDelaySeconds(secs);
            }}
            className="w-24 rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100"
          />
        </div>
        <p className="pb-2 text-xs text-slate-500">
          Default 60s (1 min). Timer shows 60, 59, 58… then sends one email and restarts.
        </p>
      </div>

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
          {selectedCampaignIds.length > 0 && (
            <Button variant="danger" onClick={() => void handleDeleteSelected()}>
              Delete Selected ({selectedCampaignIds.length})
            </Button>
          )}
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
                  Email list <span className="text-red-400">*</span>
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
                        {list.name} ({list.waiting_emails ?? list.deliverable_count ?? list.subscriber_count} waiting / {list.total_emails ?? list.subscriber_count} total)
                      </option>
                    ))}
                  </select>
                )}
                {lists.length === 0 && (
                  <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
                    No email lists found. Create lists and add emails from the
                    Emails page.
                  </p>
                )}
                {form.subscriber_list_id && (
                  <div className="mt-3 rounded-lg border border-slate-700 bg-slate-900/40 p-3">
                    <p className="text-sm text-slate-300">
                      Emails in list:{" "}
                      <span className="text-slate-200">
                        {selectedList?.total_emails ?? recipientCount} total
                      </span>
                      {" · "}
                      <span className="text-emerald-400">
                        {selectedList?.sent_emails ?? 0} sent
                      </span>
                      {" · "}
                      <span className="text-amber-300">
                        {selectedList?.waiting_emails ?? deliverableCount} waiting
                      </span>
                      {fakeRecipientCount > 0 && (
                        <span className="text-amber-400">
                          {" "}
                          ({fakeRecipientCount} fake @example.com — will not receive mail)
                        </span>
                      )}
                    </p>
                    <p className="mt-2 text-xs text-slate-500">
                      Send only queues <span className="text-amber-200">Waiting</span> emails.
                      Already sent addresses are skipped. Manage lists on the{" "}
                      <span className="text-slate-400">Emails</span> page.
                    </p>
                    {deliverableCount === 0 && (
                      <p className="mt-2 text-xs text-amber-400">
                        This list has no sendable emails. Add real addresses on the Emails page.
                      </p>
                    )}
                    <div className="mt-3 max-h-48 overflow-auto rounded-lg border border-slate-700/80">
                      {isLoadingRecipients ? (
                        <p className="px-3 py-2 text-xs text-slate-500">Loading list emails…</p>
                      ) : listRecipients.length === 0 ? (
                        <p className="px-3 py-2 text-xs text-slate-500">No emails in this list.</p>
                      ) : (
                        <ul className="divide-y divide-slate-800 text-sm">
                          {listRecipients.map((sub) => (
                            <li
                              key={sub.id}
                              className="flex items-center justify-between gap-3 px-3 py-2"
                            >
                              <span className="truncate text-slate-200">{sub.email}</span>
                              <span
                                className={`shrink-0 text-xs ${
                                  sub.send_status === "sent"
                                    ? "text-emerald-400"
                                    : "text-amber-300"
                                }`}
                              >
                                {sub.send_status === "sent" ? "Sent" : "Waiting"}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}
                <p className="mt-2 text-xs text-slate-500">
                  Send rate: 1 email every {sendDelaySeconds}s (set delay above or change here)
                </p>
                <label className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  Wait between emails (seconds)
                  <input
                    type="number"
                    min={60}
                    max={900}
                    step={30}
                    value={sendDelaySeconds}
                    onChange={(e) => {
                      const value = Number(e.target.value);
                      setSendDelaySeconds(
                        Number.isFinite(value)
                          ? Math.min(900, Math.max(60, Math.round(value)))
                          : 60,
                      );
                    }}
                    onBlur={() => {
                      void applySendDelaySeconds(sendDelaySeconds);
                    }}
                    className="w-24 rounded-lg border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-sm text-slate-100"
                  />
                </label>
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
                  Attach message <span className="text-slate-500">(optional)</span>
                </label>
                <select
                  value={form.message_version_id}
                  onChange={(e) => {
                    const versionId = e.target.value;
                    const matched = messagePurposes
                      .flatMap((purpose) =>
                        purpose.versions.map((version) => ({ purpose, version })),
                      )
                      .find((item) => item.version.id === versionId);
                    setForm((current) => ({
                      ...current,
                      message_version_id: versionId,
                      subject:
                        matched?.version.subject?.trim() ||
                        current.subject ||
                        `${matched?.purpose.name ?? "Campaign"} ${matched?.version.version.toUpperCase() ?? ""}`.trim(),
                      html_content:
                        matched?.version.html_content?.trim() || current.html_content,
                    }));
                  }}
                  className="w-full rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100"
                >
                  <option value="">No message attached</option>
                  {messagePurposes.map((purpose) => (
                    <optgroup key={purpose.id} label={purpose.name}>
                      {purpose.versions.map((version) => (
                        <option key={version.id} value={version.id}>
                          {purpose.name} — {version.version.toUpperCase()}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
                <p className="mt-1 text-xs text-slate-500">
                  Example: attach SaaS Work V1. You can still edit the campaign HTML after attaching.
                </p>
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
                  placeholder="Supports {{name}}, {{Company}}, {{Industrial Company}} from your CSV"
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
                  <th className="pb-3 pr-3">
                    <input
                      type="checkbox"
                      aria-label="Select all campaigns"
                      checked={
                        campaigns.some((campaign) => campaign.status !== "sending") &&
                        selectedCampaignIds.length ===
                          campaigns.filter((campaign) => campaign.status !== "sending").length
                      }
                      onChange={(event) =>
                        setSelectedCampaignIds(
                          event.target.checked
                            ? campaigns
                                .filter((campaign) => campaign.status !== "sending")
                                .map((campaign) => campaign.id)
                            : [],
                        )
                      }
                    />
                  </th>
                  <th className="pb-3 pr-4 font-medium">Name</th>
                  <th className="pb-3 pr-4 font-medium">Subject</th>
                  <th className="pb-3 pr-4 font-medium">List</th>
                  <th className="pb-3 pr-4 font-medium">Status</th>
                  <th className="pb-3 pr-4 font-medium">Emails</th>
                  <th className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr key={c.id} className="border-b border-slate-800/60">
                    <td className="py-3 pr-3">
                      <input
                        type="checkbox"
                        aria-label={`Select ${c.name}`}
                        disabled={c.status === "sending"}
                        checked={selectedCampaignIds.includes(c.id)}
                        onChange={(event) =>
                          setSelectedCampaignIds((current) =>
                            event.target.checked
                              ? [...current, c.id]
                              : current.filter((id) => id !== c.id),
                          )
                        }
                      />
                    </td>
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
                        <p className="mt-1 text-xs text-amber-300">
                          {sendProgress?.campaignId === c.id
                            ? `Next mail in ${sendProgress.nextInSeconds}s`
                            : "Sending in background…"}
                        </p>
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
                        {c.status === "paused" && (
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
                    opened emails ({trackingData.open_rate}%)
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
                        <th className="pb-2 pr-3 font-medium">Sent Emails</th>
                        <th className="pb-2 font-medium">Opened Emails</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trackingData.recipients.map((row) => {
                        const sendLabel =
                          row.queue_status === "sent"
                            ? "Sent"
                            : row.queue_status === "failed"
                              ? "Fail"
                              : row.queue_status === "skipped"
                                ? "Skipped"
                                : row.queue_status === "sending"
                                  ? "Sending…"
                                  : "Pending";
                        const sendClass =
                          row.queue_status === "sent"
                            ? "text-emerald-400"
                            : row.queue_status === "failed"
                              ? "text-red-400"
                              : row.queue_status === "sending"
                                ? "text-amber-300"
                                : "text-slate-400";
                        return (
                          <tr key={row.email} className="border-b border-slate-800/60">
                            <td className="py-2 pr-3 text-slate-200">{row.email}</td>
                            <td className={`py-2 pr-3 font-medium ${sendClass}`}>{sendLabel}</td>
                            <td className="py-2">
                              {row.opened ? (
                                <span className="text-emerald-400">Yes</span>
                              ) : row.delivered ? (
                                <span className="text-slate-400">No</span>
                              ) : (
                                <span className="text-slate-500">—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
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

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
import type { SmtpServer } from "@/types/smtp";
import type { Campaign, CampaignStats } from "@/types/campaigns";
import type { MessagePurpose } from "@/types/messages";
import type { Subscriber, SubscriberList } from "@/types/subscribers";

const statusColors: Record<string, string> = {
  draft: "text-slate-400 bg-slate-400/10",
  scheduled: "text-indigo-600 bg-indigo-400/10",
  sending: "text-amber-600 bg-amber-400/10",
  sent: "text-emerald-600 bg-emerald-400/10",
  paused: "text-yellow-600 bg-yellow-400/10",
  cancelled: "text-red-600 bg-red-400/10",
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
  smtp_server_ids: [] as string[],
  /** UI string: positive integer (e.g. 20) */
  emails_per_sender: "1",
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
const STOPPED_AT_STORAGE_KEY = "campaign_send_stopped_at";

function loadSendDelaySeconds(): number {
  const raw = Number(localStorage.getItem(SEND_DELAY_STORAGE_KEY) || "60");
  if (!Number.isFinite(raw)) return 60;
  return Math.min(900, Math.max(60, Math.round(raw)));
}

function loadStoppedAt(campaignId: string): number | null {
  try {
    const raw = sessionStorage.getItem(`${STOPPED_AT_STORAGE_KEY}:${campaignId}`);
    if (raw == null) return null;
    const value = Number(raw);
    return Number.isFinite(value) ? Math.max(0, Math.round(value)) : null;
  } catch {
    return null;
  }
}

function saveStoppedAt(campaignId: string, seconds: number) {
  try {
    sessionStorage.setItem(
      `${STOPPED_AT_STORAGE_KEY}:${campaignId}`,
      String(Math.max(0, Math.round(seconds))),
    );
  } catch {
    // ignore quota / private mode
  }
}

function clearStoppedAt(campaignId: string) {
  try {
    sessionStorage.removeItem(`${STOPPED_AT_STORAGE_KEY}:${campaignId}`);
  } catch {
    // ignore
  }
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
  const [smtpServers, setSmtpServers] = useState<SmtpServer[]>([]);
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
  const pollSendProgressRef = useRef<(() => void) | null>(null);
  const lastSentCountRef = useRef<Record<string, number>>({});
  const sendProgressRef = useRef(sendProgress);
  const pausedCampaignIdRef = useRef<string | null>(null);
  useEffect(() => {
    sendProgressRef.current = sendProgress;
  }, [sendProgress]);

  const activeSendingId =
    campaigns.find((campaign) => campaign.status === "sending")?.id ?? null;
  const pausedCampaignId =
    campaigns.find((campaign) => campaign.status === "paused")?.id ?? null;
  useEffect(() => {
    pausedCampaignIdRef.current = pausedCampaignId;
  }, [pausedCampaignId]);

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

  function orderedSelectedSmtpIds(selectedIds: string[]): string[] {
    // Top-to-bottom on the Senders list (first checked row sends first).
    return smtpServers.filter((s) => selectedIds.includes(s.id)).map((s) => s.id);
  }

  function parseEmailsPerSender(raw: string): number | "invalid" {
    const value = raw.trim().toLowerCase();
    if (!value || value === "unlimited") return "invalid";
    const n = Number(value);
    if (!Number.isInteger(n) || n < 1) return "invalid";
    return n;
  }

  function buildCampaignPayload() {
    const selectedIds = orderedSelectedSmtpIds(form.smtp_server_ids);
    const firstSelected = smtpServers.find((s) => selectedIds.includes(s.id));
    const emailsPerSender = parseEmailsPerSender(form.emails_per_sender);
    return {
      name: form.name,
      subject: form.subject,
      html_content: form.html_content,
      from_email: resolveFromEmail(
        firstSelected?.from_email || form.from_email || defaultFromEmail,
      ),
      from_name: firstSelected?.from_name || form.from_name,
      subscriber_list_id: form.subscriber_list_id,
      message_version_id: form.message_version_id || null,
      smtp_server_ids: selectedIds,
      emails_per_sender: emailsPerSender === "invalid" ? 1 : emailsPerSender,
    };
  }

  function toggleSmtpServer(id: string) {
    setForm((f) => {
      const exists = f.smtp_server_ids.includes(id);
      const rawIds = exists
        ? f.smtp_server_ids.filter((x) => x !== id)
        : [...f.smtp_server_ids, id];
      const smtp_server_ids = orderedSelectedSmtpIds(rawIds);
      const first = smtpServers.find((s) => smtp_server_ids.includes(s.id));
      return {
        ...f,
        smtp_server_ids,
        from_email: first?.from_email || f.from_email,
        from_name: first?.from_name || f.from_name,
      };
    });
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

  const loadData = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent ?? false;
    if (!silent) setIsLoading(true);
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
      if (!silent) {
        setError(err instanceof ApiClientError ? err.message : "Failed to load campaigns");
      }
    } finally {
      if (!silent) setIsLoading(false);
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
      // Only refresh the send timer from tracking when mail is still queued.
      // Do not clear an active countdown when opening tracking on a finished campaign.
      if ((result.send_summary?.pending ?? 0) > 0) {
        applySendSummaryToProgress(id, campaignName, result.send_summary);
      }
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
    if (!activeSendingId) {
      // Do not wipe an active local timer just because campaigns list
      // has not flipped to "sending" yet (race after Send click).
      // Poll / applySendSummaryToProgress clears it when pending hits 0.
      return;
    }

    const sendingName =
      campaigns.find((c) => c.id === activeSendingId)?.name || "Campaign";

    // Show timer immediately while the first poll loads queue stats.
    setSendProgress((current) => {
      if (current?.campaignId === activeSendingId) return current;
      const stored = loadStoppedAt(activeSendingId);
      const resumeSeconds =
        stoppedAtSecondsRef.current?.campaignId === activeSendingId
          ? stoppedAtSecondsRef.current.nextInSeconds
          : stored != null
            ? stored
            : sendDelaySeconds;
      if (stored != null) {
        stoppedAtSecondsRef.current = {
          campaignId: activeSendingId,
          nextInSeconds: stored,
        };
      }
      return {
        campaignId: activeSendingId,
        campaignName: sendingName,
        sent: 0,
        pending: 1,
        intervalSeconds: sendDelaySeconds,
        nextInSeconds: resumeSeconds,
      };
    });
  }, [activeSendingId, sendDelaySeconds]);

  // Poll queue + keep countdown while sendProgress has pending emails.
  useEffect(() => {
    if (!sendProgress || sendProgress.pending <= 0) {
      pollSendProgressRef.current = null;
      return;
    }
    const campaignId = sendProgress.campaignId;
    const campaignName = sendProgress.campaignName;

    const poll = () => {
      void loadData({ silent: true });
      void campaignsApi
        .fetchCampaignDeliveryStatus(campaignId)
        .then((result) => {
          applySendSummaryToProgress(
            campaignId,
            campaignName,
            result.send_summary,
          );
        })
        .catch(() => undefined);
    };

    pollSendProgressRef.current = poll;
    poll();
    const intervalId = window.setInterval(poll, 2000);
    return () => {
      if (pollSendProgressRef.current === poll) {
        pollSendProgressRef.current = null;
      }
      window.clearInterval(intervalId);
    };
  }, [sendProgress?.campaignId, sendProgress?.pending, loadData]);

  // Local countdown (e.g. 60→59→58→0); restarts when the next email is sent.
  // Always-on tick: only mutates state when a send is in progress (avoids effect churn).
  useEffect(() => {
    const tick = window.setInterval(() => {
      setSendProgress((current) => {
        if (!current || current.pending <= 0) return current;
        if (pausedCampaignIdRef.current === current.campaignId) return current;
        if (current.nextInSeconds <= 0) {
          pollSendProgressRef.current?.();
          return current;
        }
        const nextInSeconds = current.nextInSeconds - 1;
        if (nextInSeconds === 0) {
          pollSendProgressRef.current?.();
        }
        return { ...current, nextInSeconds };
      });
    }, 1000);
    return () => window.clearInterval(tick);
  }, []);

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
      setSmtpServers(active);
      setDefaultFromEmail(defaultServer?.from_email ?? "");
      setDefaultSmtpId(defaultServer?.id ?? null);
      return { defaultServer: defaultServer ?? null, active };
    } catch {
      return { defaultServer: null, active: [] as SmtpServer[] };
    }
  }

  async function applySendDelaySeconds(seconds: number) {
    const delay = Math.min(900, Math.max(60, Math.round(seconds) || 60));
    setSendDelaySeconds(delay);
    localStorage.setItem(SEND_DELAY_STORAGE_KEY, String(delay));
    // hourly_limit such that 3600/hourly ≈ delay (backend also enforces min 60s)
    const hourly = Math.max(1, Math.floor(3600 / delay));
    if (!defaultSmtpId) {
      const { defaultServer } = await loadDefaultSmtp();
      if (!defaultServer?.id) return delay;
      await smtpApi.updateSmtpServer(defaultServer.id, { hourly_limit: hourly });
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
      // Prefer the Wait-between value the user set in the UI.
      const interval = sendDelaySeconds || summary.send_interval_seconds || 60;
      setSendProgress((current) => {
        const same = current?.campaignId === campaignId;
        const prevSent = lastSentCountRef.current[campaignId] ?? current?.sent ?? 0;
        const emailJustSent = (summary.sent ?? 0) > prevSent;
        lastSentCountRef.current[campaignId] = summary.sent ?? 0;

        const stoppedAt =
          stoppedAtSecondsRef.current?.campaignId === campaignId
            ? stoppedAtSecondsRef.current.nextInSeconds
            : null;

        let nextIn = interval;

        if (emailJustSent) {
          nextIn = interval;
          if (stoppedAtSecondsRef.current?.campaignId === campaignId) {
            stoppedAtSecondsRef.current = null;
          }
          clearStoppedAt(campaignId);
        } else if (stoppedAt != null) {
          if (same && (current?.nextInSeconds ?? 0) > 0) {
            nextIn = current!.nextInSeconds;
          } else {
            nextIn = stoppedAt;
          }
        } else if (same && (current?.nextInSeconds ?? 0) > 0) {
          // Local 1s tick owns the countdown.
          nextIn = current!.nextInSeconds;
        } else if ((summary.next_send_in_seconds ?? 0) > 0) {
          nextIn = summary.next_send_in_seconds!;
        } else {
          nextIn = interval;
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
      clearStoppedAt(campaignId);
      if (stoppedAtSecondsRef.current?.campaignId === campaignId) {
        stoppedAtSecondsRef.current = null;
      }
      setSendProgress((current) =>
        current?.campaignId === campaignId ? null : current,
      );
    }
  }

  async function openCreate() {
    const [latestLists, smtpResult] = await Promise.all([
      reloadLists(),
      loadDefaultSmtp(),
      reloadMessages(),
    ]);
    const { defaultServer, active } = smtpResult;
    const selectedIds = active.map((s) => s.id);
    const first = active.find((s) => s.id === defaultServer?.id) ?? active[0];
    setEditingId(null);
    setForm({
      ...emptyForm,
      subscriber_list_id: latestLists[0]?.id ?? "",
      message_version_id: "",
      from_email: first?.from_email ?? defaultServer?.from_email ?? "",
      from_name: first?.from_name ?? defaultServer?.from_name ?? "",
      smtp_server_ids: selectedIds,
      emails_per_sender: "1",
    });
    setShowForm(true);
    setError("");
  }

  async function openEdit(campaign: Campaign) {
    const [latestLists, smtpResult] = await Promise.all([
      reloadLists(),
      loadDefaultSmtp(),
      reloadMessages(),
    ]);
    const { defaultServer, active } = smtpResult;
    const smtpDomain = defaultServer?.from_email?.split("@")[1] ?? "";
    const campaignDomain = campaign.from_email?.split("@")[1] ?? "";
    const fromEmailMismatch = Boolean(
      smtpDomain && campaignDomain && smtpDomain !== campaignDomain,
    );
    const savedIds = (campaign.smtp_server_ids || []).filter((id) =>
      active.some((s) => s.id === id),
    );
    const selectedIds = savedIds.length > 0 ? savedIds : active.map((s) => s.id);
    const first =
      active.find((s) => selectedIds.includes(s.id)) ?? defaultServer;
    setEditingId(campaign.id);
    setForm({
      name: campaign.name,
      subject: campaign.subject,
      from_name: campaign.from_name || first?.from_name || "",
      from_email: fromEmailMismatch
        ? defaultServer?.from_email ?? campaign.from_email
        : campaign.from_email || first?.from_email || "",
      html_content: campaign.html_content || emptyForm.html_content,
      subscriber_list_id: campaign.subscriber_list?.id ?? latestLists[0]?.id ?? "",
      message_version_id: campaign.message_version?.id ?? "",
      smtp_server_ids: selectedIds,
      emails_per_sender: String(campaign.emails_per_sender || 1),
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
    if (smtpServers.length > 0 && form.smtp_server_ids.length === 0) {
      setError("Select at least one sender.");
      return;
    }
    if (parseEmailsPerSender(form.emails_per_sender) === "invalid") {
      setError("Emails per sender must be a number (e.g. 1, 20).");
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
    const progress = sendProgressRef.current;
    const remaining =
      progress?.campaignId === id ? Math.max(0, progress.nextInSeconds) : null;
    try {
      setError("");
      if (remaining != null) {
        stoppedAtSecondsRef.current = {
          campaignId: id,
          nextInSeconds: remaining,
        };
        saveStoppedAt(id, remaining);
      }
      await campaignsApi.pauseCampaign(id);
      // Freeze timer at remaining seconds — do not clear sendProgress.
      setCampaigns((prev) =>
        prev.map((c) => (c.id === id ? { ...c, status: "paused" as const } : c)),
      );
      setSendProgress((current) =>
        current?.campaignId === id && remaining != null
          ? { ...current, nextInSeconds: remaining }
          : current,
      );
      setNotice("Sending stopped. Use Resume Send to continue.");
      await loadData({ silent: true });
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
    if (smtpServers.length > 0 && form.smtp_server_ids.length === 0) {
      setError("Select at least one sender.");
      return false;
    }
    if (parseEmailsPerSender(form.emails_per_sender) === "invalid") {
      setError("Emails per sender must be a number (e.g. 1, 20).");
      return false;
    }
    try {
      const payload = buildCampaignPayload();
      await campaignsApi.updateCampaign(id, {
        name: payload.name,
        subject: payload.subject,
        from_name: payload.from_name,
        from_email: payload.from_email,
        html_content: payload.html_content,
        subscriber_list_id: payload.subscriber_list_id,
        message_version_id: payload.message_version_id,
        smtp_server_ids: payload.smtp_server_ids,
        emails_per_sender: payload.emails_per_sender,
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
      clearStoppedAt(sentId);
      stoppedAtSecondsRef.current = null;
      const pending = result.send_summary?.pending ?? 0;
      const stillSending =
        pending > 0 || result.campaign?.status === "sending";
      const interval = sendDelaySeconds;
      if (stillSending) {
        setSendProgress({
          campaignId: sentId,
          campaignName: form.name || "Campaign",
          sent: result.send_summary?.sent ?? 0,
          pending: Math.max(pending, 1),
          intervalSeconds: interval,
          nextInSeconds: interval,
        });
        lastSentCountRef.current[sentId] = result.send_summary?.sent ?? 0;
      }
      await loadData({ silent: true });
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
    const storedStopped = loadStoppedAt(id);
    const resumeFromSeconds =
      campaign.status === "paused"
        ? stoppedAtSecondsRef.current?.campaignId === id
          ? stoppedAtSecondsRef.current.nextInSeconds
          : sendProgress?.campaignId === id
            ? sendProgress.nextInSeconds
            : storedStopped
        : null;
    if (resumeFromSeconds != null) {
      stoppedAtSecondsRef.current = {
        campaignId: id,
        nextInSeconds: resumeFromSeconds,
      };
      saveStoppedAt(id, resumeFromSeconds);
    }
    try {
      await applySendDelaySeconds(sendDelaySeconds);
      const result = await campaignsApi.sendCampaign(
        id,
        resumeFromSeconds != null ? { resume_delay_seconds: resumeFromSeconds } : undefined,
      );
      setShowForm(false);
      setEditingId(null);
      setForm(emptyForm);
      setNotice(formatSendResult(result));
      // Show timer immediately after send/resume (before polls catch up).
      const pending = result.send_summary?.pending ?? 0;
      const stillSending =
        pending > 0 || result.campaign?.status === "sending";
      const interval = sendDelaySeconds;
      if (stillSending) {
        setSendProgress({
          campaignId: id,
          campaignName: campaign.name,
          sent: result.send_summary?.sent ?? 0,
          pending: Math.max(pending, 1),
          intervalSeconds: interval,
          nextInSeconds:
            resumeFromSeconds != null ? resumeFromSeconds : interval,
        });
        lastSentCountRef.current[id] = result.send_summary?.sent ?? 0;
      }
      if (resumeFromSeconds != null) {
        // Keep saved stop seconds until the next email actually sends.
        stoppedAtSecondsRef.current = {
          campaignId: id,
          nextInSeconds: resumeFromSeconds,
        };
      }
      await loadData({ silent: true });
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
    if (smtpServers.length > 0 && form.smtp_server_ids.length === 0) {
      setError("Select at least one sender.");
      return;
    }
    if (parseEmailsPerSender(form.emails_per_sender) === "invalid") {
      setError("Emails per sender must be a number (e.g. 1, 20).");
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
      const pending = result.send_summary?.pending ?? 0;
      const stillSending =
        pending > 0 || result.campaign?.status === "sending";
      const interval = sendDelaySeconds;
      if (stillSending) {
        setSendProgress({
          campaignId: created.campaign.id,
          campaignName: created.campaign.name,
          sent: result.send_summary?.sent ?? 0,
          pending: Math.max(pending, 1),
          intervalSeconds: interval,
          nextInSeconds: interval,
        });
        lastSentCountRef.current[created.campaign.id] =
          result.send_summary?.sent ?? 0;
      }
      if (result.send_summary?.failed) {
        setError(formatSendResult(result));
      }
      await loadData({ silent: true });
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Send failed");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="space-y-6">
      {!defaultFromEmail && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-800">
          <p className="font-medium">Step 1: Add your domain sending email</p>
          <p className="mt-1 text-xs text-amber-700">
            Go to <strong>SMTP</strong> → Add server → set <strong>From email</strong> to your
            mailbox (e.g. info@datrixworld.com) → Test → Set default. Then create a campaign here.
          </p>
        </div>
      )}

      {defaultFromEmail && (
        <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-800">
          <p className="font-medium">Domain → Gmail sending</p>
          <p className="mt-1 text-xs text-indigo-700/90">
            <strong>From (sender):</strong>{" "}
            <span className="font-mono text-indigo-900">{defaultFromEmail}</span> — your domain
            mailbox only, not @gmail.com.
            <br />
            <strong>To (emails):</strong> Pick an email list below. Emails send one by
            one. Manage emails on the Emails page (not @example.com).
          </p>
        </div>
      )}

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

      {sendProgress && sendProgress.pending > 0 && (
        <div className="fixed right-4 top-24 z-[60] w-56 rounded-xl border-2 border-amber-500 bg-white p-4 shadow-xl shadow-slate-200">
          <p className="text-xs font-medium uppercase tracking-wide text-amber-700">
            {pausedCampaignId === sendProgress.campaignId ? "Send timer (paused)" : "Send timer"}
          </p>
          <p className="mt-1 truncate text-sm text-slate-700">{sendProgress.campaignName}</p>
          <p className="mt-3 text-center text-5xl font-bold tabular-nums text-slate-900">
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
            disabled={pausedCampaignId === sendProgress.campaignId}
            className="mt-4 w-full rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pausedCampaignId === sendProgress.campaignId ? "Stopped" : "Stop"}
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
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
            className="w-32 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
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
            className="w-24 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
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
            <p className="mt-2 text-3xl font-bold text-slate-900">{stats.total}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Drafts</p>
            <p className="mt-2 text-3xl font-bold text-slate-700">{stats.draft}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Scheduled</p>
            <p className="mt-2 text-3xl font-bold text-indigo-600">{stats.scheduled}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Sent</p>
            <p className="mt-2 text-3xl font-bold text-emerald-600">{stats.sent}</p>
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
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
          />
          <Button onClick={openCreate}>+ New Campaign</Button>
          {selectedCampaignIds.length > 0 && (
            <Button variant="danger" onClick={() => void handleDeleteSelected()}>
              Delete Selected ({selectedCampaignIds.length})
            </Button>
          )}
        </div>

        {!isLoading && campaigns.length > 0 && campaigns.every((c) => c.status === "sent") && (
          <div className="mb-4 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-800">
            Your campaign was already sent. Click the green{" "}
            <span className="font-semibold text-emerald-700">Send Again</span> button in the
            table to resend, or use <span className="font-semibold">+ New Campaign</span> above.
          </div>
        )}

        {showForm && (
          <form
            onSubmit={handleSubmit}
            className="mb-6 rounded-lg border border-slate-300 bg-slate-50 p-4"
          >
            <h3 className="mb-4 text-sm font-semibold text-slate-900">
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
              <div className="sm:col-span-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                From name: each selected sender uses its own name (from Sender page) —
                e.g. Ava Jackson with ava@…, Mia Anderson with mia@….
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Senders <span className="text-red-600">*</span>
                </label>
                {smtpServers.length > 0 ? (
                  <div className="max-h-48 space-y-2 overflow-y-auto rounded-lg border border-slate-300 bg-white p-3">
                    {smtpServers.map((server) => {
                      const checked = form.smtp_server_ids.includes(server.id);
                      return (
                        <label
                          key={server.id}
                          className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 hover:bg-slate-50"
                        >
                          <input
                            type="checkbox"
                            className="mt-1"
                            checked={checked}
                            onChange={() => toggleSmtpServer(server.id)}
                          />
                          <span className="min-w-0">
                            <span className="block text-sm font-medium text-slate-900">
                              {server.from_email || server.name}
                              {server.is_default ? (
                                <span className="ml-2 text-xs font-normal text-slate-500">
                                  default
                                </span>
                              ) : null}
                            </span>
                            <span className="block truncate text-xs text-slate-500">
                              {server.from_name || server.name}
                              {server.name && server.from_email
                                ? ` · ${server.name}`
                                : ""}
                            </span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                ) : (
                  <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-700">
                    No active senders. Add SMTP senders on the Sender page.
                  </p>
                )}
                <p className="mt-1 text-xs text-slate-500">
                  Selected senders are used in rotation.{" "}
                  {form.smtp_server_ids.length} selected
                  {sendingDomain ? ` · domain @${sendingDomain}` : ""}.
                </p>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Emails per sender
                </label>
                <input
                  type="text"
                  value={form.emails_per_sender}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, emails_per_sender: e.target.value }))
                  }
                  placeholder="20"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900"
                />
                <p className="mt-1 text-xs text-slate-500">
                  Upar wala sender pehle N list emails, phir next sender agli N. Har
                  sender ek baar N → stop. Baqi Waiting pe Resume / Send Again se next
                  batch.
                </p>
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Email list <span className="text-red-600">*</span>
                </label>
                {lists.length > 0 && (
                  <select
                    required
                    value={form.subscriber_list_id}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, subscriber_list_id: e.target.value }))
                    }
                    className="mb-3 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900"
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
                  <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-700">
                    No email lists found. Create lists and add emails from the
                    Emails page.
                  </p>
                )}
                {form.subscriber_list_id && (
                  <div className="mt-3 rounded-lg border border-slate-300 bg-slate-50 p-3">
                    <p className="text-sm text-slate-700">
                      Emails in list:{" "}
                      <span className="text-slate-800">
                        {selectedList?.total_emails ?? recipientCount} total
                      </span>
                      {" · "}
                      <span className="text-emerald-600">
                        {selectedList?.sent_emails ?? 0} sent
                      </span>
                      {" · "}
                      <span className="text-amber-700">
                        {selectedList?.waiting_emails ?? deliverableCount} waiting
                      </span>
                      {fakeRecipientCount > 0 && (
                        <span className="text-amber-600">
                          {" "}
                          ({fakeRecipientCount} fake @example.com — will not receive mail)
                        </span>
                      )}
                    </p>
                    <p className="mt-2 text-xs text-slate-500">
                      Send only queues <span className="text-amber-800">Waiting</span> emails.
                      Already sent addresses are skipped. Manage lists on the{" "}
                      <span className="text-slate-400">Emails</span> page.
                    </p>
                    {deliverableCount === 0 && (
                      <p className="mt-2 text-xs text-amber-600">
                        This list has no sendable emails. Add real addresses on the Emails page.
                      </p>
                    )}
                    <div className="mt-3 max-h-48 overflow-auto rounded-lg border border-slate-200">
                      {isLoadingRecipients ? (
                        <p className="px-3 py-2 text-xs text-slate-500">Loading list emails…</p>
                      ) : listRecipients.length === 0 ? (
                        <p className="px-3 py-2 text-xs text-slate-500">No emails in this list.</p>
                      ) : (
                        <ul className="divide-y divide-slate-200 text-sm">
                          {listRecipients.map((sub) => (
                            <li
                              key={sub.id}
                              className="flex items-center justify-between gap-3 px-3 py-2"
                            >
                              <span className="truncate text-slate-800">{sub.email}</span>
                              <span
                                className={`shrink-0 text-xs ${
                                  sub.send_status === "sent"
                                    ? "text-emerald-600"
                                    : "text-amber-700"
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
                    className="w-24 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900"
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
                      <label className="mb-1 block text-xs font-medium text-indigo-800">
                        Send test email (before full campaign)
                      </label>
                      <input
                        type="email"
                        value={testEmail}
                        onChange={(e) => setTestEmail(e.target.value)}
                        placeholder="yourname@gmail.com"
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                      />
                    </div>
                    <Button type="submit" isLoading={isTestSending} className="shrink-0">
                      Send test
                    </Button>
                  </form>
                )}
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
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
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900"
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
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  HTML content
                </label>
                <textarea
                  rows={5}
                  value={form.html_content}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, html_content: e.target.value }))
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
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
            <h3 className="mb-3 text-sm font-semibold text-indigo-700">Schedule Campaign</h3>
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
                <tr className="border-b border-slate-200 text-slate-500">
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
                  <tr key={c.id} className="border-b border-slate-200/60">
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
                    <td className="py-3 pr-4 font-medium text-slate-800">{c.name}</td>
                    <td className="py-3 pr-4 text-slate-400">{c.subject || "—"}</td>
                    <td className="py-3 pr-4 text-slate-500">
                      {c.subscriber_list?.name ?? (
                        <span className="text-amber-600">No list — edit to add</span>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusColors[c.status]}`}
                      >
                        {c.status}
                      </span>
                      {c.status === "sending" && (
                        <p className="mt-1 text-xs text-amber-700">
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
                              className="text-xs text-indigo-600 hover:underline"
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
                              className="text-xs text-indigo-600 hover:underline"
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
                              className="text-xs text-indigo-600 hover:underline"
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
                              className="text-xs text-amber-600 hover:underline"
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
                              className="text-xs text-indigo-600 hover:underline"
                            >
                              Tracking
                            </button>
                            <button
                              type="button"
                              onClick={() => handleStopSending(c.id)}
                              className="rounded-md bg-red-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-red-500"
                            >
                              Stop
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
                              className="text-xs text-indigo-600 hover:underline"
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
                              className="text-xs text-indigo-600 hover:underline"
                            >
                              Tracking
                            </button>
                            <button
                              type="button"
                              onClick={() => handleEditCopy(c.id)}
                              className="text-xs text-indigo-600 hover:underline"
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
                            className="text-xs text-red-600 hover:underline"
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
          <div className="max-h-[85vh] w-full max-w-3xl overflow-hidden rounded-xl border border-slate-300 bg-slate-50 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">Email Tracking</h3>
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
                className="mr-3 text-xs text-indigo-600 hover:underline"
              >
                Refresh
              </button>
              <button
                type="button"
                onClick={() => {
                  setTrackingId(null);
                  setTrackingData(null);
                }}
                className="text-slate-400 hover:text-slate-900"
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
                      <tr className="border-b border-slate-200 text-slate-500">
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
                                ? "Waiting"
                                : row.queue_status === "sending"
                                  ? "Sending…"
                                  : row.queue_status === "pending"
                                    ? "Waiting"
                                    : "Waiting";
                        const sendClass =
                          row.queue_status === "sent"
                            ? "text-emerald-600"
                            : row.queue_status === "failed"
                              ? "text-red-600"
                              : row.queue_status === "sending"
                                ? "text-amber-700"
                                : "text-amber-700";
                        return (
                          <tr key={row.email} className="border-b border-slate-200/60">
                            <td className="py-2 pr-3 text-slate-800">{row.email}</td>
                            <td className={`py-2 pr-3 font-medium ${sendClass}`}>{sendLabel}</td>
                            <td className="py-2">
                              {row.opened ? (
                                <span className="text-emerald-600">Yes</span>
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

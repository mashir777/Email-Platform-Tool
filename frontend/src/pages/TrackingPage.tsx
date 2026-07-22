import { useCallback, useEffect, useState } from "react";

import * as campaignsApi from "@/api/campaigns";
import type { CampaignDeliveryTracking } from "@/api/campaigns";
import { ApiClientError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { Campaign } from "@/types/campaigns";

function sendLabel(status: string): { text: string; className: string } {
  if (status === "sent") return { text: "Sent", className: "text-emerald-600" };
  if (status === "failed") return { text: "Fail", className: "text-red-600" };
  if (status === "sending") return { text: "Sending…", className: "text-amber-700" };
  if (status === "skipped") return { text: "Skipped", className: "text-slate-500" };
  return { text: "Pending", className: "text-slate-400" };
}

export function TrackingPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tracking, setTracking] = useState<CampaignDeliveryTracking | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isTrackingLoading, setIsTrackingLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedCampaignIds, setSelectedCampaignIds] = useState<string[]>([]);

  const loadCampaigns = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const result = await campaignsApi.fetchCampaigns();
      const trackable = result.campaigns.filter((c) =>
        ["sent", "sending"].includes(c.status),
      );
      setCampaigns(trackable);
      if (!selectedId && trackable[0]) {
        setSelectedId(trackable[0].id);
      }
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load campaigns");
    } finally {
      setIsLoading(false);
    }
  }, [selectedId]);

  const loadTracking = useCallback(async (id: string, showSpinner = true) => {
    if (showSpinner) setIsTrackingLoading(true);
    try {
      const result = await campaignsApi.fetchCampaignDeliveryStatus(id);
      setTracking(result.tracking);
    } catch (err) {
      if (showSpinner) {
        setError(err instanceof ApiClientError ? err.message : "Could not load tracking");
        setTracking(null);
      }
    } finally {
      if (showSpinner) setIsTrackingLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCampaigns();
  }, [loadCampaigns]);

  useEffect(() => {
    if (!selectedId) {
      setTracking(null);
      return;
    }
    void loadTracking(selectedId, true);
  }, [selectedId, loadTracking]);

  useEffect(() => {
    if (!selectedId) return;
    const timer = window.setInterval(() => {
      void loadTracking(selectedId, false);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [selectedId, loadTracking]);

  async function handleDeleteCampaign(id: string) {
    if (!confirm("Delete this tracking campaign?")) return;
    try {
      await campaignsApi.deleteCampaign(id);
      setSelectedCampaignIds((current) => current.filter((item) => item !== id));
      if (selectedId === id) {
        setSelectedId(null);
        setTracking(null);
      }
      await loadCampaigns();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Delete failed");
    }
  }

  async function handleDeleteSelected() {
    if (
      selectedCampaignIds.length === 0 ||
      !confirm(`Delete ${selectedCampaignIds.length} selected tracking campaign(s)?`)
    ) return;
    try {
      await Promise.all(
        selectedCampaignIds.map((id) => campaignsApi.deleteCampaign(id)),
      );
      if (selectedId && selectedCampaignIds.includes(selectedId)) {
        setSelectedId(null);
        setTracking(null);
      }
      setSelectedCampaignIds([]);
      await loadCampaigns();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Delete failed");
      await loadCampaigns();
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-400">
          Opened emails update when the email is opened and Gmail loads images (pytracking).
        </p>
        <Button
          type="button"
          onClick={() => {
            void loadCampaigns();
            if (selectedId) void loadTracking(selectedId, true);
          }}
        >
          Refresh
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <Card className="h-fit p-0 overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <label className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                <input
                  type="checkbox"
                  aria-label="Select all tracking campaigns"
                  checked={
                    campaigns.length > 0 &&
                    selectedCampaignIds.length === campaigns.length
                  }
                  onChange={(event) =>
                    setSelectedCampaignIds(
                      event.target.checked ? campaigns.map((campaign) => campaign.id) : [],
                    )
                  }
                />
                Campaigns
              </label>
              {selectedCampaignIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => void handleDeleteSelected()}
                  className="text-xs text-red-600 hover:text-red-700"
                >
                  Delete Selected
                </button>
              )}
            </div>
          </div>
          {isLoading ? (
            <p className="px-4 py-6 text-sm text-slate-500">Loading…</p>
          ) : campaigns.length === 0 ? (
            <p className="px-4 py-6 text-sm text-slate-500">
              No sent campaigns yet. Send a campaign first.
            </p>
          ) : (
            <ul className="max-h-[70vh] overflow-auto divide-y divide-slate-200">
              {campaigns.map((c) => (
                <li key={c.id} className="flex items-center">
                  <input
                    type="checkbox"
                    aria-label={`Select ${c.name}`}
                    checked={selectedCampaignIds.includes(c.id)}
                    onChange={(event) =>
                      setSelectedCampaignIds((current) =>
                        event.target.checked
                          ? [...current, c.id]
                          : current.filter((id) => id !== c.id),
                      )
                    }
                    className="ml-4"
                  />
                  <button
                    type="button"
                    onClick={() => setSelectedId(c.id)}
                    className={`min-w-0 flex-1 px-3 py-3 text-left text-sm transition ${
                      selectedId === c.id
                        ? "bg-indigo-50 text-indigo-800"
                        : "text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    <span className="block truncate font-medium">{c.name}</span>
                    <span className="mt-0.5 block text-xs capitalize text-slate-500">
                      {c.status}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDeleteCampaign(c.id)}
                    className="mr-4 text-xs text-red-600 hover:text-red-700"
                  >
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          {!selectedId ? (
            <p className="text-sm text-slate-500">Select a campaign to view tracking.</p>
          ) : isTrackingLoading && !tracking ? (
            <p className="text-sm text-slate-500">Loading tracking…</p>
          ) : tracking ? (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">{tracking.campaign_name}</h3>
                <p className="text-sm text-slate-400">
                  {tracking.opened}/{tracking.delivered} opened emails ({tracking.open_rate}%)
                </p>
                {tracking.note && (
                  <p className="mt-2 text-xs text-slate-500">{tracking.note}</p>
                )}
              </div>

              <div className="overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500">
                      <th className="pb-2 pr-3 font-medium">Email</th>
                      <th className="pb-2 pr-3 font-medium">Sent Emails</th>
                      <th className="pb-2 font-medium">Opened Emails</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tracking.recipients.map((row) => {
                      const send = sendLabel(row.queue_status);
                      return (
                        <tr key={row.email} className="border-b border-slate-200/60">
                          <td className="py-2.5 pr-3 text-slate-800">{row.email}</td>
                          <td className={`py-2.5 pr-3 font-medium ${send.className}`}>
                            {send.text}
                          </td>
                          <td className="py-2.5">
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
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">No tracking data.</p>
          )}
        </Card>
      </div>
    </div>
  );
}

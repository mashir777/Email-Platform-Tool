import { useCallback, useEffect, useState } from "react";

import * as reportsApi from "@/api/reports";
import { ApiClientError } from "@/api/client";
import { Card } from "@/components/ui/Card";
import type { CampaignReport, ReportOverview } from "@/types/reports";

function formatRate(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function ReportsPage() {
  const [overview, setOverview] = useState<ReportOverview | null>(null);
  const [reports, setReports] = useState<CampaignReport[]>([]);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [overviewRes, reportsRes] = await Promise.all([
        reportsApi.fetchReportOverview(),
        reportsApi.fetchCampaignReports({ search: search || undefined }),
      ]);
      setOverview(overviewRes.overview);
      setReports(reportsRes.reports);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load reports");
    } finally {
      setIsLoading(false);
    }
  }, [search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {overview && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Card>
            <p className="text-sm text-slate-400">Emails Sent</p>
            <p className="mt-2 text-3xl font-bold text-white">{overview.sent}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Open Rate</p>
            <p className="mt-2 text-3xl font-bold text-emerald-400">
              {formatRate(overview.open_rate)}
            </p>
            <p className="mt-1 text-xs text-slate-500">{overview.opened} opens</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Click Rate</p>
            <p className="mt-2 text-3xl font-bold text-indigo-400">
              {formatRate(overview.click_rate)}
            </p>
            <p className="mt-1 text-xs text-slate-500">{overview.clicked} clicks</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Bounce Rate</p>
            <p className="mt-2 text-3xl font-bold text-red-400">
              {formatRate(overview.bounce_rate)}
            </p>
            <p className="mt-1 text-xs text-slate-500">{overview.bounced} bounces</p>
          </Card>
        </div>
      )}

      {overview && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Card>
            <p className="text-sm text-slate-400">Delivered</p>
            <p className="mt-2 text-2xl font-bold text-slate-200">{overview.delivered}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Complaints</p>
            <p className="mt-2 text-2xl font-bold text-amber-400">{overview.complaints}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Unsubscribes</p>
            <p className="mt-2 text-2xl font-bold text-slate-400">{overview.unsubscribed}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Campaigns Tracked</p>
            <p className="mt-2 text-2xl font-bold text-indigo-300">
              {overview.campaigns_tracked}
            </p>
          </Card>
        </div>
      )}

      <Card title="Campaign Performance">
        <div className="mb-4">
          <input
            type="search"
            placeholder="Search campaigns..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 sm:max-w-md"
          />
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
          </div>
        ) : reports.length === 0 ? (
          <p className="py-12 text-center text-sm text-slate-500">
            No campaign reports yet. Data appears after campaigns are sent and tracked.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500">
                  <th className="pb-3 pr-4 font-medium">Campaign</th>
                  <th className="pb-3 pr-4 font-medium">Status</th>
                  <th className="pb-3 pr-4 font-medium">Sent</th>
                  <th className="pb-3 pr-4 font-medium">Opens</th>
                  <th className="pb-3 pr-4 font-medium">Clicks</th>
                  <th className="pb-3 pr-4 font-medium">Bounces</th>
                  <th className="pb-3 font-medium">Open Rate</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((report) => (
                  <tr key={report.campaign_id} className="border-b border-slate-800/60">
                    <td className="py-3 pr-4">
                      <div className="font-medium text-slate-200">{report.campaign_name}</div>
                      <div className="text-xs text-slate-500">{report.subject || "—"}</div>
                    </td>
                    <td className="py-3 pr-4 capitalize text-slate-400">{report.status}</td>
                    <td className="py-3 pr-4 text-slate-400">{report.sent}</td>
                    <td className="py-3 pr-4 text-emerald-400">{report.opened}</td>
                    <td className="py-3 pr-4 text-indigo-400">{report.clicked}</td>
                    <td className="py-3 pr-4 text-red-400">{report.bounced}</td>
                    <td className="py-3 text-slate-300">{formatRate(report.open_rate)}</td>
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

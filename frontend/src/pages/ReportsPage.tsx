import { useCallback, useEffect, useState } from "react";

import * as reportsApi from "@/api/reports";
import { ApiClientError } from "@/api/client";
import { Card } from "@/components/ui/Card";
import type {
  CampaignReport,
  DailyReport,
  DailyReportDetail,
  ReportOverview,
} from "@/types/reports";

function formatRate(value: number): string {
  return `${value.toFixed(1)}%`;
}

function formatDisplayDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-");
  if (!year || !month || !day) return isoDate;
  return `${day}-${month}-${year}`;
}

export function ReportsPage() {
  const [overview, setOverview] = useState<ReportOverview | null>(null);
  const [reports, setReports] = useState<CampaignReport[]>([]);
  const [daily, setDaily] = useState<DailyReport | null>(null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [dayDetail, setDayDetail] = useState<DailyReportDetail | null>(null);
  const [isDayLoading, setIsDayLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [overviewRes, reportsRes, dailyRes] = await Promise.all([
        reportsApi.fetchReportOverview(),
        reportsApi.fetchCampaignReports({ search: search || undefined }),
        reportsApi.fetchDailyReport(),
      ]);
      setOverview(overviewRes.overview);
      setReports(reportsRes.reports);
      setDaily(dailyRes.daily);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load reports");
    } finally {
      setIsLoading(false);
    }
  }, [search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function openDayDetail(day: string) {
    setSelectedDay(day);
    setIsDayLoading(true);
    setError("");
    try {
      const result = await reportsApi.fetchDailyReportDetail(day);
      setDayDetail(result.day);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load day detail");
      setDayDetail(null);
    } finally {
      setIsDayLoading(false);
    }
  }

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

      <Card
        title="Daily Email Activity"
        description="Opens count on the day the email was sent — even if opened weeks later"
      >
        {isLoading && !daily ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
          </div>
        ) : !daily || daily.days.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">
            No daily send data yet. After you send campaigns, each day appears here.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500">
                  <th className="pb-3 pr-4 font-medium">Date</th>
                  <th className="pb-3 pr-4 font-medium">Sent Emails</th>
                  <th className="pb-3 pr-4 font-medium">Opened Emails</th>
                  <th className="pb-3 pr-4 font-medium">Waiting</th>
                  <th className="pb-3 pr-4 font-medium">Open Rate</th>
                  <th className="pb-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {daily.days.map((row) => (
                  <tr key={row.date} className="border-b border-slate-800/60">
                    <td className="py-3 pr-4 font-medium text-slate-200">
                      {formatDisplayDate(row.date)}
                    </td>
                    <td className="py-3 pr-4 text-slate-300">{row.sent}</td>
                    <td className="py-3 pr-4 text-emerald-400">{row.opened}</td>
                    <td className="py-3 pr-4 text-amber-300">{row.waiting}</td>
                    <td className="py-3 pr-4 text-slate-400">{formatRate(row.open_rate)}</td>
                    <td className="py-3 text-right">
                      <button
                        type="button"
                        onClick={() => void openDayDetail(row.date)}
                        className="text-xs text-indigo-400 hover:underline"
                      >
                        View list
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {selectedDay && (
        <Card
          title={`Emails sent ${formatDisplayDate(selectedDay)}`}
          description="Opened updates here whenever someone opens — even months later"
        >
          <div className="mb-3 flex justify-end">
            <button
              type="button"
              onClick={() => {
                setSelectedDay(null);
                setDayDetail(null);
              }}
              className="text-xs text-slate-400 hover:text-white"
            >
              Close
            </button>
          </div>
          {isDayLoading ? (
            <p className="py-6 text-center text-sm text-slate-500">Loading…</p>
          ) : !dayDetail ? (
            <p className="py-6 text-center text-sm text-slate-500">No emails for this day.</p>
          ) : (
            <>
              <p className="mb-4 text-sm text-slate-400">
                Sent {dayDetail.sent} · Opened {dayDetail.opened} · Waiting {dayDetail.waiting} (
                {formatRate(dayDetail.open_rate)})
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-500">
                      <th className="pb-3 pr-4 font-medium">Email</th>
                      <th className="pb-3 pr-4 font-medium">Campaign</th>
                      <th className="pb-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dayDetail.emails.map((row) => (
                      <tr key={row.queue_item_id} className="border-b border-slate-800/60">
                        <td className="py-3 pr-4 text-slate-200">{row.email}</td>
                        <td className="py-3 pr-4 text-slate-400">{row.campaign_name}</td>
                        <td className="py-3">
                          {row.opened ? (
                            <span className="text-emerald-400">Opened</span>
                          ) : (
                            <span className="text-amber-300">Waiting</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Card>
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

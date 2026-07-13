import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchCampaignStats } from "@/api/campaigns";
import { fetchStats } from "@/api/subscribers";
import { Card } from "@/components/ui/Card";
import { useAuth } from "@/context/AuthContext";

export function DashboardPage() {
  const { user } = useAuth();
  const [subscriberTotal, setSubscriberTotal] = useState<string>("—");
  const [campaignTotal, setCampaignTotal] = useState<string>("—");

  const greeting = user?.first_name ? `Welcome, ${user.first_name}` : "Welcome back";

  useEffect(() => {
    fetchStats()
      .then((res) => setSubscriberTotal(String(res.stats.total)))
      .catch(() => setSubscriberTotal("—"));
    fetchCampaignStats()
      .then((res) => setCampaignTotal(String(res.stats.total)))
      .catch(() => setCampaignTotal("—"));
  }, []);

  const stats = [
    { label: "Subscribers", value: subscriberTotal, hint: "Live from API" },
    { label: "Campaigns", value: campaignTotal, hint: "Live from API" },
    { label: "Emails Sent", value: "—", hint: "Phase 9" },
    { label: "Open Rate", value: "—", hint: "Phase 11" },
  ];

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="text-lg font-semibold text-white">{greeting}</h2>
        <p className="mt-1 text-sm text-slate-400">
          Your email marketing command center.
        </p>
        {!user?.is_verified && (
          <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            Your email is not verified yet. Some features may be restricted until
            verification is complete.
          </div>
        )}
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <p className="text-sm text-slate-400">{stat.label}</p>
            <p className="mt-2 text-3xl font-bold text-white">{stat.value}</p>
            <p className="mt-1 text-xs text-slate-500">{stat.hint}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Quick Actions" description="Shortcuts to key modules">
          <ul className="space-y-2 text-sm text-slate-400">
            <li>
              • <Link to="/subscribers" className="text-indigo-400 hover:underline">Manage subscribers and lists</Link>
            </li>
            <li>• Build and schedule campaigns</li>
            <li>• Configure SMTP and domains</li>
            <li>• View delivery reports</li>
          </ul>
        </Card>
        <Card title="Account" description="Your current session">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Email</dt>
              <dd className="text-slate-200">{user?.email}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Role</dt>
              <dd className="capitalize text-slate-200">
                {user?.role.replace("_", " ")}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Company</dt>
              <dd className="text-slate-200">{user?.company_name || "—"}</dd>
            </div>
          </dl>
        </Card>
      </div>
    </div>
  );
}

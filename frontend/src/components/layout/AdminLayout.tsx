import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { navItems } from "@/config/navigation";

const pageMeta: Record<string, { title: string; subtitle?: string }> = {
  "/dashboard": {
    title: "Dashboard",
    subtitle: "Overview of your email marketing platform",
  },
  "/subscribers": {
    title: "Lists",
    subtitle: "Manage your email lists",
  },
  "/messages": {
    title: "Messages",
    subtitle: "Purpose-based email messages with V1, V2, and V3",
  },
  "/campaigns": {
    title: "Campaigns",
    subtitle: "Create and manage email campaigns",
  },
  "/unibox": {
    title: "Inbox",
    subtitle: "Replies from all sending mailboxes in one place",
  },
  "/warmup": {
    title: "Warmup",
    subtitle: "Add mailboxes and ramp daily sending gradually",
  },
  "/tracking": {
    title: "Tracking",
    subtitle: "See delivery and open status for each email",
  },
  "/smtp": {
    title: "SMTP Providers",
    subtitle: "Configure delivery servers and credentials",
  },
  "/domains": {
    title: "Domains",
    subtitle: "Manage sending domains and DNS verification",
  },
  "/sender": {
    title: "Sender",
    subtitle: "Add and manage From addresses for campaigns",
  },
  "/reports": {
    title: "Reports",
    subtitle: "Daily sent emails, opens, and campaign performance",
  },
  "/settings": {
    title: "Settings",
    subtitle: "Account and platform preferences",
  },
};

export function AdminLayout() {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const meta = pageMeta[location.pathname] ?? { title: "Email Platform" };

  return (
    <div className="flex min-h-screen bg-white text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="hidden md:flex md:shrink-0">
        <Sidebar />
      </div>

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/40"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close menu overlay"
          />
          <div className="relative h-full w-64">
            <Sidebar onNavigate={() => setSidebarOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <Header
          title={meta.title}
          subtitle={meta.subtitle}
          onMenuClick={() => setSidebarOpen(true)}
        />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function getNavLabel(path: string): string {
  return navItems.find((item) => item.path === path)?.label ?? "Page";
}

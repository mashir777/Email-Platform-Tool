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
    title: "Subscribers",
    subtitle: "Manage your contact lists and audiences",
  },
  "/campaigns": {
    title: "Campaigns",
    subtitle: "Create and manage email campaigns",
  },
  "/smtp": {
    title: "SMTP Providers",
    subtitle: "Configure delivery servers and credentials",
  },
  "/domains": {
    title: "Domains",
    subtitle: "Manage sending domains and DNS verification",
  },
  "/reports": {
    title: "Reports",
    subtitle: "Analytics and performance insights",
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
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <div className="hidden md:flex md:shrink-0">
        <Sidebar />
      </div>

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/60"
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

import type { ComponentType } from "react";
import { NavLink } from "react-router-dom";

import {
  IconChart,
  IconDashboard,
  IconEye,
  IconGlobe,
  IconLogout,
  IconMail,
  IconMessages,
  IconServer,
  IconSettings,
  IconUsers,
} from "@/components/icons";
import { navItems, type NavIcon } from "@/config/navigation";
import { useAuth } from "@/context/AuthContext";

const iconMap: Record<NavIcon, ComponentType<{ className?: string }>> = {
  dashboard: IconDashboard,
  users: IconUsers,
  messages: IconMessages,
  mail: IconMail,
  eye: IconEye,
  server: IconServer,
  globe: IconGlobe,
  chart: IconChart,
  settings: IconSettings,
};

interface SidebarProps {
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  const { user, logout } = useAuth();

  const displayName =
    user?.first_name || user?.last_name
      ? `${user.first_name} ${user.last_name}`.trim()
      : user?.email;

  return (
    <aside className="flex h-full w-64 flex-col border-r border-slate-800 bg-slate-950">
      <div className="border-b border-slate-800 px-5 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
            EP
          </div>
          <div>
            <p className="text-sm font-semibold text-white">Email Platform</p>
            <p className="text-xs text-slate-500">Admin Panel</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const Icon = iconMap[item.icon];
          return (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={onNavigate}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? "bg-indigo-600/15 text-indigo-300"
                    : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                }`
              }
            >
              <Icon className="h-5 w-5 shrink-0" />
              {item.label}
            </NavLink>
          );
        })}
      </nav>

      <div className="border-t border-slate-800 p-4">
        <div className="mb-3 truncate px-1">
          <p className="truncate text-sm font-medium text-slate-200">{displayName}</p>
          <p className="truncate text-xs text-slate-500">{user?.email}</p>
        </div>
        <button
          type="button"
          onClick={() => logout()}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-400 transition hover:bg-slate-900 hover:text-red-400"
        >
          <IconLogout className="h-5 w-5" />
          Logout
        </button>
      </div>
    </aside>
  );
}

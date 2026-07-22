import type { ComponentType } from "react";
import { NavLink } from "react-router-dom";

import {
  IconChart,
  IconDashboard,
  IconEye,
  IconFlame,
  IconGlobe,
  IconInbox,
  IconLogout,
  IconMail,
  IconMessages,
  IconSender,
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
  inbox: IconInbox,
  flame: IconFlame,
  eye: IconEye,
  server: IconServer,
  globe: IconGlobe,
  sender: IconSender,
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
    <aside className="flex h-full w-64 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <div className="border-b border-slate-200 px-5 py-5 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
            EP
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900 dark:text-white">Email Platform</p>
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
                    ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-600/15 dark:text-indigo-300"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200"
                }`
              }
            >
              <Icon className="h-5 w-5 shrink-0" />
              {item.label}
            </NavLink>
          );
        })}
      </nav>

      <div className="border-t border-slate-200 p-4 dark:border-slate-800">
        <div className="mb-3 truncate px-1">
          <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">
            {displayName}
          </p>
          <p className="truncate text-xs text-slate-500">{user?.email}</p>
        </div>
        <button
          type="button"
          onClick={() => logout()}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-red-600 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-red-400"
        >
          <IconLogout className="h-5 w-5" />
          Logout
        </button>
      </div>
    </aside>
  );
}

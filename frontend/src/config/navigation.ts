export const navItems = [
  { label: "Dashboard", path: "/dashboard", icon: "dashboard" as const },
  { label: "Lists", path: "/subscribers", icon: "users" as const },
  { label: "Messages", path: "/messages", icon: "messages" as const },
  { label: "Campaigns", path: "/campaigns", icon: "mail" as const },
  { label: "Inbox", path: "/unibox", icon: "inbox" as const },
  { label: "Warmup", path: "/warmup", icon: "flame" as const },
  { label: "Tracking", path: "/tracking", icon: "eye" as const },
  { label: "SMTP", path: "/smtp", icon: "server" as const },
  { label: "Domains", path: "/domains", icon: "globe" as const },
  { label: "Sender", path: "/sender", icon: "sender" as const },
  { label: "Reports", path: "/reports", icon: "chart" as const },
  { label: "Settings", path: "/settings", icon: "settings" as const },
] as const;

export type NavIcon = (typeof navItems)[number]["icon"];
